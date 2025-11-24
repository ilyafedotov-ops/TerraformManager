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
from pydantic import TypeAdapter
from sqlalchemy.orm import Session

from backend.llm_service import DEFAULT_OPENAI_MODEL
from backend.db.session import DEFAULT_DB_PATH, session_scope
from backend.db.migrations import ensure_user_profile_columns
from backend.scanner import scan_paths
from backend.report_html import render_html_report
from backend.utils.env import load_env_file
from backend.utils.logging import get_logger, setup_logging
from backend.utils.patch import collect_patches, format_patch_bundle
from backend.utils.settings import get_llm_settings, update_llm_settings
from backend.auth import auth_settings
from backend.generators.docs import generate_docs
from backend.state import (
    StateBackendConfig,
    detect_drift_from_plan,
    export_state_snapshot,
    get_state_detail,
    import_state,
    list_outputs_for_state,
    list_project_states,
    list_resources_for_state,
    move_state_resource,
    remove_state_resources,
)
from backend.state.backends import StateBackendError
from backend.state.storage import StateMutationError, StateNotFoundError
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
    update_project_artifact,
    get_project_workspace,
    resolve_workspace_paths,
    resolve_workspace_file,
    ArtifactPathError,
    WorkspacePathError,
)
from backend.workspaces.errors import TerraformWorkspaceError, WorkspaceConflictError, WorkspaceNotFoundError
from backend.workspaces.manager import WorkspaceManager
from backend.workspaces.scanner import MultiWorkspaceScanner
from backend.workspaces.comparator import compare_variables_map, load_workspace_variables, record_workspace_comparison
from backend.workspaces.services import (
    create_workspace_with_cli,
    delete_workspace_with_cli,
    discover_and_sync_workspaces,
    resolve_working_directory as resolve_tf_working_directory,
    select_workspace_with_cli,
)
from backend.workspaces.storage import (
    delete_workspace_variable,
    get_workspace_by_id,
    get_workspace_by_name,
    list_workspace_records,
    list_workspace_variables,
    upsert_workspace_variable,
)
from backend.workspaces.variables import import_tfvars_file


BASELINE_DEFAULT_OUT = "tfreview.baseline.yaml"
DOCS_DEFAULT_OUT = "docs/generators"
DOCS_DEFAULT_KNOWLEDGE_OUT = "knowledge/generated"


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


def _build_backend_config_from_args(args: argparse.Namespace) -> StateBackendConfig:
    """Construct a backend config payload from parsed CLI arguments."""

    backend = (args.backend or "").strip()
    payload: Dict[str, Any] = {"type": backend}

    if backend == "local":
        if not args.path:
            raise ValueError("--path is required for local backend imports")
        payload["path"] = args.path
    elif backend == "s3":
        if not args.bucket or not args.key:
            raise ValueError("--bucket and --key are required for s3 backend imports")
        payload.update({"bucket": args.bucket, "key": args.key})
        if args.region:
            payload["region"] = args.region
        if args.profile:
            payload["profile"] = args.profile
        if args.endpoint_url:
            payload["endpoint_url"] = args.endpoint_url
        if args.session_token:
            payload["session_token"] = args.session_token
    elif backend == "azurerm":
        if not args.storage_account or not args.container or not args.key:
            raise ValueError("--storage-account, --container, and --key are required for azurerm backend imports")
        payload.update(
            {
                "storage_account": args.storage_account,
                "container": args.container,
                "key": args.key,
            }
        )
        if args.sas_token:
            payload["sas_token"] = args.sas_token
        if args.connection_string:
            payload["connection_string"] = args.connection_string
    elif backend == "gcs":
        if not args.bucket or not args.prefix:
            raise ValueError("--bucket and --prefix are required for gcs backend imports")
        payload.update({"bucket": args.bucket, "prefix": args.prefix})
        if args.credentials_file:
            payload["credentials_file"] = args.credentials_file
        if args.project:
            payload["project"] = args.project
    elif backend == "remote":
        if not args.organization or not args.remote_workspace:
            raise ValueError("--organization and --remote-workspace are required for remote backend imports")
        payload.update(
            {
                "organization": args.organization,
                "workspace": args.remote_workspace,
            }
        )
        if args.hostname:
            payload["hostname"] = args.hostname
        if args.token:
            payload["token"] = args.token
    else:
        raise ValueError(f"Unsupported backend type '{backend}'")

    return TypeAdapter(StateBackendConfig).validate_python(payload)


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


def _resolve_workspace_destination(
    project_root: Path,
    path_token: str,
    *,
    label: str,
    expect_dir: bool = False,
) -> Path:
    root = project_root.expanduser().resolve()
    token_path = Path(path_token)
    if token_path.is_absolute():
        resolved = token_path.expanduser().resolve()
    else:
        resolved = (root / token_path).resolve()

    try:
        resolved.relative_to(root)
    except ValueError as exc:  # noqa: BLE001
        raise WorkspacePathError(f"{label} must stay inside the project workspace") from exc

    if expect_dir:
        resolved.mkdir(parents=True, exist_ok=True)
    else:
        resolved.parent.mkdir(parents=True, exist_ok=True)
    return resolved


def _resolve_tf_workspace(
    session: Session,
    *,
    project_id: str,
    working_directory: str | None,
    workspace_id: str | None,
    workspace_name: str | None,
) -> Any:
    """Look up a Terraform workspace record by id or by name within a working directory."""
    if workspace_id:
        return get_workspace_by_id(session, workspace_id)
    if not workspace_name:
        raise ValueError("workspace name or id is required")
    if not working_directory:
        raise ValueError("--working-dir is required when selecting by name")
    return get_workspace_by_name(
        session,
        project_id=project_id,
        working_directory=working_directory,
        name=workspace_name,
    )


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
    baseline.add_argument(
        "--out",
        default=None,
        help="Output file path (default: tfreview.baseline.yaml)",
    )
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
    baseline_project = baseline.add_argument_group("Project integration")
    baseline_project_ref = baseline_project.add_mutually_exclusive_group()
    baseline_project_ref.add_argument("--project-id", help="Resolve paths inside the specified project workspace")
    baseline_project_ref.add_argument("--project-slug", help="Resolve paths inside the specified project workspace")

    workspace = sub.add_parser("workspace", help="Manage Terraform workspaces")
    workspace_sub = workspace.add_subparsers(dest="workspace_cmd", required=True)

    ws_discover = workspace_sub.add_parser("discover", help="Discover Terraform workspaces in a project")
    ws_discover_ref = ws_discover.add_mutually_exclusive_group(required=True)
    ws_discover_ref.add_argument("--project-id", help="Project ID")
    ws_discover_ref.add_argument("--project-slug", help="Project slug")
    ws_discover.add_argument("--working-dir", default=".", help="Relative working directory to search (default: .)")
    ws_discover.add_argument("--json", action="store_true", help="Output JSON (default: human-readable)")

    ws_list = workspace_sub.add_parser("list", help="List Terraform workspaces stored for a project")
    ws_list_ref = ws_list.add_mutually_exclusive_group(required=True)
    ws_list_ref.add_argument("--project-id", help="Project ID")
    ws_list_ref.add_argument("--project-slug", help="Project slug")
    ws_list.add_argument("--working-dir", default=None, help="Relative working directory filter")
    ws_list.add_argument("--json", action="store_true", help="Output JSON (default: human-readable)")

    ws_create = workspace_sub.add_parser("create", help="Create a Terraform workspace via CLI and persist it")
    ws_create_ref = ws_create.add_mutually_exclusive_group(required=True)
    ws_create_ref.add_argument("--project-id", help="Project ID")
    ws_create_ref.add_argument("--project-slug", help="Project slug")
    ws_create.add_argument("--name", required=True, help="Workspace name")
    ws_create.add_argument("--working-dir", required=True, help="Relative working directory containing Terraform code")
    ws_create.add_argument("--activate", action="store_true", help="Mark the workspace active after creation")
    ws_create.add_argument(
        "--skip-terraform",
        action="store_true",
        help="Skip running terraform workspace new (DB only)",
    )

    ws_select = workspace_sub.add_parser("select", help="Select/activate a workspace via Terraform CLI")
    ws_select_ref = ws_select.add_mutually_exclusive_group(required=True)
    ws_select_ref.add_argument("--project-id", help="Project ID")
    ws_select_ref.add_argument("--project-slug", help="Project slug")
    ws_select.add_argument("--workspace-id", help="Workspace record ID")
    ws_select.add_argument("--name", help="Workspace name (requires --working-dir)")
    ws_select.add_argument("--working-dir", help="Relative working directory when using --name")

    ws_delete = workspace_sub.add_parser("delete", help="Delete a workspace from Terraform and the DB")
    ws_delete_ref = ws_delete.add_mutually_exclusive_group(required=True)
    ws_delete_ref.add_argument("--project-id", help="Project ID")
    ws_delete_ref.add_argument("--project-slug", help="Project slug")
    ws_delete.add_argument("--workspace-id", help="Workspace record ID")
    ws_delete.add_argument("--name", help="Workspace name (requires --working-dir)")
    ws_delete.add_argument("--working-dir", help="Relative working directory when using --name")
    ws_delete.add_argument(
        "--skip-terraform",
        action="store_true",
        help="Skip terraform workspace delete (DB only)",
    )

    ws_scan = workspace_sub.add_parser("scan", help="Scan Terraform code across one or more workspaces")
    ws_scan_ref = ws_scan.add_mutually_exclusive_group(required=True)
    ws_scan_ref.add_argument("--project-id", help="Project ID")
    ws_scan_ref.add_argument("--project-slug", help="Project slug")
    ws_scan.add_argument("--working-dir", required=True, help="Relative working directory to scan")
    ws_scan.add_argument(
        "--workspaces",
        help="Comma-separated list of workspace names to scan (default: all stored)",
    )
    ws_scan.add_argument(
        "--terraform-validate",
        action="store_true",
        help="Run terraform validate during scan",
    )
    ws_scan.add_argument("--json", action="store_true", help="Output JSON (default: human-readable summary)")

    ws_compare = workspace_sub.add_parser("compare", help="Compare workspace variables and record a comparison")
    ws_compare_ref = ws_compare.add_mutually_exclusive_group(required=True)
    ws_compare_ref.add_argument("--project-id", help="Project ID")
    ws_compare_ref.add_argument("--project-slug", help="Project slug")
    ws_compare.add_argument("--workspace-a-id", help="Workspace A record ID")
    ws_compare.add_argument("--workspace-b-id", help="Workspace B record ID")
    ws_compare.add_argument("--workspace-a-name", help="Workspace A name (requires --working-dir)")
    ws_compare.add_argument("--workspace-b-name", help="Workspace B name (requires --working-dir)")
    ws_compare.add_argument("--working-dir", help="Relative working directory when using names")

    ws_vars = workspace_sub.add_parser("vars", help="Manage workspace variables")
    ws_vars_ref = ws_vars.add_mutually_exclusive_group(required=True)
    ws_vars_ref.add_argument("--project-id", help="Project ID")
    ws_vars_ref.add_argument("--project-slug", help="Project slug")
    ws_vars_sub = ws_vars.add_subparsers(dest="workspace_vars_cmd", required=True)

    ws_vars_list = ws_vars_sub.add_parser("list", help="List variables for a workspace")
    ws_vars_list.add_argument("--workspace-id", help="Workspace record ID")
    ws_vars_list.add_argument("--name", help="Workspace name (requires --working-dir)")
    ws_vars_list.add_argument("--working-dir", help="Relative working directory when using --name")

    ws_vars_set = ws_vars_sub.add_parser("set", help="Set or update a workspace variable")
    ws_vars_set.add_argument("--workspace-id", help="Workspace record ID")
    ws_vars_set.add_argument("--name", help="Workspace name (requires --working-dir)")
    ws_vars_set.add_argument("--working-dir", help="Relative working directory when using --name")
    ws_vars_set.add_argument("--key", required=True, help="Variable key")
    ws_vars_set.add_argument("--value", required=True, help="Variable value")
    ws_vars_set.add_argument("--sensitive", action="store_true", help="Mark the variable as sensitive")
    ws_vars_set.add_argument("--source", help="Variable source label (tfvars/env/manual)")
    ws_vars_set.add_argument("--description", help="Variable description")

    ws_vars_unset = ws_vars_sub.add_parser("unset", help="Delete a workspace variable")
    ws_vars_unset.add_argument("--workspace-id", help="Workspace record ID")
    ws_vars_unset.add_argument("--name", help="Workspace name (requires --working-dir)")
    ws_vars_unset.add_argument("--working-dir", help="Relative working directory when using --name")
    ws_vars_unset.add_argument("--key", required=True, help="Variable key to delete")

    ws_vars_import = ws_vars_sub.add_parser("import", help="Import variables from a tfvars file into a workspace")
    ws_vars_import.add_argument("--workspace-id", help="Workspace record ID")
    ws_vars_import.add_argument("--name", help="Workspace name (requires --working-dir)")
    ws_vars_import.add_argument("--working-dir", help="Relative working directory when using --name")
    ws_vars_import.add_argument("--file", required=True, help="Path to tfvars file (project-relative)")
    ws_vars_import.add_argument(
        "--sensitive-key",
        action="append",
        dest="sensitive_keys",
        help="Treat specific keys as sensitive in addition to automatic detection (repeatable)",
    )

    state_parser = sub.add_parser("state", help="Manage stored Terraform state snapshots")
    state_sub = state_parser.add_subparsers(dest="state_cmd", required=True)

    state_import = state_sub.add_parser("import", help="Import a Terraform state file into the local database")
    state_project_ref = state_import.add_mutually_exclusive_group(required=True)
    state_project_ref.add_argument("--project-id", help="Target project ID")
    state_project_ref.add_argument("--project-slug", help="Target project slug")
    state_import.add_argument("--workspace", default="default", help="Workspace name (default: default)")
    state_import.add_argument(
        "--backend",
        required=True,
        choices=("local", "s3", "azurerm", "gcs", "remote"),
        help="State backend type to import from",
    )
    # Local backend
    state_import.add_argument("--path", help="Path to terraform.tfstate for local backend")
    # S3 backend options
    state_import.add_argument("--bucket", help="S3 bucket containing the state file")
    state_import.add_argument("--key", help="Object key inside the S3 bucket")
    state_import.add_argument("--region", help="AWS region for the state bucket")
    state_import.add_argument("--profile", help="AWS named profile")
    state_import.add_argument("--endpoint-url", dest="endpoint_url", help="Custom S3-compatible endpoint")
    state_import.add_argument("--session-token", dest="session_token", help="AWS session token")
    # Azure backend options
    state_import.add_argument("--storage-account", help="Azure Storage account name")
    state_import.add_argument("--container", help="Azure Blob container name")
    state_import.add_argument("--sas-token", dest="sas_token", help="SAS token for the blob")
    state_import.add_argument("--connection-string", dest="connection_string", help="Azure Storage connection string")
    # GCS backend options
    state_import.add_argument("--prefix", help="GCS object prefix/key")
    state_import.add_argument("--credentials-file", help="Service account JSON for GCS")
    state_import.add_argument("--project", help="GCP project for GCS access")
    # Terraform Cloud backend
    state_import.add_argument("--organization", help="Terraform Cloud organization")
    state_import.add_argument("--remote-workspace", help="Terraform Cloud workspace name")
    state_import.add_argument("--hostname", help="Terraform Cloud hostname (default: app.terraform.io)")
    state_import.add_argument("--token", help="Terraform Cloud user or team token")

    state_list = state_sub.add_parser("list", help="List imported states for a project")
    state_list_ref = state_list.add_mutually_exclusive_group(required=True)
    state_list_ref.add_argument("--project-id", help="Project ID")
    state_list_ref.add_argument("--project-slug", help="Project slug")
    state_list.add_argument("--workspace", help="Optional workspace filter")
    state_list.add_argument("--json", action="store_true", help="Output JSON (default) explicitly")

    state_show = state_sub.add_parser("show", help="Show state metadata")
    state_show.add_argument("--state-id", required=True, help="State identifier")
    state_show.add_argument("--include-snapshot", action="store_true", help="Include the raw state snapshot")

    state_export = state_sub.add_parser("export", help="Export the raw state snapshot to a file")
    state_export.add_argument("--state-id", required=True, help="State identifier")
    state_export.add_argument("--out", required=True, help="Destination file path for the JSON snapshot")

    state_resources = state_sub.add_parser("resources", help="List resources stored in a state")
    state_resources.add_argument("--state-id", required=True, help="State identifier")
    state_resources.add_argument("--limit", type=int, default=200, help="Maximum number of resources to return")
    state_resources.add_argument("--offset", type=int, default=0, help="Offset for resource pagination")

    state_outputs = state_sub.add_parser("outputs", help="List outputs stored in a state")
    state_outputs.add_argument("--state-id", required=True, help="State identifier")

    state_drift = state_sub.add_parser("drift", help="Detect drift by comparing a stored state against a plan JSON")
    state_drift.add_argument("--state-id", required=True, help="State identifier")
    state_drift.add_argument("--plan", required=True, help="Path to Terraform plan JSON or inline JSON payload")
    state_drift.add_argument(
        "--record-result",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Persist the drift summary in the database (default: True)",
    )

    state_rm = state_sub.add_parser("rm", help="Remove resource addresses from a stored state snapshot")
    state_rm.add_argument("--state-id", required=True, help="State identifier")
    state_rm.add_argument(
        "--address",
        dest="addresses",
        action="append",
        required=True,
        help="Resource address to remove (repeatable)",
    )

    state_mv = state_sub.add_parser("mv", help="Move/rename a resource address inside a stored state snapshot")
    state_mv.add_argument("--state-id", required=True, help="State identifier")
    state_mv.add_argument("--from", dest="source", required=True, help="Existing resource address")
    state_mv.add_argument("--to", dest="destination", required=True, help="New resource address")

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
        default=None,
        help="Directory to write generated documentation (default: docs/generators)",
    )
    docs_cmd.add_argument(
        "--knowledge-out",
        default=None,
        help=(
            "Optional knowledge directory to mirror generated docs (default: knowledge/generated). "
            "Pass an empty string to skip the knowledge mirror."
        ),
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
    docs_project = docs_cmd.add_argument_group("Project integration")
    docs_project_ref = docs_project.add_mutually_exclusive_group()
    docs_project_ref.add_argument("--project-id", help="Write docs inside the specified project workspace")
    docs_project_ref.add_argument("--project-slug", help="Write docs inside the specified project workspace")

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

    db_cmd = sub.add_parser("db", help="Database utilities")
    db_sub = db_cmd.add_subparsers(dest="db_cmd", required=True)
    db_migrate = db_sub.add_parser("migrate-profile", help="Add missing profile fields to the users table")
    db_migrate.add_argument(
        "--db-path",
        default=str(DEFAULT_DB_PATH),
        help=f"Path to SQLite database (default: {DEFAULT_DB_PATH})",
    )

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
    project_upload = project_sub.add_parser("upload", help="Upload files into a project run workspace")
    project_upload.add_argument("--project-id", required=True, help="Project identifier")
    project_upload.add_argument("--run-id", required=True, help="Run identifier")
    project_upload.add_argument("--file", required=True, help="Path to the local file to upload")
    project_upload.add_argument(
        "--dest",
        help="Destination relative path inside the run directory (defaults to the source filename)",
    )
    project_upload.add_argument(
        "--overwrite",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Overwrite existing artifact if it already exists (default: true)",
    )
    project_upload.add_argument(
        "--tags",
        help="Comma-separated tags to store with the uploaded artifact",
    )
    project_upload.add_argument(
        "--metadata",
        help="Inline JSON object or path describing artifact metadata",
    )
    project_upload.add_argument("--media-type", help="Optional media type override for the artifact")
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
    elif args.cmd == "db":
        if args.db_cmd == "migrate-profile":
            target = Path(args.db_path).expanduser()
            ensure_user_profile_columns(target)
            print(f"Ensured user profile columns exist in {target}")
    elif args.cmd == "baseline":
        project_record: Dict[str, Any] | None = None
        project_workspace: Path | None = None
        if args.project_id or args.project_slug:
            try:
                project_record = _resolve_project_reference(args.project_id, args.project_slug)
                project_workspace = get_project_workspace(project_record)
            except ValueError as exc:
                logger.error(str(exc))
                sys.exit(1)
            except WorkspacePathError as exc:
                logger.error("Failed to resolve project workspace: %s", exc)
                sys.exit(1)

        try:
            if project_workspace:
                paths = resolve_workspace_paths(project_workspace, args.path)
            else:
                paths = [Path(p) for p in args.path]
        except WorkspacePathError as exc:
            logger.error(str(exc))
            sys.exit(1)

        context = {"source": "cli.baseline"}
        if project_record:
            context.update({"project_id": project_record["id"], "project_slug": project_record.get("slug")})

        report = scan_paths(paths, use_terraform_validate=False, context=context)
        baseline_data = _build_baseline(report, include_waived=args.include_waived)

        output_name = args.out or BASELINE_DEFAULT_OUT
        if project_workspace:
            relative_token = output_name if args.out else str(Path("configs") / BASELINE_DEFAULT_OUT)
            try:
                out_path = _resolve_workspace_destination(
                    project_workspace,
                    relative_token,
                    label="baseline output file",
                )
            except WorkspacePathError as exc:
                logger.error(str(exc))
                sys.exit(1)
        else:
            out_path = Path(output_name)
            if not out_path.is_absolute():
                out_path = Path.cwd() / out_path
            _ensure_parent(out_path)

        if args.format == "json":
            payload = json.dumps(baseline_data, indent=2)
        else:
            payload = yaml.safe_dump(baseline_data, sort_keys=False)
        out_path.write_text(payload, encoding="utf-8")
        print(f"Wrote baseline to {out_path}")
    elif args.cmd == "workspace":
        manager = WorkspaceManager()
        try:
            project = _resolve_project_reference(args.project_id, args.project_slug)
            try:
                project_root = get_project_workspace(project)
            except WorkspacePathError as exc:
                logger.error("Failed to resolve project workspace: %s", exc)
                sys.exit(1)
            if args.workspace_cmd == "discover":
                with session_scope() as session:
                    result = discover_and_sync_workspaces(
                        session,
                        project=project,
                        manager=manager,
                        working_directory=args.working_dir,
                    )
                payload = {"discovered": result.discovered, "created": result.created}
                if args.json:
                    _print_json(payload)
                else:
                    print(f"Discovered {sum(len(v) for v in result.discovered.values())} workspaces")
                    print(f"Persisted {result.created} new records")
                    for rel_dir, names in payload["discovered"].items():
                        joined = ", ".join(names) if names else "<none>"
                        print(f"- {rel_dir}: {joined}")
            elif args.workspace_cmd == "list":
                with session_scope() as session:
                    items = list_workspace_records(
                        session,
                        project_id=project["id"],
                        working_directory=args.working_dir,
                    )
                if args.json:
                    _print_json({"items": items})
                else:
                    if not items:
                        print("No workspaces found.")
                    for ws in items:
                        flags = []
                        if ws.get("is_default"):
                            flags.append("default")
                        if ws.get("is_active"):
                            flags.append("active")
                        meta = f" ({', '.join(flags)})" if flags else ""
                        print(f"{ws['id']}  {ws['name']}  dir={ws['working_directory']}{meta}")
            elif args.workspace_cmd == "create":
                with session_scope() as session:
                    record = create_workspace_with_cli(
                        session,
                        project=project,
                        name=args.name,
                        working_directory=args.working_dir,
                        manager=manager,
                        activate=args.activate,
                        create_in_terraform=not args.skip_terraform,
                    )
                print(f"Created workspace {record['name']} (id={record['id']}) in {record['working_directory']}")
            elif args.workspace_cmd == "select":
                with session_scope() as session:
                    workspace = _resolve_tf_workspace(
                        session,
                        project_id=project["id"],
                        working_directory=args.working_dir,
                        workspace_id=args.workspace_id,
                        workspace_name=args.name,
                    )
                    record = select_workspace_with_cli(
                        session,
                        project=project,
                        workspace_id=workspace.id,
                        manager=manager,
                    )
                print(f"Selected workspace {record['name']} (dir={record['working_directory']})")
            elif args.workspace_cmd == "delete":
                with session_scope() as session:
                    workspace = _resolve_tf_workspace(
                        session,
                        project_id=project["id"],
                        working_directory=args.working_dir,
                        workspace_id=args.workspace_id,
                        workspace_name=args.name,
                    )
                    delete_workspace_with_cli(
                        session,
                        project=project,
                        workspace_id=workspace.id,
                        manager=manager,
                        skip_cli=args.skip_terraform,
                    )
                print("Workspace deleted")
            elif args.workspace_cmd == "scan":
                resolved = resolve_tf_working_directory(project, args.working_dir)
                with session_scope() as session:
                    workspace_records = list_workspace_records(
                        session,
                        project_id=project["id"],
                        working_directory=resolved.working_directory_token,
                    )
                    name_list = (
                        [name.strip() for name in args.workspaces.split(",") if name.strip()]
                        if args.workspaces
                        else [ws["name"] for ws in workspace_records]
                    )
                    if not name_list:
                        raise ValueError("No workspaces available to scan")
                    id_lookup = {ws["name"]: ws["id"] for ws in workspace_records}
                    scanner = MultiWorkspaceScanner(manager=manager)
                    results = scanner.scan(
                        resolved.working_dir,
                        name_list,
                        use_terraform_validate=args.terraform_validate,
                        context={
                            "project_id": project["id"],
                            "working_directory": resolved.working_directory_token,
                        },
                        update_ids=[id_lookup[name] for name in name_list if name in id_lookup],
                        session=session,
                    )
                payload = {
                    name: {
                        "status": result.status,
                        "workspace": result.workspace,
                        "error": result.error,
                        "summary": (result.result or {}).get("summary") if result.result else None,
                    }
                    for name, result in results.items()
                }
                if args.json:
                    _print_json({"results": payload})
                else:
                    for name, entry in payload.items():
                        if entry["status"] == "ok":
                            summary = entry.get("summary") or {}
                            issues = summary.get("issues_found")
                            print(f"{name}: ok (issues: {issues})")
                        else:
                            print(f"{name}: error - {entry['error']}")
            elif args.workspace_cmd == "compare":
                with session_scope() as session:
                    workspace_a = _resolve_tf_workspace(
                        session,
                        project_id=project["id"],
                        working_directory=args.working_dir,
                        workspace_id=getattr(args, "workspace_a_id", None),
                        workspace_name=getattr(args, "workspace_a_name", None),
                    )
                    workspace_b = _resolve_tf_workspace(
                        session,
                        project_id=project["id"],
                        working_directory=args.working_dir,
                        workspace_id=getattr(args, "workspace_b_id", None),
                        workspace_name=getattr(args, "workspace_b_name", None),
                    )
                    vars_a = load_workspace_variables(session, workspace_a.id)
                    vars_b = load_workspace_variables(session, workspace_b.id)
                    differences = compare_variables_map(vars_a, vars_b, info_keys=["region", "environment", "account_id"])
                    record = record_workspace_comparison(
                        session,
                        project_id=project["id"],
                        workspace_a_id=workspace_a.id,
                        workspace_b_id=workspace_b.id,
                        comparison_type="variables",
                        differences=differences,
                    )
                    session.commit()
                print(f"Recorded comparison {record.id} ({len(differences)} differences)")
            elif args.workspace_cmd == "vars":
                with session_scope() as session:
                    workspace = _resolve_tf_workspace(
                        session,
                        project_id=project["id"],
                        working_directory=args.working_dir,
                        workspace_id=getattr(args, "workspace_id", None),
                        workspace_name=getattr(args, "name", None),
                    )
                    if args.workspace_vars_cmd == "list":
                        items = list_workspace_variables(session, workspace_id=workspace.id)
                        _print_json({"items": items})
                    elif args.workspace_vars_cmd == "set":
                        record = upsert_workspace_variable(
                            session,
                            workspace_id=workspace.id,
                            key=args.key,
                            value=args.value,
                            sensitive=args.sensitive,
                            source=args.source,
                            description=args.description,
                        )
                        session.commit()
                        rendered_value = "<redacted>" if record.sensitive else record.value
                        print(f"Set {record.key}={rendered_value} on workspace {workspace.name}")
                    elif args.workspace_vars_cmd == "unset":
                        delete_workspace_variable(session, workspace_id=workspace.id, key=args.key)
                        session.commit()
                        print(f"Deleted variable '{args.key}' from workspace {workspace.name}")
                    elif args.workspace_vars_cmd == "import":
                        tfvars_path = resolve_workspace_file(project_root, args.file, label="tfvars file")
                        summary = import_tfvars_file(
                            session,
                            workspace_id=workspace.id,
                            tfvars_path=tfvars_path,
                            extra_sensitive=args.sensitive_keys or [],
                        )
                        session.commit()
                        print(
                            f"Imported {summary['imported']} variables from {tfvars_path} "
                            f"(sensitive keys: {', '.join(summary['sensitive_keys']) if summary['sensitive_keys'] else 'none'})"
                        )
        except (
            TerraformWorkspaceError,
            WorkspaceConflictError,
            WorkspaceNotFoundError,
            WorkspacePathError,
            ValueError,
        ) as exc:
            logger.error(str(exc))
            sys.exit(1)
    elif args.cmd == "state":
        try:
            if args.state_cmd == "import":
                project = _resolve_project_reference(args.project_id, args.project_slug)
                backend_config = _build_backend_config_from_args(args)
                with session_scope() as session:
                    record = import_state(
                        session,
                        project_id=project["id"],
                        workspace=args.workspace,
                        backend=backend_config,
                    )
                    _print_json(record)
            elif args.state_cmd == "list":
                project = _resolve_project_reference(args.project_id, args.project_slug)
                with session_scope() as session:
                    items = list_project_states(session, project_id=project["id"], workspace=args.workspace)
                _print_json({"items": items})
            elif args.state_cmd == "show":
                with session_scope() as session:
                    record = get_state_detail(session, state_id=args.state_id, include_snapshot=args.include_snapshot)
                _print_json(record)
            elif args.state_cmd == "export":
                out_path = Path(args.out).expanduser()
                _ensure_parent(out_path)
                with session_scope() as session:
                    snapshot = export_state_snapshot(session, state_id=args.state_id)
                out_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")
                print(f"Wrote state snapshot to {out_path}")
            elif args.state_cmd == "resources":
                with session_scope() as session:
                    resources = list_resources_for_state(
                        session,
                        state_id=args.state_id,
                        limit=args.limit,
                        offset=args.offset,
                    )
                _print_json({"items": resources, "limit": args.limit, "offset": args.offset})
            elif args.state_cmd == "outputs":
                with session_scope() as session:
                    outputs = list_outputs_for_state(session, state_id=args.state_id)
                _print_json({"items": outputs})
            elif args.state_cmd == "drift":
                plan_payload = _load_json_payload(args.plan)
                with session_scope() as session:
                    summary = detect_drift_from_plan(
                        session,
                        state_id=args.state_id,
                        plan_json=plan_payload,
                        record_result=args.record_result,
                    )
                _print_json(summary.model_dump())
            elif args.state_cmd == "rm":
                with session_scope() as session:
                    record = remove_state_resources(session, state_id=args.state_id, addresses=args.addresses)
                _print_json(record)
            elif args.state_cmd == "mv":
                with session_scope() as session:
                    record = move_state_resource(
                        session,
                        state_id=args.state_id,
                        source=args.source,
                        destination=args.destination,
                    )
                _print_json(record)
        except (StateNotFoundError, StateMutationError, StateBackendError, ValueError) as exc:
            logger.error(str(exc))
            sys.exit(1)
    elif args.cmd == "precommit":
        out_path = Path(args.out)
        if out_path.exists() and not args.force:
            print(f"{out_path} already exists. Use --force to overwrite.", file=sys.stderr)
            sys.exit(1)
        _ensure_parent(out_path)
        out_path.write_text(PRECOMMIT_TEMPLATE, encoding="utf-8")
        print(f"Wrote pre-commit configuration to {out_path}")
    elif args.cmd == "docs":
        project_record: Dict[str, Any] | None = None
        project_workspace: Path | None = None
        if args.project_id or args.project_slug:
            try:
                project_record = _resolve_project_reference(args.project_id, args.project_slug)
                project_workspace = get_project_workspace(project_record)
            except ValueError as exc:
                logger.error(str(exc))
                sys.exit(1)
            except WorkspacePathError as exc:
                logger.error("Failed to resolve project workspace: %s", exc)
                sys.exit(1)

        out_value = (args.out or DOCS_DEFAULT_OUT).strip() or DOCS_DEFAULT_OUT
        knowledge_raw = args.knowledge_out
        if knowledge_raw is None:
            knowledge_value: str | None = DOCS_DEFAULT_KNOWLEDGE_OUT
        else:
            knowledge_value = knowledge_raw.strip()
        knowledge_value = knowledge_value or None

        try:
            if project_workspace:
                out_dir = _resolve_workspace_destination(
                    project_workspace,
                    out_value,
                    label="docs output directory",
                    expect_dir=True,
                )
                knowledge_dir = None
                if knowledge_value:
                    knowledge_dir = _resolve_workspace_destination(
                        project_workspace,
                        knowledge_value,
                        label="knowledge mirror directory",
                        expect_dir=True,
                    )
            else:
                out_dir = Path(out_value)
                knowledge_dir = Path(knowledge_value) if knowledge_value else None
        except WorkspacePathError as exc:
            logger.error(str(exc))
            sys.exit(1)

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
            elif args.project_cmd == "upload":
                source = Path(args.file)
                if not source.exists() or not source.is_file():
                    logger.error("Upload source %s not found or not a file", source)
                    sys.exit(1)
                destination = (args.dest or "").strip() or source.name
                try:
                    data = source.read_bytes()
                except Exception as exc:  # noqa: BLE001
                    logger.error("Failed to read %s: %s", source, exc)
                    sys.exit(1)
                try:
                    entry = save_run_artifact(
                        project_id=args.project_id,
                        run_id=args.run_id,
                        path=destination,
                        data=data,
                        overwrite=args.overwrite,
                    )
                except ValueError:
                    logger.error("Project or run not found")
                    sys.exit(1)
                except FileExistsError:
                    logger.error(
                        "Artifact %s already exists for run %s. Re-run with --overwrite to replace it.",
                        destination,
                        args.run_id,
                    )
                    sys.exit(1)
                except ArtifactPathError as exc:
                    logger.error("Invalid destination path: %s", exc)
                    sys.exit(1)

                tags_payload = _parse_cli_tags(args.tags)
                metadata_payload: Dict[str, Any] | None = None
                if args.metadata:
                    try:
                        metadata_payload = _load_json_payload(args.metadata)
                    except ValueError as exc:
                        logger.error("Invalid metadata payload: %s", exc)
                        sys.exit(1)

                needs_update = (
                    args.tags is not None
                    or args.metadata is not None
                    or args.media_type is not None
                )
                artifact_record: Dict[str, Any] = dict(entry)
                artifact_id = entry.get("artifact_id")
                if needs_update and artifact_id:
                    updated = update_project_artifact(
                        artifact_id,
                        project_id=args.project_id,
                        tags=tags_payload if args.tags is not None else None,
                        metadata=metadata_payload if args.metadata is not None else None,
                        media_type=args.media_type,
                    )
                    if updated:
                        artifact_record = updated
                        artifact_id = updated.get("id", artifact_id)

                relative_path = (
                    artifact_record.get("path")
                    or artifact_record.get("relative_path")
                    or destination
                )
                size = artifact_record.get("size") or artifact_record.get("size_bytes")
                size_suffix = f" ({size} bytes)" if size is not None else ""
                final_id = artifact_id or artifact_record.get("id")
                print(
                    f"Uploaded {source} -> {relative_path}"
                    f" (artifact_id={final_id}){size_suffix}"
                )
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
