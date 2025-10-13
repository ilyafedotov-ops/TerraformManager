from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, List, Optional, Sequence

from fastapi import (
    APIRouter,
    Cookie,
    Depends,
    HTTPException,
    Response,
    Security,
    Request,
    Query,
    status,
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes
from pydantic import BaseModel, EmailStr

from backend.auth import auth_settings
from backend.auth.tokens import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    TokenError,
    TokenPayload,
    TokenType,
    TokenService,
    InvalidCredentialsError,
    InactiveUserError,
    RefreshTokenError,
    RefreshTokenExpiredError,
    RefreshTokenReuseError,
    decode_token,
    ensure_scopes,
)
from backend.auth.limiter import LoginRateLimiter
from backend.db import User
from backend.db.repositories import auth as auth_repo
from backend.db.session import get_session_dependency
from sqlalchemy.orm import Session


router = APIRouter(prefix="/auth", tags=["auth"])

DEFAULT_SCOPES = tuple(auth_settings.default_scopes)
REFRESH_COOKIE_NAME = auth_settings.refresh_cookie_name
CSRF_HEADER_NAME = "X-Refresh-Token-CSRF"
token_service = TokenService()
login_limiter = LoginRateLimiter()

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/token",
    scopes={
        "console:read": "View Terraform Manager data",
        "console:write": "Modify Terraform Manager resources",
        "reports:read": "Download report archives",
    },
)


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int
    refresh_expires_in: int
    scopes: List[str]
    refresh_token: str | None = None
    anti_csrf_token: str | None = None
    session_id: str | None = None


class UserProfile(BaseModel):
    email: str
    scopes: List[str]
    expires_in: int


class SessionInfo(BaseModel):
    id: str
    family_id: str | None = None
    created_at: datetime
    last_used_at: datetime | None = None
    expires_at: datetime
    ip_address: str | None = None
    user_agent: str | None = None
    scopes: List[str]
    is_current: bool = False


class SessionListResponse(BaseModel):
    sessions: List[SessionInfo]
    current_session_id: str | None = None


class AuthEvent(BaseModel):
    id: str
    event: str
    created_at: datetime
    subject: str | None = None
    session_id: str | None = None
    ip_address: str | None = None
    user_agent: str | None = None
    scopes: List[str]
    details: dict[str, Any]


class AuthEventListResponse(BaseModel):
    events: List[AuthEvent]


@dataclass
class CurrentUser:
    user: User
    token: TokenPayload


class RegisterPayload(BaseModel):
    email: EmailStr
    team: str | None = None
    region: str | None = None
    notes: str | None = None


class RecoverPayload(BaseModel):
    email: EmailStr


def _expected_api_token() -> Optional[str]:
    return auth_settings.expected_api_token()


def _cookie_secure_flag() -> bool:
    return auth_settings.cookie_secure


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _refresh_max_age(expires_at: datetime) -> int:
    delta = expires_at - _now()
    return max(int(delta.total_seconds()), 0)


def _set_refresh_cookie(response: Response, token: str, expires_at: datetime) -> None:
    params = {
        "path": "/",
        "httponly": True,
        "samesite": auth_settings.cookie_samesite,
        "secure": _cookie_secure_flag(),
        "max_age": _refresh_max_age(expires_at),
    }
    if auth_settings.cookie_domain:
        params["domain"] = auth_settings.cookie_domain
    response.set_cookie(REFRESH_COOKIE_NAME, token, **params)


def _delete_refresh_cookie(response: Response) -> None:
    response.delete_cookie(
        REFRESH_COOKIE_NAME,
        path="/",
        samesite=auth_settings.cookie_samesite,
        secure=_cookie_secure_flag(),
        domain=auth_settings.cookie_domain,
    )


def _calculate_expires_in(expires_at: datetime) -> int:
    return _refresh_max_age(expires_at)


def _get_request_metadata(request: Request) -> tuple[Optional[str], Optional[str]]:
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")
    return ip, user_agent


def _resolve_scopes(user: User, requested: Sequence[str]) -> list[str]:
    if requested:
        return list(dict.fromkeys(requested))
    if user.scopes:
        return list(user.scopes)
    return list(DEFAULT_SCOPES)


def _record_login_failure(
    session: Session,
    *,
    subject: str,
    scopes: Sequence[str],
    reason: str,
    ip_address: str | None,
    user_agent: str | None,
    retry_after: float | None = None,
) -> None:
    auth_repo.record_auth_event(
        session,
        event="login_failed",
        subject=subject,
        scopes=scopes,
        details={"reason": reason},
        ip_address=ip_address,
        user_agent=user_agent,
    )


def _provision_service_user(session: Session, email: str, password: str, scopes: Sequence[str]) -> User:
    hashed = token_service.hash_password(password)
    try:
        user = auth_repo.create_user(
            session,
            email=email,
            password_hash=hashed,
            scopes=list(scopes or DEFAULT_SCOPES),
            is_superuser=True,
        )
    except ValueError:
        user = auth_repo.get_user_by_email(session, email)
        if user and not token_service.verify_password(password, user.password_hash):
            user.password_hash = hashed
            session.add(user)
            session.flush()
    return auth_repo.get_user_by_email(session, email)


async def get_current_user(
    security_scopes: SecurityScopes,
    token: str = Depends(oauth2_scheme),
    session: Session = Depends(get_session_dependency),
) -> CurrentUser:
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        payload = token_service.decode_access_token(token)
        ensure_scopes(payload, security_scopes.scopes)
    except TokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate credentials",
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    user = auth_repo.get_user_by_email(session, payload.sub)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return CurrentUser(user=user, token=payload)


@router.post("/token", response_model=TokenResponse)
async def login_for_access_token(
    response: Response,
    request: Request,
    form_data: OAuth2PasswordRequestForm = Depends(),
    session: Session = Depends(get_session_dependency),
) -> TokenResponse:
    username = form_data.username.strip()
    password = form_data.password
    requested_scopes = list(form_data.scopes or [])
    ip_address, user_agent = _get_request_metadata(request)

    limiter_key = f"{username}:{ip_address or 'unknown'}"
    retry_after = login_limiter.check(limiter_key)
    if retry_after is not None:
        headers = {"Retry-After": f"{int(retry_after)}"}
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS, detail="Too many login attempts", headers=headers)

    user = auth_repo.get_user_by_email(session, username)
    expected_api_token = _expected_api_token()

    # Lazily provision a service user when legacy API token is used.
    if user is None and expected_api_token and password == expected_api_token:
        user = _provision_service_user(session, username, password, DEFAULT_SCOPES)

    if user is None:
        _record_login_failure(
            session,
            subject=username,
            scopes=requested_scopes,
            reason="invalid_credentials",
            ip_address=ip_address,
            user_agent=user_agent,
        )
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials")

    if not token_service.verify_password(password, user.password_hash):
        retry_after = login_limiter.hit(limiter_key)
        _record_login_failure(
            session,
            subject=username,
            scopes=requested_scopes,
            reason="invalid_credentials",
            ip_address=ip_address,
            user_agent=user_agent,
            retry_after=retry_after,
        )
        headers = {"Retry-After": f"{int(retry_after)}"} if retry_after else None
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Incorrect credentials", headers=headers)

    resolved_scopes = _resolve_scopes(user, requested_scopes)

    try:
        bundle = token_service.issue_tokens(
            session,
            user=user,
            scopes=resolved_scopes,
            api_token=expected_api_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except InactiveUserError as exc:
        retry_after = login_limiter.hit(limiter_key)
        _record_login_failure(
            session,
            subject=username,
            scopes=resolved_scopes,
            reason="user_inactive",
            ip_address=ip_address,
            user_agent=user_agent,
            retry_after=retry_after,
        )
        headers = {"Retry-After": f"{int(retry_after)}"} if retry_after else None
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="User account is inactive", headers=headers) from exc

    login_limiter.reset(limiter_key)
    _set_refresh_cookie(response, bundle.refresh_token, bundle.refresh_session.expires_at)
    if bundle.anti_csrf_token:
        response.headers[CSRF_HEADER_NAME] = bundle.anti_csrf_token

    refresh_expires_in = _calculate_expires_in(bundle.refresh_session.expires_at)

    return TokenResponse(
        access_token=bundle.access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=refresh_expires_in,
        scopes=list(bundle.refresh_session.scopes),
        refresh_token=bundle.refresh_token,
        anti_csrf_token=bundle.anti_csrf_token,
        session_id=bundle.refresh_session.id,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_access_token(
    response: Response,
    request: Request,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    session: Session = Depends(get_session_dependency),
) -> TokenResponse:
    if not refresh_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing refresh token")

    anti_csrf_token = request.headers.get(CSRF_HEADER_NAME)
    ip_address, user_agent = _get_request_metadata(request)

    try:
        bundle = token_service.rotate_refresh_token(
            session,
            refresh_token=refresh_token,
            anti_csrf_token=anti_csrf_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )
    except RefreshTokenExpiredError as exc:
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token expired") from exc
    except RefreshTokenReuseError as exc:
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Refresh token reuse detected") from exc
    except RefreshTokenError as exc:
        _delete_refresh_cookie(response)
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token") from exc

    _set_refresh_cookie(response, bundle.refresh_token, bundle.refresh_session.expires_at)
    if bundle.anti_csrf_token:
        response.headers[CSRF_HEADER_NAME] = bundle.anti_csrf_token

    refresh_expires_in = _calculate_expires_in(bundle.refresh_session.expires_at)

    return TokenResponse(
        access_token=bundle.access_token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        refresh_expires_in=refresh_expires_in,
        scopes=list(bundle.refresh_session.scopes),
        refresh_token=bundle.refresh_token,
        anti_csrf_token=bundle.anti_csrf_token,
        session_id=bundle.refresh_session.id,
    )


@router.post("/logout")
async def logout(
    response: Response,
    request: Request,
    refresh_token: str | None = Cookie(default=None, alias=REFRESH_COOKIE_NAME),
    session: Session = Depends(get_session_dependency),
) -> dict:
    _delete_refresh_cookie(response)
    ip_address, user_agent = _get_request_metadata(request)

    if refresh_token:
        try:
            payload = token_service.decode_refresh_token(refresh_token)
            session_id = payload.session_id
            if session_id:
                refresh_session = auth_repo.get_refresh_session(session, session_id)
                if refresh_session:
                    token_service.revoke_session(
                        session,
                        refresh_session,
                        reason="logout",
                        ip_address=ip_address,
                        user_agent=user_agent,
                    )
        except TokenError:
            pass

    return {"status": "logged_out"}


@router.get("/me", response_model=UserProfile)
async def get_profile(current_user: CurrentUser = Security(get_current_user, scopes=["console:read"])) -> UserProfile:
    now = _now()
    expires_in = max(int((current_user.token.expires_at() - now).total_seconds()), 0)
    scopes = current_user.user.scopes or current_user.token.scopes or list(DEFAULT_SCOPES)
    return UserProfile(email=current_user.user.email, scopes=list(scopes), expires_in=expires_in)


@router.get("/sessions", response_model=SessionListResponse)
async def list_sessions(
    current_user: CurrentUser = Security(get_current_user, scopes=["console:read"]),
    session: Session = Depends(get_session_dependency),
) -> SessionListResponse:
    records = auth_repo.list_active_refresh_sessions(session, current_user.user.id)
    current_session_id = current_user.token.session_id

    sorted_records = sorted(
        records,
        key=lambda item: (
            item.id == current_session_id,
            item.last_used_at or item.created_at,
        ),
        reverse=True,
    )

    sessions = [
        SessionInfo(
            id=item.id,
            family_id=item.family_id,
            created_at=item.created_at,
            last_used_at=item.last_used_at,
            expires_at=item.expires_at,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            scopes=list(item.scopes or []),
            is_current=current_session_id == item.id,
        )
        for item in sorted_records
    ]

    return SessionListResponse(sessions=sessions, current_session_id=current_session_id)


@router.get("/events", response_model=AuthEventListResponse)
async def list_auth_events(
    limit: int = Query(25, ge=1, le=200),
    current_user: CurrentUser = Security(get_current_user, scopes=["console:read"]),
    session: Session = Depends(get_session_dependency),
) -> AuthEventListResponse:
    records = auth_repo.list_recent_auth_events(session, user_id=current_user.user.id, limit=limit)
    events = [
        AuthEvent(
            id=item.id,
            event=item.event,
            created_at=item.created_at,
            subject=item.subject,
            session_id=item.session_id,
            ip_address=item.ip_address,
            user_agent=item.user_agent,
            scopes=list(item.scopes or []),
            details=dict(item.details or {}),
        )
        for item in records
    ]
    return AuthEventListResponse(events=events)


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    request: Request,
    current_user: CurrentUser = Security(get_current_user, scopes=["console:write"]),
    session: Session = Depends(get_session_dependency),
) -> dict:
    refresh_session = auth_repo.get_refresh_session(session, session_id)
    if not refresh_session or refresh_session.user_id != current_user.user.id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Session not found")

    if refresh_session.revoked_at is not None:
        return {
            "status": "already_revoked",
            "session_id": refresh_session.id,
            "revoked_at": refresh_session.revoked_at,
        }

    ip_address, user_agent = _get_request_metadata(request)
    token_service.revoke_session(
        session,
        refresh_session,
        reason="user_revoked" if current_user.token.session_id == refresh_session.id else "user_revoked_other",
        ip_address=ip_address,
        user_agent=user_agent,
    )

    return {"status": "revoked", "session_id": refresh_session.id}


@router.post("/register", status_code=status.HTTP_202_ACCEPTED)
async def submit_access_request(
    payload: RegisterPayload,
    session: Session = Depends(get_session_dependency),
) -> dict:
    auth_repo.record_auth_event(
        session,
        event="register_request",
        subject=payload.email,
        scopes=[],
        details={
            "team": payload.team,
            "region": payload.region,
            "notes": payload.notes,
        },
    )
    return {"status": "received"}


@router.post("/recover", status_code=status.HTTP_202_ACCEPTED)
async def submit_recover_request(
    payload: RecoverPayload,
    session: Session = Depends(get_session_dependency),
) -> dict:
    auth_repo.record_auth_event(
        session,
        event="recover_request",
        subject=payload.email,
        scopes=[],
        details={},
    )
    return {"status": "received"}
