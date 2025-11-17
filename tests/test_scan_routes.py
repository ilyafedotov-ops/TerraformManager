from __future__ import annotations

from pathlib import Path
from typing import Dict, Tuple

import pytest
from fastapi.testclient import TestClient

from tests.test_projects_routes import auth_headers, projects_client


def _create_project(client: TestClient, token: str, name: str) -> Dict[str, str]:
    response = client.post(
        "/projects",
        json={"name": name, "metadata": {"env": "dev"}},
        headers=auth_headers(token),
    )
    assert response.status_code == 201
    return response.json()


def test_scan_requires_project_reference(projects_client: Tuple[TestClient, str, Path, Path]) -> None:
    client, token, _, _ = projects_client
    response = client.post("/scan", json={"paths": ["."], "save": False}, headers=auth_headers(token))
    assert response.status_code == 400
    assert "project_id" in response.json()["detail"]


def test_scan_rejects_paths_outside_workspace(
    projects_client: Tuple[TestClient, str, Path, Path],
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
    projects_client: Tuple[TestClient, str, Path, Path],
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
