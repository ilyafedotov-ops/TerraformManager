from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Dict, List

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
