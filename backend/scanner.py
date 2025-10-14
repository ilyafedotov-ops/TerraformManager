from __future__ import annotations

from pathlib import Path
from typing import List, Dict, Any, Optional

from backend.llm_service import (
    FindingContext,
    LLMConfigurationError,
    LLMRequestError,
    LLMRuntimeConfig,
    load_runtime_config_from_env,
    request_explanation,
    request_patch,
)
from backend.costs import run_infracost
from backend.drift import parse_plan_summary
from backend.policies import ALL_CHECKS
from backend.policies.config import load_config, apply_config
from backend.policies.metadata import get_rule_metadata
from backend.rag import explain, get_passages_for_rule
from backend.utils.logging import get_logger
from backend.utils.diff import make_unified_diff
from backend.validators import run_terraform_validate


Finding = Dict[str, Any]
Candidate = Dict[str, Any]

LOGGER = get_logger(__name__)


def _init_llm_state(config: LLMRuntimeConfig) -> Dict[str, Any]:
    return {
        "provider": config.provider,
        "model": config.model,
        "explanations_enabled": bool(config.enable_explanations),
        "patches_enabled": bool(config.enable_patches),
        "explanations_requested": 0,
        "explanations_completed": 0,
        "patches_requested": 0,
        "patches_completed": 0,
        "errors": [],
        "disabled": False,
    }


def _record_llm_error(state: Dict[str, Any], message: str) -> None:
    errors = state.setdefault("errors", [])
    if message not in errors:
        errors.append(message)
        LOGGER.warning("LLM auxiliary output skipped", extra={"error": message})


def scan_paths(
    paths: List[Path],
    use_terraform_validate: bool = False,
    llm_options: Optional[Dict[str, Any]] = None,
    cost_options: Optional[Dict[str, Any]] = None,
    plan_path: Optional[Path] = None,
) -> Dict[str, Any]:
    LOGGER.debug(
        "scan_paths invoked",
        extra={
            "paths": [str(p) for p in paths],
            "use_terraform_validate": use_terraform_validate,
            "llm_enabled": bool(llm_options),
            "cost_enabled": cost_options is not None,
            "plan_path": str(plan_path) if plan_path else None,
        },
    )
    review_config = load_config(paths)
    candidates: List[Candidate] = []
    files_seen = 0
    llm_config: Optional[LLMRuntimeConfig] = None
    llm_state: Dict[str, Any] = {}

    if llm_options:
        llm_config = load_runtime_config_from_env(llm_options)
        llm_state = _init_llm_state(llm_config)

    for path in paths:
        if path.is_dir():
            for tf in path.rglob("*.tf"):
                files_seen += 1
                candidates.extend(_scan_file(tf))
        elif path.suffix == ".tf" and path.exists():
            files_seen += 1
            candidates.extend(_scan_file(path))

    if use_terraform_validate:
        candidates.extend(run_terraform_validate(paths))

    findings = [
        _render_candidate(candidate, llm_config=llm_config, llm_state=llm_state)
        for candidate in candidates
    ]
    config_application = apply_config(findings, review_config)

    active_findings = config_application["active"]
    waived_findings = config_application["waived"]
    severity_counts = config_application["severity_counts"]
    thresholds_state = config_application["thresholds"]

    summary: Dict[str, Any] = {
        "files_scanned": files_seen,
        "issues_found": len(active_findings),
    }
    if waived_findings:
        summary["waived"] = len(waived_findings)
    if severity_counts:
        summary["severity_counts"] = severity_counts
    if thresholds_state.get("configured"):
        summary["thresholds"] = thresholds_state

    report: Dict[str, Any] = {
        "summary": summary,
        "findings": active_findings,
    }
    if waived_findings:
        report["waived_findings"] = waived_findings
    if review_config.source_file:
        report["config"] = str(review_config.source_file)
    if llm_state:
        llm_summary = dict(llm_state)
        if not llm_summary.get("errors"):
            llm_summary.pop("errors", None)
        if not llm_summary.get("disabled"):
            llm_summary.pop("disabled", None)
        report["llm"] = llm_summary
    elif llm_options:
        report["llm"] = {
            "provider": llm_options.get("provider", "off"),
            "model": llm_options.get("model"),
            "explanations_enabled": bool(llm_options.get("enable_explanations")),
            "patches_enabled": bool(llm_options.get("enable_patches")),
        }

    if cost_options is not None:
        usage = cost_options.get("usage_file")
        usage_path = Path(usage).resolve() if usage else None
        cost_result = run_infracost(paths, usage_file=usage_path)
        report["cost"] = cost_result
        if cost_result and not cost_result.get("error"):
            cost_summary = cost_result.get("summary") or {}
            summary["cost"] = {
                "currency": cost_result.get("currency"),
                "total_monthly_cost": cost_summary.get("total_monthly_cost"),
                "total_hourly_cost": cost_summary.get("total_hourly_cost"),
                "diff_monthly_cost": cost_summary.get("diff_monthly_cost"),
                "diff_hourly_cost": cost_summary.get("diff_hourly_cost"),
            }

    if plan_path:
        drift_result = parse_plan_summary(plan_path)
        report["drift"] = drift_result
        if drift_result and not drift_result.get("error"):
            summary["drift"] = {
                "has_changes": drift_result.get("has_changes", False),
                "total_changes": drift_result.get("total_changes", 0),
                "counts": drift_result.get("counts", {}),
            }

    LOGGER.info(
        "scan_paths completed",
        extra={
            "files_scanned": files_seen,
            "active_findings": len(active_findings),
            "llm": report.get("llm"),
            "cost_summary": summary.get("cost"),
            "drift": summary.get("drift"),
        },
    )
    return report


def _scan_file(path: Path) -> List[Candidate]:
    text = _read_file_text(path)
    file_candidates: List[Candidate] = []
    for check in ALL_CHECKS:
        try:
            file_candidates.extend(check(path, text))
        except Exception:
            continue
    return file_candidates


def _render_candidate(
    candidate: Candidate,
    llm_config: Optional[LLMRuntimeConfig] = None,
    llm_state: Optional[Dict[str, Any]] = None,
) -> Finding:
    rule_id = candidate.get("rule_id", "UNKNOWN")
    file_path = candidate.get("file", "")
    meta = get_rule_metadata(rule_id)
    context = candidate.get("context", {})
    overrides = candidate.get("overrides", {})
    rendered = meta.render(context, overrides)

    unique_id = candidate.get("unique_id")
    if not unique_id:
        resource = context.get("resource")
        stem = Path(file_path).stem if file_path else "resource"
        unique_id = f"{rule_id}::{resource or stem}"

    snippet = candidate.get("snippet", "")
    suggested = candidate.get("suggested_fix_snippet", "")
    unified_diff = ""
    if snippet and suggested and file_path:
        path_obj = Path(file_path)
        if path_obj.exists():
            before = _read_file_text(path_obj)
            if snippet in before and suggested:
                after = before.replace(snippet, suggested, 1)
                if before != after:
                    unified_diff = make_unified_diff(before, after, path_obj.name)

    finding: Finding = {
        "id": unique_id,
        "rule": rendered["rule"],
        "title": rendered["title"],
        "severity": rendered["severity"],
        "description": rendered["description"],
        "recommendation": rendered["recommendation"],
        "file": file_path,
        "line": candidate.get("line", 1),
        "snippet": snippet,
        "suggested_fix_snippet": suggested,
        "knowledge_ref": rendered.get("knowledge_ref"),
        "context": context,
        "explanation": explain(rule_id)[:1200],
        "unified_diff": unified_diff,
    }
    if llm_config and llm_state is not None:
        _maybe_augment_with_llm(finding, rule_id, llm_config, llm_state)
    return finding


def _maybe_augment_with_llm(
    finding: Finding,
    rule_id: str,
    llm_config: LLMRuntimeConfig,
    llm_state: Dict[str, Any],
) -> None:
    if llm_state.get("disabled"):
        return

    need_explanation = llm_config.enable_explanations
    need_patch = llm_config.enable_patches and bool(finding.get("snippet"))
    if not need_explanation and not need_patch:
        return

    passages = get_passages_for_rule(rule_id, top_k=3)
    context = FindingContext(
        rule_id=rule_id,
        title=finding["title"],
        severity=finding["severity"],
        description=finding["description"],
        recommendation=finding["recommendation"],
        file_path=finding.get("file"),
        snippet=finding.get("snippet", ""),
        project_name=None,
    )

    if need_explanation:
        llm_state["explanations_requested"] += 1
        try:
            explanation_ai = request_explanation(context, passages, config=llm_config)
            if explanation_ai:
                llm_state["explanations_completed"] += 1
                finding["explanation_ai"] = explanation_ai
        except LLMConfigurationError as exc:
            _record_llm_error(llm_state, str(exc))
            llm_state["disabled"] = True
            llm_config.enable_explanations = False
            llm_config.enable_patches = False
            llm_state["explanations_enabled"] = False
            llm_state["patches_enabled"] = False
            return
        except LLMRequestError as exc:
            _record_llm_error(llm_state, str(exc))

    if need_patch and not llm_state.get("disabled"):
        llm_state["patches_requested"] += 1
        fix_goal = finding.get("recommendation") or ""
        try:
            patch_ai = request_patch(context, fix_goal, passages, config=llm_config)
            if patch_ai:
                llm_state["patches_completed"] += 1
                finding["patch_ai"] = patch_ai
        except LLMConfigurationError as exc:
            _record_llm_error(llm_state, str(exc))
            llm_state["disabled"] = True
            llm_config.enable_explanations = False
            llm_config.enable_patches = False
            llm_state["explanations_enabled"] = False
            llm_state["patches_enabled"] = False
        except LLMRequestError as exc:
            _record_llm_error(llm_state, str(exc))


def _read_file_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8", errors="ignore")
    except Exception:
        return ""
