from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, Response, UploadFile, status
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field, ValidationError
from sqlalchemy.orm import Session

from api.routes.auth import CurrentUser
from api.dependencies import require_current_user
from backend.generators.blueprints import render_blueprint_bundle
from backend.generators.models import BlueprintRequest
from backend.generators.registry import get_generator_definition
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
    list_generated_asset_version_files,
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
from backend.terraform_validation import TerraformSourceFile, validate_terraform_sources
from backend.utils.logging import get_logger, log_context


router = APIRouter(prefix="/projects", tags=["projects"])
LOGGER = get_logger(__name__)


def _value_error_to_http(exc: ValueError) -> HTTPException:
    detail = str(exc)
    status_code_value = status.HTTP_404_NOT_FOUND if "not found" in detail.lower() else status.HTTP_400_BAD_REQUEST
    return HTTPException(status_code=status_code_value, detail=detail)


def _merge_tags(*tag_lists: Optional[List[str]]) -> List[str]:
    merged: List[str] = []
    seen: set[str] = set()
    for tags in tag_lists:
        for tag in tags or []:
            cleaned = (tag or "").strip()
            if not cleaned or cleaned in seen:
                continue
            merged.append(cleaned)
            seen.add(cleaned)
    return merged


def _get_project_or_404(identifier: str, session: Session) -> Dict[str, Any]:
    project = get_project(project_id=identifier, session=session)
    if not project and identifier:
        project = get_project(slug=identifier, session=session)
    if not project:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="project not found")
    return project


def _extract_environment(payload: Dict[str, Any]) -> Optional[str]:
    value = payload.get("environment")
    if isinstance(value, str):
        cleaned = value.strip()
        if cleaned:
            return cleaned
    return None


def _build_generator_asset_name(definition, payload: Dict[str, Any], *, options: ProjectGeneratorRunOptions, generated_at: datetime) -> str:
    candidate = (options.asset_name or "").strip() if options.asset_name else ""
    if candidate:
        return candidate
    environment = _extract_environment(payload)
    base = definition.title
    if environment:
        base = f"{base} [{environment}]"
    return f"{base} - {generated_at.strftime('%Y-%m-%d %H:%M:%S')}"


def _build_blueprint_asset_name(name: str, *, options: ProjectGeneratorRunOptions, generated_at: datetime) -> str:
    candidate = (options.asset_name or "").strip() if options.asset_name else ""
    if candidate:
        return candidate
    base = name.strip() or "Blueprint"
    return f"{base} bundle - {generated_at.strftime('%Y-%m-%d %H:%M:%S')}"


def _build_generator_metadata(
    definition,
    payload: Dict[str, Any],
    *,
    generated_at: datetime,
    options: ProjectGeneratorRunOptions,
    extra: Optional[Dict[str, Any]] = None,
) -> Dict[str, Any]:
    metadata = dict(options.metadata or {})
    generator_meta = dict(metadata.get("generator") or {})
    generator_meta.update(
        {
            "slug": definition.slug,
            "title": definition.title,
            "provider": definition.provider,
            "service": definition.service,
            "template_path": definition.template_path,
        }
    )
    metadata["generator"] = generator_meta
    metadata["payload"] = payload
    metadata["generated_at"] = generated_at.replace(microsecond=0).isoformat()
    if extra:
        for key, value in extra.items():
            metadata.setdefault(key, value)
    return metadata


def _fingerprint_payload(payload: Dict[str, Any]) -> str:
    serialised = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()


def _mark_run_failure(
    run_id: str,
    project_id: str,
    *,
    message: str,
    started_at: datetime,
    session: Session,
) -> None:
    update_project_run(
        run_id,
        project_id=project_id,
        status="failed",
        summary={"error": message},
        started_at=started_at,
        finished_at=datetime.now(timezone.utc),
        session=session,
    )


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
    report_id: Optional[str] = None


class ProjectRunCreateRequest(BaseModel):
    label: str = Field(..., min_length=1, max_length=128)
    kind: str = Field(..., min_length=1, max_length=48)
    parameters: Dict[str, Any] = Field(default_factory=dict)
    status: Optional[str] = Field(default="queued", min_length=1, max_length=32)
    triggered_by: Optional[str] = Field(default=None, max_length=320)
    projects_root: Optional[str] = None
    report_id: Optional[str] = None


class ProjectRunUpdateRequest(BaseModel):
    status: Optional[str] = Field(default=None, min_length=1, max_length=32)
    summary: Optional[Dict[str, Any]] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None
    report_id: Optional[str] = None


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
    validation_summary: Optional[Dict[str, Any]] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    payload_fingerprint: Optional[str] = None


class GeneratedAssetVersionFileResponse(BaseModel):
    id: str
    version_id: str
    project_id: str
    path: str
    storage_path: str
    checksum: Optional[str] = None
    size_bytes: Optional[int] = None
    media_type: Optional[str] = None
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


class ProjectGeneratorRunOptions(BaseModel):
    asset_name: Optional[str] = Field(default=None, max_length=160)
    description: Optional[str] = Field(default=None, max_length=1024)
    tags: List[str] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    notes: Optional[str] = Field(default=None, max_length=2048)
    run_label: Optional[str] = Field(default=None, max_length=128)
    force_save: bool = Field(default=False)


class ProjectGeneratorRunRequest(BaseModel):
    payload: Dict[str, Any]
    options: ProjectGeneratorRunOptions = Field(default_factory=ProjectGeneratorRunOptions)


class GeneratorResponse(BaseModel):
    filename: str
    content: str


class ProjectGeneratorRunResponse(BaseModel):
    output: GeneratorResponse
    asset: GeneratedAssetSummary
    version: GeneratedAssetVersionSummary
    run: ProjectRunResponse


class BlueprintArtifactFile(BaseModel):
    path: str
    content: str


class ProjectBlueprintArtifact(BaseModel):
    archive_name: str
    archive_base64: str
    files: List[BlueprintArtifactFile]


class ProjectBlueprintRunRequest(BaseModel):
    blueprint: BlueprintRequest
    options: ProjectGeneratorRunOptions = Field(default_factory=ProjectGeneratorRunOptions)


class ProjectBlueprintRunResponse(BaseModel):
    artifact: ProjectBlueprintArtifact
    asset: GeneratedAssetSummary
    version: GeneratedAssetVersionSummary
    run: ProjectRunResponse


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
    project = _get_project_or_404(project_id, session)
    return project


@router.patch("/{project_id}", response_model=ProjectResponse)
def project_update(
    project_id: str,
    payload: ProjectUpdateRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> Dict[str, Any]:
    project = _get_project_or_404(project_id, session)
    try:
        updated = update_project(
            project["id"],
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
    project = _get_project_or_404(project_id, session)
    deleted = delete_project(project["id"], remove_files=remove_files, session=session)
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    try:
        records = list_project_configs(project_id=resolved_project_id, include_payload=include_payload, session=session)
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
    project = _get_project_or_404(project_id, session)
    if not (payload.config_name and payload.config_name.strip()) and not (payload.payload and payload.payload.strip()):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide either config_name referencing a saved config or an inline payload.",
        )
    try:
        record = create_project_config(
            project_id=project["id"],
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
    project = _get_project_or_404(project_id, session)
    record = get_project_config(config_id, project_id=project["id"], include_payload=include_payload, session=session)
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
    project = _get_project_or_404(project_id, session)
    data = payload.model_dump(exclude_unset=True)
    try:
        updated = update_project_config(
            config_id,
            project_id=project["id"],
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
    project = _get_project_or_404(project_id, session)
    deleted = delete_project_config(config_id, project_id=project["id"], session=session)
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
    project = _get_project_or_404(project_id, session)
    try:
        runs = list_project_runs(
            project_id=project["id"],
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
    project = _get_project_or_404(project_id, session)
    label = payload.label.strip()
    kind = payload.kind.strip()
    if not label:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="label cannot be empty")
    if not kind:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="kind cannot be empty")

    try:
        return create_project_run(
            project_id=project["id"],
            label=label,
            kind=kind,
            parameters=payload.parameters,
            status=(payload.status or "queued"),
            triggered_by=payload.triggered_by
            or (current_user.user.email if current_user.user else None),
            projects_root=Path(payload.projects_root).expanduser() if payload.projects_root else None,
            report_id=payload.report_id,
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    run = get_project_run(run_id=run_id, project_id=resolved_project_id, session=session)
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
    project = _get_project_or_404(project_id, session)
    status_value: Optional[str] = payload.status.strip() if payload.status else None
    if payload.status is not None and not status_value:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="status cannot be empty")

    updated = update_project_run(
        run_id=run_id,
        project_id=project["id"],
        status=status_value,
        summary=payload.summary,
        started_at=payload.started_at,
        finished_at=payload.finished_at,
        report_id=payload.report_id,
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    path_value = path or None
    try:
        return list_run_artifacts(project_id=resolved_project_id, run_id=run_id, path=path_value, session=session)
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    data = await file.read()
    try:
        return save_run_artifact(
            project_id=resolved_project_id,
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    try:
        artifact_path = get_run_artifact_path(project_id=resolved_project_id, run_id=run_id, path=path, session=session)
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    try:
        deleted = delete_run_artifact(project_id=resolved_project_id, run_id=run_id, path=path, session=session)
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    try:
        result = sync_project_run_artifacts(
            project_id=resolved_project_id,
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    try:
        payload = list_project_artifacts(
            project_id=resolved_project_id,
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
    project = _get_project_or_404(project_id, session)
    record = get_project_artifact(artifact_id, project_id=project["id"], session=session)
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
    project = _get_project_or_404(project_id, session)
    data = payload.model_dump(exclude_unset=True)
    updated = update_project_artifact(
        artifact_id,
        project_id=project["id"],
        **data,
        session=session,
    )
    if not updated:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="artifact not found")
    return ProjectArtifactResponse.model_validate(updated)


@router.post(
    "/{project_id}/generators/blueprints",
    response_model=ProjectBlueprintRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def project_generate_blueprint(
    project_id: str,
    payload: ProjectBlueprintRunRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> ProjectBlueprintRunResponse:
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]

    options = payload.options
    blueprint = payload.blueprint
    generated_at = datetime.now(timezone.utc)
    run_label = options.run_label or f"Blueprint {blueprint.name} ({generated_at.strftime('%Y-%m-%d %H:%M:%S')})"

    try:
        run_record = create_project_run(
            project_id=resolved_project_id,
            label=run_label,
            kind="generator/blueprint",
            status="running",
            parameters={
                "blueprint": blueprint.model_dump(),
            },
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    started_at = generated_at
    try:
        rendered = render_blueprint_bundle(blueprint)
    except Exception as exc:  # noqa: BLE001
        _mark_run_failure(run_record["id"], resolved_project_id, message=str(exc), started_at=started_at, session=session)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    asset_name = _build_blueprint_asset_name(blueprint.name, options=options, generated_at=generated_at)
    tags = _merge_tags(options.tags, ["generator", "blueprint"])
    metadata = dict(options.metadata or {})
    metadata.setdefault("blueprint", blueprint.model_dump())
    metadata.setdefault("generated_at", generated_at.replace(microsecond=0).isoformat())
    metadata.setdefault(
        "files",
        [
            file_info["path"]
            for file_info in rendered.get("files", [])
        ],
    )
    file_inputs = [
        {"path": file_info["path"], "content": file_info["content"], "media_type": "text/plain"}
        for file_info in rendered.get("files", [])
    ]
    validation_files = [
        TerraformSourceFile(path=file_info["path"], content=file_info["content"].encode("utf-8"))
        for file_info in rendered.get("files", [])
    ]
    validation_summary = validate_terraform_sources(validation_files)
    payload_fingerprint = _fingerprint_payload(blueprint.model_dump())
    version_metadata = {
        "blueprint_name": blueprint.name,
        "environments": list(blueprint.environments),
        "component_slugs": [component.slug for component in blueprint.components],
        "force_save": options.force_save,
    }
    metadata.setdefault("validation", validation_summary)

    validation_status = (validation_summary.get("status") or "").lower() if isinstance(validation_summary, dict) else ""
    if validation_status == "failed" and not options.force_save:
        _mark_run_failure(
            run_record["id"],
            resolved_project_id,
            message="Terraform validation failed",
            started_at=started_at,
            session=session,
        )
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            detail={
                "error": "validation_failed",
                "validation_summary": validation_summary,
            },
        )

    try:
        asset_result = register_generated_asset(
            project_id=resolved_project_id,
            name=asset_name,
            asset_type="blueprint_bundle",
            description=options.description,
            tags=tags,
            metadata=metadata,
            run_id=run_record["id"],
            storage_filename=rendered["archive_name"],
            data=rendered["archive_bytes"],
            media_type="application/zip",
            notes=options.notes,
            files=file_inputs,
            version_metadata=version_metadata,
            payload_fingerprint=payload_fingerprint,
            validation_summary=validation_summary,
            session=session,
        )
    except (ValueError, FileExistsError) as exc:
        _mark_run_failure(run_record["id"], resolved_project_id, message=str(exc), started_at=started_at, session=session)
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

    finished_at = datetime.now(timezone.utc)
    summary = {
        "asset_id": asset_result["asset"]["id"],
        "version_id": asset_result["version"]["id"],
        "artifact_type": "blueprint_bundle",
        "archive_name": rendered["archive_name"],
        "file_count": len(rendered.get("files", [])),
        "validation": validation_summary,
    }
    updated_run = update_project_run(
        run_record["id"],
        project_id=resolved_project_id,
        status="completed",
        summary=summary,
        started_at=started_at,
        finished_at=finished_at,
        session=session,
    ) or run_record

    files = [BlueprintArtifactFile(**item) for item in rendered.get("files", [])]
    artifact = ProjectBlueprintArtifact(
        archive_name=rendered["archive_name"],
        archive_base64=rendered["archive_base64"],
        files=files,
    )
    asset_payload = GeneratedAssetSummary.model_validate(asset_result["asset"])
    version_payload = GeneratedAssetVersionSummary.model_validate(asset_result["version"])
    run_payload = ProjectRunResponse.model_validate(updated_run)
    return ProjectBlueprintRunResponse(
        artifact=artifact,
        asset=asset_payload,
        version=version_payload,
        run=run_payload,
    )


@router.post(
    "/{project_id}/generators/{slug:path}",
    response_model=ProjectGeneratorRunResponse,
    status_code=status.HTTP_201_CREATED,
)
def project_generator_run(
    project_id: str,
    slug: str,
    payload: ProjectGeneratorRunRequest,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> ProjectGeneratorRunResponse:
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]

    try:
        definition = get_generator_definition(slug)
    except KeyError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    try:
        typed_payload = definition.model.model_validate(payload.payload)
    except ValidationError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=exc.errors()) from exc

    options = payload.options
    generated_at = datetime.now(timezone.utc)
    payload_dump = typed_payload.model_dump(exclude_none=True)
    run_label = options.run_label or f"{definition.title} ({generated_at.strftime('%Y-%m-%d %H:%M:%S')})"

    context_values = {
        "project_id": resolved_project_id,
        "project_slug": project.get("slug"),
        "generator_slug": definition.slug,
    }
    scoped_context = {key: value for key, value in context_values.items() if value}

    with log_context(**scoped_context):
        LOGGER.info(
            "Starting project generator run",
            extra={
                "run_label": run_label,
                "force_save": options.force_save,
                "has_tags": bool(options.tags),
            },
        )

        try:
            run_record = create_project_run(
                project_id=resolved_project_id,
                label=run_label,
                kind=f"generator/{definition.slug}",
                status="running",
                parameters={
                    "generator_slug": definition.slug,
                    "payload": payload_dump,
                },
                session=session,
            )
        except ValueError as exc:
            LOGGER.warning("Failed to create project run record", extra={"error": str(exc)})
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

        started_at = generated_at
        with log_context(run_id=run_record["id"]):
            try:
                rendered = definition.render(typed_payload)
            except ValueError as exc:
                LOGGER.warning("Generator render failed", extra={"error": str(exc)})
                _mark_run_failure(run_record["id"], resolved_project_id, message=str(exc), started_at=started_at, session=session)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
            except Exception as exc:  # noqa: BLE001
                LOGGER.exception("Unexpected error while rendering generator output")
                _mark_run_failure(run_record["id"], project_id, message=str(exc), started_at=started_at, session=session)
                raise

            asset_name = _build_generator_asset_name(definition, payload_dump, options=options, generated_at=generated_at)
            tags = _merge_tags(definition.tags, options.tags, ["generator", f"generator:{definition.slug}"])
            metadata = _build_generator_metadata(
                definition,
                payload_dump,
                generated_at=generated_at,
                options=options,
                extra={"output_filename": rendered["filename"]},
            )
            validation_files = [
                TerraformSourceFile(path=rendered["filename"], content=rendered["content"].encode("utf-8"))
            ]
            validation_summary = validate_terraform_sources(validation_files)
            metadata.setdefault("validation", validation_summary)
            payload_fingerprint = _fingerprint_payload(payload_dump)
            version_metadata = {
                "generator_slug": definition.slug,
                "environment": _extract_environment(payload_dump),
                "output_filename": rendered["filename"],
                "force_save": options.force_save,
            }

            validation_status = (validation_summary.get("status") or "").lower() if isinstance(validation_summary, dict) else ""
            LOGGER.info(
                "Terraform validation completed",
                extra={
                    "validation_status": validation_status or "unknown",
                    "force_save_override": options.force_save,
                },
            )
            if validation_status == "failed" and not options.force_save:
                LOGGER.warning("Terraform validation failed", extra={"validation_summary": validation_summary})
                _mark_run_failure(
                    run_record["id"],
                    resolved_project_id,
                    message="Terraform validation failed",
                    started_at=started_at,
                    session=session,
                )
                raise HTTPException(
                    status.HTTP_400_BAD_REQUEST,
                    detail={
                        "error": "validation_failed",
                        "validation_summary": validation_summary,
                    },
                )

            try:
                asset_result = register_generated_asset(
                    project_id=resolved_project_id,
                    name=asset_name,
                    asset_type="terraform_config",
                    description=options.description,
                    tags=tags,
                    metadata=metadata,
                    run_id=run_record["id"],
                    storage_filename=rendered["filename"],
                    data=rendered["content"].encode("utf-8"),
                    media_type="text/plain",
                    notes=options.notes,
                    version_metadata=version_metadata,
                    payload_fingerprint=payload_fingerprint,
                    validation_summary=validation_summary,
                    session=session,
                )
            except (ValueError, FileExistsError) as exc:
                LOGGER.warning("Failed to register generated asset", extra={"error": str(exc)})
                _mark_run_failure(run_record["id"], resolved_project_id, message=str(exc), started_at=started_at, session=session)
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc

            finished_at = datetime.now(timezone.utc)
            summary = {
                "asset_id": asset_result["asset"]["id"],
                "version_id": asset_result["version"]["id"],
                "filename": rendered["filename"],
                "generator_slug": definition.slug,
                "validation": validation_summary,
            }
            updated_run = update_project_run(
                run_record["id"],
                project_id=resolved_project_id,
                status="completed",
                summary=summary,
                started_at=started_at,
                finished_at=finished_at,
                session=session,
            ) or run_record

            asset_payload = GeneratedAssetSummary.model_validate(asset_result["asset"])
            version_payload = GeneratedAssetVersionSummary.model_validate(asset_result["version"])
            run_payload = ProjectRunResponse.model_validate(updated_run)
            output_payload = GeneratorResponse(**rendered)

            with log_context(asset_id=summary["asset_id"], asset_version_id=summary["version_id"]):
                LOGGER.info(
                    "Generator run completed",
                    extra={
                        "asset_name": asset_name,
                        "validation_status": validation_status or "skipped",
                        "run_status": updated_run.get("status"),
                    },
                )

            return ProjectGeneratorRunResponse(
                output=output_payload,
                asset=asset_payload,
                version=version_payload,
                run=run_payload,
            )


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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]
    try:
        assets = list_generated_assets(
            project_id=resolved_project_id,
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
    project = _get_project_or_404(project_id, session)
    asset = get_generated_asset(
        asset_id,
        project_id=project["id"],
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
    project = _get_project_or_404(project_id, session)
    try:
        overview = get_project_overview(
            project_id=project["id"],
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]

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
                project_id=resolved_project_id,
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
            project_id=resolved_project_id,
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
    project = _get_project_or_404(project_id, session)
    resolved_project_id = project["id"]

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
                project_id=resolved_project_id,
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
            project_id=resolved_project_id,
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
    project = _get_project_or_404(project_id, session)
    try:
        updated = update_generated_asset(
            asset_id,
            project_id=project["id"],
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
    project = _get_project_or_404(project_id, session)
    deleted = delete_generated_asset_version(
        asset_id,
        version_id,
        project_id=project["id"],
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
    project = _get_project_or_404(project_id, session)
    try:
        version = get_generated_asset_version(
            asset_id,
            version_id,
            project_id=project["id"],
            session=session,
        )
        if not version:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="version not found")
        path = get_generated_asset_version_path(
            asset_id,
            version_id,
            project_id=project["id"],
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except FileNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    filename = version["display_path"] or path.name
    return FileResponse(path, filename=filename)


@router.get(
    "/{project_id}/library/{asset_id}/versions/{version_id}/files",
    response_model=List[GeneratedAssetVersionFileResponse],
)
def project_library_version_files(
    project_id: str,
    asset_id: str,
    version_id: str,
    _current_user: CurrentUser = Depends(require_current_user),
    session: Session = Depends(get_session_dependency),
) -> List[GeneratedAssetVersionFileResponse]:
    project = _get_project_or_404(project_id, session)
    try:
        files = list_generated_asset_version_files(
            asset_id=asset_id,
            version_id=version_id,
            project_id=project["id"],
            session=session,
        )
    except ValueError as exc:
        raise _value_error_to_http(exc) from exc
    return [GeneratedAssetVersionFileResponse.model_validate(item) for item in files]


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
    project = _get_project_or_404(project_id, session)
    if version_id == against:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Versions must be different")
    try:
        payload = diff_generated_asset_versions(
            asset_id,
            base_version_id=against,
            compare_version_id=version_id,
            project_id=project["id"],
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
    project = _get_project_or_404(project_id, session)
    deleted = delete_generated_asset(
        asset_id,
        project_id=project["id"],
        remove_files=remove_files,
        session=session,
    )
    if not deleted:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="asset not found")
    return Response(status_code=status.HTTP_204_NO_CONTENT)
