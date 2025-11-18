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

    reports_payload = storage.list_reports(db_path=db_path)
    assert reports_payload["total_count"] == 1
    assert len(reports_payload["items"]) == 1
    assert reports_payload["items"][0]["summary"]["count"] == 2
    assert reports_payload["items"][0]["review_status"] == "pending"

    assert storage.delete_report("missing", db_path=db_path) is False
    assert storage.delete_report("r1", db_path=db_path) is True
    assert storage.get_report("r1", db_path=db_path) is None


def test_report_review_workflow(db_path: Path) -> None:
    storage.save_report(
        "r1",
        {"severity_counts": {"high": 2}},
        {"summary": {"severity_counts": {"high": 2}}},
        db_path=db_path,
    )

    payload = storage.update_report_review(
        "r1",
        review_status="in_review",
        review_assignee="alice@example.com",
        review_notes="Taking a look.",
        db_path=db_path,
    )
    assert payload is not None
    assert payload["review_status"] == "in_review"
    assert payload["review_assignee"] == "alice@example.com"

    comment = storage.create_report_comment(
        "r1",
        "Initial findings look good.",
        author="alice@example.com",
        db_path=db_path,
    )
    assert comment["body"] == "Initial findings look good."

    comments = storage.list_report_comments("r1", db_path=db_path)
    assert len(comments) == 1
    assert comments[0]["author"] == "alice@example.com"

    assert storage.delete_report_comment("r1", comment["id"], db_path=db_path) is True
    comments_after = storage.list_report_comments("r1", db_path=db_path)
    assert comments_after == []


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
    assert listed[0]["run_count"] == 0
    assert listed[0]["library_asset_count"] == 0
    assert listed[0]["last_activity_at"]

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

    runs_payload = storage.list_project_runs(project["id"], db_path=db_path)
    runs = runs_payload["items"]
    assert len(runs) == 1 and runs[0]["id"] == run["id"]
    assert runs_payload["total_count"] == 1

    listed_after_run = storage.list_projects(db_path=db_path)
    assert listed_after_run and listed_after_run[0]["run_count"] == 1

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

    overview = storage.get_project_overview(project["id"], db_path=db_path)
    assert overview["project"]["id"] == project["id"]
    assert overview["run_count"] == 1
    assert overview["latest_run"]["id"] == run["id"]

    storage.delete_project(project["id"], remove_files=True, db_path=db_path)
    assert not (projects_root / project["slug"]).exists()


def test_list_reports_filters_by_project_slug(storage_context: Dict[str, Path]) -> None:
    db_path = storage_context["db_path"]
    projects_root = storage_context["projects_root"]

    workspace_a = storage.create_project(
        "Workspace A",
        projects_root=projects_root,
        db_path=db_path,
    )
    workspace_b = storage.create_project(
        "Workspace B",
        projects_root=projects_root,
        db_path=db_path,
    )

    storage.save_report(
        "report-a",
        {"issues_found": 2},
        {"summary": {"issues_found": 2}},
        db_path=db_path,
    )
    storage.save_report(
        "report-b",
        {"issues_found": 1},
        {"summary": {"issues_found": 1}},
        db_path=db_path,
    )

    storage.create_project_run(
        workspace_a["id"],
        label="Run A",
        kind="review",
        report_id="report-a",
        projects_root=projects_root,
        db_path=db_path,
    )
    storage.create_project_run(
        workspace_b["id"],
        label="Run B",
        kind="review",
        report_id="report-b",
        projects_root=projects_root,
        db_path=db_path,
    )

    scoped = storage.list_reports(project_slug=workspace_a["slug"], db_path=db_path)
    assert scoped["total_count"] == 1
    assert scoped["items"][0]["id"] == "report-a"

    combined = storage.list_reports(
        project_id=workspace_a["id"],
        project_slug=workspace_a["slug"],
        db_path=db_path,
    )
    assert combined["total_count"] == 1
    assert combined["items"][0]["id"] == "report-a"

    with pytest.raises(ValueError):
        storage.list_reports(project_slug="missing-workspace", db_path=db_path)

    with pytest.raises(ValueError):
        storage.list_reports(
            project_id=workspace_a["id"],
            project_slug=workspace_b["slug"],
            db_path=db_path,
        )


def test_generated_asset_promotion_and_versioning(storage_context: Dict[str, Path]) -> None:
    db_path = storage_context["db_path"]
    projects_root = storage_context["projects_root"]

    project = storage.create_project(
        "Library Demo",
        description="Workspace with promoted assets",
        metadata={"team": "platform"},
        projects_root=projects_root,
        db_path=db_path,
    )
    run = storage.create_project_run(
        project["id"],
        label="Baseline generation",
        kind="generator",
        parameters={"template": "aws_vpc"},
        projects_root=projects_root,
        db_path=db_path,
    )

    artifact_bytes = b'resource "null_resource" "example" {\n  triggers = { version = "v1" }\n}\n'
    artifact_info = storage.save_run_artifact(
        project["id"],
        run["id"],
        path="outputs/main.tf",
        data=artifact_bytes,
        projects_root=projects_root,
        db_path=db_path,
    )
    assert artifact_info["path"] == "outputs/main.tf"

    artifact_file_path = storage.get_run_artifact_path(
        project["id"],
        run["id"],
        path=artifact_info["path"],
        db_path=db_path,
    )
    assert artifact_file_path.exists()

    registered = storage.register_generated_asset(
        project["id"],
        name="Baseline Terraform",
        asset_type="terraform",
        description="Initial configuration promoted from generator output.",
        tags=["baseline", "terraform"],
        metadata={"env": "dev"},
        run_id=run["id"],
        source_path=artifact_file_path,
        notes="First promotion from baseline run.",
        projects_root=projects_root,
        db_path=db_path,
    )
    asset_payload = registered["asset"]
    version_v1 = registered["version"]

    assert asset_payload["latest_version_id"] == version_v1["id"]
    assert asset_payload["versions"] is not None
    assert len(asset_payload["versions"]) == 1

    version_v1_path = Path(version_v1["storage_path"])
    assert version_v1_path.exists()
    assert version_v1_path.read_bytes() == artifact_bytes

    overview = storage.get_project_overview(project["id"], db_path=db_path)
    assert overview["library_asset_count"] == 1

    new_version_bytes = b'resource "null_resource" "example" {\n  triggers = { version = "v2" }\n  depends_on = []\n}\n'
    promoted_v2 = storage.add_generated_asset_version(
        asset_payload["id"],
        project_id=project["id"],
        run_id=run["id"],
        data=new_version_bytes,
        media_type="text/plain",
        notes="Updated triggers for version two.",
        projects_root=projects_root,
        db_path=db_path,
    )
    asset_with_v2 = promoted_v2["asset"]
    version_v2 = promoted_v2["version"]

    assert asset_with_v2["latest_version_id"] == version_v2["id"]
    assert asset_with_v2["versions"] is not None
    assert len(asset_with_v2["versions"]) == 2
    version_ids = {version["id"] for version in asset_with_v2["versions"]}
    assert version_ids == {version_v1["id"], version_v2["id"]}

    version_v2_path = Path(version_v2["storage_path"])
    assert version_v2_path.exists()
    assert version_v2_path.read_bytes() == new_version_bytes

    paged_assets = storage.list_generated_assets(
        project["id"],
        include_versions=True,
        db_path=db_path,
    )
    assert paged_assets["total_count"] == 1
    assert paged_assets["items"][0]["versions"] is not None
    assert len(paged_assets["items"][0]["versions"]) == 2

    diff_payload = storage.diff_generated_asset_versions(
        asset_payload["id"],
        base_version_id=version_v1["id"],
        compare_version_id=version_v2["id"],
        project_id=project["id"],
        db_path=db_path,
    )
    assert diff_payload["base"]["id"] == version_v1["id"]
    assert diff_payload["compare"]["id"] == version_v2["id"]
    assert "+  depends_on = []" in diff_payload["diff"]

    deleted_new = storage.delete_generated_asset_version(
        asset_payload["id"],
        version_v2["id"],
        project_id=project["id"],
        db_path=db_path,
    )
    assert deleted_new is True

    post_delete_assets = storage.list_generated_assets(
        project["id"],
        include_versions=True,
        db_path=db_path,
    )
    assert post_delete_assets["items"][0]["latest_version_id"] == version_v1["id"]
    assert post_delete_assets["items"][0]["versions"] is not None
    assert len(post_delete_assets["items"][0]["versions"]) == 1

    removed_asset = storage.delete_generated_asset(
        asset_payload["id"],
        project_id=project["id"],
        remove_files=True,
        projects_root=projects_root,
        db_path=db_path,
    )
    assert removed_asset is True

    list_after_removal = storage.list_generated_assets(
        project["id"],
        include_versions=True,
        db_path=db_path,
    )
    assert list_after_removal["total_count"] == 0
    asset_root = Path(project["root_path"]) / "library" / asset_payload["id"]
    assert not asset_root.exists()
