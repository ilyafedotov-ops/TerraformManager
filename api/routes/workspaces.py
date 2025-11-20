from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.dependencies import require_current_user
from backend.db import get_session_dependency
from backend.storage import WorkspacePathError, get_project
from backend.workspaces.manager import WorkspaceManager
from backend.workspaces.models import (
    WorkspaceCreatePayload,
    WorkspaceScanPayload,
    WorkspaceSelectPayload,
    WorkspaceVariablePayload,
)
from backend.workspaces.scanner import MultiWorkspaceScanner
from backend.workspaces.services import (
    DiscoverResult,
    create_workspace_with_cli,
    delete_workspace_with_cli,
    discover_and_sync_workspaces,
    resolve_working_directory,
    select_workspace_with_cli,
)
from backend.workspaces.storage import delete_workspace_variable, list_workspace_records, list_workspace_variables, upsert_workspace_variable
from backend.workspaces.errors import TerraformWorkspaceError, WorkspaceConflictError, WorkspaceNotFoundError

router = APIRouter(prefix="/workspaces", tags=["workspaces"])


class WorkspaceDiscoverPayload(BaseModel):
    project_id: Optional[str] = None
    project_slug: Optional[str] = None
    working_directory: Optional[str] = None


def _require_project(session: Session, project_id: str | None, project_slug: str | None) -> Dict[str, Any]:
    try:
        project = get_project(project_id=project_id, slug=project_slug, session=session)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not project:
        ident = project_id or project_slug or "<missing>"
        raise HTTPException(404, f"project '{ident}' not found")
    return project


def _serialize_scan(results: Dict[str, Any]) -> Dict[str, Any]:
    payload: Dict[str, Any] = {}
    for name, result in results.items():
        payload[name] = {
            "status": result.status,
            "workspace": result.workspace,
            "result": result.result,
            "error": result.error,
        }
    return payload


@router.get("")
def list_workspaces_endpoint(
    project_id: str | None = Query(default=None),
    project_slug: str | None = Query(default=None),
    working_directory: str | None = Query(default=None),
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, project_id, project_slug)
    return {"items": list_workspace_records(session, project_id=project["id"], working_directory=working_directory)}


@router.post("")
def create_workspace_endpoint(
    payload: WorkspaceCreatePayload,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, payload.project_id, payload.project_slug)
    manager = WorkspaceManager()
    try:
        record = create_workspace_with_cli(
            session,
            project=project,
            name=payload.name,
            working_directory=payload.working_directory,
            manager=manager,
            activate=payload.is_active,
            create_in_terraform=True,
        )
    except (TerraformWorkspaceError, WorkspaceConflictError, WorkspacePathError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return record


@router.post("/discover")
def discover_workspaces_endpoint(
    payload: WorkspaceDiscoverPayload,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, payload.project_id, payload.project_slug)
    manager = WorkspaceManager()
    try:
        result: DiscoverResult = discover_and_sync_workspaces(
            session,
            project=project,
            manager=manager,
            working_directory=payload.working_directory,
        )
    except (TerraformWorkspaceError, WorkspacePathError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"discovered": result.discovered, "created": result.created, "message": result.message}


@router.post("/{workspace_id}/select")
def select_workspace_endpoint(
    workspace_id: str,
    payload: WorkspaceSelectPayload,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, payload.project_id, payload.project_slug)
    manager = WorkspaceManager()
    try:
        record = select_workspace_with_cli(session, project=project, workspace_id=workspace_id, manager=manager)
    except (TerraformWorkspaceError, WorkspaceNotFoundError, WorkspacePathError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"workspace": record}


@router.delete("/{workspace_id}")
def delete_workspace_endpoint(
    workspace_id: str,
    project_id: str | None = Query(default=None),
    project_slug: str | None = Query(default=None),
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, project_id, project_slug)
    manager = WorkspaceManager()
    try:
        delete_workspace_with_cli(session, project=project, workspace_id=workspace_id, manager=manager)
    except (TerraformWorkspaceError, WorkspaceNotFoundError, WorkspaceConflictError, WorkspacePathError) as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"status": "ok"}


@router.post("/scan")
def scan_workspaces_endpoint(
    payload: WorkspaceScanPayload,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    project = _require_project(session, payload.project_id, payload.project_slug)
    manager = WorkspaceManager()
    try:
        resolved = resolve_working_directory(project, payload.working_directory)
    except WorkspacePathError as exc:
        raise HTTPException(400, str(exc)) from exc

    workspace_records = list_workspace_records(
        session,
        project_id=project["id"],
        working_directory=resolved.working_directory_token,
    )
    names = payload.workspaces or [ws["name"] for ws in workspace_records]
    if not names:
        raise HTTPException(400, "No workspaces to scan")
    id_lookup = {ws["name"]: ws["id"] for ws in workspace_records}

    scanner = MultiWorkspaceScanner(manager=manager)
    try:
        results = scanner.scan(
            resolved.working_dir,
            names,
            use_terraform_validate=payload.use_terraform_validate,
            context={"project_id": project["id"], "working_directory": resolved.working_directory_token},
            update_ids=[id_lookup[name] for name in names if name in id_lookup],
            session=session,
        )
    except TerraformWorkspaceError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"results": _serialize_scan(results)}


@router.get("/{workspace_id}/variables")
def list_workspace_variables_endpoint(
    workspace_id: str,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        items = list_workspace_variables(session, workspace_id=workspace_id)
    except WorkspaceNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"items": items}


@router.post("/{workspace_id}/variables")
def upsert_workspace_variable_endpoint(
    workspace_id: str,
    payload: WorkspaceVariablePayload,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        record = upsert_workspace_variable(
            session,
            workspace_id=workspace_id,
            key=payload.key,
            value=payload.value if payload.value is not None else None,
            sensitive=payload.sensitive,
            source=payload.source,
            description=payload.description,
        )
        session.commit()
    except WorkspaceNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return record.to_dict()


@router.delete("/{workspace_id}/variables/{key}")
def delete_workspace_variable_endpoint(
    workspace_id: str,
    key: str,
    session: Session = Depends(get_session_dependency),
    user=Depends(require_current_user),  # noqa: ARG001
):
    try:
        delete_workspace_variable(session, workspace_id=workspace_id, key=key)
        session.commit()
    except WorkspaceNotFoundError as exc:
        raise HTTPException(404, str(exc)) from exc
    return {"status": "ok"}
