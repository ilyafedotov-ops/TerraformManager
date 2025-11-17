from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Tuple

import pytest
from fastapi.testclient import TestClient

from backend import storage


def auth_headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}", "Accept": "application/json"}


def _create_project(client: TestClient, token: str, name: str = "API Generator Project") -> dict[str, str]:
    response = client.post(
        "/projects",
        json={"name": name, "description": "Generator validation test"},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def _sample_s3_payload() -> dict[str, str]:
    return {
        "bucket_name": "generator-bucket-1234",
        "region": "us-east-1",
        "environment": "dev",
        "owner_tag": "platform",
        "cost_center_tag": "ENG",
        "force_destroy": False,
        "versioning": True,
        "enforce_secure_transport": True,
    }


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

    registered = storage.register_generated_asset(
        project_id=project_id,
        name="Scan report bundle",
        asset_type="scan_report",
        description="Latest scan outputs",
        tags=["report"],
        metadata={"source": "api"},
        run_id=run_id,
        storage_filename="report.json",
        data=b'{"issues": []}',
        media_type="application/json",
        projects_root=projects_root,
        db_path=db_path,
    )
    asset_id = registered["asset"]["id"]
    version_id = registered["version"]["id"]

    manifest_response = client.get(
        f"/projects/{project_id}/library/{asset_id}/versions/{version_id}/files",
        headers=auth_headers(token),
    )
    assert manifest_response.status_code == 200
    manifest = manifest_response.json()
    assert len(manifest) == 1
    assert manifest[0]["path"] == registered["version"]["display_path"]
    assert manifest[0]["media_type"] == "application/json"


def test_project_generator_validation_failure(
    projects_client: Tuple[TestClient, str, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token, _, _ = projects_client
    project = _create_project(client, token, name="Generator Validation")

    def fake_validate(_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"status": "failed", "issues": ["terraform fmt failed"]}

    monkeypatch.setattr("api.routes.projects.validate_terraform_sources", fake_validate)

    response = client.post(
        f"/projects/{project['id']}/generators/aws/s3-secure-bucket",
        json={"payload": _sample_s3_payload()},
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail["error"] == "validation_failed"
    assert detail["validation_summary"]["status"] == "failed"

def test_project_generator_force_save(
    projects_client: Tuple[TestClient, str, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token, _, _ = projects_client
    project = _create_project(client, token, name="Generator Force Save")

    def fake_validate(_files: List[Dict[str, Any]]) -> Dict[str, Any]:
        return {"status": "failed", "issues": ["terraform fmt failed"]}

    monkeypatch.setattr("api.routes.projects.validate_terraform_sources", fake_validate)

    payload = {
        "payload": _sample_s3_payload(),
        "options": {
            "force_save": True,
            "asset_name": "Forced Bucket",
            "description": "Force-saved config",
        },
    }
    response = client.post(
        f"/projects/{project['id']}/generators/aws/s3-secure-bucket",
        json=payload,
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    body = response.json()
    assert body["asset"]["name"] == "Forced Bucket"
    assert body["version"]["metadata"]["force_save"] is True

    runs = client.get(f"/projects/{project['id']}/runs", headers=auth_headers(token)).json()["items"]
    assert runs
    assert runs[0]["status"] == "completed"
    assert runs[0]["summary"]["asset_id"] == body["asset"]["id"]
