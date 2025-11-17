#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Dict, Any

from backend.storage import (
    list_projects,
    list_configs,
    list_project_configs,
    create_project_config,
    list_project_runs,
    sync_project_run_artifacts,
)
from backend.db.session import DEFAULT_DB_PATH


def _iterate_project_runs(project_id: str, db_path: Path) -> list[Dict[str, Any]]:
    runs: list[Dict[str, Any]] = []
    cursor: str | None = None
    while True:
        payload = list_project_runs(project_id, limit=100, cursor=cursor, db_path=db_path)
        items = payload.get("items") or []
        if not items:
            break
        runs.extend(items)
        cursor = payload.get("next_cursor")
        if not cursor:
            break
    return runs


def backfill_configs(db_path: Path, *, default_config: str | None = None) -> int:
    workspace_configs = list_configs(db_path=db_path)
    if not workspace_configs:
        return 0
    config_names = [cfg["name"] for cfg in workspace_configs]
    target_config = default_config or config_names[0]
    if target_config not in config_names:
        raise ValueError(f"config '{target_config}' not found; available={', '.join(config_names)}")

    created = 0
    projects = list_projects(include_metadata=False, include_stats=False, db_path=db_path)
    for project in projects:
        existing = list_project_configs(project["id"], db_path=db_path)
        if existing:
            continue
        create_project_config(
            project["id"],
            name=f"{project['name']} baseline",
            config_name=target_config,
            is_default=True,
            metadata={"source": "backfill"},
            db_path=db_path,
        )
        created += 1
    return created


def backfill_artifacts(db_path: Path, *, projects_root: Path | None = None) -> Dict[str, int]:
    projects = list_projects(include_metadata=False, include_stats=False, db_path=db_path)
    stats = {"projects": 0, "runs_indexed": 0, "files_indexed": 0, "added": 0, "updated": 0, "removed": 0}
    for project in projects:
        runs = _iterate_project_runs(project["id"], db_path)
        if not runs:
            continue
        stats["projects"] += 1
        for run in runs:
            result = sync_project_run_artifacts(
                project["id"],
                run["id"],
                projects_root=projects_root,
                prune_missing=False,
                db_path=db_path,
            )
            stats["runs_indexed"] += 1
            stats["files_indexed"] += result["files_indexed"]
            stats["added"] += result["added"]
            stats["updated"] += result["updated"]
            stats["removed"] += result["removed"]
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description="Backfill project-scoped configs and artifact metadata.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to SQLite database (default: %(default)s)")
    parser.add_argument(
        "--projects-root",
        type=Path,
        default=Path("data/projects"),
        help="Root directory containing project artifacts (default: %(default)s)",
    )
    parser.add_argument("--default-config", help="Name of the workspace config to assign when creating per-project entries.")
    parser.add_argument("--skip-configs", action="store_true", help="Skip per-project config creation.")
    parser.add_argument("--skip-artifacts", action="store_true", help="Skip artifact metadata indexing for existing runs.")
    args = parser.parse_args()

    db_path = args.db_path.expanduser().resolve()
    projects_root = args.projects_root.expanduser().resolve()

    summary: Dict[str, Any] = {"db_path": str(db_path), "projects_root": str(projects_root)}

    if not args.skip_configs:
        created = backfill_configs(db_path, default_config=args.default_config)
        summary["configs_created"] = created
    else:
        summary["configs_created"] = 0

    if not args.skip_artifacts:
        artifact_stats = backfill_artifacts(db_path, projects_root=projects_root)
        summary.update({f"artifacts_{key}": value for key, value in artifact_stats.items()})
    else:
        summary.update(
            {
                "artifacts_projects": 0,
                "artifacts_runs_indexed": 0,
                "artifacts_files_indexed": 0,
                "artifacts_added": 0,
                "artifacts_updated": 0,
                "artifacts_removed": 0,
            }
        )

    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
