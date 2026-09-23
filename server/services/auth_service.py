from sqlmodel import Session, select

from server.core.config import Settings
from server.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    verify_password,
)
from server.models.user import User, utc_now


class AuthError(Exception):
    def __init__(self, status_code: int, detail: str) -> None:
        self.status_code = status_code
        self.detail = detail
        super().__init__(detail)


def register_user(
    session: Session,
    *,
    email: str,
    password: str,
    first_name: str,
    last_name: str,
) -> str:
    normalized = email.strip().lower()
    existing = session.exec(select(User).where(User.email == normalized)).first()
    if existing is not None:
        raise AuthError(409, "This email address is already in use.")

    user = User(
        email=normalized,
        password_hash=hash_password(password),
        first_name=first_name.strip(),
        last_name=last_name.strip(),
        role="User",
        created_at_utc=utc_now(),
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user.id


def login_user(session: Session, settings: Settings, *, email: str, password: str) -> tuple[str, str]:
    normalized = email.strip().lower()
    user = session.exec(
        select(User).where(User.email == normalized, User.is_deleted == False)  # noqa: E712
    ).first()

    if user is None or not verify_password(password, user.password_hash):
        raise AuthError(401, "The provided credentials are invalid.")

    access_token = create_access_token(user, settings)
    refresh = create_refresh_token(user.id)
    session.add(refresh)
    session.commit()
    return access_token, refresh.token


def refresh_session(session: Session, settings: Settings, refresh_token: str) -> tuple[str, str]:
    from server.models.user import RefreshToken

    stored = session.exec(
        select(RefreshToken).where(RefreshToken.token == refresh_token, RefreshToken.is_deleted == False)  # noqa: E712
    ).first()

    if stored is None or not stored.is_active:
        raise AuthError(401, "The refresh token is invalid or expired.")

    user = session.get(User, stored.user_id)
    if user is None or user.is_deleted:
        raise AuthError(401, "The refresh token is invalid or expired.")

    stored.revoked_on_utc = utc_now()
    access_token = create_access_token(user, settings)
    new_refresh = create_refresh_token(user.id)
    session.add(new_refresh)
    session.add(stored)
    session.commit()
    return access_token, new_refresh.token
