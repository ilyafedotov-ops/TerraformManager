from __future__ import annotations

import base64
import binascii
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
    list_generated_assets,
    get_generated_asset,
    register_generated_asset,
    update_generated_asset,
    add_generated_asset_version,
    delete_generated_asset_version,
    delete_generated_asset,
    get_generated_asset_version,
    get_generated_asset_version_path,
    diff_generated_asset_versions,
    list_project_configs,
    create_project_config,
    get_project_config,
    update_project_config,
    delete_project_config,
    list_project_artifacts,
    get_project_artifact,
    update_project_artifact,
    sync_project_run_artifacts,
    ArtifactPathError,
    get_project_overview,
)


router = APIRouter(prefix="/projects", tags=["projects"])


def _value_error_to_http(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code_value = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code_value, detail=detail)


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


class ProjectListLatestRun(BaseModel):
    id: str
    label: str
    status: str
    kind: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    finished_at: Optional[str] = None


class ProjectListItemResponse(ProjectBaseResponse):
    latest_run: Optional[ProjectListLatestRun] = None
    run_count: int = 0
    library_asset_count: int = 0
    config_count: int = 0
    artifact_count: int = 0
    last_activity_at: Optional[str] = None
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
    artifact_id: Optional[str] = None
    media_type: Optional[str] = None
    tags: Optional[List[str]] = None
    metadata: Optional[Dict[str, Any]] = None


class GeneratedAssetVersionSummary(BaseModel):
    id: str
    asset_id: str
    project_id: str
    run_id: Optional[str] = None
    report_id: Optional[str] = None
    storage_path: str
    display_path: str
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    media_type: Optional[str] = None
    notes: Optional[str] = None
    created_at: Optional[str] = None


class GeneratedAssetSummary(BaseModel):
    id: str
    project_id: str
    name: str
    description: Optional[str] = None
    asset_type: str
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    latest_version_id: Optional[str] = None
    created_at: Optional[str] = None
    updated_at: Optional[str] = None
    versions: Optional[List[GeneratedAssetVersionSummary]] = None


class GeneratedAssetCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    asset_type: str = Field(..., min_length=1, max_length=48)
    description: Optional[str] = Field(default=None, max_length=1024)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    run_id: Optional[str] = Field(default=None)
    report_id: Optional[str] = Field(default=None)
    artifact_path: Optional[str] = Field(
        default=None,
        description="Relative path to a run artifact to promote into the library.",
    )
    storage_filename: Optional[str] = Field(default=None, max_length=256)
    media_type: Optional[str] = Field(default=None, max_length=96)
    notes: Optional[str] = Field(default=None, max_length=2048)
    content_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded content for direct uploads.",
    )


class GeneratedAssetRegisterResponse(BaseModel):
    asset: GeneratedAssetSummary
    version: GeneratedAssetVersionSummary


class GeneratedAssetVersionCreateRequest(BaseModel):
    run_id: Optional[str] = Field(default=None)
    report_id: Optional[str] = Field(default=None)
    artifact_path: Optional[str] = Field(
        default=None,
        description="Relative path to a run artifact to promote into this asset.",
    )
    storage_filename: Optional[str] = Field(default=None, max_length=256)
    media_type: Optional[str] = Field(default=None, max_length=96)
    notes: Optional[str] = Field(default=None, max_length=2048)
    content_base64: Optional[str] = Field(
        default=None,
        description="Base64-encoded content for direct upload.",
    )
    promote_latest: bool = Field(default=True)


class GeneratedAssetUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    asset_type: Optional[str] = Field(default=None, min_length=1, max_length=48)
    description: Optional[str] = Field(default=None, max_length=1024)
    tags: Optional[List[str]] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = Field(default=None)


class ProjectRunListResponse(BaseModel):
    items: List[ProjectRunResponse]
    next_cursor: Optional[str] = None
    total_count: int


class ProjectLibraryListResponse(BaseModel):
    items: List[GeneratedAssetSummary]
    next_cursor: Optional[str] = None
    total_count: int


class ProjectOverviewMetrics(BaseModel):
    cost: Optional[Dict[str, Any]] = None
    drift: Optional[Dict[str, Any]] = None
    policy: Optional[Dict[str, Any]] = None


class ProjectConfigResponse(BaseModel):
    id: str
    project_id: str
    name: str
    slug: str
    description: Optional[str] = None
    config_name: Optional[str] = None
    kind: str
    payload: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectConfigCreateRequest(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    slug: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=1024)
    config_name: Optional[str] = Field(default=None, max_length=256)
    payload: Optional[str] = None
    kind: str = Field(default="tfreview", min_length=1, max_length=32)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    is_default: bool = False


class ProjectConfigUpdateRequest(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=160)
    description: Optional[str] = Field(default=None, max_length=1024)
    config_name: Optional[str] = Field(default=None, max_length=256)
    payload: Optional[str] = None
    kind: Optional[str] = Field(default=None, min_length=1, max_length=32)
    tags: Optional[List[str]] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = None
    is_default: Optional[bool] = None


class ProjectArtifactResponse(BaseModel):
    id: str
    project_id: str
    run_id: Optional[str] = None
    report_id: Optional[str] = None
    name: str
    relative_path: str
    storage_path: str
    media_type: Optional[str] = None
    size_bytes: Optional[int] = None
    checksum: Optional[str] = None
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class ProjectArtifactListResponse(BaseModel):
    items: List[ProjectArtifactResponse]
    next_cursor: Optional[str] = None
    total_count: int


class ProjectArtifactUpdateRequest(BaseModel):
    tags: Optional[List[str]] = Field(default=None)
    metadata: Optional[Dict[str, Any]] = None
    media_type: Optional[str] = None


class ProjectArtifactSyncRequest(BaseModel):
    prune_missing: bool = True


class ProjectArtifactSyncResponse(BaseModel):
    added: int
    updated: int
    removed: int
    files_indexed: int


class ProjectOverviewResponse(BaseModel):
    project: ProjectResponse
    run_count: int
    latest_run: Optional[ProjectRunResponse] = None
    library_asset_count: int
    config_count: int
    default_config: Optional[ProjectConfigResponse] = None
    artifact_count: int
    recent_assets: List[GeneratedAssetSummary]
    recent_artifacts: List[ProjectArtifactResponse] = Field(default_factory=list)
    metrics: ProjectOverviewMetrics = Field(default_factory=ProjectOverviewMetrics)
    last_activity_at: Optional[str] = None


@router.get("/", response_model=List[ProjectListItemResponse])
def projects_index(
    include_metadata: bool = Query(
        default=False,
        description="Include metadata payload for each project",
    ),
    search: Optional[str] = Query(
        default=None,
        description="Filter projects by name or slug using a case-insensitive search term",
    ),
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of projects to return",
    ),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> List[Dict[str, Any]]:
    try:
        return list_projects(
            session=session,
            include_metadata=include_metadata,
            include_stats=True,
            search=search,
            limit=limit,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc


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


@router.get("/{project_id}/configs", response_model=List[ProjectConfigResponse])
def project_configs_index(
    project_id: str,
    include_payload: bool = Query(default=False, description="Include inline payload bodies"),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> List[Dict[str, Any]]:
    try:
        records = list_project_configs(project_id=project_id, include_payload=include_payload, session=session)
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return [ProjectConfigResponse.model_validate(record) for record in records]


@router.post("/{project_id}/configs", response_model=ProjectConfigResponse, status_code=status.HTTP_201_CREATED)
def project_config_create(
    project_id: str,
    payload: ProjectConfigCreateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    if not (payload.config_name and payload.config_name.strip()) and not (payload.payload and payload.payload.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either config_name referencing a saved config or an inline payload.",
        )
    try:
        record = create_project_config(
            project_id=project_id,
            name=payload.name,
            slug=payload.slug,
            description=payload.description,
            config_name=payload.config_name,
            payload=payload.payload,
            kind=payload.kind,
            tags=payload.tags,
            metadata=payload.metadata,
            is_default=payload.is_default,
            session=session,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return ProjectConfigResponse.model_validate(record)


@router.get("/{project_id}/configs/{config_id}", response_model=ProjectConfigResponse)
def project_config_detail(
    project_id: str,
    config_id: str,
    include_payload: bool = Query(default=True, description="Include inline payload bodies"),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    record = get_project_config(config_id, project_id=project_id, include_payload=include_payload, session=session)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="config not found")
    return ProjectConfigResponse.model_validate(record)


@router.patch("/{project_id}/configs/{config_id}", response_model=ProjectConfigResponse)
def project_config_update(
    project_id: str,
    config_id: str,
    payload: ProjectConfigUpdateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    try:
        updated = update_project_config(
            config_id,
            project_id=project_id,
            **data,
            session=session,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="config not found")
    return ProjectConfigResponse.model_validate(updated)


@router.delete(
    "/{project_id}/configs/{config_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def project_config_delete(
    project_id: str,
    config_id: str,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Response:
    deleted = delete_project_config(config_id, project_id=project_id, session=session)
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="config not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/runs", response_model=ProjectRunListResponse)
def project_runs_index(
    project_id: str,
    limit: int = Query(
        default=50,
        ge=1,
        le=200,
        description="Maximum number of runs to return",
    ),
    cursor: Optional[str] = Query(
        default=None,
        description="Opaque cursor referencing the last run from the previous page",
    ),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    try:
        runs = list_project_runs(
            project_id=project_id,
            limit=limit,
            cursor=cursor,
            session=session,
        )
        runs["items"] = [ProjectRunResponse.model_validate(run) for run in runs["items"]]
        return runs
    except ValueError as exc:
        detail = str(exc)
        status_code_value = (
            status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code_value, detail=detail) from exc


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


@router.post(
    "/{project_id}/runs/{run_id}/artifacts/sync",
    response_model=ProjectArtifactSyncResponse,
    status_code=status.HTTP_200_OK,
)
def project_run_artifact_sync(
    project_id: str,
    run_id: str,
    payload: ProjectArtifactSyncRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    try:
        result = sync_project_run_artifacts(
            project_id=project_id,
            run_id=run_id,
            prune_missing=payload.prune_missing,
            session=session,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return ProjectArtifactSyncResponse.model_validate(result)


@router.get("/{project_id}/artifacts", response_model=ProjectArtifactListResponse)
def project_artifacts_index(
    project_id: str,
    run_id: Optional[str] = Query(
        default=None,
        description="Filter artifacts by run identifier",
    ),
    limit: int = Query(
        default=100,
        ge=1,
        le=500,
        description="Maximum number of artifacts to return",
    ),
    cursor: Optional[str] = Query(default=None, description="Opaque cursor for pagination"),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    try:
        payload = list_project_artifacts(
            project_id=project_id,
            run_id=run_id,
            limit=limit,
            cursor=cursor,
            session=session,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    payload["items"] = [ProjectArtifactResponse.model_validate(item) for item in payload.get("items", [])]
    return ProjectArtifactListResponse.model_validate(payload)


@router.get("/{project_id}/artifacts/{artifact_id}", response_model=ProjectArtifactResponse)
def project_artifact_detail(
    project_id: str,
    artifact_id: str,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    record = get_project_artifact(artifact_id, project_id=project_id, session=session)
    if not record:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    return ProjectArtifactResponse.model_validate(record)


@router.patch("/{project_id}/artifacts/{artifact_id}", response_model=ProjectArtifactResponse)
def project_artifact_update(
    project_id: str,
    artifact_id: str,
    payload: ProjectArtifactUpdateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    data = payload.model_dump(exclude_unset=True)
    updated = update_project_artifact(
        artifact_id,
        project_id=project_id,
        **data,
        session=session,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    return ProjectArtifactResponse.model_validate(updated)


@router.get("/{project_id}/library", response_model=ProjectLibraryListResponse)
def project_library_index(
    project_id: str,
    include_versions: bool = Query(default=False, description="Include version history for each asset"),
    limit: int = Query(
        default=100,
        ge=1,
        le=200,
        description="Maximum number of assets to return",
    ),
    cursor: Optional[str] = Query(
        default=None,
        description="Opaque cursor referencing the last asset from the previous page",
    ),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    try:
        assets = list_generated_assets(
            project_id=project_id,
            include_versions=include_versions,
            limit=limit,
            cursor=cursor,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    assets["items"] = [GeneratedAssetSummary.model_validate(asset) for asset in assets["items"]]
    return assets


@router.get("/{project_id}/library/{asset_id}", response_model=GeneratedAssetSummary)
def project_library_detail(
    project_id: str,
    asset_id: str,
    include_versions: bool = Query(default=True),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> GeneratedAssetSummary:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    asset = get_generated_asset(
        asset_id,
        project_id=project_id,
        include_versions=include_versions,
        session=session,
    )
    if not asset:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
    return GeneratedAssetSummary.model_validate(asset)


@router.get("/{project_id}/overview", response_model=ProjectOverviewResponse)
def project_overview(
    project_id: str,
    recent_assets: int = Query(
        default=3,
        ge=1,
        le=25,
        description="Maximum number of recent assets to include",
    ),
    include_metadata: bool = Query(
        default=True,
        description="Include full metadata payload for the project",
    ),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    try:
        overview = get_project_overview(
            project_id=project_id,
            recent_assets=recent_assets,
            include_metadata=include_metadata,
            session=session,
        )
    except ValueError as exc:
        detail = str(exc)
        status_code_value = (
            status.HTTP_404_NOT_FOUND if "not found" in detail else status.HTTP_400_BAD_REQUEST
        )
        raise HTTPException(status_code=status_code_value, detail=detail) from exc

    latest_run_payload = overview.get("latest_run")
    overview["project"] = ProjectResponse.model_validate(overview["project"])
    overview["latest_run"] = (
        ProjectRunResponse.model_validate(latest_run_payload) if latest_run_payload else None
    )
    overview["recent_assets"] = [
        GeneratedAssetSummary.model_validate(asset) for asset in overview.get("recent_assets", [])
    ]
    overview["recent_artifacts"] = [
        ProjectArtifactResponse.model_validate(artifact) for artifact in overview.get("recent_artifacts", [])
    ]
    overview["default_config"] = (
        ProjectConfigResponse.model_validate(overview["default_config"])
        if overview.get("default_config")
        else None
    )
    overview["metrics"] = ProjectOverviewMetrics.model_validate(overview.get("metrics", {}))
    return overview


@router.post("/{project_id}/library", response_model=GeneratedAssetRegisterResponse, status_code=status.HTTP_201_CREATED)
def project_library_register(
    project_id: str,
    payload: GeneratedAssetCreateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> GeneratedAssetRegisterResponse:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    data_bytes: Optional[bytes] = None
    if payload.content_base64:
        try:
            data_bytes = base64.b64decode(payload.content_base64)
        except binascii.Error as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content_base64 must be valid base64") from exc

    artifact_source: Path | None = None
    if payload.artifact_path:
        if not payload.run_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="run_id is required when artifact_path is supplied",
            )
        try:
            artifact_source = get_run_artifact_path(
                project_id=project_id,
                run_id=payload.run_id,
                path=payload.artifact_path,
                session=session,
            )
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project or run not found")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ArtifactPathError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if data_bytes is None and artifact_source is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either content_base64 or artifact_path for asset content.",
        )

    try:
        result = register_generated_asset(
            project_id=project_id,
            name=payload.name,
            asset_type=payload.asset_type,
            description=payload.description,
            tags=payload.tags,
            metadata=payload.metadata,
            run_id=payload.run_id,
            report_id=payload.report_id,
            storage_filename=payload.storage_filename,
            source_path=artifact_source,
            data=data_bytes,
            media_type=payload.media_type,
            notes=payload.notes,
            session=session,
        )
    except (ValueError, FileExistsError) as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return GeneratedAssetRegisterResponse.model_validate(result)


@router.post(
    "/{project_id}/library/{asset_id}/versions",
    response_model=GeneratedAssetRegisterResponse,
    status_code=status.HTTP_201_CREATED,
)
def project_library_add_version(
    project_id: str,
    asset_id: str,
    payload: GeneratedAssetVersionCreateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> GeneratedAssetRegisterResponse:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    data_bytes: Optional[bytes] = None
    if payload.content_base64:
        try:
            data_bytes = base64.b64decode(payload.content_base64)
        except binascii.Error as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="content_base64 must be valid base64") from exc

    artifact_source: Path | None = None
    if payload.artifact_path:
        if not payload.run_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="run_id is required when artifact_path is supplied",
            )
        try:
            artifact_source = get_run_artifact_path(
                project_id=project_id,
                run_id=payload.run_id,
                path=payload.artifact_path,
                session=session,
            )
        except ValueError:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project or run not found")
        except FileNotFoundError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
        except ArtifactPathError as exc:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if data_bytes is None and artifact_source is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either content_base64 or artifact_path for asset content.",
        )

    try:
        result = add_generated_asset_version(
            asset_id,
            project_id=project_id,
            run_id=payload.run_id,
            report_id=payload.report_id,
            storage_filename=payload.storage_filename,
            source_path=artifact_source,
            data=data_bytes,
            media_type=payload.media_type,
            notes=payload.notes,
            promote_latest=payload.promote_latest,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return GeneratedAssetRegisterResponse.model_validate(result)


@router.patch("/{project_id}/library/{asset_id}", response_model=GeneratedAssetSummary)
def project_library_update(
    project_id: str,
    asset_id: str,
    payload: GeneratedAssetUpdateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> GeneratedAssetSummary:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    try:
        updated = update_generated_asset(
            asset_id,
            project_id=project_id,
            name=payload.name,
            asset_type=payload.asset_type,
            description=payload.description,
            tags=payload.tags,
            metadata=payload.metadata,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
    return GeneratedAssetSummary.model_validate(updated)


@router.delete(
    "/{project_id}/library/{asset_id}/versions/{version_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def project_library_delete_version(
    project_id: str,
    asset_id: str,
    version_id: str,
    remove_files: bool = True,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Response:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    deleted = delete_generated_asset_version(
        asset_id,
        version_id,
        project_id=project_id,
        remove_files=remove_files,
        session=session,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/{project_id}/library/{asset_id}/versions/{version_id}/download")
def project_library_version_download(
    project_id: str,
    asset_id: str,
    version_id: str,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> FileResponse:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    try:
        version = get_generated_asset_version(
            asset_id,
            version_id,
            project_id=project_id,
            session=session,
        )
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")
        path = get_generated_asset_version_path(
            asset_id,
            version_id,
            project_id=project_id,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    filename = version["display_path"] or path.name
    return FileResponse(path, filename=filename)


@router.get("/{project_id}/library/{asset_id}/versions/{version_id}/diff")
def project_library_version_diff(
    project_id: str,
    asset_id: str,
    version_id: str,
    against: str = Query(..., description="Version ID to diff against"),
    ignore_whitespace: bool = Query(False, description="Ignore whitespace when generating diff"),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    if version_id == against:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Versions must be different")
    try:
        payload = diff_generated_asset_versions(
            asset_id,
            base_version_id=against,
            compare_version_id=version_id,
            project_id=project_id,
            ignore_whitespace=ignore_whitespace,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    return payload


@router.delete(
    "/{project_id}/library/{asset_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    response_class=Response,
)
def project_library_delete(
    project_id: str,
    asset_id: str,
    remove_files: bool = Query(default=False, description="Remove stored files from disk"),
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Response:
    project = get_project(project_id=project_id, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")

    deleted = delete_generated_asset(
        asset_id,
        project_id=project_id,
        remove_files=remove_files,
        session=session,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
