from __future__ import annotations

import logging
from datetime import datetime, timezone

import yfinance as yf

from server.services.market_service import (
    COMPANY_NAMES as _MARKET_COMPANY_NAMES,
    get_price as resolve_price_try,
)

logger = logging.getLogger(__name__)

# Terminal tablosu ve ticker icin bilinen sirket / enstruman adlari.
COMPANY_NAMES: dict[str, str] = {
    **_MARKET_COMPANY_NAMES,
    "XU100": "BIST 100",
    "USDTRY": "Dolar / TL",
    "EURTRY": "Euro / TL",
    "GC": "Gram Altın",
}

# Ticker seridinde izlenecek enstrumanlar: (etiket, yfinance sembolu, yerel kod)
TICKER_SPECS: list[tuple[str, str, str]] = [
    ("BIST 100", "XU100.IS", "XU100"),
    ("USD/TRY", "USDTRY=X", "USDTRY"),
    ("EUR/TRY", "EURTRY=X", "EURTRY"),
    ("Gram Altin", "GC=F", "GC"),
    ("THYAO", "THYAO.IS", "THYAO"),
    ("ASELS", "ASELS.IS", "ASELS"),
    ("GARAN", "GARAN.IS", "GARAN"),
    ("EREGL", "EREGL.IS", "EREGL"),
    ("SISE", "SISE.IS", "SISE"),
]

TICKER_FALLBACKS: dict[str, tuple[float, float]] = {
    "XU100": (10250.0, 0.35),
    "USDTRY": (34.80, 0.12),
    "EURTRY": (37.90, -0.08),
    "GC": (2680.0, 0.22),
    "THYAO": (312.50, 0.40),
    "ASELS": (88.40, -0.55),
    "GARAN": (128.70, 0.18),
    "EREGL": (54.20, -0.30),
    "SISE": (47.85, 0.10),
}

POSITIVE_WORDS = ("yuksel", "artis", "rekor", "kazanc", "buyume", "pozitif", "surge", "gain", "rally", "up")
NEGATIVE_WORDS = ("dusus", "zarar", "gerile", "risk", "negatif", "fall", "drop", "loss", "down", "sell")


def to_yahoo_symbol(symbol: str) -> str:
    """
    Geriye dönük yardımcı: BIST varsayılanı `.IS`.

    Yeni kod yolları `market_service.resolve_market_symbol` kullanmalı;
    ticker şeridi gibi sabit Yahoo kodları bu fonksiyonu kullanmaz.
    """
    cleaned = symbol.strip().upper()
    if cleaned.endswith(".IS") or "=" in cleaned:
        return cleaned
    # Global bilinenler çıplak kalsın
    from server.services.market_service import GLOBAL_FALLBACK_USD

    if cleaned in GLOBAL_FALLBACK_USD:
        return cleaned
    return f"{cleaned}.IS"


def normalize_symbol(symbol: str) -> str:
    return symbol.strip().upper().removesuffix(".IS")


def company_name(symbol: str) -> str:
    """Sembol icin okunabilir sirket adi; bilinmiyorsa sembolun kendisi."""
    return COMPANY_NAMES.get(normalize_symbol(symbol), normalize_symbol(symbol))


def classify_sentiment(text: str) -> str:
    lowered = text.lower()
    if any(word in lowered for word in POSITIVE_WORDS):
        return "Positive"
    if any(word in lowered for word in NEGATIVE_WORDS):
        return "Negative"
    return "Neutral"


def get_price(symbol: str) -> float | None:
    """
    Portföy fiyatı (TRY).

    Global-öncelikli çözümleme `market_service` içindedir:
    önce NVDA gibi çıplak sembol, sonra SYMBOL.IS.
    """
    return resolve_price_try(symbol)

def get_quote(yahoo_symbol: str, local_code: str) -> dict:
    """
    Üst şerit kotasyonu — market_service ile aynı canlı fiyat önceliği.

    Eğitici not: Eskiden önce history Close okunuyordu; BIST'te bu çoğu zaman
    dünkü kapanıştı (ASELS 374.50). Artık last_price → regularMarketPrice → …
    zinciri kullanılır (ASELS canlı ~381.50).
    """
    from server.services.market_service import probe_yahoo_symbol

    price: float | None = None
    change_percent: float | None = None
    try:
        probed = probe_yahoo_symbol(yahoo_symbol)
        if probed is not None:
            price = float(probed["price"])
            change_percent = float(probed.get("changePercent") or 0.0)
    except Exception:  # noqa: BLE001
        logger.exception("yfinance quote failed for %s", yahoo_symbol)

    if price is None or float(price) <= 0:
        fb_price, fb_chg = TICKER_FALLBACKS.get(local_code, (0.0, 0.0))
        price = fb_price
        change_percent = fb_chg

    # Ons altını kabaca grama çevir (1 ons ~ 31.1035 g).
    display_price = float(price)
    if local_code == "GC" and display_price > 100:
        display_price = display_price / 31.1035

    return {
        "symbol": local_code,
        "label": COMPANY_NAMES.get(local_code, local_code),
        "price": round(display_price, 2),
        "changePercent": round(float(change_percent or 0.0), 2),
    }



def get_market_ticker() -> list[dict]:
    """Ust piyasa seridi icin tum TICKER_SPECS kotasyonlarini doner."""
    return [get_quote(yahoo, code) for _, yahoo, code in TICKER_SPECS]


def fetch_news(symbol: str, limit: int = 5) -> list[dict]:
    normalized = normalize_symbol(symbol)
    yahoo = to_yahoo_symbol(normalized)
    items: list[dict] = []
    try:
        ticker = yf.Ticker(yahoo)
        raw_news = getattr(ticker, "news", None) or []
        for entry in raw_news[:limit]:
            content = entry.get("content") if isinstance(entry.get("content"), dict) else entry
            title = content.get("title") or entry.get("title") or ""
            if not title:
                continue
            summary = content.get("summary") or content.get("description") or entry.get("summary") or title
            link = ""
            click = content.get("clickThroughUrl") if isinstance(content, dict) else None
            if isinstance(click, dict):
                link = click.get("url") or ""
            link = link or entry.get("link") or ""
            published = content.get("pubDate") or entry.get("providerPublishTime")
            items.append(
                {
                    "symbol": normalized,
                    "title": str(title)[:500],
                    "summary": str(summary)[:2000],
                    "source_url": str(link)[:1000],
                    "sentiment": classify_sentiment(f"{title} {summary}"),
                    "published_at_utc": utc_from_news(published),
                }
            )
    except Exception:  # noqa: BLE001
        logger.exception("yfinance news lookup failed for %s", yahoo)
    return items


def utc_from_news(value: object) -> datetime:
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(value, tz=timezone.utc)
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            pass
    return datetime.now(timezone.utc)
