from datetime import datetime, timezone
from uuid import uuid4

from sqlmodel import Field, SQLModel


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class User(SQLModel, table=True):
    __tablename__ = "users"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str = Field(index=True, unique=True, max_length=256)
    password_hash: str = Field(max_length=128)
    first_name: str = Field(max_length=100)
    last_name: str = Field(max_length=100)
    role: str = Field(default="User", max_length=32)
    created_at_utc: datetime = Field(default_factory=utc_now)
    updated_at_utc: datetime | None = None
    is_deleted: bool = False


class RefreshToken(SQLModel, table=True):
    __tablename__ = "refresh_tokens"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    token: str = Field(index=True, unique=True, max_length=256)
    user_id: str = Field(index=True, foreign_key="users.id")
    expires_on_utc: datetime
    revoked_on_utc: datetime | None = None
    created_at_utc: datetime = Field(default_factory=utc_now)
    updated_at_utc: datetime | None = None
    is_deleted: bool = False

    @property
    def is_active(self) -> bool:
        now = utc_now()
        expires = self.expires_on_utc
        if expires.tzinfo is None:
            expires = expires.replace(tzinfo=timezone.utc)
        return self.revoked_on_utc is None and expires > now
