from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

from backend.utils.logging import get_logger

LOGGER = get_logger(__name__)


def _collect_roots(paths: Sequence[Path]) -> List[Path]:
    roots = set()
    for path in paths:
        resolved = path.resolve()
        if resolved.is_dir():
            roots.add(resolved)
        else:
            roots.add(resolved.parent)
    return sorted(roots)


def _parse_amount(value: Any) -> Optional[float]:
    if value is None:
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _execute(
    command: List[str],
    cwd: Path,
    env: Optional[Dict[str, str]] = None,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=str(cwd),
        check=True,
        capture_output=True,
        text=True,
        env=env,
    )


def _load_infracost_output(stdout: str) -> Dict[str, Any]:
    try:
        return json.loads(stdout)
    except json.JSONDecodeError as exc:
        raise ValueError(f"Failed to parse Infracost JSON output: {exc}") from exc


def run_infracost(
    paths: Sequence[Path],
    usage_file: Optional[Path] = None,
    binary: Optional[str] = None,
    env: Optional[Dict[str, str]] = None,
) -> Dict[str, Any]:
    if not paths:
        return {"tool": "infracost", "error": "no paths provided"}

    command_errors: List[str] = []
    projects: List[Dict[str, Any]] = []
    aggregate_summary: Dict[str, Optional[float]] = {
        "total_monthly_cost": 0.0,
        "total_hourly_cost": 0.0,
        "diff_monthly_cost": 0.0,
        "diff_hourly_cost": 0.0,
    }
    currency: Optional[str] = None
    executed_commands: List[List[str]] = []

    resolved_usage_file = usage_file.resolve() if usage_file else None
    if resolved_usage_file and not resolved_usage_file.exists():
        return {
            "tool": "infracost",
            "error": f"usage file not found: {resolved_usage_file}",
        }

    binary_path = binary or shutil.which("infracost")
    if not binary_path:
        return {"tool": "infracost", "error": "infracost CLI not found on PATH"}

    roots = _collect_roots(paths)
    for root in roots:
        command = [
            binary_path,
            "breakdown",
            "--path",
            ".",
            "--format",
            "json",
            "--log-level",
            "error",
        ]
        if resolved_usage_file:
            command.extend(["--usage-file", str(resolved_usage_file)])
        executed_commands.append(command)

        LOGGER.debug("Executing Infracost", extra={"command": command, "cwd": str(root)})

        try:
            completed = _execute(command, cwd=root, env=env)
        except FileNotFoundError as exc:
            LOGGER.error("Infracost CLI not found", extra={"command": command})
            return {"tool": "infracost", "error": "infracost CLI not found", "details": str(exc)}
        except subprocess.CalledProcessError as exc:
            stderr = exc.stderr or ""
            command_errors.append(
                f"{root}: exited with {exc.returncode} – {stderr.strip() or 'no error output'}"
            )
            continue

        try:
            data = _load_infracost_output(completed.stdout)
        except ValueError as exc:
            command_errors.append(f"{root}: {exc}")
            continue

        if not currency and data.get("currency"):
            currency = data["currency"]

        summary = data.get("summary") or {}
        for key, agg_key in [
            ("totalMonthlyCost", "total_monthly_cost"),
            ("totalHourlyCost", "total_hourly_cost"),
            ("diffTotalMonthlyCost", "diff_monthly_cost"),
            ("diffTotalHourlyCost", "diff_hourly_cost"),
        ]:
            amount = _parse_amount(summary.get(key))
            if amount is not None and aggregate_summary[agg_key] is not None:
                aggregate_summary[agg_key] = (aggregate_summary[agg_key] or 0.0) + amount

        for project in data.get("projects", []):
            proj_summary = project.get("summary") or {}
            projects.append(
                {
                    "name": project.get("name"),
                    "path": project.get("metadata", {}).get("path"),
                    "monthly_cost": _parse_amount(proj_summary.get("totalMonthlyCost")),
                    "hourly_cost": _parse_amount(proj_summary.get("totalHourlyCost")),
                    "diff_monthly_cost": _parse_amount(proj_summary.get("diffTotalMonthlyCost")),
                    "diff_hourly_cost": _parse_amount(proj_summary.get("diffTotalHourlyCost")),
                }
            )

    if not projects and command_errors:
        aggregate_summary = {
            "total_monthly_cost": None,
            "total_hourly_cost": None,
            "diff_monthly_cost": None,
            "diff_hourly_cost": None,
        }

    result: Dict[str, Any] = {
        "tool": "infracost",
        "commands": executed_commands,
        "projects": projects,
        "summary": aggregate_summary,
    }
    if currency:
        result["currency"] = currency
    if command_errors:
        result["errors"] = command_errors
    return result
