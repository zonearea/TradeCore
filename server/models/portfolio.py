"""
Portföy modelleri (SQLite / SQLModel).

Eğitici not:
- Holding tutarları artık hissenin *orijinal* para biriminde saklanır
  (BIST → TRY, ABD → USD). Böylece Kâr/Zarar %'si kur gürültüsünden etkilenmez.
- Üst toplamlar (Toplam Varlık) API katmanında güncel USDTRY ile TRY'ye çevrilir.
"""

from datetime import datetime
from uuid import uuid4

from sqlalchemy import UniqueConstraint
from sqlmodel import Field, SQLModel

from server.models.user import utc_now


class Holding(SQLModel, table=True):
    __tablename__ = "holdings"
    __table_args__ = (UniqueConstraint("user_id", "symbol", name="uq_holdings_user_symbol"),)

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(index=True, foreign_key="users.id")
    symbol: str = Field(index=True, max_length=16)
    shares_count: int
    # Ortalama maliyet — hissenin kendi para biriminde (TRY veya USD)
    average_cost: float
    # Canlı / son fiyat — yine native para biriminde
    current_price: float = 0.0
    # Para birimi: 'TRY' (BIST) veya 'USD' (ABD borsaları)
    currency: str = Field(default="TRY", max_length=8)
    total_cost: float = 0.0
    current_value: float = 0.0
    profit_loss: float = 0.0
    profit_loss_percentage: float = 0.0
    created_at_utc: datetime = Field(default_factory=utc_now)
    updated_at_utc: datetime | None = None
    is_deleted: bool = False

    def recalculate(self) -> None:
        """
        Kâr/zararı *native* para biriminde yeniden hesaplar.

        Örnek (NVDA / USD): maliyet $100, canlı $225 → K/Z +$125 (+%125).
        Kur çevirisi burada yapılmaz; özet API TRY karşılığını ayrıca üretir.
        """
        self.total_cost = round(self.shares_count * self.average_cost, 2)
        self.current_value = round(self.shares_count * self.current_price, 2)
        self.profit_loss = round(self.current_value - self.total_cost, 2)
        if self.total_cost == 0:
            self.profit_loss_percentage = 0.0
        else:
            self.profit_loss_percentage = round(self.profit_loss / self.total_cost * 100, 2)


class MarketNews(SQLModel, table=True):
    __tablename__ = "market_news"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    symbol: str = Field(index=True, max_length=16)
    title: str = Field(max_length=500)
    summary: str = Field(default="")
    source_url: str = Field(default="", max_length=1000)
    sentiment: str = Field(default="Neutral", max_length=16)
    published_at_utc: datetime = Field(default_factory=utc_now)
    created_at_utc: datetime = Field(default_factory=utc_now)
    updated_at_utc: datetime | None = None
    is_deleted: bool = False


class AiReport(SQLModel, table=True):
    __tablename__ = "ai_reports"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    user_id: str = Field(index=True, foreign_key="users.id")
    title: str = Field(max_length=250)
    executive_summary: str = Field(default="")
    full_report_markdown: str = Field(default="")
    risk_score: int = Field(default=5, ge=1, le=10)
    recommendations_json: str = Field(default="[]")
    created_at_utc: datetime = Field(default_factory=utc_now)
    updated_at_utc: datetime | None = None
    is_deleted: bool = False
