#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Dict

from backend.db.session import DEFAULT_DB_PATH
from backend.storage import (
    get_report,
    list_project_runs,
    list_projects,
    update_project_run,
)


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


def _extract_report_id(summary: Any) -> str | None:
    if not isinstance(summary, dict):
        return None
    for key in ("report_id", "saved_report_id", "saved_report"):
        value = summary.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return None


def backfill_report_links(db_path: Path, *, dry_run: bool = False) -> Dict[str, int]:
    stats = {
        "projects": 0,
        "runs_scanned": 0,
        "candidates_found": 0,
        "missing_reports": 0,
        "updated": 0,
    }
    projects = list_projects(include_metadata=False, include_stats=False, db_path=db_path)
    for project in projects:
        runs = _iterate_project_runs(project["id"], db_path)
        if not runs:
            continue
        stats["projects"] += 1
        for run in runs:
            stats["runs_scanned"] += 1
            if run.get("report_id"):
                continue
            candidate = _extract_report_id(run.get("summary"))
            if not candidate:
                continue
            stats["candidates_found"] += 1
            report = get_report(candidate, db_path=db_path)
            if not report:
                stats["missing_reports"] += 1
                continue
            if dry_run:
                continue
            updated = update_project_run(
                run["id"],
                project_id=project["id"],
                report_id=candidate,
                db_path=db_path,
            )
            if updated:
                stats["updated"] += 1
    return stats


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Link existing project runs to saved reports using stored summary metadata."
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=DEFAULT_DB_PATH,
        help="Path to SQLite database (default: %(default)s)",
    )
    parser.add_argument("--dry-run", action="store_true", help="Scan without applying updates.")
    args = parser.parse_args()

    db_path = args.db_path.expanduser().resolve()
    stats = backfill_report_links(db_path, dry_run=args.dry_run)
    summary = {
        "db_path": str(db_path),
        "dry_run": args.dry_run,
        **stats,
    }
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
