from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies import require_current_user
from backend.db import get_session_dependency
from backend.state import (
    StateBackendError,
    StateImportRequest,
    StateMoveRequest,
    StateRemoveRequest,
    WorkspaceCreateRequest,
    PlanCreateRequest,
    detect_drift_from_plan,
    export_state_snapshot,
    get_state_detail,
    list_outputs_for_state,
    list_project_states,
    list_resources_for_state,
    import_state,
    remove_state_resources,
    move_state_resource,
    create_workspace_entry,
    list_workspace_entries,
    create_plan_entry,
    list_plan_entries,
)
from backend.state.storage import StateMutationError, StateNotFoundError
from backend.storage import get_project

router = APIRouter(prefix="/state", tags=["state"])


class DriftPlanRequest(BaseModel):
    plan: Dict[str, Any]
    record_result: bool = True


def _require_project(session: Session, project_id: str | None, project_slug: str | None) -> Dict[str, Any]:
    record = get_project(project_id=project_id, slug=project_slug, session=session)
    if not record:
        identifier = project_id or project_slug or "<missing>"
        raise HTTPException(404, f"project '{identifier}' not found")
    return record


@router.post("/import")
def import_state_endpoint(
    payload: StateImportRequest,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, payload.project_id, payload.project_slug)
    try:
        record = import_state(
            session,
            project_id=project["id"],
            workspace=payload.workspace or "default",
            backend=payload.backend,
        )
    except StateBackendError as exc:
        raise HTTPException(400, f"state backend error: {exc}") from exc
    return record


@router.get("")
def list_states_endpoint(
    project_id: str | None = Query(default=None),
    project_slug: str | None = Query(default=None),
    workspace: str | None = Query(default=None),
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, project_id, project_slug)
    items = list_project_states(session, project_id=project["id"], workspace=workspace)
    return {"items": items}


@router.get("/{state_id}")
def get_state_endpoint(
    state_id: str,
    include_snapshot: bool = Query(default=False),
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        return get_state_detail(session, state_id=state_id, include_snapshot=include_snapshot)
    except StateNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc


@router.get("/{state_id}/resources")
def list_state_resources_endpoint(
    state_id: str,
    limit: int = Query(default=200, ge=1, le=1000),
    offset: int = Query(default=0, ge=0),
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        resources = list_resources_for_state(session, state_id=state_id, limit=limit, offset=offset)
    except StateNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"items": resources, "limit": limit, "offset": offset}


@router.get("/{state_id}/outputs")
def list_state_outputs_endpoint(
    state_id: str,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        outputs = list_outputs_for_state(session, state_id=state_id)
    except StateNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"items": outputs}


@router.get("/{state_id}/export")
def export_state_endpoint(
    state_id: str,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        state_json = export_state_snapshot(session, state_id=state_id)
    except StateNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return JSONResponse(content=state_json)


@router.post("/{state_id}/drift/plan")
def plan_drift_endpoint(
    state_id: str,
    payload: DriftPlanRequest,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        summary = detect_drift_from_plan(
            session,
            state_id=state_id,
            plan_json=payload.plan,
            record_result=payload.record_result,
        )
    except StateNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return summary.model_dump()


@router.post("/{state_id}/operations/remove")
def remove_state_resources_endpoint(
    state_id: str,
    payload: StateRemoveRequest,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        record = remove_state_resources(session, state_id=state_id, addresses=payload.addresses)
    except StateNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except StateMutationError as exc:
        raise HTTPException(400, str(exc)) from exc
    return record


@router.post("/{state_id}/operations/move")
def move_state_resource_endpoint(
    state_id: str,
    payload: StateMoveRequest,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        record = move_state_resource(session, state_id=state_id, source=payload.source, destination=payload.destination)
    except StateNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    except StateMutationError as exc:
        raise HTTPException(400, str(exc)) from exc
    return record


@router.post("/workspaces")
def create_workspace_endpoint(
    payload: WorkspaceCreateRequest,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, payload.project_id, payload.project_slug)
    record = create_workspace_entry(
        session,
        project_id=project["id"],
        name=payload.name,
        working_directory=payload.working_directory,
        is_default=payload.is_default,
        is_active=payload.is_active,
    )
    return record


@router.get("/workspaces")
def list_workspaces_endpoint(
    project_id: str | None = Query(default=None),
    project_slug: str | None = Query(default=None),
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, project_id, project_slug)
    return {"items": list_workspace_entries(session, project_id=project["id"])}


@router.post("/plans")
def create_plan_endpoint(
    payload: PlanCreateRequest,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, payload.project_id, payload.project_slug)
    record = create_plan_entry(
        session,
        project_id=project["id"],
        workspace=payload.workspace,
        working_directory=payload.working_directory,
        plan_type=payload.plan_type,
        has_changes=payload.has_changes,
        target_resources=payload.target_resources,
        resource_changes=payload.resource_changes,
        resource_changes_detail=payload.resource_changes_detail,
        output_changes=payload.output_changes,
        plan_file_path=payload.plan_file_path,
        plan_json_path=payload.plan_json_path,
        plan_output=payload.plan_output,
        cost_estimate=payload.cost_estimate,
        security_impact=payload.security_impact,
        approval_status=payload.approval_status,
        run_id=payload.run_id,
    )
    return record


@router.get("/plans")
def list_plans_endpoint(
    project_id: str | None = Query(default=None),
    project_slug: str | None = Query(default=None),
    workspace: str | None = Query(default=None),
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, project_id, project_slug)
    return {"items": list_plan_entries(session, project_id=project["id"], workspace=workspace)}
