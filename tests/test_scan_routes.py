from __future__ import annotations

import io
import zipfile
from pathlib import Path
from typing import Dict, Tuple

import copy

import pytest
from fastapi.testclient import TestClient

from tests.test_projects_routes import auth_headers

ProjectsClientFixture = Tuple[TestClient, str, Path, Path]


def _create_project(client: TestClient, token: str, name: str) -> Dict[str, str]:
    response = client.post(
        "/projects",
        json={"name": name, "metadata": {"env": "dev"}},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def test_scan_requires_project_reference(projects_client: ProjectsClientFixture) -> None:
    client, token, _, _ = projects_client
    response = client.post("/scan", json={"paths": ["."], "save": False}, headers=auth_headers(token))
    assert response.status_code == 400
    assert "project_id" in response.json()["detail"]


def test_scan_rejects_paths_outside_workspace(
    projects_client: ProjectsClientFixture,
) -> None:
    client, token, _, _ = projects_client
    project = _create_project(client, token, "Workspace Guardrails")
    payload = {
        "paths": ["../etc"],
        "project_id": project["id"],
        "save": False,
    }
    response = client.post("/scan", json=payload, headers=auth_headers(token))
    assert response.status_code == 400
    assert "workspace" in response.json()["detail"]


def test_scan_uses_project_workspace_paths(
    projects_client: ProjectsClientFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token, _, _ = projects_client
    project = _create_project(client, token, "Workspace Scan")
    project_root = Path(project["root_path"])
    target_dir = project_root / "modules" / "app"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "main.tf").write_text('resource "null_resource" "example" {}', encoding="utf-8")
    plan_path = project_root / "plans" / "plan.json"
    plan_path.parent.mkdir(parents=True, exist_ok=True)
    plan_path.write_text("{}", encoding="utf-8")

    captured: Dict[str, object] = {}

    def fake_scan_paths(paths, **kwargs):
        captured["paths"] = paths
        captured["plan_path"] = kwargs.get("plan_path")
        captured["context"] = kwargs.get("context")
        return {"summary": {"issues_found": 0}, "findings": []}

    monkeypatch.setattr("api.main.scan_paths", fake_scan_paths)

    payload = {
        "paths": ["modules/app"],
        "project_id": project["id"],
        "plan_path": "plans/plan.json",
        "save": False,
    }
    response = client.post("/scan", json=payload, headers=auth_headers(token))
    assert response.status_code == 200
    assert captured["paths"] == [target_dir]
    assert captured["plan_path"] == plan_path
    context = captured["context"]
    assert isinstance(context, dict)
    assert context.get("project_id") == project["id"]


def test_scan_upload_requires_project(projects_client: Tuple[TestClient, str, Path, Path]) -> None:
    client, token, _, _ = projects_client
    files = {"files": ("scan.tf", b'resource "null_resource" "example" {}', "text/plain")}
    response = client.post(
        "/scan/upload",
        data={"terraform_validate": "false", "save": "false"},
        files=files,
        headers=auth_headers(token),
    )
    assert response.status_code == 400
    assert "project_id" in response.text


def test_scan_upload_uses_workspace(
    projects_client: Tuple[TestClient, str, Path, Path],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token, _, _ = projects_client
    project = _create_project(client, token, "Upload Workspace")
    project_root = Path(project["root_path"])
    captured: Dict[str, object] = {}

    def fake_scan_paths(paths, **kwargs):
        captured["paths"] = paths
        captured["plan_path"] = kwargs.get("plan_path")
        captured["context"] = kwargs.get("context")
        return {"summary": {"issues_found": 0}, "findings": []}

    monkeypatch.setattr("api.main.scan_paths", fake_scan_paths)

    files = {"files": ("scan.tf", b'resource "null_resource" "example" {}', "text/plain")}
    data = {
        "project_id": project["id"],
        "terraform_validate": "false",
        "save": "false",
    }
    response = client.post("/scan/upload", data=data, files=files, headers=auth_headers(token))
    assert response.status_code == 200
    assert response.json()["summary"]["issues_found"] == 0
    paths = captured["paths"]
    assert isinstance(paths, list) and paths
    target_path = paths[0]
    assert isinstance(target_path, Path)
    assert target_path.resolve().is_relative_to(project_root)
    assert captured["plan_path"] is None
    context = captured["context"]
    assert isinstance(context, dict)
    assert context.get("project_id") == project["id"]


def test_scan_upload_rejects_zip_escape(projects_client: Tuple[TestClient, str, Path, Path]) -> None:
    client, token, _, _ = projects_client
    project = _create_project(client, token, "Upload Zip Guard")

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        zf.writestr("../evil.tf", 'resource "null_resource" "oops" {}')
    buffer.seek(0)

    files = {"files": ("payload.zip", buffer.read(), "application/zip")}
    data = {
        "project_id": project["id"],
        "terraform_validate": "false",
        "save": "false",
    }
    response = client.post("/scan/upload", data=data, files=files, headers=auth_headers(token))
    assert response.status_code == 400
    assert "zip entry" in response.text


def test_scan_save_persists_report_asset(
    projects_client: ProjectsClientFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token, _, _ = projects_client
    project = _create_project(client, token, "Scan Auto Save")
    project_root = Path(project["root_path"])
    target_dir = project_root / "services" / "demo"
    target_dir.mkdir(parents=True, exist_ok=True)
    (target_dir / "main.tf").write_text('resource "null_resource" "example" {}', encoding="utf-8")

    base_report = {
        "summary": {
            "issues_found": 2,
            "files_scanned": 1,
            "severity_counts": {"high": 1},
        },
        "findings": [
            {"id": "TFM001", "severity": "high", "resource": "aws_s3_bucket.example"},
        ],
    }

    def fake_scan_paths(paths, **kwargs):  # type: ignore[no-untyped-def]
        assert paths and isinstance(paths[0], Path)
        return copy.deepcopy(base_report)

    monkeypatch.setattr("api.main.scan_paths", fake_scan_paths)

    payload = {
        "paths": ["services/demo"],
        "project_id": project["id"],
        "save": True,
    }
    response = client.post("/scan", json=payload, headers=auth_headers(token))
    assert response.status_code == 200
    report = response.json()
    assert report["summary"]["issues_found"] == 2
    saved_report_id = report.get("id")
    assert saved_report_id
    summary_block = report.get("summary") or {}
    assert summary_block.get("asset_id")
    assert summary_block.get("version_id")
    assert summary_block.get("artifacts")

    runs_response = client.get(f"/projects/{project['id']}/runs", headers=auth_headers(token))
    assert runs_response.status_code == 200
    runs_payload = runs_response.json()
    assert runs_payload["items"], "Expected run to be created"
    run = runs_payload["items"][0]
    assert run["report_id"] == saved_report_id
    summary = run.get("summary") or {}
    assert summary.get("asset_id")
    assert summary.get("version_id")
    assert summary.get("report_id") == saved_report_id
    artifacts = summary.get("artifacts") or []
    assert any(str(saved_report_id) in entry for entry in artifacts)

    artifacts_response = client.get(
        f"/projects/{project['id']}/runs/{run['id']}/artifacts",
        headers=auth_headers(token),
    )
    assert artifacts_response.status_code == 200
    stored_root = artifacts_response.json()
    reports_dir = next((entry for entry in stored_root if entry["path"] == "reports"), None)
    assert reports_dir and reports_dir["is_dir"]

    report_entries_response = client.get(
        f"/projects/{project['id']}/runs/{run['id']}/artifacts",
        headers=auth_headers(token),
        params={"path": "reports"},
    )
    assert report_entries_response.status_code == 200
    report_entries = report_entries_response.json()
    artifact_paths = [entry["path"] for entry in report_entries if not entry["is_dir"]]
    assert f"reports/{saved_report_id}.json" in artifact_paths
    assert f"reports/{saved_report_id}.html" in artifact_paths

    library_response = client.get(
        f"/projects/{project['id']}/library",
        headers=auth_headers(token),
        params={"include_versions": "true"},
    )
    assert library_response.status_code == 200
    library_payload = library_response.json()
    assert library_payload["items"], "Expected scan report asset in library"
    asset = library_payload["items"][0]
    assert asset["asset_type"] == "scan_report"
    assert "scan" in " ".join(asset.get("tags", []))
    versions = asset.get("versions") or []
    assert versions, "Expected asset version metadata"
    version = versions[0]
    assert version["metadata"].get("report_id") == saved_report_id


def test_scan_upload_save_persists_report_asset(
    projects_client: ProjectsClientFixture,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, token, _, _ = projects_client
    project = _create_project(client, token, "Upload Auto Save")

    base_report = {
        "summary": {
            "issues_found": 1,
            "files_scanned": 1,
            "severity_counts": {"medium": 1},
        },
        "findings": [
            {"id": "TFM099", "severity": "medium", "resource": "azurerm_storage_account.demo"},
        ],
    }

    def fake_scan_paths(paths, **kwargs):  # type: ignore[no-untyped-def]
        assert paths and isinstance(paths[0], Path)
        return copy.deepcopy(base_report)

    monkeypatch.setattr("api.main.scan_paths", fake_scan_paths)

    files = {
        "files": ("scan.tf", b'resource "null_resource" "example" {}', "text/plain"),
    }
    data = {
        "project_id": project["id"],
        "terraform_validate": "false",
        "save": "true",
    }
    response = client.post("/scan/upload", data=data, files=files, headers=auth_headers(token))
    assert response.status_code == 200
    payload = response.json()
    saved_report_id = payload.get("id")
    assert saved_report_id
    summary_block = payload.get("summary") or {}
    assert summary_block.get("asset_id")
    assert summary_block.get("version_id")
    assert summary_block.get("artifacts")

    runs_response = client.get(f"/projects/{project['id']}/runs", headers=auth_headers(token))
    assert runs_response.status_code == 200
    run = runs_response.json()["items"][0]
    assert run["report_id"] == saved_report_id
    summary = run.get("summary") or {}
    assert summary.get("asset_id")
    assert summary.get("report_id") == saved_report_id

    artifacts_response = client.get(
        f"/projects/{project['id']}/runs/{run['id']}/artifacts",
        headers=auth_headers(token),
    )
    assert artifacts_response.status_code == 200
    stored_root = artifacts_response.json()
    reports_dir = next((entry for entry in stored_root if entry["path"] == "reports"), None)
    assert reports_dir and reports_dir["is_dir"]

    report_entries_response = client.get(
        f"/projects/{project['id']}/runs/{run['id']}/artifacts",
        headers=auth_headers(token),
        params={"path": "reports"},
    )
    assert report_entries_response.status_code == 200
    report_entries = report_entries_response.json()
    artifact_paths = [entry["path"] for entry in report_entries if not entry["is_dir"]]
    assert f"reports/{saved_report_id}.json" in artifact_paths
    assert f"reports/{saved_report_id}.html" in artifact_paths

    library_response = client.get(
        f"/projects/{project['id']}/library",
        headers=auth_headers(token),
        params={"include_versions": "true"},
    )
    assert library_response.status_code == 200
    asset = library_response.json()["items"][0]
    assert asset["asset_type"] == "scan_report"
    versions = asset.get("versions") or []
    assert versions
    assert versions[0]["metadata"].get("source") == "api.scan_upload"
