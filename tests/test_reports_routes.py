from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Tuple

import pytest
from fastapi.testclient import TestClient

from api.main import app
from backend.auth.tokens import TokenService
from backend.db import get_session_dependency
from backend.db.repositories import auth as auth_repo
from backend.db.session import init_models, session_scope
from backend import storage


@pytest.fixture()
def reports_client(
    tmp_path_factory: pytest.TempPathFactory,
) -> Iterator[Tuple[TestClient, str, Path]]:
    base_dir = tmp_path_factory.mktemp("reports_api")
    db_path = base_dir / "app.db"
    init_models(db_path)

    def override_session_dependency():
        with session_scope(db_path) as session:
            yield session

    app.dependency_overrides[get_session_dependency] = override_session_dependency

    email = "reviewer@example.com"
    password = "Sup3rStrong!"
    token_service = TokenService()

    with session_scope(db_path) as session:
        auth_repo.create_user(
            session,
            email=email,
            password_hash=token_service.hash_password(password),
            scopes=["console:read", "console:write"],
        )

    try:
        with TestClient(app) as client:
            login_response = client.post(
                "/auth/token",
                data={"username": email, "password": password, "scope": "console:read console:write"},
                headers={"Accept": "application/json"},
            )
            assert login_response.status_code == 200
            token = login_response.json()["access_token"]
            yield client, token, db_path
    finally:
        app.dependency_overrides.pop(get_session_dependency, None)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def test_reports_review_workflow(reports_client: Tuple[TestClient, str, Path]) -> None:
    client, token, db_path = reports_client

    with session_scope(db_path) as session:
        project = storage.create_project(
            name="Workspace A",
            description="test",
            session=session,
        )
        storage.save_report(
            "r1",
            summary={
                "issues_found": 3,
                "severity_counts": {"high": 2, "medium": 1},
            },
            report={"summary": {"issues_found": 3, "severity_counts": {"high": 2, "medium": 1}}},
            session=session,
            review_metadata={
                "review_status": "in_review",
                "review_assignee": "alice@example.com",
                "review_notes": "Initial import",
            },
        )
        storage.create_project_run(
            project_id=project["id"],
            label="UI upload",
            kind="review",
            report_id="r1",
            session=session,
        )
        storage.save_report(
            "r2",
            summary={
                "issues_found": 1,
                "severity_counts": {"low": 1},
            },
            report={"summary": {"issues_found": 1, "severity_counts": {"low": 1}}},
            session=session,
            review_metadata={
                "review_status": "resolved",
                "review_assignee": "bob@example.com",
            },
        )

    list_response = client.get("/reports", headers=auth_headers(token))
    assert list_response.status_code == 200
    payload = list_response.json()
    assert payload["total_count"] == 2
    assert payload["aggregates"]["status_counts"]["in_review"] == 1
    assert payload["aggregates"]["status_counts"]["resolved"] == 1
    assert payload["aggregates"]["severity_counts"]["high"] == 2
    assert payload["items"][0]["id"] in {"r1", "r2"}

    filtered = client.get(
        "/reports",
        params={"status": "resolved"},
        headers=auth_headers(token),
    )
    assert filtered.status_code == 200
    filtered_payload = filtered.json()
    assert filtered_payload["total_count"] == 1
    assert filtered_payload["items"][0]["id"] == "r2"

    project_filtered = client.get(
        "/reports",
        params={"project_id": project["id"]},
        headers=auth_headers(token),
    )
    assert project_filtered.status_code == 200
    scoped_payload = project_filtered.json()
    assert scoped_payload["total_count"] == 1
    assert scoped_payload["items"][0]["id"] == "r1"

    due_date = datetime(2025, 1, 15, 0, 0, tzinfo=timezone.utc).isoformat()
    patch_response = client.patch(
        "/reports/r1",
        json={
            "review_status": "changes_requested",
            "review_assignee": "carol@example.com",
            "review_due_at": due_date,
            "review_notes": "Need additional context",
        },
        headers=auth_headers(token),
    )
    assert patch_response.status_code == 200
    updated = patch_response.json()
    assert updated["review_status"] == "changes_requested"
    assert updated["review_assignee"] == "carol@example.com"
    assert updated["review_due_at"].startswith("2025-01-15")

    detail_response = client.get("/reports/r1", headers=auth_headers(token))
    assert detail_response.status_code == 200
    detail = detail_response.json()
    assert detail["review_status"] == "changes_requested"
    assert detail["review_notes"] == "Need additional context"

    create_comment = client.post(
        "/reports/r1/comments",
        json={"body": "Flagging follow-up.", "author": "carol@example.com"},
        headers=auth_headers(token),
    )
    assert create_comment.status_code == 201
    comment = create_comment.json()
    comment_id = comment["id"]
    assert comment["body"] == "Flagging follow-up."

    comments_list = client.get("/reports/r1/comments", headers=auth_headers(token))
    assert comments_list.status_code == 200
    comments_payload = comments_list.json()
    assert comments_payload["items"][0]["id"] == comment_id

    delete_comment = client.delete(
        f"/reports/r1/comments/{comment_id}",
        headers=auth_headers(token),
    )
    assert delete_comment.status_code == 200
    assert delete_comment.json()["status"] == "deleted"

    post_delete_list = client.get("/reports/r1/comments", headers=auth_headers(token))
    assert post_delete_list.status_code == 200
    assert post_delete_list.json()["items"] == []
