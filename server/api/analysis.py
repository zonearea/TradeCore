from __future__ import annotations

import json
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status
from sqlmodel import Session, select

from server.core.config import Settings, get_settings
from server.core.database import get_session
from server.core.security import get_current_user
from server.models.portfolio import AiReport, Holding, MarketNews
from server.models.user import User
from server.services.gemini_analyst import AnalysisError, generate_portfolio_analysis
from server.services.portfolio_service import refresh_holding_prices, sync_news_for_symbols

router = APIRouter(prefix="/api/analysis", tags=["analysis"])


def _serialize_report(report: AiReport) -> dict:
    try:
        recommendations = json.loads(report.recommendations_json or "[]")
    except json.JSONDecodeError:
        recommendations = []
    return {
        "id": report.id,
        "title": report.title,
        "executiveSummary": report.executive_summary,
        "fullReportMarkdown": report.full_report_markdown,
        "riskScore": report.risk_score,
        "recommendations": recommendations,
        "createdAtUtc": report.created_at_utc.isoformat(),
    }


@router.post("/generate", status_code=status.HTTP_201_CREATED)
def generate_report(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> dict:
    holdings = list(
        session.exec(
            select(Holding).where(Holding.user_id == user.id, Holding.is_deleted == False)  # noqa: E712
        ).all()
    )
    if not holdings:
        raise HTTPException(status_code=400, detail="Portfolio is empty. Add holdings before generating a report.")

    refresh_holding_prices(session, holdings)
    symbols = [item.symbol for item in holdings]
    sync_news_for_symbols(session, symbols)
    news = list(
        session.exec(
            select(MarketNews)
            .where(MarketNews.symbol.in_(symbols), MarketNews.is_deleted == False)  # noqa: E712
            .order_by(MarketNews.published_at_utc.desc())
            .limit(20)
        ).all()
    )

    try:
        report = generate_portfolio_analysis(settings, user_id=user.id, holdings=holdings, news=news)
    except AnalysisError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None

    session.add(report)
    session.commit()
    session.refresh(report)
    return _serialize_report(report)


@router.get("/reports")
def list_reports(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> list[dict]:
    reports = session.exec(
        select(AiReport)
        .where(AiReport.user_id == user.id, AiReport.is_deleted == False)  # noqa: E712
        .order_by(AiReport.created_at_utc.desc())
    ).all()
    return [_serialize_report(report) for report in reports]
