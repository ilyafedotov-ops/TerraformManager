from __future__ import annotations

from pathlib import Path
from typing import Tuple

from fastapi.testclient import TestClient

from backend.db.migrations import run_terraform_management_migration
from tests.test_projects_routes import auth_headers


def test_workspace_variable_import_and_compare(projects_client: Tuple[TestClient, str, Path, Path]) -> None:
    client, token, db_path, projects_root = projects_client
    run_terraform_management_migration(db_path)

    # Create project
    resp = client.post(
        "/projects",
        json={"name": "workspace-api", "description": "ws compare"},
        headers=auth_headers(token),
    )
    assert resp.status_code == 201
    project = resp.json()

    working_dir = Path(project["root_path"]) / "envs"
    working_dir.mkdir(parents=True, exist_ok=True)
    tfvars_prod = working_dir / "prod.tfvars"
    tfvars_prod.write_text('region = "us-east-1"\ndb_password = "supersecret"\n', encoding="utf-8")
    tfvars_stage = working_dir / "staging.tfvars"
    tfvars_stage.write_text('region = "us-west-1"\ninstance_count = 2\n', encoding="utf-8")

    # Create workspaces (skip terraform CLI to avoid binary dependency)
    prod_resp = client.post(
        "/workspaces",
        json={
            "project_id": project["id"],
            "name": "prod",
            "working_directory": "envs",
            "skip_terraform": True,
        },
        headers=auth_headers(token),
    )
    assert prod_resp.status_code == 200
    prod_ws = prod_resp.json()

    stage_resp = client.post(
        "/workspaces",
        json={
            "project_id": project["id"],
            "name": "staging",
            "working_directory": "envs",
            "skip_terraform": True,
        },
        headers=auth_headers(token),
    )
    assert stage_resp.status_code == 200
    stage_ws = stage_resp.json()

    # Import tfvars into each workspace
    prod_import = client.post(
        f"/workspaces/{prod_ws['id']}/variables/import",
        json={
            "project_id": project["id"],
            "file": "envs/prod.tfvars",
        },
        headers=auth_headers(token),
    )
    assert prod_import.status_code == 200
    assert prod_import.json()["imported"] == 2

    stage_import = client.post(
        f"/workspaces/{stage_ws['id']}/variables/import",
        json={
            "project_id": project["id"],
            "file": "envs/staging.tfvars",
        },
        headers=auth_headers(token),
    )
    assert stage_import.status_code == 200
    assert stage_import.json()["imported"] == 2

    # Compare variables between the two workspaces
    compare_resp = client.post(
        "/workspaces/compare",
        json={
            "project_id": project["id"],
            "workspace_a_id": prod_ws["id"],
            "workspace_b_id": stage_ws["id"],
            "comparison_types": ["variables"],
        },
        headers=auth_headers(token),
    )
    assert compare_resp.status_code == 200
    payload = compare_resp.json()
    variables_result = payload["variables"]
    assert variables_result["differences_count"] >= 1
    difference_items = {diff["item"] for diff in variables_result["differences"]}
    assert "region" in difference_items
    assert "db_password" in difference_items
