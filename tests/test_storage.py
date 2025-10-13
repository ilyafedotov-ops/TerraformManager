from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

import pytest

from backend import storage


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    db_file = tmp_path / "app.db"
    storage.init_db(db_file)
    return db_file


@pytest.fixture()
def storage_context(tmp_path: Path) -> Dict[str, Path]:
    db_file = tmp_path / "app.db"
    storage.init_db(db_file)
    projects_root = tmp_path / "projects"
    return {"db_path": db_file, "projects_root": projects_root}


def test_config_crud(db_path: Path) -> None:
    assert storage.get_config("demo", db_path=db_path) is None

    storage.upsert_config("demo", payload="{}", db_path=db_path)
    cfg = storage.get_config("demo", db_path=db_path)
    assert cfg is not None
    assert cfg["payload"] == "{}"
    assert cfg["kind"] == "tfreview"
    assert cfg["created_at"] is not None
    assert cfg["updated_at"] is not None

    storage.upsert_config("demo", payload='{"foo": "bar"}', kind="custom", db_path=db_path)
    cfg_updated = storage.get_config("demo", db_path=db_path)
    assert cfg_updated is not None
    assert cfg_updated["payload"] == '{"foo": "bar"}'
    assert cfg_updated["kind"] == "custom"

    configs = storage.list_configs(db_path=db_path)
    assert len(configs) == 1
    assert configs[0]["size"] == len('{"foo": "bar"}')

    assert storage.delete_config("demo", db_path=db_path) is True
    assert storage.delete_config("demo", db_path=db_path) is False
    assert storage.get_config("demo", db_path=db_path) is None


def test_report_roundtrip(db_path: Path) -> None:
    summary: Dict[str, int] = {"count": 1}
    report_payload: Dict[str, object] = {"findings": [], "summary": summary}

    storage.save_report("r1", summary, report_payload, db_path=db_path)
    first = storage.get_report("r1", db_path=db_path)
    assert first is not None
    assert first["summary"] == summary
    assert first["report"] == report_payload
    created_at = first["created_at"]

    storage.save_report("r1", {"count": 2}, {"findings": [1], "summary": {"count": 2}}, db_path=db_path)
    second = storage.get_report("r1", db_path=db_path)
    assert second is not None
    assert second["summary"]["count"] == 2
    assert second["report"]["findings"] == [1]
    assert second["created_at"] == created_at

    reports = storage.list_reports(db_path=db_path)
    assert len(reports) == 1
    assert reports[0]["summary"]["count"] == 2

    assert storage.delete_report("missing", db_path=db_path) is False
    assert storage.delete_report("r1", db_path=db_path) is True
    assert storage.get_report("r1", db_path=db_path) is None


def test_settings_helpers(db_path: Path) -> None:
    assert storage.get_setting("llm", db_path=db_path) is None

    storage.upsert_setting("llm", {"provider": "openai"}, db_path=db_path)
    raw = storage.get_setting("llm", db_path=db_path)
    assert raw is not None
    assert '"provider": "openai"' in raw

    settings = storage.get_llm_settings(db_path=db_path)
    assert settings["provider"] == "openai"

    storage.upsert_setting("llm", '{"provider": "off"}', db_path=db_path)
    assert storage.get_llm_settings(db_path=db_path)["provider"] == "off"


def test_project_and_run_artifacts(storage_context: Dict[str, Path]) -> None:
    db_path = storage_context["db_path"]
    projects_root = storage_context["projects_root"]

    project = storage.create_project(
        "Demo Project",
        description="Example workspace",
        metadata={"env": "dev"},
        projects_root=projects_root,
        db_path=db_path,
    )
    assert project["name"] == "Demo Project"
    assert project["slug"]
    assert (projects_root / project["slug"]).exists()

    with pytest.raises(ValueError):
        storage.create_project(
            "Demo Project",
            projects_root=projects_root,
            db_path=db_path,
        )

    listed = storage.list_projects(db_path=db_path)
    assert listed and listed[0]["id"] == project["id"]

    fetched = storage.get_project(project_id=project["id"], db_path=db_path)
    assert fetched is not None and fetched["metadata"]["env"] == "dev"

    run = storage.create_project_run(
        project["id"],
        label="Initial generation",
        kind="generator",
        parameters={"template": "aws_s3"},
        projects_root=projects_root,
        db_path=db_path,
    )
    assert run["status"] == "queued"

    runs = storage.list_project_runs(project["id"], db_path=db_path)
    assert len(runs) == 1 and runs[0]["id"] == run["id"]

    run_detail = storage.get_project_run(run["id"], project_id=project["id"], db_path=db_path)
    assert run_detail is not None

    started_at = datetime.now(timezone.utc)
    updated = storage.update_project_run(
        run["id"],
        project_id=project["id"],
        status="in_progress",
        started_at=started_at,
        db_path=db_path,
    )
    assert updated is not None and updated["status"] == "in_progress"

    artifact_info = storage.save_run_artifact(
        project["id"],
        run["id"],
        path="outputs/main.tf",
        data=b'resource "null_resource" "example" {}',
        db_path=db_path,
        projects_root=projects_root,
    )
    assert artifact_info["path"] == "outputs/main.tf"

    entries_root = storage.list_run_artifacts(project["id"], run["id"], db_path=db_path)
    assert any(entry["path"] == "outputs" and entry["is_dir"] for entry in entries_root)

    entries_outputs = storage.list_run_artifacts(
        project["id"],
        run["id"],
        path="outputs",
        db_path=db_path,
    )
    assert entries_outputs and entries_outputs[0]["path"] == "outputs/main.tf"

    artifact_path = storage.get_run_artifact_path(
        project["id"],
        run["id"],
        path="outputs/main.tf",
        db_path=db_path,
    )
    assert artifact_path.exists()

    with pytest.raises(storage.ArtifactPathError):
        storage.save_run_artifact(
            project["id"],
            run["id"],
            path="../escape.txt",
            data=b"nope",
            db_path=db_path,
        )

    assert storage.delete_run_artifact(
        project["id"],
        run["id"],
        path="outputs/main.tf",
        db_path=db_path,
    )
    assert not storage.delete_run_artifact(
        project["id"],
        run["id"],
        path="outputs/main.tf",
        db_path=db_path,
    )

    storage.delete_project(project["id"], remove_files=True, db_path=db_path)
    assert not (projects_root / project["slug"]).exists()
