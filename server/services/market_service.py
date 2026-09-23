"""
Piyasa hisse çözümleme servisi (BIST + Global / NASDAQ).

Mimari amaç:
- Eskiden her sembole körü körüne `.IS` ekleniyordu; NVDA yanlışlıkla BIST gibi
  okunuyor veya anlamsız fallback fiyata düşüyordu.
- Yeni sıra (akıllı):
  * Bilinen global (NVDA, AAPL…) → önce çıplak sembol; USD ise USDTRY × fiyat
  * Bilinen BIST (THYAO, EREGL…) → doğrudan `SYMBOL.IS`
  * Bilinmeyen → önce çıplak, sonra `.IS`
- Canlı fiyat yoksa hata fırlatmak yerine en son kapanış (history Close) kullanılır.
- Portföy tutarlılığı için `get_price` her zaman TRY cinsinden sayı döner.
"""

from __future__ import annotations

import logging
from typing import Any

import yfinance as yf

logger = logging.getLogger(__name__)

# Bilinen şirket adları (terminal tablosu / çip seçimi)
COMPANY_NAMES: dict[str, str] = {
    "THYAO": "Türk Hava Yolları",
    "ASELS": "Aselsan",
    "GARAN": "Garanti BBVA",
    "EREGL": "Ereğli Demir Çelik",
    "SISE": "Şişecam",
    "TUPRS": "Tüpraş",
    "BIMAS": "BİM",
    "NVDA": "NVIDIA",
    "AAPL": "Apple",
    "TSLA": "Tesla",
    "MSFT": "Microsoft",
}

# BIST bilinenleri — doğrudan .IS yoklanır (ABD çakışması riskini azaltır)
BIST_KNOWN: frozenset[str] = frozenset(
    {"THYAO", "ASELS", "GARAN", "EREGL", "SISE", "TUPRS", "BIMAS"}
)

# BIST fallback (ağ yoksa)
BIST_FALLBACK_TRY: dict[str, float] = {
    "THYAO": 312.50,
    "ASELS": 88.40,
    "GARAN": 128.70,
    "EREGL": 54.20,
    "SISE": 47.85,
    "TUPRS": 165.0,
    "BIMAS": 520.0,
}

# Global USD fallback (ağ yoksa; sonra kura çarpılır)
GLOBAL_FALLBACK_USD: dict[str, float] = {
    "NVDA": 120.0,
    "AAPL": 220.0,
    "TSLA": 250.0,
    "MSFT": 420.0,
}

_USDTRY_CACHE: dict[str, float] = {"rate": 0.0}


def normalize_symbol(symbol: str) -> str:
    """Kullanıcı girdisini büyük harfe çevirir; sondaki .IS varsa budar."""
    return symbol.strip().upper().removesuffix(".IS")


def company_name(symbol: str) -> str:
    """Sembol için okunabilir şirket adı."""
    return COMPANY_NAMES.get(normalize_symbol(symbol), normalize_symbol(symbol))


def get_usdtry_rate() -> float:
    """
    Güncel USD/TRY kurunu döner.

    Önce yfinance `USDTRY=X`, başarısızsa makul bir yedek kur.
    Kısa ömürlü bellek önbelleği ile ardışık NVDA/AAPL çağrılarını hızlandırır.
    """
    cached = float(_USDTRY_CACHE.get("rate") or 0.0)
    if cached > 0:
        return cached

    rate: float | None = None
    try:
        ticker = yf.Ticker("USDTRY=X")
        fast = getattr(ticker, "fast_info", None)
        if fast is not None:
            rate = getattr(fast, "last_price", None) or (
                fast.get("last_price") if hasattr(fast, "get") else None
            )
        if rate is None:
            history = ticker.history(period="5d")
            if history is not None and not history.empty:
                rate = float(history["Close"].iloc[-1])
    except Exception:  # noqa: BLE001
        logger.exception("USDTRY kuru alınamadı")

    if rate is None or float(rate) <= 0:
        rate = 42.0  # çevrimdışı yedek

    _USDTRY_CACHE["rate"] = float(rate)
    return float(rate)


def _read_fast(ticker: Any, key: str) -> Any:
    """fast_info hem nesne hem dict olabilir; güvenli okur (KeyError yutmaz)."""
    try:
        fast = getattr(ticker, "fast_info", None)
        if fast is None:
            return None
        if hasattr(fast, "get"):
            try:
                return fast.get(key)
            except Exception:  # noqa: BLE001
                # yfinance bazı anahtarlarda get içinde AttributeError/KeyError fırlatır
                return None
        return getattr(fast, key, None)
    except Exception:  # noqa: BLE001
        return None


def _read_fast_aliases(ticker: Any, *keys: str) -> Any:
    """
    fast_info üzerinde birden fazla anahtar dener (snake_case + camelCase).

    BIST'te yfinance sürümüne göre `last_price` veya `lastPrice` gelebilir;
    ikisini de denemek canlı fiyatı kaçırmamayı sağlar.
    """
    for key in keys:
        value = _read_fast(ticker, key)
        if value is not None:
            try:
                if float(value) > 0:
                    return float(value)
            except (TypeError, ValueError):
                continue
    return None


def _read_info_price(ticker: Any, *keys: str) -> float | None:
    """
    ticker.info sözlüğünden fiyat okur (yavaş olabilir; canlı yedek katmanı).

    info bazen ağ çağrısı tetikler; bu yüzden yalnızca fast_info boşsa çağrılmalı.
    """
    try:
        info = getattr(ticker, "info", None)
        if not isinstance(info, dict):
            return None
        for key in keys:
            raw = info.get(key)
            if raw is None:
                continue
            try:
                value = float(raw)
            except (TypeError, ValueError):
                continue
            if value > 0:
                return value
    except Exception:  # noqa: BLE001
        logger.debug("ticker.info okunamadı", exc_info=True)
    return None


def _as_positive_float(value: Any) -> float | None:
    """Pozitif sayıya çevir; aksi halde None."""
    if value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if number > 0 else None


def extract_live_price(ticker: Any) -> tuple[float | None, float | None, bool]:
    """
    Yfinance kotasyonundan en güncel işlem fiyatını çıkarır.

    Öncelik sırası:
      1) fast_info last_price / lastPrice  → anlık işlem
      2) ABD: postMarketPrice (seans sonrası) vs regularMarketPrice —
         hangisi daha taze ise o (NVDA after-hours için kritik)
      3) info.regularMarketPrice / currentPrice
      4) previousClose / history Close     → en son çare (dünkü kapanış)

    Dönüş: (fiyat, günlük_yüzde_değişim, from_close)
    from_close=True → canlı bulunamadı, kapanış kullanıldı.
    """
    # previousClose'u önce ucuz kaynaktan al; info'yu last_price denemeden tetikleme
    previous_close = _as_positive_float(
        _read_fast_aliases(ticker, "previous_close", "previousClose")
    )

    price: float | None = None
    from_close = False

    # --- 1) Canlı: fast_info last_price / lastPrice ---
    # BIST'te yfinance çoğu zaman yalnızca camelCase `lastPrice` doldurur;
    # yalnız `last_price` bakmak 374.50 (kapanış) tuzağına düşürürdü.
    price = _as_positive_float(
        _read_fast_aliases(ticker, "last_price", "lastPrice", "last")
    )

    # --- 2–3) info: regularMarket + (ABD) postMarket / preMarket ---
    # BIST'te fast_info yeterliyse info'yu tetikleme (ağ maliyeti).
    # USD / fiyat yoksa: regularMarketPrice ↔ postMarketPrice arasından en günceli seç.
    currency_hint = _read_fast(ticker, "currency")
    needs_session = price is None or (
        currency_hint is not None and str(currency_hint).upper() == "USD"
    )
    if needs_session:
        session_price = _pick_session_aware_price(ticker)
        if session_price is not None:
            if price is None or _is_us_extended_session(ticker):
                # Seans dışı ABD: post/pre; aksi halde regular (veya tek kaynak)
                price = session_price

    if price is None:
        price = _read_info_price(ticker, "regularMarketPrice")
    if price is None:
        price = _read_info_price(ticker, "currentPrice")

    # Yüzde hesabı için previousClose; hâlâ yoksa info'dan tamamla
    if previous_close is None:
        previous_close = _read_info_price(
            ticker, "previousClose", "regularMarketPreviousClose"
        )

    # --- 4) En son çare: previousClose (veya history Close) ---
    if price is None:
        if previous_close is not None:
            price = previous_close
            from_close = True
        else:
            hist_price, hist_change = _last_close_from_history(ticker)
            if hist_price is not None:
                price = hist_price
                from_close = True
                return price, hist_change, from_close

    if price is None:
        return None, None, False

    # Günlük %: canlı (veya kapanış) vs previousClose
    change_percent: float | None = None
    if previous_close is not None and previous_close > 0:
        change_percent = (price - previous_close) / previous_close * 100
    elif from_close:
        _, hist_change = _last_close_from_history(ticker)
        change_percent = hist_change

    return price, change_percent, from_close


def _is_us_extended_session(ticker: Any) -> bool:
    """
    ABD seans dışı mı? (PRE / POST / POSTPOST).

    marketState yoksa postMarketPrice doluysa yine seans dışı sayılır.
    """
    try:
        info = getattr(ticker, "info", None)
        if not isinstance(info, dict):
            return False
        state = str(info.get("marketState") or "").upper()
        if state in {"PRE", "PREPRE", "POST", "POSTPOST"}:
            return True
        # Durum belirsiz ama post fiyatı varsa after-hours kabul et
        if _as_positive_float(info.get("postMarketPrice")) is not None and state in {
            "",
            "CLOSED",
        }:
            return True
    except Exception:  # noqa: BLE001
        return False
    return False


def _pick_session_aware_price(ticker: Any) -> float | None:
    """
    regularMarketPrice ile postMarketPrice / preMarketPrice arasından
    en güncel işlem fiyatını seçer (NVDA after-hours hassasiyeti).

    Karar kuralı:
    - postMarketTime > regularMarketTime → postMarketPrice
    - preMarketTime daha yeni ve PRE → preMarketPrice
    - aksi halde regularMarketPrice
    """
    try:
        info = getattr(ticker, "info", None)
        if not isinstance(info, dict):
            return None

        regular = _as_positive_float(info.get("regularMarketPrice"))
        post = _as_positive_float(info.get("postMarketPrice"))
        pre = _as_positive_float(info.get("preMarketPrice"))

        regular_t = info.get("regularMarketTime")
        post_t = info.get("postMarketTime")
        pre_t = info.get("preMarketTime")
        state = str(info.get("marketState") or "").upper()

        # Zaman damgaları epoch saniye olabilir
        def _ts(value: Any) -> float:
            try:
                return float(value)
            except (TypeError, ValueError):
                return 0.0

        # Seans sonrası: post daha yeni veya marketState POST*
        if post is not None:
            if state in {"POST", "POSTPOST"} or (_ts(post_t) > _ts(regular_t) > 0):
                return post
            if regular is None:
                return post

        # Seans öncesi: pre
        if pre is not None and (state in {"PRE", "PREPRE"} or (_ts(pre_t) > _ts(regular_t) > 0 and regular is None)):
            return pre

        return regular
    except Exception:  # noqa: BLE001
        logger.debug("seans bilinçli fiyat seçilemedi", exc_info=True)
        return None


def _last_close_from_history(ticker: Any) -> tuple[float | None, float | None]:
    """
    En son kapanış fiyatını history'den alır (canlı yoksa yedek).

    Uyarı: BIST'te history['Close'].iloc[-1] çoğu zaman *dünkü* kapanıştır;
    canlı saatlerde asla birinci öncelik olmamalı — extract_live_price sırasına bak.
    """
    for period in ("5d", "1mo", "3mo"):
        try:
            history = ticker.history(period=period)
            if history is None or history.empty:
                continue
            closes = history["Close"].dropna()
            if len(closes) < 1:
                continue
            price = float(closes.iloc[-1])
            change: float | None = None
            if len(closes) >= 2 and float(closes.iloc[-2]) != 0:
                prev = float(closes.iloc[-2])
                change = (price - prev) / prev * 100
            return price, change
        except Exception:  # noqa: BLE001
            continue
    return None, None


def probe_yahoo_symbol(yahoo_symbol: str) -> dict | None:
    """
    Tek bir Yahoo sembolünü yoklar.

    Fiyat önceliği: last_price → regularMarketPrice → currentPrice → previousClose.
    Böylece ASELS gibi BIST hisselerinde dünkü 374.50 yerine canlı 381.50 gelir.
    @return Bulunursa {
        yahooSymbol, price, currency, changePercent, fromClose
      }; bulunamazsa None.
    """
    try:
        ticker = yf.Ticker(yahoo_symbol)
        price, change_percent, from_close = extract_live_price(ticker)

        if price is None or price <= 0:
            return None

        # Para birimi (yoksa varsayılan: .IS → TRY, diğer → USD)
        currency = "TRY" if yahoo_symbol.upper().endswith(".IS") else "USD"
        raw_cur = _read_fast(ticker, "currency")
        if raw_cur:
            currency = str(raw_cur).upper()
        else:
            try:
                info = getattr(ticker, "info", None)
                if isinstance(info, dict) and info.get("currency"):
                    currency = str(info["currency"]).upper()
            except Exception:  # noqa: BLE001
                pass

        return {
            "yahooSymbol": yahoo_symbol,
            "price": round(float(price), 4),
            "currency": currency,
            "changePercent": round(float(change_percent or 0.0), 2),
            "fromClose": from_close,
        }
    except Exception:  # noqa: BLE001
        # Beklenen 'sembol yok' durumları için exception log şişirmeyelim
        logger.debug("Yahoo yoklama sonucu yok/hata: %s", yahoo_symbol, exc_info=True)
        return None


def resolve_market_symbol(symbol: str) -> dict | None:
    """
    Akıllı sembol çözümlemesi.

    - Bilinen BIST → önce `SYMBOL.IS`
    - Bilinen global / diğer → önce çıplak, sonra `.IS`
    """
    code = normalize_symbol(symbol)
    if not code:
        return None

    # --- Bilinen BIST: doğrudan İstanbul ---
    if code in BIST_KNOWN or code in BIST_FALLBACK_TRY:
        bist = probe_yahoo_symbol(f"{code}.IS")
        if bist is not None:
            return {
                **bist,
                "symbol": code,
                "market": "BIST",
                "yahooSymbol": f"{code}.IS",
            }
        # BIST bulunamadıysa yine de global dene (nadir)
        direct = probe_yahoo_symbol(code)
        if direct is not None:
            return {
                **direct,
                "symbol": code,
                "market": "GLOBAL" if direct["currency"] != "TRY" else "BIST",
            }
        return None

    # --- Global / bilinmeyen: önce çıplak ---
    direct = probe_yahoo_symbol(code)
    if direct is not None:
        return {
            **direct,
            "symbol": code,
            "market": "GLOBAL" if direct["currency"] != "TRY" else "BIST",
        }

    # --- Adım 2: BIST yedek ---
    bist = probe_yahoo_symbol(f"{code}.IS")
    if bist is not None:
        return {
            **bist,
            "symbol": code,
            "market": "BIST",
            "yahooSymbol": f"{code}.IS",
        }

    return None


def to_try_price(native_price: float, currency: str) -> float:
    """Yerel para birimindeki fiyatı TRY'ye çevirir (USD → kur × fiyat)."""
    currency = (currency or "TRY").upper()
    if currency in {"TRY", "TL"}:
        return round(float(native_price), 2)
    if currency == "USD":
        return round(float(native_price) * get_usdtry_rate(), 2)
    # Diğer para birimleri için şimdilik olduğu gibi (nadir)
    return round(float(native_price), 2)


def get_price(symbol: str) -> float | None:
    """
    Portföy için güncel fiyat (her zaman TRY).

    NVDA gibi USD hisselerde kur çarpımı uygulanır; BIST hisselerinde
    doğrudan TL fiyat döner. Canlı yoksa son kapanış / statik yedek.
    """
    code = normalize_symbol(symbol)
    resolved = resolve_market_symbol(code)
    if resolved is not None:
        return to_try_price(resolved["price"], resolved["currency"])

    # Çevrimiçi bulunamadı → yedek tablolar
    if code in GLOBAL_FALLBACK_USD:
        return to_try_price(GLOBAL_FALLBACK_USD[code], "USD")
    if code in BIST_FALLBACK_TRY:
        return BIST_FALLBACK_TRY[code]
    return None


def _static_fallback_quote(code: str) -> dict | None:
    """Ağ tamamen suskunsa bilinen semboller için statik kotasyon üretir."""
    if code in GLOBAL_FALLBACK_USD:
        native = GLOBAL_FALLBACK_USD[code]
        rate = get_usdtry_rate()
        return {
            "symbol": code,
            "companyName": company_name(code),
            "market": "GLOBAL",
            "currency": "USD",
            "priceNative": native,
            "priceTry": round(native * rate, 2),
            "yahooSymbol": code,
            "changePercent": 0.0,
            "usdTryRate": rate,
            "fromClose": True,
            "stale": True,
        }
    if code in BIST_FALLBACK_TRY:
        return {
            "symbol": code,
            "companyName": company_name(code),
            "market": "BIST",
            "currency": "TRY",
            "priceNative": BIST_FALLBACK_TRY[code],
            "priceTry": BIST_FALLBACK_TRY[code],
            "yahooSymbol": f"{code}.IS",
            "changePercent": 0.0,
            "fromClose": True,
            "stale": True,
        }
    return None


def lookup_symbol_quote(symbol: str) -> dict:
    """
    UI çipleri / hızlı ekleme için zengin kotasyon.

    Önemli: Bulunamazsa 404 yerine son kapanış / statik yedek döner.
    En kötü ihtimalde priceTry=0 ile sembol bilgisi döner (UI kırılmasın).

    Dönüş örneği:
    {
      symbol, companyName, market, currency,
      priceNative, priceTry, yahooSymbol, changePercent, usdTryRate?,
      fromClose?, stale?
    }
    """
    code = normalize_symbol(symbol)
    if not code:
        return {
            "symbol": "",
            "companyName": "",
            "market": "UNKNOWN",
            "currency": "TRY",
            "priceNative": 0.0,
            "priceTry": 0.0,
            "yahooSymbol": "",
            "changePercent": 0.0,
            "fromClose": True,
            "stale": True,
        }

    resolved = resolve_market_symbol(code)

    if resolved is None:
        # Canlı / kapanış yok → bilinen statik; o da yoksa yumuşak boş kotasyon
        fallback = _static_fallback_quote(code)
        if fallback is not None:
            return fallback
        return {
            "symbol": code,
            "companyName": company_name(code),
            "market": "UNKNOWN",
            "currency": "TRY",
            "priceNative": 0.0,
            "priceTry": 0.0,
            "yahooSymbol": code,
            "changePercent": 0.0,
            "fromClose": True,
            "stale": True,
        }

    currency = resolved["currency"]
    native = float(resolved["price"])
    price_try = to_try_price(native, currency)
    payload: dict[str, Any] = {
        "symbol": code,
        "companyName": company_name(code),
        "market": resolved.get("market") or ("GLOBAL" if currency == "USD" else "BIST"),
        "currency": currency,
        "priceNative": round(native, 4),
        "priceTry": price_try,
        "yahooSymbol": resolved["yahooSymbol"],
        "changePercent": resolved.get("changePercent") or 0.0,
        "fromClose": bool(resolved.get("fromClose")),
        "stale": False,
    }
    if currency == "USD":
        payload["usdTryRate"] = get_usdtry_rate()
    return payload


def detect_currency(symbol: str, hint: str | None = None) -> str:
    """
    Sembolün saklanacağı para birimini belirler ('TRY' | 'USD').

    Öncelik:
    1) İstemciden gelen hint (BIST/ABD sekmesi)
    2) Bilinen global / BIST listeleri
    3) Yahoo çözümlemesi
    4) Varsayılan TRY
    """
    if hint:
        h = hint.strip().upper()
        if h in {"USD", "US", "USA", "NASDAQ", "NYSE", "GLOBAL", "ABD"}:
            return "USD"
        if h in {"TRY", "TL", "BIST", "TR"}:
            return "TRY"

    code = normalize_symbol(symbol)
    if not code:
        return "TRY"
    if code in GLOBAL_FALLBACK_USD:
        return "USD"
    if code in BIST_KNOWN or code in BIST_FALLBACK_TRY:
        return "TRY"

    resolved = resolve_market_symbol(code)
    if resolved is not None:
        cur = str(resolved.get("currency") or "").upper()
        if cur in {"USD", "TRY"}:
            return cur
        if resolved.get("market") == "GLOBAL":
            return "USD"
    return "TRY"


def get_native_quote(symbol: str) -> dict:
    """
    Portföy yenileme için kısayol: native fiyat + currency + TRY karşılığı.

    get_price (yalnızca TRY) yerine bunu kullan — USD hisselerde
    current_price'ı dolar olarak saklamak için şart.
    """
    return lookup_symbol_quote(symbol)


# ---------------------------------------------------------------------------
# Madde 3 — Teknik Analiz Motoru (pandas-ta)
# ---------------------------------------------------------------------------

# Kısa ömürlü bellek önbelleği: aynı portföy yenilemesinde her hisseyi 2 kez hesaplama
_TA_CACHE: dict[str, dict[str, Any]] = {}
_TA_CACHE_TTL_SECONDS = 60.0


def _rsi_signal_tr(rsi: float) -> str:
    """
    Klasik RSI eşikleri ile Türkçe sinyal üretir.

    - ≥ 70 → Aşırı Alım (overbought; düzeltme riski)
    - ≤ 30 → Aşırı Satım (oversold; tepki alımı ihtimali)
    - aksi → Nötr
    """
    if rsi >= 70:
        return "Aşırı Alım"
    if rsi <= 30:
        return "Aşırı Satım"
    return "Nötr"


def calculate_technical_indicators(symbol: str) -> dict:
    """
    pandas-ta ile RSI(14) ve SMA(20) tabanlı teknik özet üretir.

    Adımlar:
    1) Sembolü Yahoo koduna çöz (NVDA / THYAO.IS)
    2) Son ~1 aylık günlük kapanışları çek (history period='1mo')
    3) RSI(14) → momentum; SMA(20) → trend (fiyat ≥ SMA → Yükseliş)

    Dönüş:
    {
      "rsi": 42.5,              # son RSI değeri
      "rsi_signal": "Nötr",     # Aşırı Alım | Aşırı Satım | Nötr
      "trend": "Yükseliş",      # Yükseliş | Düşüş
    }
    Veri yoksa güvenli varsayılanlar (rsi=50, Nötr, Yükseliş) döner — UI kırılmaz.
    """
    import time

    import pandas_ta as ta  # noqa: PLC0415 — ağır import; fonksiyon çağrısında yükle

    code = normalize_symbol(symbol)
    now = time.time()
    cached = _TA_CACHE.get(code)
    if cached and (now - float(cached.get("fetched_at") or 0)) < _TA_CACHE_TTL_SECONDS:
        return {
            "rsi": cached["rsi"],
            "rsi_signal": cached["rsi_signal"],
            "trend": cached["trend"],
        }

    # Güvenli varsayılan (ağ / veri hatasında UI boş kalmasın)
    result = {"rsi": 50.0, "rsi_signal": "Nötr", "trend": "Yükseliş"}

    try:
        resolved = resolve_market_symbol(code)
        yahoo = (resolved or {}).get("yahooSymbol") or (
            f"{code}.IS" if code in BIST_KNOWN or code in BIST_FALLBACK_TRY else code
        )

        ticker = yf.Ticker(str(yahoo))
        # 1 aylık günlük mumlar — RSI(14) ve SMA(20) için yeterli bar sayısı
        history = ticker.history(period="1mo", interval="1d")
        if history is None or history.empty or "Close" not in history.columns:
            _TA_CACHE[code] = {**result, "fetched_at": now}
            return result

        closes = history["Close"].dropna()
        if len(closes) < 15:
            # RSI(14) için en az ~15 kapanış gerekir
            _TA_CACHE[code] = {**result, "fetched_at": now}
            return result

        # pandas-ta: Series döner; son geçerli hücreyi al
        rsi_series = ta.rsi(closes, length=14)
        sma_series = ta.sma(closes, length=20)

        rsi_val: float | None = None
        if rsi_series is not None and not rsi_series.dropna().empty:
            rsi_val = float(rsi_series.dropna().iloc[-1])

        last_close = float(closes.iloc[-1])
        sma_val: float | None = None
        if sma_series is not None and not sma_series.dropna().empty:
            sma_val = float(sma_series.dropna().iloc[-1])
        elif len(closes) >= 20:
            # SMA serisi boşsa elle 20 günlük ortalama (yedek)
            sma_val = float(closes.iloc[-20:].mean())

        if rsi_val is not None and rsi_val == rsi_val:  # NaN değil
            result["rsi"] = round(rsi_val, 1)
            result["rsi_signal"] = _rsi_signal_tr(rsi_val)

        if sma_val is not None and sma_val > 0:
            # Fiyat SMA20'nin üstündeyse yükseliş trendi kabul edilir
            result["trend"] = "Yükseliş" if last_close >= sma_val else "Düşüş"

    except Exception:  # noqa: BLE001
        logger.debug("Teknik analiz hesaplanamadı: %s", code, exc_info=True)

    _TA_CACHE[code] = {**result, "fetched_at": now}
    return result
