from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator
from uuid import uuid4

import pytest

from backend.db.repositories import auth as auth_repo
from backend.db.session import init_models, session_scope


@pytest.fixture()
def db_path(tmp_path: Path) -> Iterator[Path]:
    database = tmp_path / "auth.db"
    init_models(database)
    yield database


def test_create_and_fetch_user(db_path: Path) -> None:
    email = "TestUser@example.com"
    with session_scope(db_path) as session:
        user = auth_repo.create_user(
            session,
            email=email,
            password_hash="hashed",
            scopes=["console:read"],
        )
        user_id = user.id

    with session_scope(db_path) as session:
        fetched = auth_repo.get_user_by_email(session, email.lower())
        assert fetched is not None
        assert fetched.id == user_id
        assert fetched.scopes == ["console:read"]
        assert fetched.is_active

        listed = auth_repo.list_users(session)
        assert listed
        assert listed[0].email == email.lower()


def test_refresh_session_lifecycle(db_path: Path) -> None:
    with session_scope(db_path) as session:
        user = auth_repo.create_user(
            session,
            email="session@example.com",
            password_hash="hash",
            scopes=["console:read"],
        )
        user_id = user.id
        expires_at = datetime.now(tz=timezone.utc) + timedelta(days=1)
        refresh = auth_repo.create_refresh_session(
            session,
            session_id=str(uuid4()),
            user_id=user_id,
            token_hash="refresh-hash",
            expires_at=expires_at,
            scopes=["console:read"],
            user_agent="pytest",
            ip_address="127.0.0.1",
        )
        refresh_id = refresh.id

    with session_scope(db_path) as session:
        active = auth_repo.list_active_refresh_sessions(session, user_id)
        assert len(active) == 1
        fetched = auth_repo.get_refresh_session(session, refresh_id)
        assert fetched is not None
        assert fetched.user_id == user_id

        auth_repo.touch_refresh_session(
            session,
            fetched,
            last_used_at=datetime.now(tz=timezone.utc) + timedelta(minutes=5),
        )
        auth_repo.revoke_refresh_session(session, fetched, reason="logout")

    with session_scope(db_path) as session:
        active_after = auth_repo.list_active_refresh_sessions(session, user_id)
        assert active_after == []


def test_auth_audit_records(db_path: Path) -> None:
    with session_scope(db_path) as session:
        user = auth_repo.create_user(
            session,
            email="audit@example.com",
            password_hash="hash",
        )
        user_id = user.id
        session_id = str(uuid4())
        auth_repo.record_auth_event(
            session,
            event="login_success",
            user_id=user_id,
            subject="audit@example.com",
            session_id=session_id,
            ip_address="127.0.0.1",
            details={"source": "test"},
        )

    with session_scope(db_path) as session:
        events = auth_repo.list_recent_auth_events(session, user_id=user_id, limit=10)
        assert len(events) == 1
        event = events[0]
        assert event.event == "login_success"
        assert event.details.get("source") == "test"
