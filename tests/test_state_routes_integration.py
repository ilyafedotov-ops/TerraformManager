from __future__ import annotations

import json
from pathlib import Path
from typing import Tuple

from fastapi.testclient import TestClient

from backend.db.migrations import run_terraform_management_migration
from tests.test_projects_routes import auth_headers


def _write_state_file(tmp_path: Path) -> Path:
    payload = {
        "serial": 1,
        "terraform_version": "1.8.5",
        "lineage": "api-demo",
        "resources": [
            {
                "address": "aws_s3_bucket.logs",
                "mode": "managed",
                "type": "aws_s3_bucket",
                "name": "logs",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [{"schema_version": 1, "attributes": {"bucket": "logs-bucket"}, "dependencies": []}],
            },
            {
                "module": "module.network",
                "address": "module.network.aws_vpc.default",
                "mode": "managed",
                "type": "aws_vpc",
                "name": "default",
                "provider": 'provider["registry.terraform.io/hashicorp/aws"]',
                "instances": [
                    {"index_key": 0, "schema_version": 1, "attributes": {"cidr_block": "10.0.0.0/16"}, "dependencies": []}
                ],
            },
        ],
        "outputs": {"bucket_name": {"value": "logs-bucket", "sensitive": False, "type": "string"}},
    }
    path = tmp_path / "api-state.tfstate"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_plan_file(tmp_path: Path) -> dict:
    return {
        "planned_values": {
            "root_module": {
                "resources": [
                    {"address": "aws_s3_bucket.logs"},
                    {"address": "module.network.aws_vpc.default[0]"},
                ]
            }
        },
        "resource_changes": [
            {"address": "aws_s3_bucket.logs", "change": {"actions": ["update"]}},
            {"address": "module.network.aws_vpc.default[0]", "change": {"actions": ["delete"]}},
            {"address": "aws_iam_role.state", "change": {"actions": ["create"]}},
        ],
    }


def test_state_routes_end_to_end(projects_client: Tuple[TestClient, str, Path, Path], tmp_path: Path) -> None:
    client, token, db_path, projects_root = projects_client

    # Ensure terraform management tables exist for this test DB
    run_terraform_management_migration(db_path)

    # Create project
    proj_resp = client.post(
        "/projects",
        json={"name": "State API Project", "description": "state import", "metadata": {"team": "platform"}},
        headers=auth_headers(token),
    )
    assert proj_resp.status_code == 201
    project = proj_resp.json()

    state_path = _write_state_file(tmp_path)

    # Import state
    import_resp = client.post(
        "/state/import",
        json={
            "project_id": project["id"],
            "workspace": "default",
            "backend": {"type": "local", "path": str(state_path)},
        },
        headers=auth_headers(token),
    )
    assert import_resp.status_code == 200
    state_record = import_resp.json()
    assert state_record["resource_count"] == 2
    state_id = state_record["id"]

    # List states
    list_resp = client.get(
        "/state",
        params={"project_id": project["id"]},
        headers=auth_headers(token),
    )
    assert list_resp.status_code == 200
    items = list_resp.json()["items"]
    assert any(item["id"] == state_id for item in items)

    # Resources and outputs
    resources_resp = client.get(f"/state/{state_id}/resources", headers=auth_headers(token))
    assert resources_resp.status_code == 200
    resources = resources_resp.json()["items"]
    assert len(resources) == 2
    assert any(r["address"] == "module.network.aws_vpc.default[0]" for r in resources)

    outputs_resp = client.get(f"/state/{state_id}/outputs", headers=auth_headers(token))
    assert outputs_resp.status_code == 200
    outputs = outputs_resp.json()["items"]
    assert outputs[0]["name"] == "bucket_name"

    # Drift detection against a plan payload
    plan_payload = _write_plan_file(tmp_path)
    drift_resp = client.post(
        f"/state/{state_id}/drift/plan",
        json={"plan": plan_payload, "record_result": True},
        headers=auth_headers(token),
    )
    assert drift_resp.status_code == 200
    drift = drift_resp.json()
    assert drift["resources_added"] == 1
    assert drift["resources_destroyed"] == 1

    # Mutation: remove the VPC entry
    remove_resp = client.post(
        f"/state/{state_id}/operations/remove",
        json={"addresses": ["module.network.aws_vpc.default[0]"]},
        headers=auth_headers(token),
    )
    assert remove_resp.status_code == 200
    assert remove_resp.json()["resource_count"] == 1

    # Export snapshot should reflect mutation
    export_resp = client.get(f"/state/{state_id}/export", headers=auth_headers(token))
    assert export_resp.status_code == 200
    exported = export_resp.json()
    assert exported["resources"][0]["address"] == "aws_s3_bucket.logs"
