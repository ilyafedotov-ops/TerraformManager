from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Dict, List

import pytest

from backend import cli


def _stub_project(root: Path) -> Dict[str, str]:
    return {
        "id": "project-123",
        "slug": "project-123",
        "root_path": str(root),
        "name": "Workspace Project",
    }


def _patch_project_dependencies(monkeypatch: pytest.MonkeyPatch, project_record: Dict[str, str]) -> None:
    monkeypatch.setattr(cli, "_resolve_project_reference", lambda _pid, _slug: project_record)
    monkeypatch.setattr(cli, "create_project_run", lambda **kwargs: {"id": "run-xyz"})
    monkeypatch.setattr(cli, "update_project_run", lambda **kwargs: None)
    monkeypatch.setattr(cli, "save_run_artifact", lambda *args, **kwargs: None)


def test_cli_scan_resolves_workspace_paths(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "projects" / "project-123"
    module_dir = project_root / "modules" / "app"
    module_dir.mkdir(parents=True, exist_ok=True)
    (module_dir / "main.tf").write_text('resource "null_resource" "example" {}', encoding="utf-8")

    project_record = _stub_project(project_root)
    _patch_project_dependencies(monkeypatch, project_record)

    captured: Dict[str, List[Path]] = {}

    def fake_scan_paths(paths, **kwargs):
        captured["paths"] = paths
        captured["context"] = kwargs.get("context")
        return {"summary": {"issues_found": 0}, "findings": []}

    monkeypatch.setattr(cli, "scan_paths", fake_scan_paths)

    report_out = tmp_path / "report.json"
    argv = [
        "backend.cli",
        "scan",
        "--path",
        "modules/app",
        "--project-id",
        project_record["id"],
        "--out",
        str(report_out),
    ]
    monkeypatch.setenv("TFM_LOG_LEVEL", "ERROR")
    monkeypatch.setattr(sys, "argv", argv)

    cli.main()

    assert captured["paths"] == [module_dir]
    assert captured["context"]["project_id"] == project_record["id"]
    data = json.loads(report_out.read_text())
    assert data["summary"]["issues_found"] == 0


def test_cli_scan_rejects_workspace_escape(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "projects" / "project-123"
    project_root.mkdir(parents=True, exist_ok=True)

    project_record = _stub_project(project_root)
    _patch_project_dependencies(monkeypatch, project_record)

    argv = [
        "backend.cli",
        "scan",
        "--path",
        "../outside",
        "--project-id",
        project_record["id"],
        "--out",
        str(tmp_path / "report.json"),
    ]
    monkeypatch.setattr(sys, "argv", argv)

    with pytest.raises(SystemExit):
        cli.main()


def test_cli_baseline_writes_inside_workspace(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "projects" / "project-abc"
    tf_dir = project_root / "stacks" / "prod"
    tf_dir.mkdir(parents=True, exist_ok=True)
    (tf_dir / "main.tf").write_text('resource "null_resource" "example" {}', encoding="utf-8")

    project_record = _stub_project(project_root)
    _patch_project_dependencies(monkeypatch, project_record)

    captured: Dict[str, List[Path]] = {}

    def fake_scan_paths(paths, **kwargs):
        captured["paths"] = paths
        return {"summary": {}, "findings": []}

    monkeypatch.setattr(cli, "scan_paths", fake_scan_paths)

    argv = [
        "backend.cli",
        "baseline",
        "--path",
        "stacks/prod",
        "--project-id",
        project_record["id"],
    ]
    monkeypatch.setattr(sys, "argv", argv)

    cli.main()

    assert captured["paths"] == [tf_dir]
    baseline_path = project_root / "configs" / "tfreview.baseline.yaml"
    assert baseline_path.exists()
    payload = baseline_path.read_text(encoding="utf-8")
    assert "generated_at" in payload


def test_cli_docs_prefers_workspace_directories(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    project_root = tmp_path / "projects" / "project-docs"
    project_record = _stub_project(project_root)
    _patch_project_dependencies(monkeypatch, project_record)

    captured: Dict[str, Any] = {}

    def fake_generate_docs(**kwargs):
        captured.update(kwargs)
        return {"status": "ok", "generated": ["docs/generators/foo.md"], "indexed_documents": 1}

    monkeypatch.setattr(cli, "generate_docs", fake_generate_docs)

    argv = [
        "backend.cli",
        "docs",
        "--project-id",
        project_record["id"],
    ]
    monkeypatch.setattr(sys, "argv", argv)

    cli.main()

    expected_docs = project_root / "docs" / "generators"
    expected_knowledge = project_root / "knowledge" / "generated"
    assert captured["output_dir"] == expected_docs
    assert captured["knowledge_dir"] == expected_knowledge
    assert expected_docs.is_dir()
    assert expected_knowledge.is_dir()


def test_cli_project_upload_updates_metadata(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source_file = tmp_path / "report.json"
    source_payload = {"summary": {"issues_found": 0}}
    source_file.write_text(json.dumps(source_payload), encoding="utf-8")

    save_params: Dict[str, Any] = {}
    update_params: Dict[str, Any] = {}

    def fake_save_run_artifact(**kwargs):
        save_params.update(kwargs)
        return {
            "name": Path(kwargs["path"]).name,
            "path": kwargs["path"],
            "artifact_id": "artifact-123",
            "size": len(kwargs["data"]),
        }

    def fake_update_project_artifact(artifact_id, project_id, **kwargs):
        update_params.update({"artifact_id": artifact_id, "project_id": project_id, **kwargs})
        metadata = kwargs.get("metadata") or {}
        relative = metadata.get("path", "reports/report.json")
        return {
            "id": artifact_id,
            "relative_path": relative,
            "size_bytes": len(source_payload),
        }

    monkeypatch.setattr(cli, "save_run_artifact", fake_save_run_artifact)
    monkeypatch.setattr(cli, "update_project_artifact", fake_update_project_artifact)

    argv = [
        "backend.cli",
        "project",
        "upload",
        "--project-id",
        "project-1",
        "--run-id",
        "run-1",
        "--file",
        str(source_file),
        "--dest",
        "reports/uploaded-report.json",
        "--no-overwrite",
        "--tags",
        "report,scan",
        "--metadata",
        '{"path": "reports/uploaded-report.json"}',
        "--media-type",
        "application/json",
    ]
    monkeypatch.setattr(sys, "argv", argv)

    cli.main()

    assert save_params["project_id"] == "project-1"
    assert save_params["run_id"] == "run-1"
    assert save_params["path"] == "reports/uploaded-report.json"
    assert save_params["overwrite"] is False
    assert update_params["artifact_id"] == "artifact-123"
    assert update_params["tags"] == ["report", "scan"]
    assert update_params["media_type"] == "application/json"
