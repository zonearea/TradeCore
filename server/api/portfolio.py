from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, Response, UploadFile, status
from pydantic import BaseModel, Field
from sqlmodel import Session

from server.core.database import get_session
from server.core.security import get_current_user
from server.models.user import User
from server.services.portfolio_service import (
    PortfolioError,
    add_or_merge_holding,
    get_portfolio_summary,
    remove_holding,
)
from server.services.statement_parser import StatementError, preview_statement

router = APIRouter(prefix="/api/portfolio", tags=["portfolio"])


class AddHoldingRequest(BaseModel):
    symbol: str = Field(min_length=1, max_length=16)
    sharesCount: int = Field(gt=0)
    # Maliyet: BIST sekmesinde ₺, ABD sekmesinde $ (native)
    averageCost: float = Field(gt=0)
    # İsteğe bağlı para birimi ipucu: 'TRY' | 'USD' (sekmeden gelir)
    currency: str | None = Field(default=None, max_length=8)


class ImportStatementRequest(BaseModel):
    holdings: list[AddHoldingRequest] = Field(min_length=1)


@router.get("")
def portfolio_summary(
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    return get_portfolio_summary(session, user.id)


@router.post("/holdings", status_code=status.HTTP_201_CREATED)
def create_holding(
    body: AddHoldingRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    try:
        holding = add_or_merge_holding(
            session,
            user_id=user.id,
            symbol=body.symbol,
            shares_count=body.sharesCount,
            average_cost=body.averageCost,
            currency=body.currency,
        )
    except PortfolioError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None

    return {
        "id": holding.id,
        "symbol": holding.symbol,
        "currency": holding.currency,
        "sharesCount": holding.shares_count,
        "averageCost": holding.average_cost,
        "currentPrice": holding.current_price,
        "totalCost": holding.total_cost,
        "currentValue": holding.current_value,
        "profitLoss": holding.profit_loss,
        "profitLossPercentage": holding.profit_loss_percentage,
    }


@router.post("/holdings/{holding_id}/remove", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_holding(
    holding_id: str,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> Response:
    try:
        remove_holding(session, user_id=user.id, holding_id=holding_id)
    except PortfolioError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/statements/preview")
async def statement_preview(
    user: Annotated[User, Depends(get_current_user)],
    file: UploadFile = File(...),
) -> dict:
    _ = user
    if not file.filename or not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are supported.")
    data = await file.read()
    if not data:
        raise HTTPException(status_code=400, detail="Empty file.")
    try:
        return preview_statement(data)
    except StatementError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None


@router.post("/statements/import")
def statement_import(
    body: ImportStatementRequest,
    user: Annotated[User, Depends(get_current_user)],
    session: Annotated[Session, Depends(get_session)],
) -> dict:
    imported = []
    try:
        for item in body.holdings:
            holding = add_or_merge_holding(
                session,
                user_id=user.id,
                symbol=item.symbol,
                shares_count=item.sharesCount,
                average_cost=item.averageCost,
            )
            imported.append({"id": holding.id, "symbol": holding.symbol, "sharesCount": holding.shares_count})
    except PortfolioError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return {"importedCount": len(imported), "holdings": imported}
