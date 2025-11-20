from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import TerraformWorkspace, WorkspaceVariable

from .errors import WorkspaceConflictError, WorkspaceNotFoundError


def _normalize_working_dir(value: str) -> str:
    token = value.strip() or "."
    if token == ".":
        return "."
    # store as forward-slash paths for consistency
    return "/".join(token.split("\\"))


def get_workspace_by_id(session: Session, workspace_id: str) -> TerraformWorkspace:
    workspace = session.get(TerraformWorkspace, workspace_id)
    if not workspace:
        raise WorkspaceNotFoundError(f"workspace '{workspace_id}' not found")
    return workspace


def get_workspace_by_name(
    session: Session,
    *,
    project_id: str,
    working_directory: str,
    name: str,
) -> TerraformWorkspace:
    normalized_dir = _normalize_working_dir(working_directory)
    record = (
        session.execute(
            select(TerraformWorkspace).where(
                TerraformWorkspace.project_id == project_id,
                TerraformWorkspace.working_directory == normalized_dir,
                TerraformWorkspace.name == name,
            )
        )
        .scalars()
        .first()
    )
    if not record:
        raise WorkspaceNotFoundError(f"workspace '{name}' not found under {normalized_dir}")
    return record


def list_workspace_records(session: Session, *, project_id: str, working_directory: str | None = None) -> List[Dict[str, Any]]:
    query = select(TerraformWorkspace).where(TerraformWorkspace.project_id == project_id)
    if working_directory:
        query = query.where(TerraformWorkspace.working_directory == _normalize_working_dir(working_directory))
    rows = session.execute(query.order_by(TerraformWorkspace.created_at.is_(None), TerraformWorkspace.created_at.desc())).scalars()
    return [row.to_dict() for row in rows]


def create_workspace_record(
    session: Session,
    *,
    project_id: str,
    name: str,
    working_directory: str,
    is_default: bool = False,
    is_active: bool = False,
) -> TerraformWorkspace:
    normalized_dir = _normalize_working_dir(working_directory)
    exists = (
        session.execute(
            select(TerraformWorkspace).where(
                TerraformWorkspace.project_id == project_id,
                TerraformWorkspace.working_directory == normalized_dir,
                TerraformWorkspace.name == name,
            )
        )
        .scalars()
        .first()
    )
    if exists:
        raise WorkspaceConflictError(f"workspace '{name}' already exists for {normalized_dir}")

    workspace = TerraformWorkspace(
        project_id=project_id,
        name=name,
        working_directory=normalized_dir,
        is_default=is_default,
        is_active=is_active,
        created_at=datetime.now(timezone.utc),
    )
    session.add(workspace)
    session.flush()

    if is_active:
        set_active_workspace(session, workspace_id=workspace.id, working_directory=normalized_dir)
    return workspace


def set_active_workspace(session: Session, *, workspace_id: str, working_directory: str | None = None) -> TerraformWorkspace:
    workspace = get_workspace_by_id(session, workspace_id)
    working_directory = working_directory or workspace.working_directory
    session.query(TerraformWorkspace).filter(
        TerraformWorkspace.project_id == workspace.project_id,
        TerraformWorkspace.working_directory == working_directory,
    ).update({"is_active": False})
    workspace.is_active = True
    workspace.selected_at = datetime.now(timezone.utc)
    session.flush()
    session.refresh(workspace)
    return workspace


def delete_workspace_record(session: Session, workspace_id: str) -> None:
    workspace = get_workspace_by_id(session, workspace_id)
    if workspace.name == "default":
        raise WorkspaceConflictError("cannot delete the default workspace")
    session.delete(workspace)
    session.flush()


def touch_workspace_scan(session: Session, workspace_ids: Iterable[str]) -> None:
    timestamp = datetime.now(timezone.utc)
    session.query(TerraformWorkspace).filter(TerraformWorkspace.id.in_(list(workspace_ids))).update(
        {"last_scanned_at": timestamp},
        synchronize_session=False,
    )
    session.flush()


def upsert_workspace_variable(
    session: Session,
    *,
    workspace_id: str,
    key: str,
    value: str | None,
    sensitive: bool = False,
    source: str | None = None,
    description: str | None = None,
) -> WorkspaceVariable:
    workspace = get_workspace_by_id(session, workspace_id)
    existing = (
        session.execute(
            select(WorkspaceVariable).where(
                WorkspaceVariable.workspace_id == workspace.id,
                WorkspaceVariable.key == key,
            )
        )
        .scalars()
        .first()
    )
    if existing:
        existing.value = value
        existing.sensitive = sensitive
        existing.source = source
        existing.description = description
        existing.updated_at = datetime.now(timezone.utc)
        session.flush()
        session.refresh(existing)
        return existing

    variable = WorkspaceVariable(
        workspace_id=workspace.id,
        key=key,
        value=value,
        sensitive=sensitive,
        source=source,
        description=description,
    )
    session.add(variable)
    session.flush()
    return variable


def list_workspace_variables(session: Session, *, workspace_id: str) -> List[Dict[str, Any]]:
    workspace = get_workspace_by_id(session, workspace_id)
    rows = session.execute(
        select(WorkspaceVariable).where(WorkspaceVariable.workspace_id == workspace.id).order_by(WorkspaceVariable.key.asc())
    ).scalars()
    return [row.to_dict() for row in rows]


def delete_workspace_variable(session: Session, *, workspace_id: str, key: str) -> None:
    workspace = get_workspace_by_id(session, workspace_id)
    record = (
        session.execute(
            select(WorkspaceVariable).where(
                WorkspaceVariable.workspace_id == workspace.id,
                WorkspaceVariable.key == key,
            )
        )
        .scalars()
        .first()
    )
    if not record:
        raise WorkspaceNotFoundError(f"variable '{key}' not found for workspace '{workspace_id}'")
    session.delete(record)
    session.flush()
