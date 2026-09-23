"""
Canlı piyasa haber servisi (RSS + Yahoo Finance).

Mimari amaç:
- Genel akış: Bloomberg HT + Google News BIST (Tüm Piyasa).
- Portföy akışı: `symbols=THYAO,NVDA` ile her hisse için Google News + Yahoo
  Finance başlıklarını çeker ve listenin en başına koyar.
- 5 dakikalık bellek içi önbellek (genel + sembol anahtarlı) ağı yormaz.
"""

from __future__ import annotations

import hashlib
import logging
import time
from datetime import datetime, timezone
from email.utils import parsedate_to_datetime
from typing import Any
from urllib.parse import quote_plus

import feedparser
import yfinance as yf
from bs4 import BeautifulSoup

from server.services.market_service import (
    COMPANY_NAMES,
    GLOBAL_FALLBACK_USD,
    normalize_symbol,
)

logger = logging.getLogger(__name__)

# Genel piyasa RSS kaynakları (Tüm Piyasa sekmesi).
RSS_FEEDS: list[tuple[str, str]] = [
    ("Bloomberg HT", "https://www.bloomberght.com/rss"),
    (
        "Google News BIST",
        "https://news.google.com/rss/search?q=Borsa+Istanbul+BIST&hl=tr&gl=TR&ceid=TR:tr",
    ),
]

# Duygu analizi için basit Türkçe / İngilizce anahtar kelimeler.
POSITIVE_KEYWORDS = (
    "yüksel",
    "artis",
    "artış",
    "rekor",
    "kazanç",
    "kazanc",
    "büyüme",
    "buyume",
    "pozitif",
    "rally",
    "surge",
    "gain",
    "güçlü",
    "guclu",
    "alış",
    "alis",
)
NEGATIVE_KEYWORDS = (
    "düşüş",
    "dusus",
    "düştü",
    "dustu",
    "zarar",
    "gerile",
    "risk",
    "negatif",
    "satış",
    "satis",
    "çöküş",
    "cokus",
    "kriz",
    "fall",
    "drop",
    "loss",
    "selloff",
)

# Bellek içi önbellek: anahtar → {fetched_at, items}
# "market" = genel BIST; "SYM:NVDA,THYAO" = portföy filtresi
_CACHE: dict[str, dict[str, Any]] = {}
_CACHE_TTL_SECONDS = 5 * 60


def _strip_html(raw: str) -> str:
    """RSS açıklamalarındaki HTML etiketlerini temizleyip düz metin üretir."""
    if not raw:
        return ""
    soup = BeautifulSoup(raw, "html.parser")
    text = soup.get_text(" ", strip=True)
    return " ".join(text.split())


def classify_sentiment_tr(text: str) -> str:
    """
    Başlık + özetten kaba duygu etiketi üretir.

    Dönüş değerleri UI rozetleri için Türkçe tutulur:
    'Pozitif' | 'Nötr' | 'Negatif'
    """
    lowered = text.casefold()
    if any(word in lowered for word in POSITIVE_KEYWORDS):
        return "Pozitif"
    if any(word in lowered for word in NEGATIVE_KEYWORDS):
        return "Negatif"
    return "Nötr"


def _parse_published(entry: dict) -> datetime:
    """
    feedparser tarih alanını UTC datetime'a çevirir.

    Önce yapılandırılmış published_parsed / updated_parsed bakılır;
    yoksa RFC 2822 metin tarihi denenir; hiçbiri yoksa şimdiki UTC.
    """
    for key in ("published_parsed", "updated_parsed"):
        parsed = entry.get(key)
        if parsed:
            try:
                return datetime(*parsed[:6], tzinfo=timezone.utc)
            except (TypeError, ValueError):
                pass

    for key in ("published", "updated"):
        raw = entry.get(key)
        if not raw:
            continue
        try:
            dt = parsedate_to_datetime(raw)
            if dt.tzinfo is None:
                return dt.replace(tzinfo=timezone.utc)
            return dt.astimezone(timezone.utc)
        except (TypeError, ValueError, IndexError):
            continue

    return datetime.now(timezone.utc)


def _make_item(
    *,
    title: str,
    summary: str,
    link: str,
    source_name: str,
    symbol: str,
    published: datetime | None = None,
) -> dict | None:
    """API sözleşmesine uygun tek haber kartı üretir."""
    title = _strip_html(title).strip()
    if not title:
        return None
    summary = _strip_html(summary) or title
    published = published or datetime.now(timezone.utc)
    sentiment = classify_sentiment_tr(f"{title} {summary}")
    digest = hashlib.sha1(f"{title}|{link}|{symbol}".encode("utf-8")).hexdigest()[:16]

    return {
        "id": digest,
        "title": title[:500],
        "summary": summary[:2000],
        "source": source_name,
        "url": (link or "")[:1000],
        "sourceUrl": (link or "")[:1000],
        "publishedAt": published.isoformat(),
        "publishedAtUtc": published.isoformat(),
        "sentiment": sentiment,
        # Portföy filtresinde UI rozeti için gerçek sembol; genel akışta "BIST"
        "symbol": symbol or "BIST",
    }


def _entry_to_item(entry: dict, source_name: str, symbol: str = "BIST") -> dict | None:
    """Tek bir RSS kaydını API'nin beklediği sözlüğe dönüştürür."""
    title = entry.get("title") or ""
    summary = entry.get("summary") or entry.get("description") or ""
    link = (entry.get("link") or "").strip()
    published = _parse_published(entry)
    return _make_item(
        title=title,
        summary=summary,
        link=link,
        source_name=source_name,
        symbol=symbol,
        published=published,
    )


def _fetch_feed(source_name: str, url: str, symbol: str = "BIST") -> list[dict]:
    """Tek bir RSS adresini okuyup haber listesi döner; hata olursa boş liste."""
    items: list[dict] = []
    try:
        parsed = feedparser.parse(
            url,
            request_headers={
                "User-Agent": "TradeCoreTerminal/1.0 (+local-first; RSS reader)",
                "Accept": "application/rss+xml, application/xml, text/xml, */*",
            },
        )
        for entry in parsed.entries:
            item = _entry_to_item(entry, source_name, symbol=symbol)
            if item is not None:
                items.append(item)
    except Exception:  # noqa: BLE001
        logger.exception("RSS okunamadi: %s (%s)", source_name, url)
    return items


def _yahoo_ticker_for_news(code: str) -> str:
    """Haber çekimi için Yahoo sembolü: global çıplak, BIST → .IS."""
    code = normalize_symbol(code)
    if code in GLOBAL_FALLBACK_USD:
        return code
    # Bilinen ABD tickers kısa yolu
    if code in {"NVDA", "AAPL", "TSLA", "MSFT", "GOOGL", "AMZN", "META"}:
        return code
    # BIST varsayılanı
    return f"{code}.IS"


def _google_news_query(code: str) -> str:
    """
    Google News arama ifadesi.

    Şirket adı varsa OR ile ekler: NVDA OR NVIDIA — daha zengin sonuç.
    """
    code = normalize_symbol(code)
    name = COMPANY_NAMES.get(code)
    if name:
        return f"{code} OR \"{name}\" hisse OR stock"
    return f"{code} hisse OR stock"


def _fetch_symbol_google_news(code: str, per_symbol: int = 5) -> list[dict]:
    """Google News RSS ile tek hisseye özel son haberler."""
    code = normalize_symbol(code)
    query = _google_news_query(code)
    # Türkçe sonuçlar için TR; global hisselerde de TR arayüzü yeterli
    url = (
        "https://news.google.com/rss/search?"
        f"q={quote_plus(query)}&hl=tr&gl=TR&ceid=TR:tr"
    )
    return _fetch_feed(f"Google News · {code}", url, symbol=code)[:per_symbol]


def _fetch_symbol_yahoo_rss(code: str, per_symbol: int = 5) -> list[dict]:
    """Yahoo Finance headline RSS — doğrudan ticker başlıkları."""
    code = normalize_symbol(code)
    yahoo = _yahoo_ticker_for_news(code)
    # Yahoo RSS: s=NVDA veya s=THYAO.IS
    url = f"https://finance.yahoo.com/rss/headline?s={quote_plus(yahoo)}"
    return _fetch_feed(f"Yahoo Finance · {code}", url, symbol=code)[:per_symbol]


def _fetch_symbol_yahoo_api(code: str, per_symbol: int = 4) -> list[dict]:
    """
    yfinance `Ticker.news` API yedeği.

    RSS boş dönerse (engelleme / boş feed) bu yol devreye girer.
    """
    code = normalize_symbol(code)
    yahoo = _yahoo_ticker_for_news(code)
    items: list[dict] = []
    try:
        raw_news = getattr(yf.Ticker(yahoo), "news", None) or []
        for row in raw_news[:per_symbol]:
            # yfinance bazen iç içe content yapısı döndürür
            content = row.get("content") if isinstance(row.get("content"), dict) else {}
            title = row.get("title") or content.get("title") or ""
            summary = (
                row.get("summary")
                or content.get("summary")
                or content.get("description")
                or title
            )
            link = (
                row.get("link")
                or (content.get("clickThroughUrl") or {}).get("url")
                or (content.get("canonicalUrl") or {}).get("url")
                or ""
            )
            publisher = (
                row.get("publisher")
                or (content.get("provider") or {}).get("displayName")
                or "Yahoo Finance"
            )
            # Epoch saniye veya ISO
            published: datetime | None = None
            ts = row.get("providerPublishTime") or content.get("pubDate")
            if isinstance(ts, (int, float)):
                published = datetime.fromtimestamp(float(ts), tz=timezone.utc)
            elif isinstance(ts, str):
                try:
                    published = parsedate_to_datetime(ts)
                    if published.tzinfo is None:
                        published = published.replace(tzinfo=timezone.utc)
                except (TypeError, ValueError, IndexError):
                    published = None

            item = _make_item(
                title=str(title),
                summary=str(summary),
                link=str(link),
                source_name=f"{publisher} · {code}",
                symbol=code,
                published=published,
            )
            if item is not None:
                items.append(item)
    except Exception:  # noqa: BLE001
        logger.debug("Yahoo news API okunamadi: %s", yahoo, exc_info=True)
    return items


def fetch_news_for_symbols(symbols: list[str], *, per_symbol: int = 5) -> list[dict]:
    """
    Portföy hisselerine özel haberleri çeker (Google News + Yahoo).

    Aynı başlık birden fazla kaynaktan gelirse ilk görülen tutulur.
    Sonuçlar tarihe göre yeniden eskiye sıralanır.
    """
    combined: list[dict] = []
    seen: set[str] = set()

    for raw in symbols:
        code = normalize_symbol(raw)
        if not code:
            continue
        # Sıra: Google (taze) → Yahoo RSS → Yahoo API yedek
        buckets = (
            _fetch_symbol_google_news(code, per_symbol=per_symbol),
            _fetch_symbol_yahoo_rss(code, per_symbol=per_symbol),
            _fetch_symbol_yahoo_api(code, per_symbol=per_symbol),
        )
        for bucket in buckets:
            for item in bucket:
                key = item["title"].casefold()
                if key in seen:
                    continue
                seen.add(key)
                combined.append(item)

    combined.sort(key=lambda row: row.get("publishedAtUtc") or "", reverse=True)
    return combined


def _fetch_all_market_feeds(limit: int = 15) -> list[dict]:
    """
    Genel BIST/KAP kaynaklarını birleştirir, tarihe göre sıralar.
    """
    combined: list[dict] = []
    seen_titles: set[str] = set()

    for source_name, url in RSS_FEEDS:
        for item in _fetch_feed(source_name, url, symbol="BIST"):
            key = item["title"].casefold()
            if key in seen_titles:
                continue
            seen_titles.add(key)
            combined.append(item)

    combined.sort(key=lambda row: row.get("publishedAtUtc") or "", reverse=True)
    return combined[:limit]


def _cache_get(key: str, limit: int) -> list[dict] | None:
    """TTL dolmamış önbelleği döner; yoksa None."""
    entry = _CACHE.get(key)
    if not entry:
        return None
    age = time.time() - float(entry.get("fetched_at") or 0.0)
    items = list(entry.get("items") or [])
    if items and age < _CACHE_TTL_SECONDS:
        return items[:limit]
    return None


def _cache_set(key: str, items: list[dict]) -> None:
    """Önbelleği günceller."""
    _CACHE[key] = {"fetched_at": time.time(), "items": items}


def get_live_bist_news(
    limit: int = 15,
    *,
    force_refresh: bool = False,
    symbols: list[str] | None = None,
) -> list[dict]:
    """
    Canlı haber listesi.

    @param limit: Maksimum haber sayısı
    @param force_refresh: True ise 5 dk önbelleği aşar
    @param symbols: Verilirse yalnızca bu hisselere özel haberler
                    (Sadece Portföyüm). Boş/None ise genel BIST piyasa akışı.
    """
    # Sembolleri normalize + benzersiz tut
    cleaned: list[str] = []
    seen_sym: set[str] = set()
    for raw in symbols or []:
        code = normalize_symbol(raw)
        if code and code not in seen_sym:
            seen_sym.add(code)
            cleaned.append(code)

    if cleaned:
        cache_key = "SYM:" + ",".join(cleaned)
        if not force_refresh:
            hit = _cache_get(cache_key, limit)
            if hit is not None:
                return hit

        # Portföy haberleri en başa; gerekirse genel piyasa ile doldur
        portfolio_news = fetch_news_for_symbols(cleaned, per_symbol=5)
        if len(portfolio_news) < limit:
            # Genel akıştan doldur ama portföy başlıklarını tekrarlama
            market = _fetch_all_market_feeds(limit=limit)
            seen = {n["title"].casefold() for n in portfolio_news}
            for item in market:
                if item["title"].casefold() in seen:
                    continue
                portfolio_news.append(item)
                if len(portfolio_news) >= limit:
                    break

        fresh = portfolio_news[:limit]
        if not fresh:
            # Ağ çöktüyse eski önbellek
            old = _CACHE.get(cache_key, {}).get("items") or []
            if old:
                return list(old)[:limit]
        else:
            _cache_set(cache_key, fresh)
        return fresh[:limit]

    # --- Tüm Piyasa ---
    cache_key = "market"
    if not force_refresh:
        hit = _cache_get(cache_key, limit)
        if hit is not None:
            return hit

    fresh = _fetch_all_market_feeds(limit=limit)
    if not fresh:
        old = _CACHE.get(cache_key, {}).get("items") or []
        if old:
            logger.warning("RSS bos dondu; onceki onbellek kullaniliyor.")
            return list(old)[:limit]

    _cache_set(cache_key, fresh)
    return fresh[:limit]


def parse_symbols_query(raw: str | None) -> list[str]:
    """
    `symbols=THYAO,NVDA,EREGL` sorgu dizisini listeye çevirir.

    Virgül veya boşluk ayırıcı kabul eder.
    """
    if not raw:
        return []
    parts: list[str] = []
    for chunk in raw.replace(";", ",").split(","):
        for piece in chunk.split():
            code = normalize_symbol(piece)
            if code:
                parts.append(code)
    # Sıra korunarak benzersiz
    out: list[str] = []
    seen: set[str] = set()
    for code in parts:
        if code not in seen:
            seen.add(code)
            out.append(code)
    return out
