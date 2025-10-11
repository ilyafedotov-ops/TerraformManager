import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List

import yaml

from backend.llm_service import DEFAULT_OPENAI_MODEL
from backend.scanner import scan_paths
from backend.report_html import render_html_report
from backend.utils.env import load_env_file
from backend.utils.logging import get_logger, setup_logging
from backend.utils.patch import collect_patches, format_patch_bundle
from backend.utils.settings import get_llm_settings, update_llm_settings


def _ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _build_baseline(report: Dict[str, Any], include_waived: bool = False) -> Dict[str, Any]:
    timestamp = datetime.now(timezone.utc).replace(microsecond=0).isoformat()
    reason = f"baseline generated {timestamp}"

    def _simplify(finding: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "id": finding.get("id"),
            "rule": finding.get("rule"),
            "title": finding.get("title"),
            "severity": finding.get("severity"),
            "file": finding.get("file"),
            "line": finding.get("line", 1),
        }

    active: List[Dict[str, Any]] = [_simplify(f) for f in report.get("findings", [])]
    waived: List[Dict[str, Any]] = []
    if include_waived:
        waived = [_simplify(f) for f in report.get("waived_findings", [])]

    ignore_entries = [{"id": item["id"], "reason": reason} for item in active if item.get("id")]
    if include_waived:
        ignore_entries.extend(
            {"id": item["id"], "reason": reason} for item in waived if item.get("id")
        )

    baseline = {
        "generated_at": timestamp,
        "summary": {
            "active_findings": len(active),
            "waived_included": len(waived),
        },
        "ignore": ignore_entries,
        "findings": active,
    }
    if include_waived:
        baseline["waived_findings"] = waived
    return baseline


def main() -> None:
    load_env_file()
    setup_logging(service="terraform-manager-cli")
    logger = get_logger(__name__)
    parser = argparse.ArgumentParser(prog="terraform-manager-cli")
    sub = parser.add_subparsers(dest="cmd", required=True)

    scan = sub.add_parser("scan", help="Scan .tf paths and produce JSON report")
    scan.add_argument("--path", action="append", required=True, help="Path to a .tf file or a directory (repeatable)")
    scan.add_argument("--out", default="terraform_review_report.json", help="Output JSON path")
    scan.add_argument("--terraform-validate", action="store_true", help="Attempt `terraform validate` if available")
    scan.add_argument(
        "--patch-out",
        help="Optional file path to write combined diff for autofixable findings",
    )
    scan.add_argument(
        "--html-out",
        help="Optional file path to write an HTML summary report",
    )
    scan.add_argument(
        "--llm",
        choices=("off", "openai", "azure"),
        default=None,
        help="Select the AI provider (persisted in user settings). Use 'off' to disable.",
    )
    scan.add_argument(
        "--llm-model",
        default=None,
        help=f"Override the model/deployment name (default: {DEFAULT_OPENAI_MODEL}).",
    )
    scan.add_argument(
        "--llm-explanations",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Toggle AI-authored explanations (persisted in user settings).",
    )
    scan.add_argument(
        "--llm-patches",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Toggle AI-authored patch suggestions (persisted in user settings).",
    )

    baseline = sub.add_parser("baseline", help="Generate a baseline file listing current findings for waivers")
    baseline.add_argument("--path", action="append", required=True, help="Path to a .tf file or directory (repeatable)")
    baseline.add_argument("--out", default="tfreview.baseline.yaml", help="Output file path (YAML by default)")
    baseline.add_argument(
        "--format",
        choices=("yaml", "json"),
        default="yaml",
        help="Serialization format for the baseline output",
    )
    baseline.add_argument(
        "--include-waived",
        action="store_true",
        help="Include findings already waived by existing configuration",
    )

    reindex = sub.add_parser("reindex", help="Build the TF-IDF knowledge index (optional)")

    args = parser.parse_args()
    if args.cmd == "scan":
        paths = [Path(p) for p in args.path]
        logger.debug("Starting scan", extra={"paths": [str(p) for p in paths], "terraform_validate": args.terraform_validate})
        stored_llm = get_llm_settings()
        final_llm = dict(stored_llm)
        if args.llm is not None:
            final_llm["provider"] = args.llm
        if args.llm_model:
            final_llm["model"] = args.llm_model
        if args.llm_explanations is not None:
            final_llm["enable_explanations"] = args.llm_explanations
        if args.llm_patches is not None:
            final_llm["enable_patches"] = args.llm_patches

        update_llm_settings(final_llm)

        provider = final_llm.get("provider", "off")
        llm_options = None
        if provider in {"openai", "azure"} and (
            final_llm.get("enable_explanations") or final_llm.get("enable_patches")
        ):
            llm_options = final_llm

        report = scan_paths(
            paths,
            use_terraform_validate=args.terraform_validate,
            llm_options=llm_options,
        )
        logger.info(
            "Scan completed",
            extra={
                "files_scanned": report.get("summary", {}).get("files_scanned"),
                "issues_found": report.get("summary", {}).get("issues_found"),
            },
        )
        out_path = Path(args.out)
        _ensure_parent(out_path)
        out_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(f"Wrote {args.out}")

        if args.patch_out:
            patches = collect_patches(report.get("findings", []))
            if patches:
                patch_path = Path(args.patch_out)
                _ensure_parent(patch_path)
                patch_path.write_text(format_patch_bundle(patches), encoding="utf-8")
                print(f"Wrote autofix patch bundle to {args.patch_out}")
            else:
                print("No autofixable findings with diffs; no patch bundle created.")

        if args.html_out:
            html_path = Path(args.html_out)
            _ensure_parent(html_path)
            html_path.write_text(render_html_report(report), encoding="utf-8")
            print(f"Wrote HTML report to {args.html_out}")

        thresholds = report.get("summary", {}).get("thresholds", {})
        if thresholds.get("triggered"):
            violated = ", ".join(thresholds.get("violated_ids", []))
            fail_sev = ", ".join(thresholds.get("fail_on", []))
            print(
                f"Threshold triggered (fail_on={fail_sev}). Offending findings: {violated}",
                file=sys.stderr,
            )
            sys.exit(2)
    elif args.cmd == "baseline":
        paths = [Path(p) for p in args.path]
        report = scan_paths(paths, use_terraform_validate=False)
        baseline_data = _build_baseline(report, include_waived=args.include_waived)
        out_path = Path(args.out)
        _ensure_parent(out_path)
        if args.format == "json":
            payload = json.dumps(baseline_data, indent=2)
        else:
            payload = yaml.safe_dump(baseline_data, sort_keys=False)
        out_path.write_text(payload, encoding="utf-8")
        print(f"Wrote baseline to {args.out}")
    elif args.cmd == "reindex":
        try:
            from backend.rag import warm_index
            count = warm_index()
            print(f"Knowledge index ready: {count} documents")
        except Exception as exc:
            print(f"Failed to build knowledge index: {exc}")


if __name__ == "__main__":
    main()
