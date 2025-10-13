from __future__ import annotations

import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from fastapi import Depends, Header, HTTPException, Request
from sqlalchemy.orm import Session

from api.routes import auth as auth_routes
from backend.auth import auth_settings
from backend.auth.tokens import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    TokenError,
    TokenPayload,
    TokenType,
    TokenService,
)
from backend.db import get_session_dependency
from backend.db.repositories import auth as auth_repo

token_service = TokenService()
SERVICE_USER_EMAIL = os.getenv("TFM_SERVICE_USER_EMAIL", "service@local")


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ensure_service_user(session: Session, email: str, password: str, scopes: List[str]) -> auth_repo.User:
    user = auth_repo.get_user_by_email(session, email)
    password_hash = token_service.hash_password(password)
    if user is None:
        user = auth_repo.create_user(
            session,
            email=email,
            password_hash=password_hash,
            scopes=scopes,
            is_superuser=True,
        )
    else:
        if not token_service.verify_password(password, user.password_hash):
            user.password_hash = password_hash
            session.add(user)
            session.flush()
        if not user.is_active:
            user.is_active = True
            session.add(user)
            session.flush()
    return user


def require_current_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    session: Session = Depends(get_session_dependency),
) -> auth_routes.CurrentUser:
    bearer_token: str | None = None
    provided_token: str | None = None

    if authorization:
        auth_value = authorization.strip()
        if auth_value.lower().startswith("bearer "):
            bearer_token = auth_value.split(" ", 1)[1].strip()
        else:
            provided_token = auth_value

    if x_api_token:
        provided_token = x_api_token.strip()

    if bearer_token:
        try:
            payload = token_service.decode_access_token(bearer_token)
        except TokenError as exc:
            raise HTTPException(status_code=401, detail="invalid or missing API token") from exc

        user = auth_repo.get_user_by_email(session, payload.sub)
        if not user:
            raise HTTPException(status_code=401, detail="invalid or missing API token")
        return auth_routes.CurrentUser(user=user, token=payload)

    expected_api_token = auth_settings.expected_api_token()
    if expected_api_token and provided_token and provided_token == expected_api_token:
        scopes = list(auth_routes.DEFAULT_SCOPES)
        user = _ensure_service_user(session, SERVICE_USER_EMAIL, expected_api_token, scopes)
        now = _now()
        payload = TokenPayload(
            sub=user.email,
            scopes=scopes,
            api_token=expected_api_token,
            type=TokenType.ACCESS,
            exp=int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
            iat=int(now.timestamp()),
            jti=str(uuid.uuid4()),
            sid=None,
            fam=None,
            iss=auth_settings.jwt_issuer,
            aud=auth_settings.jwt_audience,
        )
        return auth_routes.CurrentUser(user=user, token=payload)

    if expected_api_token:
        raise HTTPException(status_code=401, detail="invalid or missing API token")

    raise HTTPException(status_code=401, detail="Not authenticated")
