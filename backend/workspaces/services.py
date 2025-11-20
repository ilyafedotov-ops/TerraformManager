from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from sqlalchemy.orm import Session

from backend.storage import WorkspacePathError, get_project_workspace, resolve_workspace_path
from backend.db.models import TerraformWorkspace

from .errors import TerraformWorkspaceError, WorkspaceConflictError, WorkspaceNotFoundError
from .manager import WorkspaceManager
from .storage import (
    create_workspace_record,
    delete_workspace_record,
    get_workspace_by_id,
    list_workspace_records,
    set_active_workspace,
    touch_workspace_scan,
)


@dataclass
class ResolvedWorkingDirectory:
    project_root: Path
    working_dir: Path
    working_directory_token: str


@dataclass
class DiscoverResult:
    discovered: Dict[str, List[str]]
    created: int
    message: str | None = None


def resolve_working_directory(project: Dict[str, str], working_directory: str | None) -> ResolvedWorkingDirectory:
    project_root = get_project_workspace(project)
    try:
        working_dir = resolve_workspace_path(project_root, working_directory, label="working directory", require_file=False)
    except WorkspacePathError as exc:
        raise WorkspacePathError(str(exc)) from exc
    relative = working_dir.relative_to(project_root)
    token = "." if relative.as_posix() == "." else relative.as_posix()
    return ResolvedWorkingDirectory(project_root=project_root, working_dir=working_dir, working_directory_token=token)


def create_workspace_with_cli(
    session: Session,
    *,
    project: Dict[str, str],
    name: str,
    working_directory: str,
    manager: WorkspaceManager,
    activate: bool = False,
    create_in_terraform: bool = True,
) -> Dict[str, str]:
    resolved = resolve_working_directory(project, working_directory)
    if create_in_terraform:
        manager.create_workspace(resolved.working_dir, name)
    record = create_workspace_record(
        session,
        project_id=project["id"],
        name=name,
        working_directory=resolved.working_directory_token,
        is_default=name == "default",
        is_active=activate,
    )
    if activate:
        set_active_workspace(session, workspace_id=record.id, working_directory=resolved.working_directory_token)
    session.commit()
    return record.to_dict()


def select_workspace_with_cli(
    session: Session,
    *,
    project: Dict[str, str],
    workspace_id: str,
    manager: WorkspaceManager,
) -> Dict[str, str]:
    record = get_workspace_by_id(session, workspace_id)
    resolved = resolve_working_directory(project, record.working_directory)
    manager.select_workspace(resolved.working_dir, record.name)
    set_active_workspace(session, workspace_id=record.id, working_directory=record.working_directory)
    session.commit()
    return record.to_dict()


def delete_workspace_with_cli(
    session: Session,
    *,
    project: Dict[str, str],
    workspace_id: str,
    manager: WorkspaceManager,
    skip_cli: bool = False,
) -> None:
    record = get_workspace_by_id(session, workspace_id)
    resolved = resolve_working_directory(project, record.working_directory)
    if not skip_cli:
        manager.delete_workspace(resolved.working_dir, record.name)
    delete_workspace_record(session, workspace_id)
    session.commit()


def discover_and_sync_workspaces(
    session: Session,
    *,
    project: Dict[str, str],
    manager: WorkspaceManager,
    working_directory: str | None = None,
) -> DiscoverResult:
    resolved = resolve_working_directory(project, working_directory or ".")
    search_root = resolved.project_root if resolved.working_directory_token == "." else resolved.working_dir
    raw = manager.discover_workspaces(search_root)
    discovered: Dict[str, List[str]] = {}
    for rel_dir, names in raw.items():
        if resolved.working_directory_token != ".":
            prefix = resolved.working_directory_token if resolved.working_directory_token != "." else ""
            rel_token = rel_dir if rel_dir != "." else ""
            combined = "/".join(filter(None, [prefix, rel_token])) or "."
            discovered[combined] = names
        else:
            discovered[rel_dir] = names
    created = 0
    for relative_dir, names in discovered.items():
        for name in names:
            try:
                create_workspace_record(
                    session,
                    project_id=project["id"],
                    name=name,
                    working_directory=relative_dir,
                    is_default=name == "default",
                    is_active=False,
                )
                created += 1
            except WorkspaceConflictError:
                continue
    session.commit()
    return DiscoverResult(discovered=discovered, created=created, message=None)


def sync_scan_timestamps(session: Session, workspaces: Iterable[TerraformWorkspace]) -> None:
    touch_workspace_scan(session, [ws.id for ws in workspaces])
    session.commit()
