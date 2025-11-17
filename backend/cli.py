import argparse
import json
import os
import shutil
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from getpass import getpass
from pathlib import Path
from typing import Any, Dict, List, Optional, Sequence

import httpx
import yaml

from backend.llm_service import DEFAULT_OPENAI_MODEL
from backend.scanner import scan_paths
from backend.report_html import render_html_report
from backend.utils.env import load_env_file
from backend.utils.logging import get_logger, setup_logging
from backend.utils.patch import collect_patches, format_patch_bundle
from backend.utils.settings import get_llm_settings, update_llm_settings
from backend.auth import auth_settings
from backend.generators.docs import generate_docs
from backend.storage import (
    create_project,
    create_project_run,
    get_project,
    list_project_runs,
    list_projects,
    list_run_artifacts,
    save_report,
    save_run_artifact,
    update_project_run,
    get_project_workspace,
    resolve_workspace_paths,
    resolve_workspace_file,
    WorkspacePathError,
)


PRECOMMIT_TEMPLATE = """repos:
- repo: https://github.com/antonbabenko/pre-commit-terraform
  rev: v1.88.0
  hooks:
    - id: terraform_fmt
    - id: terraform_validate
    - id: terraform_docs
    - id: terraform_tflint
    - id: terraform_checkov
- repo: https://github.com/infracost/infracost
  rev: v0.10.33
  hooks:
    - id: infracost_breakdown
      args:
        - --path=.
        - --usage-file=usage.yml
      additional_dependencies:
        - pyaml
"""


def _ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _collect_fmt_targets(paths: Sequence[Path]) -> List[Path]:
    targets: set[Path] = set()
    for path in paths:
        resolved = path.resolve()
        if resolved.is_file():
            targets.add(resolved.parent)
        else:
            targets.add(resolved)
    return sorted(targets)


def _load_json_payload(value: str) -> Dict[str, Any]:
    """Load JSON from an inline string or a file path."""
    if not value:
        return {}
    candidate = Path(value)
    try:
        if candidate.exists():
            return json.loads(candidate.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"failed to parse JSON from file {value}: {exc}") from exc
    try:
        return json.loads(value)
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"failed to parse JSON payload: {exc}") from exc


def _resolve_project_reference(project_id: str | None, project_slug: str | None) -> Dict[str, Any]:
    if not project_id and not project_slug:
        raise ValueError("project_id or project_slug is required")
    project = get_project(project_id=project_id, slug=project_slug)
    if not project:
        identifier = project_id or project_slug or "<unknown>"
        raise ValueError(f"project '{identifier}' not found")
    return project


def _save_run_artifact_from_path(
    project_id: str,
    run_id: str,
    source: Path,
    relative_path: str,
) -> None:
    if not source.exists() or not source.is_file():
        return
    data = source.read_bytes()
    save_run_artifact(project_id, run_id, path=relative_path, data=data)


def _print_json(data: Any) -> None:
    print(json.dumps(data, indent=2, sort_keys=False, default=str))


def _load_cli_auth_credentials(logger):
    credentials_file = Path(os.getenv("TM_AUTH_FILE", "tm_auth.json"))
    auth_credentials = _load_cli_auth(credentials_file, logger)
    if not auth_credentials:
        logger.error(
            "CLI authentication is required. Run `python -m backend.cli auth login --email you@example.com` first."
        )
        sys.exit(1)
    refreshed = _maybe_refresh_access_token(dict(auth_credentials), logger)
    try:
        credentials_file.write_text(json.dumps(refreshed, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        logger.debug("Unable to update credential file %s", credentials_file)
    if not refreshed.get("access_token") or not refreshed.get("base_url"):
        logger.error("Credential file is missing access_token/base_url fields. Re-run the auth login command.")
        sys.exit(1)
    return refreshed


def _parse_cli_tags(value: Optional[str]) -> List[str]:
    if not value:
        return []
    return [tag.strip() for tag in value.split(",") if tag.strip()]


def _run_terraform_fmt(target_dirs: Sequence[Path], write: bool, logger) -> None:
    binary = shutil.which("terraform")
    if not binary:
        logger.warning("terraform binary not found on PATH; skipping fmt step.")
        return

    flag = [] if write else ["-check"]
    mode = "write" if write else "check"
    for directory in target_dirs:
        if not directory.exists():
            logger.warning("Skipping terraform fmt for %s (path does not exist).", directory)
            continue

        logger.info("Running terraform fmt (%s) in %s", mode, directory)
        command = [binary, "fmt", "-recursive", *flag]
        try:
            subprocess.run(command, check=True, cwd=str(directory), capture_output=False)
        except subprocess.CalledProcessError as exc:
            logger.error(
                "terraform fmt (%s) failed in %s (exit=%s)", mode, directory, exc.returncode
            )
            if exc.stdout:
                logger.error(exc.stdout.decode("utf-8", errors="ignore"))
            if exc.stderr:
                logger.error(exc.stderr.decode("utf-8", errors="ignore"))
            sys.exit(exc.returncode)


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


def _format_scope(scopes: Sequence[str]) -> str:
    return " ".join(scopes)


def _handle_auth_login(args: argparse.Namespace, logger) -> None:
    base_url = args.base_url.rstrip("/")
    email: str = args.email.strip().lower()
    scopes = args.scope.split() if args.scope else ["console:read", "console:write"]
    password: str = args.password or getpass("Password or API token: ")

    if not password:
        logger.error("Password/API token is required.")
        sys.exit(1)

    data = {
        "username": email,
        "password": password,
        "scope": _format_scope(scopes),
    }

    timeout = httpx.Timeout(30.0)
    with httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=False) as client:
        response = client.post(
            "/auth/token",
            data=data,
            headers={"Accept": "application/json"},
        )

        if response.status_code != 200:
            try:
                detail = response.json()
            except Exception:  # noqa: BLE001
                detail = response.text
            logger.error("Authentication failed with status %s: %s", response.status_code, detail)
            sys.exit(1)

        payload = response.json()
        anti_csrf_header = response.headers.get("X-Refresh-Token-CSRF")
        refresh_cookie = client.cookies.get(auth_settings.refresh_cookie_name)
        csrf_cookie = client.cookies.get("tm_refresh_csrf")

        result = {
            "base_url": base_url,
            "email": email,
            "scope": scopes,
            "access_token": payload.get("access_token"),
            "expires_in": payload.get("expires_in"),
            "refresh_token": refresh_cookie or payload.get("refresh_token"),
            "refresh_expires_in": payload.get("refresh_expires_in"),
            "anti_csrf_token": anti_csrf_header or payload.get("anti_csrf_token") or csrf_cookie,
        }

        out_path = Path(args.out)
        _ensure_parent(out_path)
        out_path.write_text(json.dumps(result, indent=2), encoding="utf-8")
        print(f"Wrote credentials to {out_path}")


def _load_cli_auth(path: Path, logger) -> dict | None:
    if not path.exists():
        logger.debug("Credential file %s not found", path)
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        logger.warning("Failed to read credential file %s: %s", path, exc)
        return None


def _maybe_refresh_access_token(auth_payload: dict, logger) -> dict:
    base_url = auth_payload.get("base_url")
    refresh_token = auth_payload.get("refresh_token")
    anti_csrf = auth_payload.get("anti_csrf_token")
    if not base_url or not refresh_token or not anti_csrf:
        return auth_payload

    timeout = httpx.Timeout(10.0)
    with httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=False) as client:
        client.cookies.set(auth_settings.refresh_cookie_name, refresh_token)
        headers = {"X-Refresh-Token-CSRF": anti_csrf, "Accept": "application/json"}
        response = client.post("/auth/refresh", headers=headers)

        if response.status_code != 200:
            logger.warning("Refresh token invalid (status %s); continuing with stored access token.", response.status_code)
            return auth_payload

        payload = response.json()
        new_refresh = client.cookies.get(auth_settings.refresh_cookie_name)
        new_csrf = response.headers.get("X-Refresh-Token-CSRF") or payload.get("anti_csrf_token")
        if new_refresh:
            auth_payload["refresh_token"] = new_refresh
        if new_csrf:
            auth_payload["anti_csrf_token"] = new_csrf
        auth_payload["access_token"] = payload.get("access_token")
        auth_payload["expires_in"] = payload.get("expires_in")
        auth_payload["refresh_expires_in"] = payload.get("refresh_expires_in")
        logger.info("Access token refreshed")
        return auth_payload


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
    fmt_group = scan.add_mutually_exclusive_group()
    fmt_group.add_argument(
        "--terraform-fmt",
        action="store_true",
        help="Run `terraform fmt -check -recursive` prior to scanning.",
    )
    fmt_group.add_argument(
        "--terraform-fmt-write",
        action="store_true",
        help="Run `terraform fmt -recursive` to rewrite files prior to scanning.",
    )
    scan.add_argument(
        "--cost",
        action="store_true",
        help="Run Infracost breakdown and attach cost summary.",
    )
    scan.add_argument(
        "--cost-usage-file",
        help="Optional Infracost usage file to include usage-based resources.",
    )
    scan.add_argument(
        "--plan-json",
        help="Path to a Terraform plan JSON file (terraform show -json) for drift analysis.",
    )
    scan.add_argument(
        "--patch-out",
        help="Optional file path to write combined diff for autofixable findings",
    )
    scan.add_argument(
        "--html-out",
        help="Optional file path to write an HTML summary report",
    )
    scan.add_argument(
        "--save-report",
        action="store_true",
        help="Persist the JSON report in the local SQLite database for project linking",
    )
    project_group = scan.add_argument_group("Project logging")
    project_ref = project_group.add_mutually_exclusive_group()
    project_ref.add_argument("--project-id", help="Log this scan under the specified project id")
    project_ref.add_argument("--project-slug", help="Log this scan under the specified project slug")
    project_group.add_argument(
        "--project-run-label",
        help="Custom label for the run entry (defaults to a timestamped label)",
    )
    project_group.add_argument(
        "--project-run-kind",
        default="review",
        help="Run kind label when logging scans (default: review)",
    )
    project_group.add_argument(
        "--project-run-metadata",
        help="Inline JSON or path to JSON merged into logged run parameters",
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

    precommit = sub.add_parser("precommit", help="Generate a sample pre-commit configuration for Terraform policies")
    precommit.add_argument(
        "--out",
        default=".pre-commit-config.yaml",
        help="Path to write the generated configuration (default: .pre-commit-config.yaml)",
    )
    precommit.add_argument(
        "--force",
        action="store_true",
        help="Overwrite the destination file if it already exists.",
    )
    docs_cmd = sub.add_parser("docs", help="Generate Terraform docs for generator templates")
    docs_cmd.add_argument(
        "--out",
        default="docs/generators",
        help="Directory to write generated documentation (default: docs/generators)",
    )
    docs_cmd.add_argument(
        "--knowledge-out",
        default="knowledge/generated",
        help="Optional knowledge directory to mirror generated docs (default: knowledge/generated)",
    )
    docs_cmd.add_argument(
        "--config",
        default=".terraform-docs.yml",
        help="Path to terraform-docs configuration file (default: .terraform-docs.yml)",
    )
    docs_cmd.add_argument(
        "--terraform-docs-bin",
        default=None,
        help="Path to terraform-docs binary (defaults to resolving from PATH).",
    )
    docs_cmd.add_argument(
        "--skip-reindex",
        action="store_true",
        help="Skip knowledge base reindex after docs generation.",
    )

    auth = sub.add_parser("auth", help="Authenticate against the FastAPI service")
    auth_sub = auth.add_subparsers(dest="auth_cmd", required=True)

    login = auth_sub.add_parser("login", help="Obtain access and refresh tokens from /auth/token")
    login.add_argument("--email", required=True, help="Account email address")
    login.add_argument("--password", help="Password or legacy API token. Prompted if omitted.")
    login.add_argument(
        "--base-url",
        default=os.getenv("TFM_API_BASE", "http://localhost:8890"),
        help="FastAPI base URL (default: http://localhost:8890)",
    )
    login.add_argument(
        "--scope",
        default="console:read console:write",
        help="Space-separated scopes to request (default: console:read console:write)",
    )
    login.add_argument(
        "--out",
        default="tm_auth.json",
        help="Where to write the resulting credential payload",
    )

    sub.add_parser("reindex", help="Build the TF-IDF knowledge index (optional)")

    project = sub.add_parser("project", help="Manage Terraform Manager projects and runs")
    project_sub = project.add_subparsers(dest="project_cmd", required=True)

    project_list = project_sub.add_parser("list", help="List known projects")
    project_list.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable summary",
    )

    project_create = project_sub.add_parser("create", help="Create a new project workspace")
    project_create.add_argument("--name", required=True, help="Project name")
    project_create.add_argument("--description", help="Optional project description")
    project_create.add_argument("--slug", help="Optional slug (auto-generated if omitted)")
    project_create.add_argument(
        "--metadata",
        help="Inline JSON object or path to JSON file for project metadata",
    )

    project_runs = project_sub.add_parser("runs", help="List runs for a project")
    project_runs.add_argument("--project-id", required=True, help="Project identifier")
    project_runs.add_argument(
        "--limit",
        type=int,
        default=50,
        help="Number of runs to return (default: 50)",
    )
    project_runs.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable summary",
    )

    project_run_create = project_sub.add_parser("run-create", help="Create a run entry for a project")
    project_run_create.add_argument("--project-id", required=True, help="Project identifier")
    project_run_create.add_argument("--label", required=True, help="Run label/description")
    project_run_create.add_argument("--kind", required=True, help="Run kind (e.g., generator, review)")
    project_run_create.add_argument(
        "--parameters",
        help="Inline JSON object or path to JSON file for run parameters",
    )

    project_artifacts = project_sub.add_parser("artifacts", help="Inspect run artifacts on disk")
    project_artifacts.add_argument("--project-id", required=True, help="Project identifier")
    project_artifacts.add_argument("--run-id", required=True, help="Run identifier")
    project_artifacts.add_argument(
        "--path",
        default="",
        help="Relative directory within the run artifacts (default: root)",
    )
    project_artifacts.add_argument(
        "--json",
        action="store_true",
        help="Output JSON instead of human-readable summary",
    )
    project_generator = project_sub.add_parser("generator", help="Invoke a registered generator via the API")
    project_generator.add_argument("--project-id", required=True, help="Project identifier")
    project_generator.add_argument("--slug", required=True, help="Generator slug (e.g., aws/s3-secure-bucket)")
    project_generator.add_argument(
        "--payload",
        required=True,
        help="Inline JSON payload or path to a JSON file describing generator inputs",
    )
    project_generator.add_argument(
        "--out",
        help="Path to write the rendered Terraform (defaults to the filename returned by the API)",
    )
    project_generator.add_argument("--asset-name", help="Override the saved library asset name")
    project_generator.add_argument("--description", help="Override the saved asset description")
    project_generator.add_argument(
        "--tags",
        help="Comma-separated asset tags to apply (e.g., 'terraform,baseline')",
    )
    project_generator.add_argument(
        "--metadata",
        help="Inline JSON object or path describing additional asset metadata",
    )
    project_generator.add_argument("--notes", help="Optional notes stored with the asset version")
    project_generator.add_argument("--run-label", help="Custom run label for the project log entry")
    project_generator.add_argument(
        "--force-save",
        action="store_true",
        help="Save the generated asset even if server-side validation fails",
    )

    args = parser.parse_args()
    auth_credentials: dict | None = None
    if args.cmd == "scan":
        credentials_file = Path(os.getenv("TM_AUTH_FILE", "tm_auth.json"))
        auth_credentials = _load_cli_auth(credentials_file, logger)
        if auth_credentials:
            auth_credentials = _maybe_refresh_access_token(dict(auth_credentials), logger)
            # Persist updated refresh token / expiry if it changed
            try:
                credentials_file.write_text(json.dumps(auth_credentials, indent=2), encoding="utf-8")
            except Exception:  # noqa: BLE001
                logger.warning("Unable to update credential file %s", credentials_file)

        project_record: Dict[str, Any] | None = None
        project_run_parameters: Dict[str, Any] | None = None
        project_run_record: Dict[str, Any] | None = None
        project_workspace: Path | None = None
        metadata_payload: Dict[str, Any] = {}
        if args.project_id or args.project_slug:
            try:
                project_record = _resolve_project_reference(args.project_id, args.project_slug)
            except ValueError as exc:
                logger.error(str(exc))
                sys.exit(1)
            try:
                project_workspace = get_project_workspace(project_record)
            except WorkspacePathError as exc:
                logger.error("Failed to resolve project workspace: %s", exc)
                sys.exit(1)
            if args.project_run_metadata:
                try:
                    metadata_payload = _load_json_payload(args.project_run_metadata)
                except ValueError as exc:
                    logger.error("Invalid JSON for --project-run-metadata: %s", exc)
                    sys.exit(1)
        try:
            if project_workspace:
                paths = resolve_workspace_paths(project_workspace, args.path)
            else:
                paths = [Path(p).expanduser().resolve() for p in args.path]
        except WorkspacePathError as exc:
            logger.error("Invalid project path: %s", exc)
            sys.exit(1)

        if project_record:
            project_run_parameters = {
                "paths": [str(p) for p in paths],
                "terraform_validate": args.terraform_validate,
                "terraform_fmt": "write"
                if args.terraform_fmt_write
                else ("check" if args.terraform_fmt else "skip"),
                "cost": args.cost,
                "plan_json": args.plan_json,
            }
            project_run_parameters.update(metadata_payload)

        if args.terraform_fmt or args.terraform_fmt_write:
            fmt_targets = _collect_fmt_targets(paths)
            _run_terraform_fmt(fmt_targets, write=args.terraform_fmt_write, logger=logger)
        logger.debug(
            "Starting scan",
            extra={
                "paths": [str(p) for p in paths],
                "terraform_validate": args.terraform_validate,
                "terraform_fmt": "write" if args.terraform_fmt_write else ("check" if args.terraform_fmt else "skip"),
            },
        )
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

        cost_usage_path: Optional[Path] = None
        if args.cost_usage_file:
            try:
                if project_workspace:
                    cost_usage_path = resolve_workspace_file(
                        project_workspace, args.cost_usage_file, label="cost usage file"
                    )
                else:
                    cost_usage_path = Path(args.cost_usage_file).expanduser().resolve()
            except WorkspacePathError as exc:
                logger.error("Invalid cost usage file: %s", exc)
                sys.exit(1)

        cost_opts = None
        if args.cost:
            cost_opts = {}
            if cost_usage_path:
                cost_opts["usage_file"] = cost_usage_path

        plan_path: Optional[Path] = None
        if args.plan_json:
            try:
                if project_workspace:
                    plan_path = resolve_workspace_file(project_workspace, args.plan_json, label="plan file")
                else:
                    plan_path = Path(args.plan_json).expanduser().resolve()
            except WorkspacePathError as exc:
                logger.error("Invalid plan file: %s", exc)
                sys.exit(1)

        run_label = None
        scan_context = {"source": "cli.scan"}
        if project_record:
            run_label = args.project_run_label or f"CLI scan {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
            try:
                project_run_record = create_project_run(
                    project_id=project_record["id"],
                    label=run_label,
                    kind=args.project_run_kind or "review",
                    parameters=project_run_parameters or {},
                    status="running",
                )
            except ValueError as exc:
                logger.error("Failed to create project run: %s", exc)
                sys.exit(1)
            scan_context.update(
                {
                    "project_id": project_record["id"],
                    "project_slug": project_record.get("slug"),
                    "run_id": project_run_record["id"],
                }
            )

        try:
            report = scan_paths(
                paths,
                use_terraform_validate=args.terraform_validate,
                llm_options=llm_options,
                cost_options=cost_opts,
                plan_path=plan_path,
                context=scan_context,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Scan failed")
            if project_record and project_run_record:
                update_project_run(
                    run_id=project_run_record["id"],
                    project_id=project_record["id"],
                    status="failed",
                    summary={"error": str(exc)},
                    finished_at=datetime.now(timezone.utc),
                )
            raise
        report_id: str | None = None
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
        generated_artifacts: List[tuple[Path, str]] = []
        generated_artifacts.append((out_path, f"reports/{out_path.name}"))

        if args.patch_out:
            patches = collect_patches(report.get("findings", []))
            if patches:
                patch_path = Path(args.patch_out)
                _ensure_parent(patch_path)
                patch_path.write_text(format_patch_bundle(patches), encoding="utf-8")
                print(f"Wrote autofix patch bundle to {args.patch_out}")
                generated_artifacts.append((patch_path, f"reports/{patch_path.name}"))
            else:
                print("No autofixable findings with diffs; no patch bundle created.")

        if args.html_out:
            html_path = Path(args.html_out)
            _ensure_parent(html_path)
            html_path.write_text(render_html_report(report), encoding="utf-8")
            print(f"Wrote HTML report to {args.html_out}")
            generated_artifacts.append((html_path, f"reports/{html_path.name}"))

        if args.save_report:
            report_id = str(uuid.uuid4())
            save_report(report_id, report.get("summary", {}), report)
            report["id"] = report_id

        if project_record and project_run_record:
            summary_payload = dict(report.get("summary", {}))
            if report_id:
                summary_payload["saved_report_id"] = report_id
            summary_payload["artifacts"] = [rel for _, rel in generated_artifacts]
            update_project_run(
                run_id=project_run_record["id"],
                project_id=project_record["id"],
                status="completed",
                summary=summary_payload,
                finished_at=datetime.now(timezone.utc),
                report_id=report_id,
            )
            for artifact_path, relative in generated_artifacts:
                _save_run_artifact_from_path(project_record["id"], project_run_record["id"], artifact_path, relative)
            print(f"Logged run {project_run_record['id']} under project {project_record['name']}")
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
        report = scan_paths(paths, use_terraform_validate=False, context={"source": "cli.baseline"})
        baseline_data = _build_baseline(report, include_waived=args.include_waived)
        out_path = Path(args.out)
        _ensure_parent(out_path)
        if args.format == "json":
            payload = json.dumps(baseline_data, indent=2)
        else:
            payload = yaml.safe_dump(baseline_data, sort_keys=False)
        out_path.write_text(payload, encoding="utf-8")
        print(f"Wrote baseline to {args.out}")
    elif args.cmd == "precommit":
        out_path = Path(args.out)
        if out_path.exists() and not args.force:
            print(f"{out_path} already exists. Use --force to overwrite.", file=sys.stderr)
            sys.exit(1)
        _ensure_parent(out_path)
        out_path.write_text(PRECOMMIT_TEMPLATE, encoding="utf-8")
        print(f"Wrote pre-commit configuration to {out_path}")
    elif args.cmd == "docs":
        out_dir = Path(args.out)
        knowledge_dir = Path(args.knowledge_out) if args.knowledge_out else None
        config_path = Path(args.config) if args.config else None
        result = generate_docs(
            output_dir=out_dir,
            knowledge_dir=knowledge_dir,
            config_path=config_path,
            binary=args.terraform_docs_bin,
            reindex=not args.skip_reindex,
        )
        if result.get("status") != "ok":
            print(f"Docs generation skipped: {result.get('reason')}", file=sys.stderr)
        else:
            generated = result.get("generated", [])
            print(f"Generated {len(generated)} documentation files in {out_dir}")
            if knowledge_dir and generated:
                print(f"Knowledge mirror updated in {knowledge_dir}")
            if not args.skip_reindex and knowledge_dir:
                print(f"Knowledge index refreshed (documents indexed: {result.get('indexed_documents')})")
    elif args.cmd == "auth" and args.auth_cmd == "login":
        _handle_auth_login(args, logger)
    elif args.cmd == "reindex":
        try:
            from backend.rag import warm_index
            count = warm_index()
            print(f"Knowledge index ready: {count} documents")
        except Exception as exc:
            print(f"Failed to build knowledge index: {exc}")
    elif args.cmd == "project":
        try:
            if args.project_cmd == "list":
                projects = list_projects()
                if args.json:
                    _print_json(projects)
                else:
                    if not projects:
                        print("No projects found.")
                    for project in projects:
                        print(
                            f"{project['id']}  {project['name']} "
                            f"(slug={project['slug']}) updated={project.get('updated_at')}"
                        )
            elif args.project_cmd == "create":
                metadata: Dict[str, Any] = {}
                if args.metadata:
                    metadata = _load_json_payload(args.metadata)
                project = create_project(
                    name=args.name,
                    description=args.description,
                    slug=args.slug,
                    metadata=metadata,
                )
                _print_json(project)
            elif args.project_cmd == "runs":
                runs_payload = list_project_runs(args.project_id, limit=args.limit)
                if args.json:
                    _print_json(runs_payload)
                else:
                    runs = runs_payload.get("items", [])
                    if not runs:
                        print("No runs found.")
                    for run in runs:
                        print(
                            f"{run['id']}  {run['label']} [{run['status']}] kind={run['kind']} "
                            f"created={run.get('created_at')}"
                        )
                    next_cursor = runs_payload.get("next_cursor")
                    if next_cursor:
                        print(f"... more available (next cursor: {next_cursor})")
            elif args.project_cmd == "run-create":
                parameters: Dict[str, Any] = {}
                if args.parameters:
                    parameters = _load_json_payload(args.parameters)
                run = create_project_run(
                    project_id=args.project_id,
                    label=args.label,
                    kind=args.kind,
                    parameters=parameters,
                )
                _print_json(run)
            elif args.project_cmd == "artifacts":
                entries = list_run_artifacts(args.project_id, args.run_id, path=args.path or None)
                if args.json:
                    _print_json(entries)
                else:
                    if not entries:
                        print("No artifacts found.")
                    for entry in entries:
                        marker = "<dir>" if entry["is_dir"] else f"{entry.get('size', 0)} bytes"
                        print(f"{entry['path'] or '.'}  {marker}  modified={entry.get('modified_at')}")
            elif args.project_cmd == "generator":
                auth_payload = _load_cli_auth_credentials(logger)
                payload = _load_json_payload(args.payload)
                asset_metadata: Dict[str, Any] = {}
                if args.metadata:
                    asset_metadata = _load_json_payload(args.metadata)
                options = {
                    "asset_name": args.asset_name,
                    "description": args.description,
                    "tags": _parse_cli_tags(args.tags),
                    "metadata": asset_metadata,
                    "notes": args.notes,
                    "run_label": args.run_label,
                    "force_save": args.force_save,
                }
                filtered_options = {key: value for key, value in options.items() if value not in (None, [], {})}
                body = {
                    "payload": payload,
                    "options": filtered_options,
                }
                timeout = httpx.Timeout(60.0)
                base_url = auth_payload["base_url"].rstrip("/")
                headers = {
                    "Authorization": f"Bearer {auth_payload['access_token']}",
                    "Accept": "application/json",
                }
                url = f"/projects/{args.project_id}/generators/{args.slug}"
                try:
                    with httpx.Client(base_url=base_url, timeout=timeout, follow_redirects=False) as client:
                        response = client.post(url, json=body, headers=headers)
                except httpx.HTTPError as exc:
                    logger.error("Generator request failed: %s", exc)
                    sys.exit(1)
                if response.status_code >= 400:
                    try:
                        detail = response.json()
                    except Exception:  # noqa: BLE001
                        detail = response.text
                    logger.error("Generator request failed (%s): %s", response.status_code, detail)
                    sys.exit(response.status_code)
                payload = response.json()
                output = payload.get("output") or {}
                if not output.get("content"):
                    logger.error("Generator response did not include output content.")
                    sys.exit(1)
                out_path = Path(args.out or output.get("filename") or f"{args.slug.split('/')[-1]}.tf")
                _ensure_parent(out_path)
                out_path.write_text(output["content"], encoding="utf-8")
                print(f"Wrote Terraform to {out_path}")
                asset = payload.get("asset") or {}
                version = payload.get("version") or {}
                run = payload.get("run") or {}
                print(f"Saved asset {asset.get('name')} (id={asset.get('id')}) version={version.get('id')}")
                if run:
                    print(f"Logged run {run.get('id')} status={run.get('status')}")
        except ValueError as exc:
            logger.error(str(exc))
            sys.exit(1)
        except Exception as exc:  # noqa: BLE001
            logger.error("Command failed: %s", exc)
            sys.exit(1)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
