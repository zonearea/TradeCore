from collections.abc import Generator
from pathlib import Path

from sqlalchemy import text
from sqlmodel import Session, SQLModel, create_engine

from server.core.config import get_settings

settings = get_settings()
sqlite_path = settings.sqlite_path
sqlite_path.parent.mkdir(parents=True, exist_ok=True)
database_url = f"sqlite:///{sqlite_path.as_posix()}"
engine = create_engine(database_url, connect_args={"check_same_thread": False})


def _migrate_holdings_currency() -> None:
    """
    Mevcut SQLite dosyasına `currency` kolonunu ekler (create_all kolon eklemez).

    Eğitici not: SQLModel create_all yalnızca yok tabloyu yaratır; ALTER gerekir.
    Varsayılan 'TRY' — eski BIST satırları bozulmaz; ABD hisseleri refresh'te düzeltilir.
    """
    with engine.begin() as conn:
        rows = conn.execute(text("PRAGMA table_info(holdings)")).fetchall()
        if not rows:
            return  # tablo henüz yok; create_all halledecek
        col_names = {row[1] for row in rows}
        if "currency" not in col_names:
            conn.execute(
                text("ALTER TABLE holdings ADD COLUMN currency VARCHAR(8) NOT NULL DEFAULT 'TRY'")
            )


def init_db() -> None:
    """Tabloları oluşturur ve hafif şema yamalarını uygular."""
    SQLModel.metadata.create_all(engine)
    _migrate_holdings_currency()


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
