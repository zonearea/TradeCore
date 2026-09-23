"""
Kimlik doğrulama ve yerel (Local-First) kullanıcı çözümleme.

Mimari amaç:
- Çok kullanıcılı web sitesinde JWT zorunluydu.
- Kişisel masaüstü kokpitte token yoksa varsayılan 'Berkay' kullanıcısı kullanılır.
- Auth uçları (login/register) hâlâ çalışır; portföy/analiz/ekstre giriş olmadan açılır.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import Cookie, Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from passlib.context import CryptContext
from sqlmodel import Session, select

from server.core.config import Settings, get_settings
from server.core.database import get_session
from server.models.user import RefreshToken, User, utc_now

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
bearer_scheme = HTTPBearer(auto_error=False)

ACCESS_COOKIE = "accessToken"
REFRESH_COOKIE = "refreshToken"

# Yerel masaüstü sahibi — token yokken tüm kişisel veriler bu kullanıcıya yazılır.
LOCAL_OWNER_EMAIL = "berkay@localhost"
LOCAL_OWNER_FIRST_NAME = "Berkay"
LOCAL_OWNER_LAST_NAME = "TradeCore"


def hash_password(password: str) -> str:
    """Düz metin parolayı BCrypt ile hash'ler (kayıt / yerel kullanıcı oluşturma)."""
    return pwd_context.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Parola doğrulaması; bozuk hash'te False döner, exception fırlatmaz."""
    if not password or not password_hash:
        return False
    try:
        return pwd_context.verify(password, password_hash)
    except ValueError:
        return False


def create_access_token(user: User, settings: Settings) -> str:
    """Kısa ömürlü JWT access token üretir (Next.js çerez sözleşmesiyle uyumlu claim'ler)."""
    now = utc_now()
    payload = {
        "sub": user.id,
        "email": user.email,
        "given_name": user.first_name,
        "family_name": user.last_name,
        "role": user.role,
        "jti": secrets.token_urlsafe(16),
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": int(now.timestamp()),
        "nbf": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=settings.jwt_expiration_minutes)).timestamp()),
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm="HS256")


def create_refresh_token(user_id: str) -> RefreshToken:
    """7 gün geçerli rastgele refresh token kaydı oluşturur."""
    return RefreshToken(
        token=secrets.token_urlsafe(64),
        user_id=user_id,
        expires_on_utc=utc_now() + timedelta(days=7),
        created_at_utc=utc_now(),
    )


def decode_access_token(token: str, settings: Settings) -> dict:
    """JWT'yi doğrular; issuer/audience/expiry kontrol eder."""
    return jwt.decode(
        token,
        settings.jwt_secret,
        algorithms=["HS256"],
        audience=settings.jwt_audience,
        issuer=settings.jwt_issuer,
    )


def get_token_from_request(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None,
    access_token: str | None,
) -> str | None:
    """Önce Authorization: Bearer, sonra accessToken çerezini okur."""
    if credentials and credentials.scheme.lower() == "bearer" and credentials.credentials:
        return credentials.credentials
    if access_token:
        return access_token
    cookie_token = request.cookies.get(ACCESS_COOKIE)
    return cookie_token


def ensure_local_owner(session: Session) -> User:
    """
    Varsayılan yerel kullanıcıyı bulur veya oluşturur.

    Dönüş: 'Berkay' adlı tek-kişilik masaüstü sahibi kaydı.
    E-posta sabit tutulur ki her açılışta aynı kullanıcıya bağlanalım.
    """
    existing = session.exec(
        select(User).where(User.email == LOCAL_OWNER_EMAIL, User.is_deleted == False)  # noqa: E712
    ).first()
    if existing is not None:
        return existing

    # Rastgele parola: yerel modda login gerekmez; yine de hash kolonu boş bırakılmaz.
    owner = User(
        email=LOCAL_OWNER_EMAIL,
        password_hash=hash_password(secrets.token_urlsafe(24)),
        first_name=LOCAL_OWNER_FIRST_NAME,
        last_name=LOCAL_OWNER_LAST_NAME,
        role="User",
        created_at_utc=utc_now(),
    )
    session.add(owner)
    session.commit()
    session.refresh(owner)
    return owner


def get_current_user(
    request: Request,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
    access_token: Annotated[str | None, Cookie(alias=ACCESS_COOKIE)] = None,
) -> User:
    """
    İstek sahibini çözer (Local-First).

    1) Geçerli JWT varsa o kullanıcıyı döner.
    2) Token yoksa veya geçersizse otomatik 'Berkay' yerel kullanıcısına düşer.
       Böylece portföy / analiz / ekstre uçları giriş zorunluluğu olmadan çalışır.
    """
    token = get_token_from_request(request, credentials, access_token)

    # Token yok → doğrudan yerel sahip.
    if not token:
        return ensure_local_owner(session)

    try:
        payload = decode_access_token(token, settings)
    except jwt.PyJWTError:
        # Süresi dolmuş / bozuk token: kişisel kokpitte kilitlemek yerine yereline düş.
        return ensure_local_owner(session)

    user_id = payload.get("sub")
    if not user_id:
        return ensure_local_owner(session)

    user = session.get(User, user_id)
    if user is None or user.is_deleted:
        return ensure_local_owner(session)
    return user


def ensure_aware(value: datetime) -> datetime:
    """Naif datetime'ı UTC aware yapar (SQLite karşılaştırmaları için)."""
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value
