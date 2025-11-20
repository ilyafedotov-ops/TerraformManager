from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from backend import cli
from backend import storage
from backend.db import migrations as db_migrations
from backend.db import session as db_session


def _write_state_file(base: Path) -> Path:
    payload = {
        "serial": 1,
        "terraform_version": "1.8.5",
        "lineage": "cli-demo",
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
    path = base / "cli-state.tfstate"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def _write_plan_file(base: Path) -> Path:
    payload = {
        "planned_values": {"root_module": {"resources": [{"address": "aws_s3_bucket.logs"}]}},
        "resource_changes": [{"address": "aws_s3_bucket.logs", "change": {"actions": ["update"]}}],
    }
    path = base / "cli-plan.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_cli_state_workflow(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    db_path = tmp_path / "app.db"
    projects_root = tmp_path / "projects"
    state_root = projects_root / "cli-state"
    state_root.mkdir(parents=True, exist_ok=True)

    # Reset DB session caches and defaults to a temp location
    db_session._ENGINES.clear()
    db_session._SESSIONMAKERS.clear()
    monkeypatch.setattr(db_session, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(storage, "_DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(storage, "DEFAULT_DB_PATH", db_path)
    monkeypatch.setattr(storage, "DEFAULT_PROJECTS_ROOT", projects_root)

    def _get_project_override(project_id=None, slug=None):
        return storage.get_project(project_id=project_id, slug=slug, db_path=db_path)

    monkeypatch.setattr(cli, "get_project", _get_project_override)

    # Create tables and project
    db_session.init_models(db_path)
    db_migrations.run_terraform_management_migration(db_path)
    project = storage.create_project("CLI State", projects_root=projects_root, db_path=db_path)

    state_file = _write_state_file(tmp_path)
    plan_file = _write_plan_file(tmp_path)

    # Import state
    argv_import = [
        "backend.cli",
        "state",
        "import",
        "--project-id",
        project["id"],
        "--workspace",
        "default",
        "--backend",
        "local",
        "--path",
        str(state_file),
    ]
    monkeypatch.setenv("TFM_LOG_LEVEL", "ERROR")
    monkeypatch.setattr(sys, "argv", argv_import)
    cli.main()
    capsys.readouterr()  # reset captured output

    # List states
    monkeypatch.setattr(sys, "argv", ["backend.cli", "state", "list", "--project-id", project["id"]])
    cli.main()
    list_output = capsys.readouterr().out
    items = json.loads(list_output)["items"]
    assert len(items) == 1
    state_id = items[0]["id"]

    # Drift detection
    monkeypatch.setattr(
        sys,
        "argv",
        ["backend.cli", "state", "drift", "--state-id", state_id, "--plan", str(plan_file)],
    )
    cli.main()
    drift_output = capsys.readouterr().out
    drift_summary = json.loads(drift_output)
    assert drift_summary["resources_changed"] == 1

    # Remove resource
    monkeypatch.setattr(
        sys,
        "argv",
        ["backend.cli", "state", "rm", "--state-id", state_id, "--address", "aws_s3_bucket.logs"],
    )
    cli.main()
    rm_output = capsys.readouterr().out
    updated_state = json.loads(rm_output)
    assert updated_state["resource_count"] == 1
