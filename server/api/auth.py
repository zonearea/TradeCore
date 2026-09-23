from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlmodel import Session

from server.api.schemas import (
    AccessTokenResponse,
    CurrentUserResponse,
    LoginRequest,
    RegisterRequest,
    RegisterResponse,
)
from server.core.config import Settings, get_settings
from server.core.database import get_session
from server.core.security import ACCESS_COOKIE, REFRESH_COOKIE, get_current_user
from server.models.user import User
from server.services.auth_service import AuthError, login_user, refresh_session, register_user

router = APIRouter(prefix="/api/auth", tags=["auth"])


def _cookie_kwargs(request: Request, expires: datetime | None = None) -> dict:
    options: dict = {
        "httponly": True,
        "secure": request.url.scheme == "https",
        "samesite": "lax",
        "path": "/",
    }
    if expires is not None:
        options["expires"] = expires
    return options


def _set_auth_cookies(
    response: Response,
    request: Request,
    settings: Settings,
    access_token: str,
    refresh_token: str,
) -> None:
    now = datetime.now(timezone.utc)
    response.set_cookie(
        ACCESS_COOKIE,
        access_token,
        **_cookie_kwargs(request, now + timedelta(minutes=settings.jwt_expiration_minutes)),
    )
    response.set_cookie(
        REFRESH_COOKIE,
        refresh_token,
        **_cookie_kwargs(request, now + timedelta(days=7)),
    )


def _clear_auth_cookies(response: Response, request: Request) -> None:
    options = _cookie_kwargs(request)
    response.delete_cookie(ACCESS_COOKIE, path=options["path"], samesite=options["samesite"])
    response.delete_cookie(REFRESH_COOKIE, path=options["path"], samesite=options["samesite"])


@router.post("/register", status_code=status.HTTP_201_CREATED, response_model=RegisterResponse)
def register(
    body: RegisterRequest,
    session: Annotated[Session, Depends(get_session)],
) -> RegisterResponse:
    try:
        user_id = register_user(
            session,
            email=body.email,
            password=body.password,
            first_name=body.firstName,
            last_name=body.lastName,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None
    return RegisterResponse(id=user_id)


@router.post("/login", response_model=AccessTokenResponse)
def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenResponse:
    try:
        access_token, refresh_token = login_user(
            session,
            settings,
            email=body.email,
            password=body.password,
        )
    except AuthError as exc:
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None

    _set_auth_cookies(response, request, settings, access_token, refresh_token)
    return AccessTokenResponse(accessToken=access_token)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response) -> Response:
    _clear_auth_cookies(response, request)
    response.status_code = status.HTTP_204_NO_CONTENT
    return response


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh(
    request: Request,
    response: Response,
    session: Annotated[Session, Depends(get_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AccessTokenResponse:
    refresh_token = request.cookies.get(REFRESH_COOKIE)
    if not refresh_token or not refresh_token.strip():
        _clear_auth_cookies(response, request)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="The refresh token is invalid or expired.",
        )

    try:
        access_token, new_refresh = refresh_session(session, settings, refresh_token)
    except AuthError as exc:
        _clear_auth_cookies(response, request)
        raise HTTPException(status_code=exc.status_code, detail=exc.detail) from None

    _set_auth_cookies(response, request, settings, access_token, new_refresh)
    return AccessTokenResponse(accessToken=access_token)


@router.get("/me", response_model=CurrentUserResponse)
def me(user: Annotated[User, Depends(get_current_user)]) -> CurrentUserResponse:
    return CurrentUserResponse(
        id=user.id,
        email=user.email,
        firstName=user.first_name,
        lastName=user.last_name,
        role=user.role,
    )
