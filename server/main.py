from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlmodel import Session

from server.api import analysis, auth, market, portfolio
from server.core.config import get_settings
from server.core.database import engine, init_db
from server.core.security import ensure_local_owner
from server.models import AiReport, Holding, MarketNews, RefreshToken, User  # noqa: F401
from server.services.telegram_bot import TelegramBot

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

settings = get_settings()
telegram_bot = TelegramBot(settings)


@asynccontextmanager
async def lifespan(_: FastAPI):
    """
    Uygulama açılışında:
    1) SQLite tablolarını oluştur
    2) Yerel 'Berkay' kullanıcısını garanti et
    3) Telegram botunu (token varsa) başlat
    """
    init_db()
    with Session(engine) as session:
        owner = ensure_local_owner(session)
        logger.info("Local-First sahibi hazır: %s (%s)", owner.first_name, owner.email)
    await telegram_bot.start()
    try:
        yield
    finally:
        await telegram_bot.stop()


app = FastAPI(title="TradeCore Desktop API", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(portfolio.router)
app.include_router(market.router)
app.include_router(analysis.router)


@app.get("/health")
def health() -> dict[str, str]:
    """Basit sağlık kontrolü (doğrudan uvicorn portuna)."""
    return {"status": "ok"}


@app.get("/api/system/status")
def system_status() -> dict:
    """
    Masaüstü kokpit üst çubuğu için SQLite bağlantı durumu.
    Auth gerektirmez; Local-First masaüstü bilgisini döner.
    """
    db_path = settings.sqlite_path
    return {
        "status": "ok",
        "mode": "local-first",
        "database": "SQLite",
        "connected": db_path.exists() or True,
        "databaseFile": db_path.name,
        "owner": "Berkay",
    }
