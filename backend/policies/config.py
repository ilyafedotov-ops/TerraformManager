from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Dict, Any, Optional

import yaml


CONFIG_FILENAMES = ("tfreview.yaml", "tfreview.yml")


@dataclass
class Waiver:
    scope: str  # "id" or "rule"
    value: str
    reason: str | None = None


@dataclass
class Thresholds:
    fail_on: List[str] = field(default_factory=list)


@dataclass
class ReviewConfig:
    waivers: List[Waiver] = field(default_factory=list)
    thresholds: Thresholds = field(default_factory=Thresholds)
    source_file: Optional[Path] = None


SEVERITY_ORDER = ["CRITICAL", "HIGH", "MEDIUM", "LOW", "INFO"]


def load_config(paths: List[Path]) -> ReviewConfig:
    config_path = _discover_config(paths)
    if not config_path:
        return ReviewConfig()

    try:
        data = yaml.safe_load(config_path.read_text(encoding="utf-8"))
    except Exception:
        return ReviewConfig(source_file=config_path)

    data = data or {}
    waivers = _parse_waivers(data.get("ignore", []))
    thresholds = _parse_thresholds(data.get("thresholds", {}))
    return ReviewConfig(waivers=waivers, thresholds=thresholds, source_file=config_path)


def apply_config(findings: List[Dict[str, Any]], config: ReviewConfig) -> Dict[str, Any]:
    waived: List[Dict[str, Any]] = []
    active: List[Dict[str, Any]] = []

    for finding in findings:
        waiver = _match_waiver(finding, config.waivers)
        if waiver:
            waived.append(
                {
                    "id": finding["id"],
                    "rule": finding["rule"],
                    "title": finding["title"],
                    "severity": finding["severity"],
                    "file": finding["file"],
                    "line": finding.get("line", 1),
                    "reason": waiver.reason,
                }
            )
            continue
        active.append(finding)

    severity_counts: Dict[str, int] = {}
    for f in active:
        severity_counts[f["severity"]] = severity_counts.get(f["severity"], 0) + 1

    fail_on_set = {s.upper() for s in config.thresholds.fail_on}
    violated_ids = [
        f["id"] for f in active if f["severity"].upper() in fail_on_set
    ]
    thresholds_state = {
        "configured": bool(fail_on_set),
        "fail_on": sorted(list(fail_on_set), key=lambda s: SEVERITY_ORDER.index(s) if s in SEVERITY_ORDER else len(SEVERITY_ORDER)),
        "triggered": bool(violated_ids),
        "violated_ids": violated_ids,
    }

    return {
        "active": active,
        "waived": waived,
        "severity_counts": severity_counts,
        "thresholds": thresholds_state,
    }


def _discover_config(paths: List[Path]) -> Optional[Path]:
    candidates = []
    for p in paths:
        target = p if p.is_dir() else p.parent
        candidates.append(target)

    cwd = Path.cwd()
    candidates.append(cwd)

    seen = set()
    for base in candidates:
        if base in seen:
            continue
        seen.add(base)
        for name in CONFIG_FILENAMES:
            cfg = base / name
            if cfg.exists():
                return cfg
    return None


def _parse_waivers(items: Any) -> List[Waiver]:
    waivers: List[Waiver] = []
    if not items:
        return waivers

    if not isinstance(items, list):
        return waivers

    for entry in items:
        if isinstance(entry, str):
            scope, value = _waiver_scope(entry)
            waivers.append(Waiver(scope=scope, value=value))
        elif isinstance(entry, dict):
            identifier = entry.get("id") or entry.get("rule")
            if not identifier:
                continue
            scope, value = _waiver_scope(identifier)
            reason = entry.get("reason")
            waivers.append(Waiver(scope=scope, value=value, reason=reason))
    return waivers


def _waiver_scope(identifier: str) -> tuple[str, str]:
    identifier = identifier.strip()
    if "::" in identifier:
        return "id", identifier
    return "rule", identifier


def _match_waiver(finding: Dict[str, Any], waivers: List[Waiver]) -> Optional[Waiver]:
    for waiver in waivers:
        if waiver.scope == "id" and finding["id"] == waiver.value:
            return waiver
        if waiver.scope == "rule" and finding["rule"] == waiver.value:
            return waiver
    return None


def _parse_thresholds(data: Any) -> Thresholds:
    thresholds = Thresholds()
    if not isinstance(data, dict):
        return thresholds
    fail_on = data.get("fail_on")
    if isinstance(fail_on, list):
        thresholds.fail_on = [str(item).upper() for item in fail_on if isinstance(item, (str, int, float))]
    return thresholds
