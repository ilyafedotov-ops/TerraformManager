from __future__ import annotations

from datetime import timedelta
from pathlib import Path

import pytest

from backend.auth.tokens import (
    TokenService,
    RefreshTokenExpiredError,
    RefreshTokenReuseError,
)
from backend.db.repositories import auth as auth_repo
from backend.db.session import init_models, session_scope


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    path = tmp_path / "tokens.db"
    init_models(path)
    return path


@pytest.fixture()
def token_service() -> TokenService:
    return TokenService()


def _create_user(db_path: Path) -> str:
    with session_scope(db_path) as session:
        user = auth_repo.create_user(
            session,
            email="bundle@example.com",
            password_hash="hash",
            scopes=["console:read"],
        )
        return user.id


def test_issue_and_rotate_refresh_token(db_path: Path, token_service: TokenService) -> None:
    user_id = _create_user(db_path)

    with session_scope(db_path) as session:
        user = auth_repo.get_user_by_id(session, user_id)
        bundle = token_service.issue_tokens(session, user=user, scopes=["console:read"])
        original_refresh = bundle.refresh_token
        original_session_id = bundle.refresh_session.id
        assert bundle.refresh_session.family_id is not None
        assert bundle.refresh_session.token_hash
        assert bundle.anti_csrf_token is not None

    with session_scope(db_path) as session:
        rotated = token_service.rotate_refresh_token(
            session,
            refresh_token=original_refresh,
            anti_csrf_token=bundle.anti_csrf_token,
        )
        new_session_id = rotated.refresh_session.id
        assert new_session_id != original_session_id

        old_session = auth_repo.get_refresh_session(session, original_session_id)
        assert old_session is not None
        assert old_session.revoked_at is not None
        assert old_session.replaced_by == new_session_id

        # Attempting to reuse the old token should revoke the entire family
        with pytest.raises(RefreshTokenReuseError):
            token_service.rotate_refresh_token(
                session,
                refresh_token=original_refresh,
                anti_csrf_token=bundle.anti_csrf_token,
            )

        family_sessions = auth_repo.list_sessions_by_family(session, old_session.family_id, include_revoked=True)
        assert all(s.revoked_at is not None for s in family_sessions)


def test_refresh_token_expiration(db_path: Path, token_service: TokenService) -> None:
    user_id = _create_user(db_path)

    with session_scope(db_path) as session:
        user = auth_repo.get_user_by_id(session, user_id)
        bundle = token_service.issue_tokens(session, user=user)
        # Manually expire session
        session_obj = bundle.refresh_session
        session_obj.expires_at = session_obj.expires_at - timedelta(days=10)
        session.add(session_obj)

    with session_scope(db_path) as session:
        with pytest.raises(RefreshTokenExpiredError):
            token_service.rotate_refresh_token(session, refresh_token=bundle.refresh_token)
