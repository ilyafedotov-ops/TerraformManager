from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Iterable, Sequence
from uuid import uuid4

from jose import JWTError, jwt
from pydantic import BaseModel, ValidationError, field_validator
from sqlalchemy.orm import Session

from backend.auth.settings import auth_settings, AuthSettings
from backend.db.models import RefreshSession, User
from backend.db.repositories import auth as auth_repo

# === Exceptions ===


class TokenError(RuntimeError):
    """Raised when access or refresh tokens are invalid."""


class AuthenticationServiceError(RuntimeError):
    """Base exception for token service failures."""


class InvalidCredentialsError(AuthenticationServiceError):
    """Raised when user credentials are incorrect."""


class InactiveUserError(AuthenticationServiceError):
    """Raised when an inactive user attempts authentication."""


class RefreshTokenError(AuthenticationServiceError):
    """Raised for generic refresh token failures."""


class RefreshTokenExpiredError(RefreshTokenError):
    """Raised when a refresh token has expired."""


class RefreshTokenReuseError(RefreshTokenError):
    """Raised when a refresh token is reused after rotation."""


class RefreshTokenMismatchError(RefreshTokenError):
    """Raised when a refresh token hash or anti-CSRF token mismatches."""


# === Token types & payload ===


class TokenType(str):
    ACCESS = "access"
    REFRESH = "refresh"


class TokenPayload(BaseModel):
    sub: str
    scopes: list[str] = []
    api_token: str | None = None
    type: str = TokenType.ACCESS
    exp: int
    iat: int | None = None
    jti: str | None = None
    sid: str | None = None
    fam: str | None = None
    iss: str | None = None
    aud: str | None = None

    @field_validator("exp", "iat", mode="before")
    @classmethod
    def _coerce_int(cls, value: int | float | datetime | None) -> int | None:
        if value is None:
            return None
        if isinstance(value, datetime):
            return int(value.replace(tzinfo=timezone.utc).timestamp())
        if isinstance(value, (int, float)):
            return int(value)
        raise ValueError("Unable to coerce timestamp")

    def expires_at(self) -> datetime:
        return datetime.fromtimestamp(self.exp, tz=timezone.utc)

    @property
    def session_id(self) -> str | None:
        return self.sid or self.jti

    @property
    def family_id(self) -> str | None:
        return self.fam

    @property
    def token_type(self) -> str:
        return self.type


ACCESS_TOKEN_EXPIRE_MINUTES = auth_settings.access_token_minutes
REFRESH_TOKEN_EXPIRE_MINUTES = auth_settings.refresh_token_minutes
JWT_ALGORITHM = auth_settings.jwt_algorithm
ACCESS_TOKEN_SECRET = auth_settings.access_token_secret.get_secret_value()
REFRESH_TOKEN_SECRET = auth_settings.resolved_refresh_secret().get_secret_value()


def _common_claims(
    subject: str,
    *,
    token_type: str,
    scopes: Iterable[str],
    minutes: int,
    api_token: str | None = None,
    token_id: str | None = None,
    session_id: str | None = None,
    family_id: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
    issued_at: datetime | None = None,
) -> dict:
    issued = issued_at or datetime.now(tz=timezone.utc)
    payload: dict[str, object] = {
        "sub": subject,
        "type": token_type,
        "scopes": list(scopes),
        "iat": int(issued.timestamp()),
        "exp": int((issued + timedelta(minutes=minutes)).timestamp()),
    }
    if api_token:
        payload["api_token"] = api_token
    if token_id:
        payload["jti"] = token_id
    if session_id:
        payload["sid"] = session_id
    if family_id:
        payload["fam"] = family_id
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience
    return payload


def create_access_token(
    subject: str,
    *,
    scopes: Iterable[str] = (),
    api_token: str | None = None,
    minutes: int | None = None,
    token_id: str | None = None,
    session_id: str | None = None,
    family_id: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    payload = _common_claims(
        subject,
        token_type=TokenType.ACCESS,
        scopes=scopes,
        api_token=api_token,
        minutes=minutes or ACCESS_TOKEN_EXPIRE_MINUTES,
        token_id=token_id,
        session_id=session_id,
        family_id=family_id,
        issuer=issuer or auth_settings.jwt_issuer,
        audience=audience or auth_settings.jwt_audience,
    )
    return jwt.encode(payload, ACCESS_TOKEN_SECRET, algorithm=JWT_ALGORITHM)


def create_refresh_token(
    subject: str,
    *,
    scopes: Iterable[str] = (),
    api_token: str | None = None,
    minutes: int | None = None,
    token_id: str | None = None,
    session_id: str | None = None,
    family_id: str | None = None,
    issuer: str | None = None,
    audience: str | None = None,
) -> str:
    payload = _common_claims(
        subject,
        token_type=TokenType.REFRESH,
        scopes=scopes,
        api_token=api_token,
        minutes=minutes or REFRESH_TOKEN_EXPIRE_MINUTES,
        token_id=token_id,
        session_id=session_id,
        family_id=family_id,
        issuer=issuer or auth_settings.jwt_issuer,
        audience=audience or auth_settings.jwt_audience,
    )
    return jwt.encode(payload, REFRESH_TOKEN_SECRET, algorithm=JWT_ALGORITHM)


def decode_token(token: str, expected_type: str = TokenType.ACCESS) -> TokenPayload:
    secret = ACCESS_TOKEN_SECRET if expected_type == TokenType.ACCESS else REFRESH_TOKEN_SECRET
    decode_kwargs = {}
    if auth_settings.jwt_audience:
        decode_kwargs["audience"] = auth_settings.jwt_audience
    if auth_settings.jwt_issuer:
        decode_kwargs["issuer"] = auth_settings.jwt_issuer
    try:
        payload = jwt.decode(token, secret, algorithms=[JWT_ALGORITHM], **decode_kwargs)
        data = TokenPayload.model_validate(payload)
    except (JWTError, ValidationError) as exc:
        raise TokenError("Could not validate credentials") from exc

    if data.token_type != expected_type:
        raise TokenError("Unexpected token type")
    return data


def ensure_scopes(payload: TokenPayload, required_scopes: Sequence[str]) -> None:
    missing = [scope for scope in required_scopes if scope not in payload.scopes]
    if missing:
        raise TokenError(f"Missing required scopes: {', '.join(missing)}")


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _coerce_utc(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


@dataclass
class TokenBundle:
    access_token: str
    refresh_token: str
    refresh_session: RefreshSession
    anti_csrf_token: str | None
    user: User


class TokenService:
    def __init__(self, settings: AuthSettings | None = None):
        self.settings = settings or auth_settings

    # ---- public helpers ----

    def hash_password(self, password: str) -> str:
        from backend.auth.passwords import hash_password as _hash

        return _hash(password)

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        from backend.auth.passwords import verify_password as _verify

        return _verify(plain_password, hashed_password)

    def decode_access_token(self, token: str) -> TokenPayload:
        return decode_token(token, expected_type=TokenType.ACCESS)

    def decode_refresh_token(self, token: str) -> TokenPayload:
        return decode_token(token, expected_type=TokenType.REFRESH)

    # ---- issuance ----

    def issue_tokens(
        self,
        db: Session,
        *,
        user: User,
        scopes: Sequence[str] | None = None,
        api_token: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
        family_id: str | None = None,
    ) -> TokenBundle:
        if not user.is_active:
            raise InactiveUserError("User is inactive.")

        session_id = str(uuid4())
        token_id = str(uuid4())
        family_id = family_id or str(uuid4())
        anti_csrf = uuid4().hex
        resolved_scopes = list(scopes or user.scopes or self.settings.default_scopes)

        access_token = create_access_token(
            user.email,
            scopes=resolved_scopes,
            api_token=api_token,
            token_id=token_id,
            session_id=session_id,
            family_id=family_id,
        )
        refresh_token = create_refresh_token(
            user.email,
            scopes=resolved_scopes,
            api_token=api_token,
            token_id=session_id,
            session_id=session_id,
            family_id=family_id,
        )

        refresh_session = auth_repo.create_refresh_session(
            db,
            session_id=session_id,
            user_id=user.id,
            token_hash=hash_token(refresh_token),
            expires_at=_now() + timedelta(minutes=self.settings.refresh_token_minutes),
            scopes=resolved_scopes,
            user_agent=user_agent,
            ip_address=ip_address,
            anti_csrf_token=anti_csrf,
            family_id=family_id,
        )

        auth_repo.record_auth_event(
            db,
            event="login_success",
            user_id=user.id,
            subject=user.email,
            session_id=refresh_session.id,
            scopes=resolved_scopes,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return TokenBundle(
            access_token=access_token,
            refresh_token=refresh_token,
            refresh_session=refresh_session,
            anti_csrf_token=anti_csrf,
            user=user,
        )

    # ---- refresh ----

    def rotate_refresh_token(
        self,
        db: Session,
        *,
        refresh_token: str,
        anti_csrf_token: str | None = None,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> TokenBundle:
        payload = self.decode_refresh_token(refresh_token)
        session_id = payload.session_id
        if not session_id:
            raise RefreshTokenError("Refresh token missing session identifier.")

        refresh_session = auth_repo.get_refresh_session(db, session_id)
        if not refresh_session:
            raise RefreshTokenError("Refresh session not found.")

        hashed = hash_token(refresh_token)
        if hashed != refresh_session.token_hash:
            raise RefreshTokenMismatchError("Refresh token signature mismatch.")

        now = _now()
        revoked_at = _coerce_utc(refresh_session.revoked_at)
        if revoked_at != refresh_session.revoked_at:
            refresh_session.revoked_at = revoked_at
        if revoked_at is not None:
            # Token reuse or manual revocation
            self._handle_reuse(db, refresh_session, ip_address=ip_address, user_agent=user_agent)
            raise RefreshTokenReuseError("Refresh token has been revoked.")

        expires_at = _coerce_utc(refresh_session.expires_at)
        if expires_at != refresh_session.expires_at:
            refresh_session.expires_at = expires_at
        if expires_at and expires_at <= now:
            auth_repo.revoke_refresh_session(db, refresh_session, revoked_at=now, reason="expired")
            raise RefreshTokenExpiredError("Refresh token expired.")

        if refresh_session.anti_csrf_token and anti_csrf_token is not None:
            if anti_csrf_token != refresh_session.anti_csrf_token:
                raise RefreshTokenMismatchError("Anti-CSRF token mismatch.")

        user = refresh_session.user
        if user is None:
            raise RefreshTokenError("Associated user not found.")
        if not user.is_active:
            auth_repo.revoke_refresh_session(db, refresh_session, revoked_at=now, reason="user_inactive")
            raise InactiveUserError("User is inactive.")

        new_bundle = self.issue_tokens(
            db,
            user=user,
            scopes=refresh_session.scopes,
            api_token=payload.api_token,
            ip_address=ip_address,
            user_agent=user_agent,
            family_id=refresh_session.family_id,
        )

        auth_repo.revoke_refresh_session(
            db,
            refresh_session,
            revoked_at=now,
            reason="rotated",
            replaced_by=new_bundle.refresh_session.id,
        )

        auth_repo.touch_refresh_session(
            db,
            new_bundle.refresh_session,
            last_used_at=now,
        )

        auth_repo.record_auth_event(
            db,
            event="token_refreshed",
            user_id=user.id,
            subject=user.email,
            session_id=new_bundle.refresh_session.id,
            scopes=new_bundle.refresh_session.scopes,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        return new_bundle

    # ---- revocation helpers ----

    def revoke_session(
        self,
        db: Session,
        refresh_session: RefreshSession,
        *,
        reason: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> None:
        auth_repo.revoke_refresh_session(db, refresh_session, reason=reason)
        user = refresh_session.user
        auth_repo.record_auth_event(
            db,
            event="session_revoked",
            user_id=user.id if user else None,
            subject=user.email if user else None,
            session_id=refresh_session.id,
            scopes=refresh_session.scopes,
            ip_address=ip_address,
            user_agent=user_agent,
            details={"reason": reason},
        )

    # ---- internal helpers ----

    def _handle_reuse(
        self,
        db: Session,
        compromised_session: RefreshSession,
        *,
        ip_address: str | None,
        user_agent: str | None,
    ) -> None:
        now = _now()
        family_id = compromised_session.family_id
        sessions = auth_repo.list_sessions_by_family(db, family_id, include_revoked=False)
        for session_obj in sessions:
            auth_repo.revoke_refresh_session(
                db,
                session_obj,
                revoked_at=now,
                reason="reuse_detected",
            )
        user = compromised_session.user
        auth_repo.record_auth_event(
            db,
            event="refresh_reuse_detected",
            user_id=user.id if user else None,
            subject=user.email if user else None,
            session_id=compromised_session.id,
            scopes=compromised_session.scopes,
            ip_address=ip_address,
            user_agent=user_agent,
        )
