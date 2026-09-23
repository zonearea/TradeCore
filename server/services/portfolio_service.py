"""
Portföy servisi — BIST (TRY) ve ABD (USD) hisselerini native para biriminde tutar.

Mimari amaç:
- average_cost / current_price / K/Z → hissenin kendi para biriminde (hatasız %).
- Toplam Varlık kartı → her şeyi güncel USDTRY ile TRY'ye çevirip birleştirir.
- Kırılım: `₺ BIST: … | $ ABD: …` için ayrı toplamlar üretir.
"""

from __future__ import annotations

from sqlmodel import Session, select

from server.models.portfolio import Holding, MarketNews
from server.models.user import utc_now
from server.services.market_price_service import company_name, fetch_news, normalize_symbol
from server.services.market_service import (
    calculate_technical_indicators,
    detect_currency,
    get_native_quote,
    get_usdtry_rate,
    to_try_price,
)


class PortfolioError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def _round_money(value: float) -> float:
    return round(float(value), 2)


def add_or_merge_holding(
    session: Session,
    *,
    user_id: str,
    symbol: str,
    shares_count: int,
    average_cost: float,
    currency: str | None = None,
) -> Holding:
    """
    Hisse ekler veya mevcut satırla ağırlıklı ortalama maliyet birleştirir.

    @param average_cost: Kullanıcının girdiği maliyet — **native** (BIST→₺, ABD→$).
    @param currency: İstemci sekmesinden gelen ipucu ('TRY' | 'USD'); yoksa sembolden bulunur.
    """
    if shares_count <= 0:
        raise PortfolioError(400, "Shares count must be greater than zero.")
    if average_cost <= 0:
        raise PortfolioError(400, "Average cost must be greater than zero.")

    normalized = normalize_symbol(symbol)
    if not normalized or len(normalized) > 16:
        raise PortfolioError(400, "Symbol is invalid.")

    # Para birimi: sekme ipucu → sembol çözümlemesi
    cur = detect_currency(normalized, currency)
    quote = get_native_quote(normalized)
    # Kotasyon para birimi ile çelişirse kotasyona güven (piyasa gerçeği)
    if quote.get("currency") in {"USD", "TRY"} and quote["priceNative"] > 0:
        cur = str(quote["currency"]).upper()
        native_price = float(quote["priceNative"])
    else:
        native_price = _round_money(average_cost)

    existing = session.exec(
        select(Holding).where(
            Holding.user_id == user_id,
            Holding.symbol == normalized,
            Holding.is_deleted == False,  # noqa: E712
        )
    ).first()

    if existing is None:
        holding = Holding(
            user_id=user_id,
            symbol=normalized,
            shares_count=shares_count,
            average_cost=_round_money(average_cost),
            current_price=_round_money(native_price),
            currency=cur,
            created_at_utc=utc_now(),
        )
        holding.recalculate()
        session.add(holding)
        session.commit()
        session.refresh(holding)
        return holding

    # Birleştirme: aynı para biriminde ağırlıklı ortalama
    # Eski satır yanlışlıkla TRY iken USD'ye geçiyorsa maliyeti olduğu gibi bırakırız
    # (kullanıcı ABD sekmesinden yeniden girmeli).
    existing.currency = cur
    total_shares = existing.shares_count + shares_count
    weighted = (
        (existing.shares_count * existing.average_cost) + (shares_count * average_cost)
    ) / total_shares
    existing.shares_count = total_shares
    existing.average_cost = _round_money(weighted)
    existing.current_price = _round_money(native_price)
    existing.updated_at_utc = utc_now()
    existing.recalculate()
    session.add(existing)
    session.commit()
    session.refresh(existing)
    return existing


def remove_holding(session: Session, *, user_id: str, holding_id: str) -> None:
    holding = session.get(Holding, holding_id)
    if holding is None or holding.is_deleted or holding.user_id != user_id:
        raise PortfolioError(404, "The holding was not found.")
    session.delete(holding)
    session.commit()


def refresh_holding_prices(session: Session, holdings: list[Holding]) -> list[Holding]:
    """
    Her satırın current_price'ını **native** para biriminde günceller.

    Ayrıca currency alanını sembole göre düzeltir (eski TRY-yanlış NVDA satırları).
    """
    changed = False
    for holding in holdings:
        quote = get_native_quote(holding.symbol)
        native = float(quote.get("priceNative") or 0.0)
        cur = str(quote.get("currency") or detect_currency(holding.symbol)).upper()
        if cur not in {"USD", "TRY"}:
            cur = detect_currency(holding.symbol)

        # Para birimi düzeltmesi (migrasyon sonrası)
        if (holding.currency or "TRY").upper() != cur:
            holding.currency = cur
            changed = True

        if native <= 0:
            # Fiyat alınamadıysa en azından recalculate
            if holding.current_value == 0 and holding.shares_count > 0:
                holding.recalculate()
                session.add(holding)
                changed = True
            continue

        if abs(native - holding.current_price) > 0.0001:
            holding.current_price = _round_money(native)
            holding.updated_at_utc = utc_now()
            holding.recalculate()
            session.add(holding)
            changed = True
        elif holding.current_value == 0 and holding.shares_count > 0:
            holding.recalculate()
            session.add(holding)
            changed = True

    if changed:
        session.commit()
        for holding in holdings:
            session.refresh(holding)
    return holdings


def _holding_to_api_row(item: Holding, *, total_value_try: float, usd_try: float) -> dict:
    """
    Tek holding satırını UI sözleşmesine çevirir.

    Native alanlar: averageCost, currentPrice, profitLoss, …
    TRY karşılıkları: averageCostTry, currentPriceTry, … (ABD için gri alt satır)
    """
    cur = (item.currency or "TRY").upper()
    if cur not in {"USD", "TRY"}:
        cur = "TRY"

    avg = _round_money(item.average_cost)
    price = _round_money(item.current_price)
    total_cost = _round_money(item.total_cost)
    value = _round_money(item.current_value)
    pnl = _round_money(item.profit_loss)
    pnl_pct = _round_money(item.profit_loss_percentage)

    avg_try = to_try_price(avg, cur)
    price_try = to_try_price(price, cur)
    total_cost_try = to_try_price(total_cost, cur)
    value_try = to_try_price(value, cur)
    pnl_try = to_try_price(pnl, cur)

    market = "US" if cur == "USD" else "BIST"

    # Madde 3: pandas-ta RSI / SMA özeti — UI 'Teknik Durum' sütunu
    ta = calculate_technical_indicators(item.symbol)

    return {
        "id": item.id,
        "symbol": item.symbol,
        "companyName": company_name(item.symbol),
        "market": market,
        "currency": cur,
        "sharesCount": item.shares_count,
        # Native (orijinal para birimi)
        "averageCost": avg,
        "currentPrice": price,
        "totalCost": total_cost,
        "currentValue": value,
        "profitLoss": pnl,
        "profitLossPercentage": pnl_pct,
        # TRY karşılıkları (üst toplam / gri alt satır)
        "averageCostTry": avg_try,
        "currentPriceTry": price_try,
        "totalCostTry": total_cost_try,
        "currentValueTry": value_try,
        "profitLossTry": pnl_try,
        "usdTryRate": usd_try if cur == "USD" else None,
        "portfolioWeight": 0.0
        if total_value_try == 0
        else _round_money(value_try / total_value_try * 100),
        # Teknik analiz: signal = rsi_signal (frontend sözleşmesi)
        "technical": {
            "rsi": ta.get("rsi", 50.0),
            "signal": ta.get("rsi_signal", "Nötr"),
            "trend": ta.get("trend", "Yükseliş"),
        },
    }


def get_portfolio_summary(session: Session, user_id: str) -> dict:
    """
    Portföy özeti.

    - holdings[*]: native K/Z + TRY karşılıkları
    - totalValue / totalCost / profitLoss: **TRY** (üst kart)
    - breakdown: BIST ₺ ve ABD $ kırılımı
    """
    holdings = list(
        session.exec(
            select(Holding).where(Holding.user_id == user_id, Holding.is_deleted == False)  # noqa: E712
        ).all()
    )
    refresh_holding_prices(session, holdings)

    usd_try = get_usdtry_rate()

    bist_value_try = 0.0
    bist_cost_try = 0.0
    us_value_usd = 0.0
    us_cost_usd = 0.0

    for item in holdings:
        cur = (item.currency or "TRY").upper()
        if cur == "USD":
            us_value_usd += float(item.current_value)
            us_cost_usd += float(item.total_cost)
        else:
            bist_value_try += float(item.current_value)
            bist_cost_try += float(item.total_cost)

    us_value_try = _round_money(us_value_usd * usd_try)
    us_cost_try = _round_money(us_cost_usd * usd_try)
    bist_value_try = _round_money(bist_value_try)
    bist_cost_try = _round_money(bist_cost_try)

    total_value = _round_money(bist_value_try + us_value_try)
    total_cost = _round_money(bist_cost_try + us_cost_try)
    profit_loss = _round_money(total_value - total_cost)
    profit_loss_percentage = 0.0 if total_cost == 0 else _round_money(profit_loss / total_cost * 100)

    rows = [
        _holding_to_api_row(item, total_value_try=total_value, usd_try=usd_try)
        for item in holdings
    ]

    return {
        # Üst kartlar — her zaman TRY
        "totalCost": total_cost,
        "totalValue": total_value,
        "profitLoss": profit_loss,
        "profitLossPercentage": profit_loss_percentage,
        "usdTryRate": usd_try,
        # Kırılım: ₺ BIST | $ ABD
        "breakdown": {
            "bistValueTry": bist_value_try,
            "bistCostTry": bist_cost_try,
            "usValueUsd": _round_money(us_value_usd),
            "usCostUsd": _round_money(us_cost_usd),
            "usValueTry": us_value_try,
            "usCostTry": us_cost_try,
            "usdTryRate": usd_try,
        },
        "holdings": rows,
    }


def sync_news_for_symbols(session: Session, symbols: list[str]) -> list[MarketNews]:
    collected: list[MarketNews] = []
    for symbol in symbols:
        for item in fetch_news(symbol, limit=3):
            exists = session.exec(
                select(MarketNews).where(
                    MarketNews.symbol == item["symbol"],
                    MarketNews.title == item["title"],
                )
            ).first()
            if exists is not None:
                collected.append(exists)
                continue
            news = MarketNews(
                symbol=item["symbol"],
                title=item["title"],
                summary=item["summary"],
                source_url=item["source_url"],
                sentiment=item["sentiment"],
                published_at_utc=item["published_at_utc"],
                created_at_utc=utc_now(),
            )
            session.add(news)
            collected.append(news)
    session.commit()
    for news in collected:
        session.refresh(news)
    return collected


def list_market_news(session: Session, *, symbol: str | None = None, limit: int = 20) -> list[dict]:
    statement = select(MarketNews).where(MarketNews.is_deleted == False)  # noqa: E712
    if symbol:
        statement = statement.where(MarketNews.symbol == normalize_symbol(symbol))
    statement = statement.order_by(MarketNews.published_at_utc.desc()).limit(limit)
    rows = list(session.exec(statement).all())

    if not rows:
        seed_symbols = [normalize_symbol(symbol)] if symbol else ["THYAO", "ASELS", "GARAN", "EREGL", "SISE"]
        sync_news_for_symbols(session, seed_symbols)
        rows = list(session.exec(statement).all())

    return [
        {
            "id": row.id,
            "symbol": row.symbol,
            "title": row.title,
            "summary": row.summary,
            "sourceUrl": row.source_url,
            "sentiment": row.sentiment,
            "publishedAtUtc": row.published_at_utc.isoformat(),
        }
        for row in rows
    ]
