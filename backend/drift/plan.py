from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

from backend.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _load_plan(path: Path) -> Dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError as exc:
        raise FileNotFoundError(f"plan file not found: {path}") from exc
    except json.JSONDecodeError as exc:
        raise ValueError(f"invalid plan JSON: {exc}") from exc


def parse_plan_summary(plan_path: Path) -> Dict[str, Any]:
    try:
        data = _load_plan(plan_path)
    except (FileNotFoundError, ValueError) as exc:
        return {"error": str(exc), "source": str(plan_path)}

    resource_changes: List[Dict[str, Any]] = []
    counts = {"create": 0, "update": 0, "delete": 0, "replace": 0, "no-op": 0}

    for change in data.get("resource_changes", []):
        change_block = change.get("change", {}) or {}
        actions = change_block.get("actions", [])
        action_label = "no-op"
        if "create" in actions and "delete" in actions:
            counts["replace"] += 1
            action_label = "replace"
        elif "create" in actions:
            counts["create"] += 1
            action_label = "create"
        elif "delete" in actions:
            counts["delete"] += 1
            action_label = "delete"
        elif "update" in actions:
            counts["update"] += 1
            action_label = "update"
        else:
            counts["no-op"] += 1

        resource_changes.append(
            {
                "address": change.get("address"),
                "module_address": change.get("module_address"),
                "mode": change.get("mode"),
                "type": change.get("type"),
                "name": change.get("name"),
                "provider": change.get("provider_name"),
                "actions": actions,
                "action": action_label,
            }
        )

    total_changes = counts["create"] + counts["update"] + counts["delete"] + counts["replace"]

    output_changes: List[Dict[str, Any]] = []
    for name, info in (data.get("output_changes") or {}).items():
        output_changes.append(
            {
                "name": name,
                "actions": info.get("actions", []),
                "before": info.get("before"),
                "after": info.get("after"),
            }
        )

    return {
        "source": str(plan_path),
        "counts": counts,
        "total_changes": total_changes,
        "has_changes": total_changes > 0,
        "resource_changes": resource_changes,
        "output_changes": output_changes,
    }
