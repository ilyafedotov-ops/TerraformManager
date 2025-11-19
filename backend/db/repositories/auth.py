from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Mapping, Sequence
from uuid import uuid4

from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from backend.db.models import AuthAudit, RefreshSession, User


def _normalize_email(email: str) -> str:
    return email.strip().lower()


def _ensure_utc(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def _clean_optional_string(value: str | None) -> str | None:
    if value is None:
        return None
    trimmed = value.strip()
    return trimmed or None


def _normalize_timezone(value: str | None) -> str | None:
    cleaned = _clean_optional_string(value)
    if cleaned is None:
        return None
    try:
        ZoneInfo(cleaned)
    except ZoneInfoNotFoundError as exc:  # noqa: WPS440
        raise ValueError(f"Unknown timezone: {cleaned}") from exc
    return cleaned


def create_user(
    session: Session,
    *,
    email: str,
    password_hash: str,
    scopes: Sequence[str] | None = None,
    is_active: bool = True,
    is_superuser: bool = False,
) -> User:
    """
    Persist a new user record. Raises ValueError if email already exists.
    """
    normalized_email = _normalize_email(email)
    if get_user_by_email(session, normalized_email):
        raise ValueError(f"user with email {normalized_email!r} already exists")

    user = User(
        email=normalized_email,
        password_hash=password_hash,
        is_active=is_active,
        is_superuser=is_superuser,
        scopes=list(scopes or []),
    )
    session.add(user)
    session.flush()
    return user


def get_user_by_email(session: Session, email: str) -> User | None:
    stmt: Select[User] = select(User).where(User.email == _normalize_email(email))
    return session.scalar(stmt)


def get_user_by_id(session: Session, user_id: str) -> User | None:
    return session.get(User, user_id)


def list_users(session: Session) -> list[User]:
    stmt: Select[User] = select(User).order_by(User.created_at.desc())
    return list(session.scalars(stmt).all())


def create_refresh_session(
    session: Session,
    *,
    session_id: str,
    user_id: str,
    token_hash: str,
    expires_at: datetime,
    scopes: Sequence[str] | None = None,
    user_agent: str | None = None,
    ip_address: str | None = None,
    anti_csrf_token: str | None = None,
    family_id: str | None = None,
) -> RefreshSession:
    refresh_session = RefreshSession(
        id=session_id,
        user_id=user_id,
        token_hash=token_hash,
        family_id=family_id or str(uuid4()),
        scopes=list(scopes or []),
        user_agent=user_agent,
        ip_address=ip_address,
        anti_csrf_token=anti_csrf_token,
        expires_at=_ensure_utc(expires_at),
        last_used_at=_ensure_utc(datetime.now(tz=timezone.utc)),
    )
    session.add(refresh_session)
    session.flush()
    return refresh_session


def get_refresh_session(session: Session, session_id: str) -> RefreshSession | None:
    return session.get(RefreshSession, session_id)


def list_active_refresh_sessions(session: Session, user_id: str, *, now: datetime | None = None) -> list[RefreshSession]:
    now = _ensure_utc(now or datetime.now(tz=timezone.utc))
    stmt: Select[RefreshSession] = (
        select(RefreshSession)
        .where(
            RefreshSession.user_id == user_id,
            RefreshSession.revoked_at.is_(None),
            RefreshSession.expires_at > now,
        )
        .order_by(RefreshSession.created_at.desc())
    )
    return list(session.scalars(stmt).all())


def list_sessions_by_family(
    session: Session,
    family_id: str,
    *,
    include_revoked: bool = True,
) -> list[RefreshSession]:
    stmt: Select[RefreshSession] = select(RefreshSession).where(RefreshSession.family_id == family_id)
    if not include_revoked:
        stmt = stmt.where(RefreshSession.revoked_at.is_(None))
    stmt = stmt.order_by(RefreshSession.created_at.desc())
    return list(session.scalars(stmt).all())


def revoke_refresh_session(
    session: Session,
    refresh_session: RefreshSession,
    *,
    revoked_at: datetime | None = None,
    reason: str | None = None,
    replaced_by: str | None = None,
) -> RefreshSession:
    refresh_session.revoked_at = _ensure_utc(revoked_at or datetime.now(tz=timezone.utc))
    refresh_session.revoked_reason = reason
    refresh_session.replaced_by = replaced_by
    session.add(refresh_session)
    session.flush()
    return refresh_session


def touch_refresh_session(
    session: Session,
    refresh_session: RefreshSession,
    *,
    token_hash: str | None = None,
    expires_at: datetime | None = None,
    anti_csrf_token: str | None = None,
    last_used_at: datetime | None = None,
) -> RefreshSession:
    if token_hash is not None:
        refresh_session.token_hash = token_hash
    if expires_at is not None:
        refresh_session.expires_at = _ensure_utc(expires_at)
    if anti_csrf_token is not None:
        refresh_session.anti_csrf_token = anti_csrf_token
    refresh_session.last_used_at = _ensure_utc(last_used_at or datetime.now(tz=timezone.utc))
    session.add(refresh_session)
    session.flush()
    return refresh_session


def record_auth_event(
    session: Session,
    *,
    event: str,
    user_id: str | None = None,
    subject: str | None = None,
    session_id: str | None = None,
    scopes: Sequence[str] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
    details: dict | None = None,
) -> AuthAudit:
    audit = AuthAudit(
        event=event,
        user_id=user_id,
        subject=subject,
        session_id=session_id,
        scopes=list(scopes or []),
        ip_address=ip_address,
        user_agent=user_agent,
        details=dict(details or {}),
    )
    session.add(audit)
    session.flush()
    return audit


def list_recent_auth_events(
    session: Session,
    *,
    limit: int = 50,
    user_id: str | None = None,
    session_id: str | None = None,
) -> list[AuthAudit]:
    stmt: Select[AuthAudit] = select(AuthAudit).order_by(AuthAudit.created_at.desc())
    if user_id:
        stmt = stmt.where(AuthAudit.user_id == user_id)
    if session_id:
        stmt = stmt.where(AuthAudit.session_id == session_id)
    stmt = stmt.limit(limit)
    return list(session.scalars(stmt).all())


def update_user_profile(
    session: Session,
    user: User,
    *,
    full_name: str | None = None,
    job_title: str | None = None,
    timezone_value: str | None = None,
    avatar_url: str | None = None,
    preferences: Mapping[str, Any] | None = None,
) -> User:
    """Mutate and persist basic profile attributes."""
    user.full_name = _clean_optional_string(full_name) if full_name is not None else user.full_name
    user.job_title = _clean_optional_string(job_title) if job_title is not None else user.job_title
    if timezone_value is not None:
        user.timezone = _normalize_timezone(timezone_value)
    user.avatar_url = _clean_optional_string(avatar_url) if avatar_url is not None else user.avatar_url
    if preferences is not None:
        user.profile_preferences = dict(preferences)
    session.add(user)
    session.flush()
    return user


def change_user_password(session: Session, user: User, *, new_hash: str) -> User:
    user.password_hash = new_hash
    session.add(user)
    session.flush()
    return user


def get_last_login_at(session: Session, user_id: str) -> datetime | None:
    stmt: Select[datetime] = (
        select(AuthAudit.created_at)
        .where(AuthAudit.user_id == user_id, AuthAudit.event == "login_success")
        .order_by(AuthAudit.created_at.desc())
        .limit(1)
    )
    return session.scalar(stmt)
