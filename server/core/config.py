from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

ROOT_DIR = Path(__file__).resolve().parents[2]
SERVER_DIR = Path(__file__).resolve().parents[1]


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(SERVER_DIR / ".env", ROOT_DIR / ".env"),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    jwt_secret: str = Field(
        default="TradeCore-Dev-Secret-Key-At-Least-32-Chars",
        alias="JWT_SECRET",
        min_length=32,
    )
    jwt_issuer: str = Field(default="CleanCore", alias="JWT_ISSUER")
    jwt_audience: str = Field(default="CleanCore", alias="JWT_AUDIENCE")
    jwt_expiration_minutes: int = Field(default=15, alias="JWT_EXPIRATION_MINUTES")
    database_url: str = Field(default="sqlite:///./tradecore.db", alias="DATABASE_URL")
    cors_origins: str = Field(
        default="http://localhost:3000,http://localhost:3010,http://127.0.0.1:3010",
        alias="CORS_ORIGINS",
    )
    gemini_api_key: str = Field(default="", alias="GEMINI_API_KEY")
    gemini_model: str = Field(default="gemini-2.5-flash", alias="GEMINI_MODEL")
    telegram_bot_token: str = Field(default="", alias="TELEGRAM_BOT_TOKEN")
    telegram_chat_id: str = Field(default="", alias="TELEGRAM_CHAT_ID")
    telegram_user_email: str = Field(default="", alias="TELEGRAM_USER_EMAIL")

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def sqlite_path(self) -> Path:
        if self.database_url.startswith("sqlite:///"):
            raw = self.database_url.removeprefix("sqlite:///")
            path = Path(raw)
            if not path.is_absolute():
                return (ROOT_DIR / path).resolve()
            return path
        return (ROOT_DIR / "tradecore.db").resolve()


@lru_cache
def get_settings() -> Settings:
    return Settings()
