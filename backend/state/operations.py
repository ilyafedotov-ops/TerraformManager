from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.db.session import session_scope
from . import analyzer, reader
from .models import DriftSummary, StateBackendConfig, TerraformStateDocument
from .storage import (
    StateMutationError,
    StateNotFoundError,
    WorkspaceNotFoundError,
    get_state,
    get_state_snapshot,
    list_state_outputs,
    list_state_resources,
    list_states,
    persist_state_document,
    record_drift_detection,
    remove_state_addresses,
    move_state_address,
    create_workspace,
    list_workspaces,
    create_plan_record,
    list_plans,
)


def import_state(
    session: Session,
    *,
    project_id: str,
    workspace: str,
    backend: StateBackendConfig,
) -> Dict[str, Any]:
    """Import a Terraform state file into the database."""

    document = reader.load_state_from_backend(backend)
    record = persist_state_document(
        session=session,
        project_id=project_id,
        workspace=workspace or "default",
        backend=backend,
        document=document,
    )
    return record.to_dict(include_snapshot=False)


def list_project_states(
    session: Session,
    *,
    project_id: str,
    workspace: str | None = None,
) -> List[Dict[str, Any]]:
    return list_states(session=session, project_id=project_id, workspace=workspace)


def get_state_detail(
    session: Session,
    *,
    state_id: str,
    include_snapshot: bool = False,
) -> Dict[str, Any]:
    return get_state(session=session, state_id=state_id, include_snapshot=include_snapshot)


def export_state_snapshot(session: Session, *, state_id: str) -> Dict[str, Any]:
    snapshot = get_state_snapshot(session=session, state_id=state_id)
    return json.loads(snapshot)


def list_resources_for_state(
    session: Session,
    *,
    state_id: str,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    return list_state_resources(session=session, state_id=state_id, limit=limit, offset=offset)


def list_outputs_for_state(session: Session, *, state_id: str) -> List[Dict[str, Any]]:
    return list_state_outputs(session=session, state_id=state_id)


def detect_drift_from_plan(
    session: Session,
    *,
    state_id: str,
    plan_json: Dict[str, Any],
    record_result: bool = True,
) -> DriftSummary:
    """Compare a stored state file with a Terraform plan JSON payload."""

    state_record = get_state(session=session, state_id=state_id, include_snapshot=True)
    snapshot = state_record.get("state_snapshot")
    if not snapshot:
        raise StateNotFoundError(f"State '{state_id}' snapshot is unavailable")

    document = reader.load_state_from_bytes(
        snapshot.encode("utf-8"),
        backend_type=state_record.get("backend_type"),
    )
    summary = analyzer.compare_state_to_plan(document, plan_json)
    if record_result:
        record_drift_detection(
            session=session,
            project_id=state_record["project_id"],
            workspace=state_record["workspace"],
            method="plan_comparison",
            summary=summary,
            state_id=state_id,
        )
    return summary


def remove_state_resources(
    session: Session,
    *,
    state_id: str,
    addresses: List[str],
) -> Dict[str, Any]:
    return remove_state_addresses(session, state_id=state_id, addresses=addresses)


def move_state_resource(
    session: Session,
    *,
    state_id: str,
    source: str,
    destination: str,
) -> Dict[str, Any]:
    return move_state_address(session, state_id=state_id, source=source, destination=destination)


def import_state_from_path(
    *,
    project_id: str,
    workspace: str,
    path: str,
) -> Dict[str, Any]:
    """Helper used by the CLI to import a local terraform.tfstate file."""

    from .models import LocalBackendConfig  # Local import to avoid circular dependency at module import time.

    backend_config = LocalBackendConfig(path=path)
    with session_scope() as session:
        return import_state(session, project_id=project_id, workspace=workspace, backend=backend_config)


def create_workspace_entry(
    session: Session,
    *,
    project_id: str,
    name: str,
    working_directory: str,
    is_default: bool = False,
    is_active: bool = False,
) -> Dict[str, Any]:
    workspace = create_workspace(
        session,
        project_id=project_id,
        name=name,
        working_directory=working_directory,
        is_default=is_default,
        is_active=is_active,
    )
    return workspace.to_dict()


def list_workspace_entries(session: Session, *, project_id: str) -> List[Dict[str, Any]]:
    return list_workspaces(session, project_id=project_id)


def create_plan_entry(
    session: Session,
    *,
    project_id: str,
    workspace: str,
    working_directory: str,
    plan_type: str,
    has_changes: bool,
    target_resources: Optional[List[str]] = None,
    resource_changes: Optional[Dict[str, Any]] = None,
    resource_changes_detail: Optional[List[Dict[str, Any]]] = None,
    output_changes: Optional[Dict[str, Any]] = None,
    plan_file_path: Optional[str] = None,
    plan_json_path: Optional[str] = None,
    plan_output: Optional[str] = None,
    cost_estimate: Optional[Dict[str, Any]] = None,
    security_impact: Optional[Dict[str, Any]] = None,
    approval_status: Optional[str] = None,
    run_id: Optional[str] = None,
) -> Dict[str, Any]:
    plan = create_plan_record(
        session,
        project_id=project_id,
        workspace=workspace,
        working_directory=working_directory,
        plan_type=plan_type,
        has_changes=has_changes,
        target_resources=target_resources,
        resource_changes=resource_changes,
        resource_changes_detail=resource_changes_detail,
        output_changes=output_changes,
        plan_file_path=plan_file_path,
        plan_json_path=plan_json_path,
        plan_output=plan_output,
        cost_estimate=cost_estimate,
        security_impact=security_impact,
        approval_status=approval_status,
        run_id=run_id,
    )
    return plan.to_dict()


def list_plan_entries(session: Session, *, project_id: str, workspace: Optional[str] = None) -> List[Dict[str, Any]]:
    return list_plans(session, project_id=project_id, workspace=workspace)
