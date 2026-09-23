"""
Piyasa API uçları: haber, tek sembol kotasyonu, ticker şeridi, AI haber açıklama.

Eğitici not:
- Router `main.py` içinde `app.include_router(market.router)` ile bağlanır.
- Prefix `/api/market` → uçlar `/api/market/quote`, `/api/market/news` …
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field

from server.core.config import get_settings
from server.core.security import get_current_user
from server.models.user import User
from server.services.gemini_analyst import explain_market_news
from server.services.market_price_service import get_market_ticker
from server.services.market_service import lookup_symbol_quote
from server.services.news_service import get_live_bist_news, parse_symbols_query

router = APIRouter(prefix="/api/market", tags=["market"])


class NewsExplainRequest(BaseModel):
    """POST /api/market/news/explain gövdesi."""

    title: str = Field(min_length=1, max_length=500)
    summary: str = Field(default="", max_length=4000)
    # İlgili hisse (NVDA / THYAO) veya BIST geneli için boş / "BIST"
    symbol: str | None = Field(default=None, max_length=16)


@router.get("/news")
def market_news(
    user: Annotated[User, Depends(get_current_user)],
    symbol: Annotated[str | None, Query()] = None,
    symbols: Annotated[str | None, Query()] = None,
    refresh: Annotated[bool, Query()] = False,
) -> list[dict]:
    """
    Canlı haber akışı.

    Parametreler:
    - `symbols=THYAO,NVDA,EREGL` → portföy hisselerine özel Google/Yahoo haberleri
      (Sadece Portföyüm). Sonuçlar listenin en başında.
    - `symbol=THYAO` → geriye dönük tek sembol (symbols yoksa kullanılır).
    - Parametre yok → genel BIST & KAP (Tüm Piyasa).
    - `refresh=true` → 5 dk önbelleği bypass eder.
    """
    _ = user

    # Öncelik: symbols (çoklu) → symbol (tekil, eski istemciler)
    parsed = parse_symbols_query(symbols)
    if not parsed and symbol:
        parsed = parse_symbols_query(symbol)

    return get_live_bist_news(
        limit=20 if parsed else 15,
        force_refresh=refresh,
        symbols=parsed or None,
    )


@router.post("/news/explain")
def market_news_explain(
    body: NewsExplainRequest,
    user: Annotated[User, Depends(get_current_user)],
) -> dict:
    """
    Gemini ile haber özeti + etki analizi.

    Çıktı: { summary, impact, verdict [, warning] }
    Anahtar yoksa veya hata olursa nazik uyarı alanlarıyla 200 döner (UI kırılmaz).
    """
    _ = user
    settings = get_settings()
    return explain_market_news(
        settings,
        title=body.title,
        summary=body.summary,
        symbol=body.symbol,
    )


@router.get("/quote")
def market_quote(
    user: Annotated[User, Depends(get_current_user)],
    symbol: Annotated[str, Query(min_length=1, max_length=16)],
) -> dict:
    """
    Tek sembol kotasyonu (Hızlı Hisse çipleri için).

    Davranış:
    - Global (NVDA, AAPL…) → çıplak Yahoo sembolü + USDTRY ile priceTry
    - BIST (THYAO, EREGL…) → SYMBOL.IS üzerinden TRY
    - Canlı yoksa → en son kapanış (fromClose=true); 404 dönülmez
    """
    _ = user
    # lookup_symbol_quote asla None dönmez; UI kırılmaz
    return lookup_symbol_quote(symbol)


@router.get("/ticker")
def market_ticker(user: Annotated[User, Depends(get_current_user)]) -> list[dict]:
    """
    Üst canlı piyasa şeridi (BIST 100, USD/TRY, EUR/TRY, altın, örnek hisseler).
    yfinance çağrıları services katmanındadır.
    """
    _ = user
    return get_market_ticker()


@router.get("/watchlist")
def watchlist(user: Annotated[User, Depends(get_current_user)]) -> list[dict]:
    _ = user
    return []
