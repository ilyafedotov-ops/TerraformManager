from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from api.routes.auth import CurrentUser
from api.dependencies import require_current_user
from backend.db.session import get_session_dependency
from backend.storage import (
    create_project,
    list_projects,
    get_project,
    delete_project,
    update_project,
    create_project_run,
    list_project_runs,
    get_project_run,
    update_project_run,
    list_run_artifacts,
    save_run_artifact,
    get_run_artifact_path,
    delete_run_artifact,
    ArtifactPathError,
)


router = APIRouter(prefix="/projects", tags=["projects"])


class ProjectBaseResponse(BaseModel):
    id: str
    name: str
    slug: str
    root_path: str
    description: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectResponse(ProjectBaseResponse):
    metadata: Optional[Dict[str, Any]] = None


class ProjectCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    slug: Optional[str] = Field(default=None, max_length=160)
    metadata: Dict[str, Any] = Field(default_factory=dict)


class ProjectUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=128)
    description: Optional[str] = Field(default=None, max_length=512)
    metadata: Optional[Dict[str, Any]] = None


class ProjectRunResponse(BaseModel):
    id: str
    project_id: str
    label: str
    kind: str
    status: str
    triggered_by: Optional[str] = None
    parameters: Optional[Dict[str, Any]] = None
    summary: Optional[Dict[str, Any]] = None
    artifacts_path: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    started_at: Optional[str] = None
    finished_at: Optional[str] = None


class ProjectRunCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=128)
    kind: str = Field(..., min_length=1, max_length=48)
    parameters: Dict[str, Any] = Field(default_factory=dict)


class ProjectRunUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, min_length=1, max_length=32)
    summary: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


class ArtifactEntry(BaseModel):
    name: str
    path: str
    is_dir: bool
    size: Optional[int] = None
    modified_at: Optional[str] = None


@router.get("/", response_model=List[ProjectBaseResponse])
def projects_index(
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> List[Dict[str, Any]]:
    return list_projects(session=session)


@router.post("/", response_model=ProjectResponse, status_code=status.HTTP_201_CREATED)
def project_create(
    payload: ProjectCreateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    try:
        return create_project(
            name=payload.name,
            description=payload.description,
            slug=payload.slug,
            metadata=payload.metadata,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{project_id}", response_model=ProjectResponse)
def project_detail(
    project_id: str,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def project_update(
    project_id: str,
    payload: ProjectUpdateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    try:
        updated = update_project(
            project_id,
            name=payload.name,
            description=payload.description,
            metadata=payload.metadata,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return updated


@router.delete(
    "/{project_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def project_delete(
    project_id: str,
    remove_files: bool = False,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Response:
    deleted = delete_project(project_id, remove_files=remove_files, session=session)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/runs", response_model=List[ProjectRunResponse])
def project_runs_index(
    project_id: str,
    limit: int = 50,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> List[Dict[str, Any]]:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return list_project_runs(project_id=project_id, limit=limit, session=session)


@router.post("/{project_id}/runs", response_model=ProjectRunResponse, status_code=status.HTTP_201_CREATED)
def project_run_create(
    project_id: str,
    payload: ProjectRunCreateRequest,
    current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    label = payload.label.strip()
    kind = payload.kind.strip()
    if not label:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="label cannot be empty")
    if not kind:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="kind cannot be empty")

    try:
        return create_project_run(
            project_id=project_id,
            label=label,
            kind=kind,
            parameters=payload.parameters,
            triggered_by=current_user.user.email if current_user.user else None,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{project_id}/runs/{run_id}", response_model=ProjectRunResponse)
def project_run_detail(
    project_id: str,
    run_id: str,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    run = get_project_run(run_id=run_id, project_id=project_id, session=session)
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return run


@router.patch("/{project_id}/runs/{run_id}", response_model=ProjectRunResponse)
def project_run_update(
    project_id: str,
    run_id: str,
    payload: ProjectRunUpdateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    status_value: Optional[str] = payload.status.strip() if payload.status else None
    if payload.status is not None and not status_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status cannot be empty")

    updated = update_project_run(
        run_id=run_id,
        project_id=project_id,
        status=status_value,
        summary=payload.summary,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        session=session,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="run not found")
    return updated


@router.get("/{project_id}/runs/{run_id}/artifacts", response_model=List[ArtifactEntry])
def project_run_artifacts_list(
    project_id: str,
    run_id: str,
    path: str = Query(default="", description="Optional directory path relative to the run root"),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> List[Dict[str, Any]]:
    path_value = path or None
    try:
        return list_run_artifacts(project_id=project_id, run_id=run_id, path=path_value, session=session)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project or run not found")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="path not found")
    except ArtifactPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.post("/{project_id}/runs/{run_id}/artifacts", response_model=ArtifactEntry, status_code=status.HTTP_201_CREATED)
async def project_run_artifact_upload(
    project_id: str,
    run_id: str,
    path: str = Form(..., description="Destination file path relative to the run root"),
    overwrite: bool = Form(True),
    file: UploadFile = File(...),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    data = await file.read()
    try:
        return save_run_artifact(
            project_id=project_id,
            run_id=run_id,
            path=path,
            data=data,
            overwrite=overwrite,
            session=session,
        )
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project or run not found")
    except FileExistsError:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="artifact already exists; set overwrite=true to replace",
        ) from None
    except ArtifactPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


@router.get("/{project_id}/runs/{run_id}/artifacts/download")
def project_run_artifact_download(
    project_id: str,
    run_id: str,
    path: str = Query(..., description="File path to download, relative to the run root"),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> FileResponse:
    if not path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path is required")
    try:
        artifact_path = get_run_artifact_path(project_id=project_id, run_id=run_id, path=path, session=session)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project or run not found")
    except FileNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    except ArtifactPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    filename = Path(path).name or artifact_path.name
    return FileResponse(artifact_path, filename=filename)


@router.delete(
    "/{project_id}/runs/{run_id}/artifacts",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def project_run_artifact_delete(
    project_id: str,
    run_id: str,
    path: str = Query(..., description="File path to delete, relative to the run root"),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Response:
    if not path:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="path is required")
    try:
        deleted = delete_run_artifact(project_id=project_id, run_id=run_id, path=path, session=session)
    except ValueError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project or run not found")
    except ArtifactPathError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
