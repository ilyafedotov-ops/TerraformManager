from __future__ import annotations

from pathlib import Path
from typing import Iterator, Tuple

import pytest
from fastapi.testclient import TestClient

from api.main import app
from backend.auth.tokens import TokenService
from backend.db.session import get_session_dependency, init_models, session_scope
from backend.db.repositories import auth as auth_repo
from backend import storage


@pytest.fixture()
def projects_client(
    tmp_path_factory: pytest.TempPathFactory,
    monkeypatch: pytest.MonkeyPatch,
) -> Iterator[Tuple[TestClient, str, Path, Path]]:
    base_dir = tmp_path_factory.mktemp("projects_api")
    db_path = base_dir / "app.db"
    init_models(db_path)
    projects_root = base_dir / "projects"
    monkeypatch.setattr(storage, "DEFAULT_PROJECTS_ROOT", projects_root)

    def override_session_dependency():
        with session_scope(db_path) as session:
            yield session

    app.dependency_overrides[get_session_dependency] = override_session_dependency

    email = "api@example.com"
    password = "Str0ngPass!"
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
            access_token = login_response.json()["access_token"]
            yield client, access_token, db_path, projects_root
    finally:
        app.dependency_overrides.pop(get_session_dependency, None)


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def test_project_route_lifecycle(projects_client: Tuple[TestClient, str, Path, Path]) -> None:
    client, token, db_path, projects_root = projects_client

    storage.upsert_config("baseline", "thresholds:\n  high: fail\n", db_path=db_path)

    create_body = {
        "name": "API Project",
        "description": "Managed via API",
        "metadata": {"team": "platform"},
    }
    create_response = client.post("/projects", json=create_body, headers=auth_headers(token))
    assert create_response.status_code == 201
    project = create_response.json()
    project_id = project["id"]
    assert project["name"] == "API Project"
    assert (projects_root / project["slug"]).exists()

    conflict = client.post("/projects", json=create_body, headers=auth_headers(token))
    assert conflict.status_code == 400

    list_response = client.get("/projects", headers=auth_headers(token))
    assert list_response.status_code == 200
    assert list_response.json()[0]["id"] == project_id

    detail_response = client.get(f"/projects/{project_id}", headers=auth_headers(token))
    assert detail_response.status_code == 200
    assert detail_response.json()["metadata"]["team"] == "platform"

    configs_response = client.get(
        f"/projects/{project_id}/configs",
        headers=auth_headers(token),
        params={"include_payload": "true"},
    )
    assert configs_response.status_code == 200
    assert configs_response.json() == []

    create_config_response = client.post(
        f"/projects/{project_id}/configs",
        json={
            "name": "Default gates",
            "config_name": "baseline",
            "is_default": True,
            "metadata": {"scope": "workspace"},
        },
        headers=auth_headers(token),
    )
    assert create_config_response.status_code == 201
    config_record = create_config_response.json()
    config_id = config_record["id"]
    assert config_record["is_default"] is True

    inline_config_response = client.post(
        f"/projects/{project_id}/configs",
        json={
            "name": "Inline profile",
            "payload": "thresholds:\n  medium: warn\n",
            "tags": ["prod"],
            "metadata": {"scope": "prod"},
        },
        headers=auth_headers(token),
    )
    assert inline_config_response.status_code == 201
    inline_config_id = inline_config_response.json()["id"]

    configs_response = client.get(
        f"/projects/{project_id}/configs",
        headers=auth_headers(token),
        params={"include_payload": "true"},
    )
    assert configs_response.status_code == 200
    configs_payload = configs_response.json()
    assert len(configs_payload) == 2

    update_inline = client.patch(
        f"/projects/{project_id}/configs/{inline_config_id}",
        json={"tags": ["prod", "critical"], "is_default": True},
        headers=auth_headers(token),
    )
    assert update_inline.status_code == 200
    assert update_inline.json()["is_default"] is True

    config_detail = client.get(
        f"/projects/{project_id}/configs/{config_id}",
        headers=auth_headers(token),
        params={"include_payload": "false"},
    )
    assert config_detail.status_code == 200
    assert config_detail.json()["is_default"] is False

    delete_inline = client.delete(
        f"/projects/{project_id}/configs/{inline_config_id}",
        headers=auth_headers(token),
    )
    assert delete_inline.status_code == 204

    configs_response = client.get(
        f"/projects/{project_id}/configs",
        headers=auth_headers(token),
        params={"include_payload": "false"},
    )
    assert configs_response.status_code == 200
    configs_payload = configs_response.json()
    assert len(configs_payload) == 1
    assert configs_payload[0]["is_default"] is True

    update_response = client.patch(
        f"/projects/{project_id}",
        json={"description": "Updated description", "metadata": {"team": "platform", "env": "prod"}},
        headers=auth_headers(token),
    )
    assert update_response.status_code == 200
    updated = update_response.json()
    assert updated["description"] == "Updated description"
    assert updated["metadata"]["env"] == "prod"

    run_payload = {"label": "Initial review", "kind": "review", "parameters": {"branch": "main"}}
    run_create = client.post(f"/projects/{project_id}/runs", json=run_payload, headers=auth_headers(token))
    assert run_create.status_code == 201
    run = run_create.json()
    run_id = run["id"]
    run_dir = Path(run["artifacts_path"])
    assert run_dir.exists()

    runs_response = client.get(f"/projects/{project_id}/runs", headers=auth_headers(token))
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["items"][0]["id"] == run_id

    patch_response = client.patch(
        f"/projects/{project_id}/runs/{run_id}",
        json={"status": "completed"},
        headers=auth_headers(token),
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["status"] == "completed"

    upload_response = client.post(
        f"/projects/{project_id}/runs/{run_id}/artifacts",
        data={"path": "outputs/report.json", "overwrite": "true"},
        files={"file": ("report.json", b'{"ok": true}', "application/json")},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert upload_response.status_code == 201
    assert upload_response.json()["path"] == "outputs/report.json"
    artifact_id = upload_response.json().get("artifact_id")
    assert artifact_id

    list_artifacts = client.get(
        f"/projects/{project_id}/runs/{run_id}/artifacts",
        headers=auth_headers(token),
    )
    assert list_artifacts.status_code == 200
    assert any(entry["path"] == "outputs" for entry in list_artifacts.json())

    project_artifacts = client.get(
        f"/projects/{project_id}/artifacts",
        headers=auth_headers(token),
    )
    assert project_artifacts.status_code == 200
    payload = project_artifacts.json()
    assert payload["total_count"] == 1
    assert payload["items"][0]["id"] == artifact_id

    artifact_update = client.patch(
        f"/projects/{project_id}/artifacts/{artifact_id}",
        json={"tags": ["report"], "metadata": {"format": "json"}},
        headers=auth_headers(token),
    )
    assert artifact_update.status_code == 200
    assert artifact_update.json()["tags"] == ["report"]

    artifact_detail = client.get(
        f"/projects/{project_id}/artifacts/{artifact_id}",
        headers=auth_headers(token),
    )
    assert artifact_detail.status_code == 200
    assert artifact_detail.json()["metadata"]["format"] == "json"

    download = client.get(
        f"/projects/{project_id}/runs/{run_id}/artifacts/download",
        params={"path": "outputs/report.json"},
        headers=auth_headers(token),
    )
    assert download.status_code == 200
    assert download.content == b'{"ok": true}'

    delete_file = client.delete(
        f"/projects/{project_id}/runs/{run_id}/artifacts",
        params={"path": "outputs/report.json"},
        headers=auth_headers(token),
    )
    assert delete_file.status_code == 204

    manual_file = run_dir / "manual.txt"
    manual_file.write_text("manual")
    sync_response = client.post(
        f"/projects/{project_id}/runs/{run_id}/artifacts/sync",
        json={"prune_missing": False},
        headers=auth_headers(token),
    )
    assert sync_response.status_code == 200
    assert sync_response.json()["files_indexed"] >= 1

    project_artifacts = client.get(
        f"/projects/{project_id}/artifacts",
        headers=auth_headers(token),
    )
    assert project_artifacts.status_code == 200
    assert project_artifacts.json()["total_count"] == 1

    remove_response = client.delete(
        f"/projects/{project_id}",
        params={"remove_files": "true"},
        headers=auth_headers(token),
    )
    assert remove_response.status_code == 204
    assert not (projects_root / project["slug"]).exists()
