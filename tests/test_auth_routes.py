from __future__ import annotations

from pathlib import Path
from typing import Iterator

import pytest
from fastapi.testclient import TestClient

from api.main import app
from backend.auth.tokens import TokenService
from backend.db.repositories import auth as auth_repo
from backend.db.session import init_models, session_scope, get_session_dependency


@pytest.fixture()
def client(tmp_path_factory: pytest.TempPathFactory) -> Iterator[tuple[TestClient, Path]]:
    db_dir = tmp_path_factory.mktemp("db")
    db_path = db_dir / "app.db"
    init_models(db_path)

    def override_session_dependency():
        with session_scope(db_path) as session:
            yield session

    app.dependency_overrides[get_session_dependency] = override_session_dependency

    try:
        with TestClient(app) as test_client:
            yield test_client, db_path
    finally:
        app.dependency_overrides.pop(get_session_dependency, None)


def test_password_login_and_refresh_flow(client: tuple[TestClient, Path]) -> None:
    test_client, db_path = client
    email = "user@example.com"
    password = "S3cret!"
    token_service = TokenService()

    with session_scope(db_path) as session:
        auth_repo.create_user(
            session,
            email=email,
            password_hash=token_service.hash_password(password),
            scopes=["console:read", "console:write"],
        )

    login_response = test_client.post(
        "/auth/token",
        data={"username": email, "password": password, "scope": "console:read console:write"},
        headers={"Accept": "application/json"},
    )
    assert login_response.status_code == 200
    body = login_response.json()
    assert body["access_token"]
    assert body["refresh_token"]

    old_refresh_token = test_client.cookies.get("tm_refresh_token")
    assert old_refresh_token is not None
    old_csrf = login_response.headers.get("X-Refresh-Token-CSRF") or body.get("anti_csrf_token")
    assert old_csrf

    refresh_response = test_client.post(
        "/auth/refresh",
        headers={"X-Refresh-Token-CSRF": old_csrf},
    )
    assert refresh_response.status_code == 200
    refresh_body = refresh_response.json()
    new_refresh_token = test_client.cookies.get("tm_refresh_token")
    assert new_refresh_token and new_refresh_token != old_refresh_token
    new_csrf = refresh_response.headers.get("X-Refresh-Token-CSRF") or refresh_body.get("anti_csrf_token")
    assert new_csrf

    # Attempt reuse of the old token should fail and revoke the family.
    test_client.cookies.set("tm_refresh_token", old_refresh_token, domain="testserver", path="/")
    reuse_response = test_client.post(
        "/auth/refresh",
        headers={"X-Refresh-Token-CSRF": old_csrf},
    )
    assert reuse_response.status_code == 401

    # Restore new token for subsequent requests.
    test_client.cookies.set("tm_refresh_token", new_refresh_token, domain="testserver", path="/")
    profile_response = test_client.get("/auth/me", headers={"Authorization": f"Bearer {refresh_body['access_token']}"})
    assert profile_response.status_code == 200
    assert profile_response.json()["email"] == email


def test_login_rate_limiting(client: tuple[TestClient, Path]) -> None:
    test_client, db_path = client
    email = "throttle@example.com"
    password = "CorrectHorseBatteryStaple"
    token_service = TokenService()

    with session_scope(db_path) as session:
        auth_repo.create_user(
            session,
            email=email,
            password_hash=token_service.hash_password(password),
            scopes=["console:read"],
        )

    for _ in range(5):
        response = test_client.post(
            "/auth/token",
            data={"username": email, "password": "wrong", "scope": "console:read"},
            headers={"Accept": "application/json"},
        )
        assert response.status_code == 401

    blocked = test_client.post(
        "/auth/token",
        data={"username": email, "password": "wrong", "scope": "console:read"},
        headers={"Accept": "application/json"},
    )
    assert blocked.status_code == 429


def test_session_listing_and_revocation(client: tuple[TestClient, Path]) -> None:
    test_client, db_path = client
    primary_email = "session-owner@example.com"
    other_email = "other@example.com"
    password = "S3cure!"
    token_service = TokenService()

    with session_scope(db_path) as session:
        auth_repo.create_user(
            session,
            email=primary_email,
            password_hash=token_service.hash_password(password),
            scopes=["console:read", "console:write"],
        )
        auth_repo.create_user(
            session,
            email=other_email,
            password_hash=token_service.hash_password(password),
            scopes=["console:read", "console:write"],
        )

    login_response = test_client.post(
        "/auth/token",
        data={"username": primary_email, "password": password, "scope": "console:read console:write"},
        headers={"Accept": "application/json"},
    )
    assert login_response.status_code == 200
    login_body = login_response.json()
    access_token = login_body["access_token"]

    list_response = test_client.get(
        "/auth/sessions",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    assert list_response.status_code == 200
    sessions_payload = list_response.json()
    assert sessions_payload["current_session_id"]
    sessions = sessions_payload["sessions"]
    assert len(sessions) == 1
    session_id = sessions[0]["id"]
    assert sessions[0]["is_current"] is True

    # A different user should be unable to revoke the owner's session.
    other_login = test_client.post(
        "/auth/token",
        data={"username": other_email, "password": password, "scope": "console:read console:write"},
        headers={"Accept": "application/json"},
    )
    assert other_login.status_code == 200
    other_access = other_login.json()["access_token"]
    forbidden_revoke = test_client.delete(
        f"/auth/sessions/{session_id}",
        headers={"Authorization": f"Bearer {other_access}", "Accept": "application/json"},
    )
    assert forbidden_revoke.status_code == 404

    revoke_response = test_client.delete(
        f"/auth/sessions/{session_id}",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    assert revoke_response.status_code == 200
    assert revoke_response.json()["status"] == "revoked"

    # Subsequent listing omits the revoked session.
    post_revoke_list = test_client.get(
        "/auth/sessions",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    assert post_revoke_list.status_code == 200
    assert post_revoke_list.json()["sessions"] == []

    # Revoking again returns an informative payload.
    second_revoke = test_client.delete(
        f"/auth/sessions/{session_id}",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    assert second_revoke.status_code == 200
    assert second_revoke.json()["status"] == "already_revoked"


def test_session_listing_requires_authentication(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    response = test_client.get("/auth/sessions", headers={"Accept": "application/json"})
    assert response.status_code == 401


def test_session_revocation_requires_write_scope(client: tuple[TestClient, Path]) -> None:
    test_client, db_path = client
    email = "reader@example.com"
    password = "OnlyRead!"
    token_service = TokenService()

    with session_scope(db_path) as session:
        auth_repo.create_user(
            session,
            email=email,
            password_hash=token_service.hash_password(password),
            scopes=["console:read"],
        )

    login_response = test_client.post(
        "/auth/token",
        data={"username": email, "password": password, "scope": "console:read"},
        headers={"Accept": "application/json"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    sessions_response = test_client.get(
        "/auth/sessions",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    assert sessions_response.status_code == 200
    session_id = sessions_response.json()["sessions"][0]["id"]

    revoke_attempt = test_client.delete(
        f"/auth/sessions/{session_id}",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    assert revoke_attempt.status_code == 401
    body = revoke_attempt.json()
    assert "detail" in body


def test_auth_events_listing(client: tuple[TestClient, Path]) -> None:
    test_client, db_path = client
    email = "events@example.com"
    password = "S3cret!"
    token_service = TokenService()

    with session_scope(db_path) as session:
        auth_repo.create_user(
            session,
            email=email,
            password_hash=token_service.hash_password(password),
            scopes=["console:read", "console:write"],
        )

    login_response = test_client.post(
        "/auth/token",
        data={"username": email, "password": password, "scope": "console:read console:write"},
        headers={"Accept": "application/json"},
    )
    assert login_response.status_code == 200
    access_token = login_response.json()["access_token"]

    events_response = test_client.get(
        "/auth/events",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    assert events_response.status_code == 200
    payload = events_response.json()
    assert "events" in payload
    events = payload["events"]
    assert isinstance(events, list)
    assert any(event["event"] == "login_success" for event in events)

    limited_response = test_client.get(
        "/auth/events?limit=1",
        headers={"Authorization": f"Bearer {access_token}", "Accept": "application/json"},
    )
    assert limited_response.status_code == 200
    assert len(limited_response.json()["events"]) <= 1


def test_auth_events_requires_authentication(client: tuple[TestClient, Path]) -> None:
    test_client, _ = client
    response = test_client.get("/auth/events", headers={"Accept": "application/json"})
    assert response.status_code == 401
