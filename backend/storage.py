from __future__ import annotations

import hashlib
import difflib
import json
import re
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple, Sequence
from uuid import uuid4
import shutil

from sqlalchemy import and_, func, or_, select, text
from sqlalchemy.orm import Session

from backend.db.models import (
    Config,
    Report,
    ReportComment,
    Setting,
    Project,
    ProjectRun,
    ProjectConfig,
    ProjectArtifact,
    GeneratedAsset,
    GeneratedAssetVersion,
    GeneratedAssetVersionFile,
    format_timestamp,
)
from backend.db.session import DEFAULT_DB_PATH as _DEFAULT_DB_PATH, init_models, session_scope

DEFAULT_DB_PATH = _DEFAULT_DB_PATH
DEFAULT_PROJECTS_ROOT = Path("data/projects")
MAX_VERSION_TEXT_BYTES = 512 * 1024


@dataclass
class VersionFilePayload:
    path: str
    content: bytes
    media_type: str | None = None


@dataclass
class VersionFileView:
    path: str
    storage_path: str
    checksum: str | None
    size_bytes: int | None
    media_type: str | None


class ProjectNotFoundError(Exception):
    """Raised when a project cannot be located in the database."""


class ProjectRunNotFoundError(Exception):
    """Raised when a project run cannot be located or is mismatched."""


class ArtifactPathError(Exception):
    """Raised when a requested artifact path is invalid or escapes the run root."""


class ReportNotFoundError(Exception):
    """Raised when a report cannot be located in the database."""


class WorkspacePathError(ValueError):
    """Raised when resolving project workspace paths fails."""


REVIEW_STATUS_CHOICES: set[str] = {
    "pending",
    "in_review",
    "changes_requested",
    "resolved",
    "waived",
}
DEFAULT_REVIEW_STATUS = "pending"


def get_projects_root(base_path: Path | None = None) -> Path:
    root = (base_path or DEFAULT_PROJECTS_ROOT).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def get_project_workspace(project: Project | Dict[str, Any], base_path: Path | None = None) -> Path:
    """
    Return the on-disk workspace root for the provided project, ensuring it exists.
    """

    if isinstance(project, dict):
        raw = project.get("root_path")
        slug = project.get("slug")
    else:
        raw = project.root_path
        slug = project.slug

    if raw:
        root = Path(str(raw))
    else:
        derived_slug = slug or f"project-{uuid4().hex[:8]}"
        root = get_projects_root(base_path) / derived_slug

    root = root.expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def resolve_workspace_path(
    project_root: Path,
    token: str | None,
    *,
    label: str = "path",
    require_file: bool | None = None,
) -> Path:
    """
    Resolve a project-relative path to an absolute location inside the workspace, enforcing boundaries.
    """

    relative_value = (token or "").strip() or "."
    relative_path = Path(relative_value)
    if relative_path.is_absolute():
        raise WorkspacePathError(f"{label} must be relative to the project workspace")

    candidate = (project_root / relative_path).resolve()
    try:
        candidate.relative_to(project_root)
    except ValueError as exc:
        raise WorkspacePathError(f"{label} '{relative_value}' escapes the project workspace") from exc

    if not candidate.exists():
        raise WorkspacePathError(f"{label} '{relative_value}' not found in project workspace")

    if require_file is True and not candidate.is_file():
        raise WorkspacePathError(f"{label} '{relative_value}' must be an existing file in the project workspace")
    if require_file is False and not candidate.is_dir():
        raise WorkspacePathError(f"{label} '{relative_value}' must be a directory in the project workspace")
    return candidate


def resolve_workspace_paths(project_root: Path, tokens: Sequence[str] | None) -> List[Path]:
    values = list(tokens or [])
    if not values:
        values = ["."]
    resolved: List[Path] = []
    for index, value in enumerate(values, start=1):
        resolved.append(resolve_workspace_path(project_root, value, label=f"path #{index}"))
    return resolved


def resolve_workspace_file(project_root: Path, token: str | None, *, label: str) -> Path:
    return resolve_workspace_path(project_root, token, label=label, require_file=True)


def _slugify(value: str) -> str:
    slug = re.sub(r"[^a-z0-9]+", "-", value.lower()).strip("-")
    if not slug:
        return f"project-{uuid4().hex[:8]}"
    return slug


def _ensure_unique_slug(db: Session, slug: str) -> str:
    base_slug = slug
    counter = 2
    stmt = select(Project.slug).where(Project.slug == slug)
    while db.execute(stmt).scalar_one_or_none():
        slug = f"{base_slug}-{counter}"
        counter += 1
        stmt = select(Project.slug).where(Project.slug == slug)
    return slug


def _ensure_project_config_slug(db: Session, project_id: str, slug: str) -> str:
    base_slug = slug
    counter = 2
    stmt = select(ProjectConfig.id).where(
        ProjectConfig.project_id == project_id,
        ProjectConfig.slug == slug,
    )
    while db.execute(stmt).scalar_one_or_none():
        slug = f"{base_slug}-{counter}"
        counter += 1
        stmt = select(ProjectConfig.id).where(
            ProjectConfig.project_id == project_id,
            ProjectConfig.slug == slug,
        )
    return slug


def _has_project_default_config(db: Session, project_id: str) -> bool:
    stmt = (
        select(ProjectConfig.id)
        .where(ProjectConfig.project_id == project_id, ProjectConfig.is_default.is_(True))
        .limit(1)
    )
    return db.execute(stmt).scalar_one_or_none() is not None


def _mark_default_project_config(db: Session, project_id: str, config: ProjectConfig | None) -> None:
    stmt = select(ProjectConfig).where(ProjectConfig.project_id == project_id, ProjectConfig.is_default.is_(True))
    for record in db.execute(stmt).scalars():
        record.is_default = False
    if config is not None:
        config.is_default = True
    db.flush()


def _ensure_project_default_config(db: Session, project_id: str) -> None:
    if _has_project_default_config(db, project_id):
        return
    fallback = (
        select(ProjectConfig)
        .where(ProjectConfig.project_id == project_id)
        .order_by(ProjectConfig.updated_at.desc(), ProjectConfig.name.asc())
        .limit(1)
    )
    record = db.execute(fallback).scalars().first()
    if record:
        record.is_default = True
        db.flush()


def _get_project_or_raise(db: Session, project_id: str) -> Project:
    project = db.get(Project, project_id)
    if not project:
        raise ProjectNotFoundError(project_id)
    return project


def _get_project_and_run_or_raise(db: Session, project_id: str, run_id: str) -> Tuple[Project, ProjectRun]:
    project = _get_project_or_raise(db, project_id)
    run = db.get(ProjectRun, run_id)
    if not run or run.project_id != project.id:
        raise ProjectRunNotFoundError(run_id)
    return project, run


def _resolve_project_root(project: Project, projects_root: Path | None = None) -> Path:
    root_base = get_projects_root(projects_root)
    project_root = Path(project.root_path) if project.root_path else root_base / project.slug
    project_root.mkdir(parents=True, exist_ok=True)
    return project_root


def _ensure_run_directory(
    db: Session,
    project: Project,
    run: ProjectRun,
    projects_root: Path | None = None,
) -> Path:
    project_root = _resolve_project_root(project, projects_root)
    runs_root = project_root / "runs"
    runs_root.mkdir(parents=True, exist_ok=True)

    if run.artifacts_path:
        run_dir = Path(run.artifacts_path).expanduser()
    else:
        run_dir = runs_root / run.id
        run.artifacts_path = str(run_dir.resolve())
        db.flush()

    run_dir = run_dir.resolve()
    run_dir.mkdir(parents=True, exist_ok=True)

    try:
        run_dir.relative_to(project_root.resolve())
    except ValueError as exc:
        raise ArtifactPathError("run directory escapes project root") from exc

    return run_dir


def _resolve_artifact_path(run_dir: Path, relative_path: str | None) -> Path:
    if relative_path is None:
        return run_dir

    cleaned = relative_path.strip()
    if cleaned in {"", ".", "./"}:
        return run_dir

    candidate = (run_dir / cleaned).resolve()
    try:
        candidate.relative_to(run_dir)
    except ValueError as exc:
        raise ArtifactPathError("artifact path escapes run directory") from exc
    return candidate


def _record_project_artifact(
    db: Session,
    project: Project,
    *,
    run: ProjectRun | None,
    relative_path: str,
    absolute_path: Path,
    report: Report | None = None,
    media_type: str | None = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> ProjectArtifact:
    relative = _normalise_relative_path(relative_path)
    record = (
        db.execute(
            select(ProjectArtifact).where(
                ProjectArtifact.project_id == project.id,
                ProjectArtifact.run_id == (run.id if run else None),
                ProjectArtifact.relative_path == relative,
            )
        )
        .scalars()
        .first()
    )
    tags_value = _normalise_tags(tags) if tags is not None else None
    metadata_value = dict(metadata or {}) if metadata is not None else None

    size_bytes: int | None = None
    checksum: str | None = None
    if absolute_path.exists() and absolute_path.is_file():
        stat = absolute_path.stat()
        size_bytes = int(stat.st_size)
        checksum = _hash_file(absolute_path)

    if record is None:
        record = ProjectArtifact(
            project_id=project.id,
            run_id=run.id if run else None,
            report_id=report.id if report else None,
            name=absolute_path.name,
            relative_path=relative,
            storage_path=str(absolute_path),
            media_type=media_type,
            size_bytes=size_bytes,
            checksum=checksum,
            tags=tags_value or [],
            artifact_metadata=metadata_value or {},
        )
        db.add(record)
    else:
        record.name = absolute_path.name
        record.storage_path = str(absolute_path)
        record.media_type = media_type or record.media_type
        record.size_bytes = size_bytes
        record.checksum = checksum
        if tags_value is not None:
            record.tags = tags_value
        if metadata_value is not None:
            record.artifact_metadata = metadata_value
        if report:
            record.report_id = report.id
    db.flush()
    return record


def _ensure_report_review_columns(db: Session) -> None:
    """Add review workflow columns to reports table if they are missing."""
    existing_columns = {
        row[1]
        for row in db.execute(text("PRAGMA table_info(reports)"))
    }
    if "review_status" not in existing_columns:
        db.execute(
            text("ALTER TABLE reports ADD COLUMN review_status TEXT NOT NULL DEFAULT 'pending'")
        )
    if "review_assignee" not in existing_columns:
        db.execute(
            text("ALTER TABLE reports ADD COLUMN review_assignee TEXT")
        )
    if "review_due_at" not in existing_columns:
        db.execute(
            text("ALTER TABLE reports ADD COLUMN review_due_at TIMESTAMP")
        )
    if "review_notes" not in existing_columns:
        db.execute(
            text("ALTER TABLE reports ADD COLUMN review_notes TEXT")
        )
    if "updated_at" not in existing_columns:
        db.execute(text("ALTER TABLE reports ADD COLUMN updated_at TIMESTAMP"))
    db.execute(
        text("UPDATE reports SET updated_at = created_at WHERE updated_at IS NULL")
    )
    db.execute(
        text("UPDATE reports SET review_status = 'pending' WHERE review_status IS NULL OR review_status = ''")
    )


def _apply_report_review_metadata(report: Report, metadata: Optional[Dict[str, Any]]) -> None:
    if not metadata:
        return
    status_raw = metadata.get("review_status") or metadata.get("status")
    assignee_raw = metadata.get("review_assignee") or metadata.get("assignee")
    due_raw = metadata.get("review_due_at") or metadata.get("due_at")
    notes_raw = metadata.get("review_notes") or metadata.get("notes")

    if status_raw is not None:
        status_value = _normalise_review_status(status_raw)
        report.review_status = status_value or DEFAULT_REVIEW_STATUS
    if assignee_raw is not None:
        cleaned = assignee_raw.strip() if isinstance(assignee_raw, str) else assignee_raw
        report.review_assignee = cleaned or None
    if due_raw is not None:
        report.review_due_at = _parse_datetime(due_raw)
    if notes_raw is not None:
        if isinstance(notes_raw, str):
            report.review_notes = notes_raw.strip() or None
        else:
            report.review_notes = None
    report.updated_at = datetime.now(timezone.utc)


def _normalise_tags(values: Optional[List[str]]) -> List[str]:
    if not values:
        return []
    normalised: List[str] = []
    seen: set[str] = set()
    for raw in values:
        if raw is None:
            continue
        cleaned = raw.strip()
        if not cleaned or cleaned in seen:
            continue
        normalised.append(cleaned)
        seen.add(cleaned)
    return normalised


def _normalise_relative_path(value: str) -> str:
    cleaned = value.strip().replace("\\", "/")
    cleaned = re.sub(r"^\./+", "", cleaned)
    cleaned = cleaned.strip("/")
    if not cleaned:
        return "."
    return cleaned


def _sanitize_storage_name(value: str) -> str:
    candidate = Path(value).name
    if not candidate:
        raise ValueError("storage filename cannot be empty")
    return candidate


def _hash_file(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(1024 * 1024)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _normalise_review_status(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    candidate = value.strip().lower()
    if not candidate:
        return DEFAULT_REVIEW_STATUS
    if candidate not in REVIEW_STATUS_CHOICES:
        raise ValueError(f"invalid review status: {value!r}")
    return candidate


def _parse_datetime(value: Optional[str | datetime]) -> Optional[datetime]:
    if value is None:
        return None
    if isinstance(value, datetime):
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)
    if isinstance(value, str):
        cleaned = value.strip()
        if not cleaned:
            return None
        if cleaned.endswith("Z"):
            cleaned = f"{cleaned[:-1]}+00:00"
        try:
            parsed = datetime.fromisoformat(cleaned)
        except ValueError as exc:
            raise ValueError(f"invalid datetime string: {value!r}") from exc
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.astimezone(timezone.utc)
    raise TypeError("datetime value must be str or datetime instance")


def _resolve_asset_bytes(source_path: Path | None, data: bytes | None) -> bytes:
    if data is not None:
        return data
    if source_path is None:
        raise ValueError("either 'data' or 'source_path' must be provided")
    resolved = source_path.expanduser()
    if not resolved.exists() or not resolved.is_file():
        raise FileNotFoundError(str(resolved))
    return resolved.read_bytes()


def _coerce_bytes(value: bytes | str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        return value.encode("utf-8")
    raise TypeError("file content must be bytes or str")


def _prepare_version_files(files: Optional[Sequence[Dict[str, Any]]]) -> List[VersionFilePayload]:
    prepared: List[VersionFilePayload] = []
    if not files:
        return prepared
    seen: set[str] = set()
    for index, file_entry in enumerate(files, start=1):
        if not isinstance(file_entry, dict):
            raise ValueError(f"files[{index}] must be a mapping with 'path' and 'content'")
        raw_path = file_entry.get("path")
        if not raw_path or not isinstance(raw_path, str):
            raise ValueError(f"files[{index}] must include a non-empty string path")
        cleaned_path = _normalise_relative_path(raw_path)
        if cleaned_path in {".", ""}:
            raise ValueError(f"files[{index}] path cannot reference the root directory")
        if cleaned_path in seen:
            raise ValueError(f"duplicate file path detected: {cleaned_path}")
        seen.add(cleaned_path)
        raw_content = file_entry.get("content")
        if raw_content is None:
            raise ValueError(f"files[{index}] must include content")
        try:
            content_bytes = _coerce_bytes(raw_content)
        except TypeError as exc:
            raise ValueError(f"files[{index}] content must be bytes or string") from exc
        media_type = file_entry.get("media_type")
        if media_type is not None and not isinstance(media_type, str):
            raise ValueError(f"files[{index}] media_type must be a string if provided")
        prepared.append(VersionFilePayload(path=cleaned_path, content=content_bytes, media_type=media_type))
    return prepared


def _create_asset_version(
    db: Session,
    project: Project,
    asset: GeneratedAsset,
    *,
    run: ProjectRun | None,
    report: Report | None,
    storage_name: str,
    content_bytes: bytes,
    media_type: str | None,
    notes: str | None,
    projects_root: Path | None,
    files: Optional[List[VersionFilePayload]] = None,
    version_metadata: Optional[Dict[str, Any]] = None,
    validation_summary: Optional[Dict[str, Any]] = None,
    payload_fingerprint: str | None = None,
) -> GeneratedAssetVersion:
    version_id = str(uuid4())
    library_dir = _ensure_library_directory(project, asset.id, version_id, projects_root)
    destination = library_dir / storage_name
    if destination.exists():
        raise FileExistsError(str(destination))

    checksum = hashlib.sha256(content_bytes).hexdigest()
    with open(destination, "wb") as handle:
        handle.write(content_bytes)

    version = GeneratedAssetVersion(
        id=version_id,
        asset_id=asset.id,
        project_id=project.id,
        run_id=run.id if run else None,
        report_id=report.id if report else None,
        storage_path=str(destination),
        display_path=storage_name,
        checksum=checksum,
        size_bytes=len(content_bytes),
        media_type=media_type,
        notes=notes,
        version_metadata=dict(version_metadata or {}),
        validation_summary=(dict(validation_summary) if isinstance(validation_summary, dict) else None),
        payload_fingerprint=payload_fingerprint,
    )
    db.add(version)
    db.flush()
    _record_version_file(db, version, relative_path=storage_name, absolute_path=destination, media_type=media_type)
    for file_payload in files or []:
        file_destination = _write_version_file(library_dir, file_payload.path, file_payload.content)
        _record_version_file(db, version, relative_path=file_payload.path, absolute_path=file_destination, media_type=file_payload.media_type)
    db.flush()
    return version


def _read_text_file(path: Path, *, max_bytes: int = MAX_VERSION_TEXT_BYTES) -> str:
    if not path.exists() or not path.is_file():
        raise FileNotFoundError(str(path))
    size = path.stat().st_size
    if size > max_bytes:
        raise ValueError("file too large for text preview")
    data = path.read_bytes()
    try:
        return data.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("file is not valid UTF-8 text") from exc


def _ensure_library_directory(
    project: Project,
    asset_id: str,
    version_id: str,
    projects_root: Path | None = None,
) -> Path:
    project_root = _resolve_project_root(project, projects_root)
    library_root = project_root / "library" / asset_id / version_id
    library_root.mkdir(parents=True, exist_ok=True)
    return library_root


def _write_version_file(root: Path, relative_path: str, content: bytes) -> Path:
    target = (root / relative_path).resolve()
    try:
        target.relative_to(root.resolve())
    except ValueError as exc:
        raise ValueError(f"file path '{relative_path}' escapes version directory") from exc
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise FileExistsError(f"file '{relative_path}' already exists in version directory")
    with open(target, "wb") as handle:
        handle.write(content)
    return target


def _record_version_file(
    db: Session,
    version: GeneratedAssetVersion,
    *,
    relative_path: str,
    absolute_path: Path,
    media_type: str | None,
) -> None:
    checksum = _hash_file(absolute_path)
    stat = absolute_path.stat()
    record = GeneratedAssetVersionFile(
        project_id=version.project_id,
        version_id=version.id,
        path=_normalise_relative_path(relative_path),
        storage_path=str(absolute_path),
        checksum=checksum,
        size_bytes=int(stat.st_size),
        media_type=media_type,
    )
    db.add(record)


def _get_version_file_views(version: GeneratedAssetVersion) -> Dict[str, VersionFileView]:
    if getattr(version, "files", None):
        records = {
            file_record.path: VersionFileView(
                path=file_record.path,
                storage_path=file_record.storage_path,
                checksum=file_record.checksum,
                size_bytes=file_record.size_bytes,
                media_type=file_record.media_type,
            )
            for file_record in version.files
        }
        if records:
            return records
    fallback = VersionFileView(
        path=version.display_path,
        storage_path=version.storage_path,
        checksum=version.checksum,
        size_bytes=version.size_bytes,
        media_type=version.media_type,
    )
    return {fallback.path: fallback}


def _get_asset_library_root(
    project: Project,
    asset_id: str,
    projects_root: Path | None = None,
) -> Path:
    project_root = _resolve_project_root(project, projects_root)
    return project_root / "library" / asset_id


def create_project(
    name: str,
    *,
    description: str | None = None,
    slug: str | None = None,
    metadata: Dict[str, Any] | None = None,
    projects_root: Path | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    normalised_name = name.strip()
    if not normalised_name:
        raise ValueError("project name cannot be empty")
    metadata = dict(metadata or {})
    root_base = get_projects_root(projects_root)
    with _get_session(session, db_path) as db:
        existing = db.execute(select(Project).where(Project.name == normalised_name)).scalars().first()
        if existing:
            raise ValueError(f"project with name '{normalised_name}' already exists")
        slug_value = _slugify(slug.strip() if slug else normalised_name)
        slug_value = _ensure_unique_slug(db, slug_value)
        project = Project(
            name=normalised_name,
            slug=slug_value,
            description=description.strip() if description else None,
            project_metadata=metadata,
            root_path=str(root_base / slug_value),
        )
        db.add(project)
        db.flush()
        project_root = Path(project.root_path)
        project_root.mkdir(parents=True, exist_ok=True)
        (project_root / "runs").mkdir(parents=True, exist_ok=True)
        return project.to_dict()


def list_projects(
    *,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
    include_metadata: bool = False,
    include_stats: bool = True,
    search: str | None = None,
    limit: int | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        stmt = select(Project).order_by(Project.updated_at.desc(), Project.created_at.desc())
        if search:
            pattern = f"%{search.lower()}%"
            stmt = stmt.where(
                or_(
                    func.lower(Project.name).like(pattern),
                    func.lower(Project.slug).like(pattern),
                )
            )
        if limit is not None:
            stmt = stmt.limit(limit)
        projects = list(db.execute(stmt).scalars())
        if not include_stats:
            return [project.to_dict(include_metadata=include_metadata) for project in projects]

        project_ids = [project.id for project in projects]
        run_counts: Dict[str, int] = {}
        latest_runs: Dict[str, ProjectRun] = {}
        assets_count: Dict[str, int] = {}
        assets_updated: Dict[str, datetime] = {}
        config_counts: Dict[str, int] = {}
        artifact_counts: Dict[str, int] = {}
        artifact_updated: Dict[str, datetime] = {}

        if project_ids:
            run_count_stmt = (
                select(ProjectRun.project_id, func.count(ProjectRun.id))
                .where(ProjectRun.project_id.in_(project_ids))
                .group_by(ProjectRun.project_id)
            )
            for project_id, count in db.execute(run_count_stmt):
                run_counts[project_id] = int(count or 0)

            latest_run_stmt = (
                select(ProjectRun)
                .where(ProjectRun.project_id.in_(project_ids))
                .order_by(ProjectRun.project_id, ProjectRun.created_at.desc(), ProjectRun.id.desc())
            )
            for run in db.execute(latest_run_stmt).scalars():
                if run.project_id not in latest_runs:
                    latest_runs[run.project_id] = run

            asset_count_stmt = (
                select(GeneratedAsset.project_id, func.count(GeneratedAsset.id))
                .where(GeneratedAsset.project_id.in_(project_ids))
                .group_by(GeneratedAsset.project_id)
            )
            for project_id, count in db.execute(asset_count_stmt):
                assets_count[project_id] = int(count or 0)

            asset_updated_stmt = (
                select(GeneratedAsset.project_id, func.max(GeneratedAsset.updated_at))
                .where(GeneratedAsset.project_id.in_(project_ids))
                .group_by(GeneratedAsset.project_id)
            )
            for project_id, value in db.execute(asset_updated_stmt):
                if value is not None:
                    assets_updated[project_id] = value

            config_count_stmt = (
                select(ProjectConfig.project_id, func.count(ProjectConfig.id))
                .where(ProjectConfig.project_id.in_(project_ids))
                .group_by(ProjectConfig.project_id)
            )
            for project_id, count in db.execute(config_count_stmt):
                config_counts[project_id] = int(count or 0)

            artifact_count_stmt = (
                select(ProjectArtifact.project_id, func.count(ProjectArtifact.id))
                .where(ProjectArtifact.project_id.in_(project_ids))
                .group_by(ProjectArtifact.project_id)
            )
            for project_id, count in db.execute(artifact_count_stmt):
                artifact_counts[project_id] = int(count or 0)

            artifact_updated_stmt = (
                select(ProjectArtifact.project_id, func.max(ProjectArtifact.updated_at))
                .where(ProjectArtifact.project_id.in_(project_ids))
                .group_by(ProjectArtifact.project_id)
            )
            for project_id, value in db.execute(artifact_updated_stmt):
                if value is not None:
                    artifact_updated[project_id] = value

        results: List[Dict[str, Any]] = []
        for project in projects:
            payload = project.to_dict(include_metadata=include_metadata)
            latest_run = latest_runs.get(project.id)
            payload["latest_run"] = (
                {
                    "id": latest_run.id,
                    "label": latest_run.label,
                    "status": latest_run.status,
                    "kind": latest_run.kind,
                    "created_at": format_timestamp(latest_run.created_at),
                    "finished_at": format_timestamp(latest_run.finished_at),
                    "updated_at": format_timestamp(latest_run.updated_at),
                }
                if latest_run
                else None
            )
            payload["run_count"] = run_counts.get(project.id, 0)
            payload["library_asset_count"] = assets_count.get(project.id, 0)
            payload["config_count"] = config_counts.get(project.id, 0)
            payload["artifact_count"] = artifact_counts.get(project.id, 0)

            last_activity_candidates = [
                project.updated_at,
                latest_run.updated_at if latest_run else None,
                assets_updated.get(project.id),
                artifact_updated.get(project.id),
            ]
            last_activity = max(
                (value for value in last_activity_candidates if value is not None),
                default=project.updated_at,
            )
            payload["last_activity_at"] = format_timestamp(last_activity)

            results.append(payload)
        return results


def get_project(
    project_id: str | None = None,
    *,
    slug: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    if project_id is None and slug is None:
        raise ValueError("either project_id or slug must be provided")
    with _get_session(session, db_path) as db:
        project: Project | None
        if project_id:
            project = db.get(Project, project_id)
        else:
            project = (
                db.execute(select(Project).where(Project.slug == slug)).scalars().first()
            )
        if not project:
            return None
        return project.to_dict()


def delete_project(
    project_id: str,
    *,
    remove_files: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        project = db.get(Project, project_id)
        if not project:
            return False
        project_root = Path(project.root_path)
        db.delete(project)
        db.flush()
        if remove_files and project_root.exists():
            for path in sorted(project_root.glob("**/*"), reverse=True):
                if path.is_dir():
                    try:
                        path.rmdir()
                    except OSError:
                        continue
                else:
                    path.unlink(missing_ok=True)
            try:
                project_root.rmdir()
            except OSError:
                pass
        return True


def update_project(
    project_id: str,
    *,
    name: str | None = None,
    description: str | None = None,
    metadata: Dict[str, Any] | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        project = db.get(Project, project_id)
        if not project:
            return None

        if name is not None:
            normalised = name.strip()
            if not normalised:
                raise ValueError("project name cannot be empty")
            existing = (
                db.execute(
                    select(Project).where(Project.name == normalised, Project.id != project_id)
                )
                .scalars()
                .first()
            )
            if existing:
                raise ValueError(f"project with name '{normalised}' already exists")
            project.name = normalised

        if description is not None:
            project.description = description.strip() if description else None

        if metadata is not None:
            project.project_metadata = dict(metadata)

        db.flush()
        db.refresh(project)
        return project.to_dict()


def list_project_configs(
    project_id: str,
    *,
    include_payload: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        try:
            _get_project_or_raise(db, project_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc

        stmt = (
            select(ProjectConfig)
            .where(ProjectConfig.project_id == project_id)
            .order_by(ProjectConfig.created_at.asc(), ProjectConfig.id.asc())
        )
        return [record.to_dict(include_payload=include_payload) for record in db.execute(stmt).scalars()]


def get_project_config(
    config_id: str,
    *,
    project_id: str | None = None,
    include_payload: bool = True,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        record = db.get(ProjectConfig, config_id)
        if not record:
            return None
        if project_id and record.project_id != project_id:
            return None
        return record.to_dict(include_payload=include_payload)


def create_project_config(
    project_id: str,
    *,
    name: str,
    slug: str | None = None,
    config_name: str | None = None,
    payload: str | None = None,
    kind: str = "tfreview",
    description: str | None = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    is_default: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("config name cannot be empty")
    cleaned_kind = kind.strip() or "tfreview"
    tags_value = _normalise_tags(tags)
    metadata_value = dict(metadata or {})
    payload_value = None
    if payload is not None:
        payload_value = payload if payload.strip() else None
    config_name_value = config_name.strip() if config_name else None

    with _get_session(session, db_path) as db:
        try:
            project = _get_project_or_raise(db, project_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc

        if config_name_value:
            exists = db.get(Config, config_name_value)
            if not exists:
                raise ValueError(f"config '{config_name_value}' does not exist")

        if not config_name_value and payload_value is None:
            raise ValueError("either config_name or payload must be provided")

        slug_input = slug.strip() if slug else cleaned_name
        slug_value = _ensure_project_config_slug(db, project.id, _slugify(slug_input))

        record = ProjectConfig(
            project_id=project.id,
            name=cleaned_name,
            slug=slug_value,
            description=description.strip() if description else None,
            config_name=config_name_value,
            payload=payload_value,
            kind=cleaned_kind,
            tags=tags_value,
            config_metadata=metadata_value,
            is_default=False,
        )
        db.add(record)
        db.flush()

        if is_default or not _has_project_default_config(db, project.id):
            _mark_default_project_config(db, project.id, record)
        else:
            db.flush()

        return record.to_dict()


def update_project_config(
    config_id: str,
    *,
    project_id: str,
    name: str | None = None,
    config_name: str | None = None,
    payload: str | None = None,
    kind: str | None = None,
    description: str | None = None,
    tags: Optional[List[str]] | None = None,
    metadata: Optional[Dict[str, Any]] | None = None,
    is_default: bool | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        record = db.get(ProjectConfig, config_id)
        if not record or record.project_id != project_id:
            return None

        if name is not None:
            cleaned = name.strip()
            if not cleaned:
                raise ValueError("config name cannot be empty")
            record.name = cleaned
        if description is not None:
            record.description = description.strip() if description else None
        if kind is not None:
            cleaned_kind = kind.strip() or "tfreview"
            record.kind = cleaned_kind
        if tags is not None:
            record.tags = _normalise_tags(tags)
        if metadata is not None:
            record.config_metadata = dict(metadata or {})
        if config_name is not None:
            cleaned_config = config_name.strip() if config_name else None
            if cleaned_config:
                exists = db.get(Config, cleaned_config)
                if not exists:
                    raise ValueError(f"config '{cleaned_config}' does not exist")
            record.config_name = cleaned_config
        if payload is not None:
            record.payload = payload if payload.strip() else None

        if not record.payload and not record.config_name:
            raise ValueError("project config must reference a saved config or include payload data")

        if is_default is True:
            _mark_default_project_config(db, project_id, record)
        elif is_default is False and record.is_default:
            record.is_default = False
            db.flush()
            _ensure_project_default_config(db, project_id)

        db.flush()
        return record.to_dict()


def delete_project_config(
    config_id: str,
    *,
    project_id: str,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        record = db.get(ProjectConfig, config_id)
        if not record or record.project_id != project_id:
            return False
        was_default = record.is_default
        db.delete(record)
        db.flush()
        if was_default:
            _ensure_project_default_config(db, project_id)
        return True


def create_project_run(
    project_id: str,
    label: str,
    *,
    kind: str,
    status: str = "queued",
    triggered_by: str | None = None,
    parameters: Dict[str, Any] | None = None,
    projects_root: Path | None = None,
    report_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    metadata = dict(parameters or {})
    with _get_session(session, db_path) as db:
        try:
            project = _get_project_or_raise(db, project_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        if report_id:
            report = db.get(Report, report_id)
            if not report:
                raise ValueError(f"report '{report_id}' not found")
        run = ProjectRun(
            project_id=project.id,
            label=label,
            kind=kind,
            status=status,
            triggered_by=triggered_by,
            parameters=metadata,
            report_id=report_id,
        )
        db.add(run)
        db.flush()
        _ensure_run_directory(db, project, run, projects_root)
        db.flush()
        return run.to_dict()


def list_project_runs(
    project_id: str,
    *,
    limit: int = 50,
    cursor: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    limit = min(limit, 200)

    with _get_session(session, db_path) as db:
        try:
            project = _get_project_or_raise(db, project_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        cursor_run: ProjectRun | None = None
        if cursor:
            candidate = db.get(ProjectRun, cursor)
            if not candidate or candidate.project_id != project.id:
                raise ValueError("cursor does not reference a project run for this project")
            cursor_run = candidate

        stmt = select(ProjectRun).where(ProjectRun.project_id == project_id)
        if cursor_run:
            stmt = stmt.where(
                or_(
                    ProjectRun.created_at < cursor_run.created_at,
                    and_(
                        ProjectRun.created_at == cursor_run.created_at,
                        ProjectRun.id < cursor_run.id,
                    ),
                )
            )

        stmt = stmt.order_by(ProjectRun.created_at.desc(), ProjectRun.id.desc()).limit(limit + 1)
        fetched = list(db.execute(stmt).scalars())
        items = fetched[:limit]

        next_cursor: Optional[str] = None
        if items and len(fetched) > limit:
            next_cursor = items[-1].id

        count_stmt = select(func.count(ProjectRun.id)).where(ProjectRun.project_id == project_id)
        total_count = int(db.execute(count_stmt).scalar_one() or 0)

        return {
            "items": [run.to_dict(include_parameters=False) for run in items],
            "next_cursor": next_cursor,
            "total_count": total_count,
        }


def get_project_run(
    run_id: str,
    *,
    project_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        run = db.get(ProjectRun, run_id)
        if not run:
            return None
        if project_id and run.project_id != project_id:
            return None
        return run.to_dict()


def update_project_run(
    run_id: str,
    *,
    project_id: str | None = None,
    status: str | None = None,
    summary: Dict[str, Any] | None = None,
    started_at: datetime | None = None,
    finished_at: datetime | None = None,
    report_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        run = db.get(ProjectRun, run_id)
        if not run:
            return None
        if project_id and run.project_id != project_id:
            return None
        if status:
            run.status = status
        if summary is not None:
            run.summary = summary
        if started_at:
            run.started_at = started_at
        if finished_at:
            run.finished_at = finished_at
        if report_id is not None:
            if report_id:
                report = db.get(Report, report_id)
                if not report:
                    raise ValueError(f"report '{report_id}' not found")
            run.report_id = report_id
        db.flush()
        return run.to_dict()


def list_run_artifacts(
    project_id: str,
    run_id: str,
    *,
    path: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        try:
            project, run = _get_project_and_run_or_raise(db, project_id, run_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        except ProjectRunNotFoundError as exc:
            raise ValueError(f"run '{run_id}' not found") from exc
        run_dir = _ensure_run_directory(db, project, run)
        artifact_records: Dict[str, ProjectArtifact] = {
            record.relative_path: record
            for record in db.execute(
                select(ProjectArtifact).where(
                    ProjectArtifact.project_id == project.id,
                    ProjectArtifact.run_id == run.id,
                )
            ).scalars()
        }
        target = _resolve_artifact_path(run_dir, path)
        if not target.exists():
            raise FileNotFoundError(str(path or ""))
        if not target.is_dir():
            raise ArtifactPathError("path must reference a directory")

        entries: List[Dict[str, Any]] = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            stat = child.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            relative = str(child.relative_to(run_dir))
            normalised_relative = _normalise_relative_path(relative)
            record = artifact_records.get(normalised_relative)
            entries.append(
                {
                    "name": child.name,
                    "path": relative,
                    "is_dir": child.is_dir(),
                    "size": int(stat.st_size) if child.is_file() else None,
                    "modified_at": format_timestamp(modified),
                    "artifact_id": record.id if record else None,
                    "media_type": record.media_type if record else None,
                    "metadata": record.artifact_metadata if record else None,
                    "tags": record.tags if record else None,
                }
            )
        return entries


def save_run_artifact(
    project_id: str,
    run_id: str,
    *,
    path: str,
    data: bytes,
    overwrite: bool = True,
    projects_root: Path | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    if not path or path.endswith("/"):
        raise ArtifactPathError("artifact path must reference a file")

    with _get_session(session, db_path) as db:
        try:
            project, run = _get_project_and_run_or_raise(db, project_id, run_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        except ProjectRunNotFoundError as exc:
            raise ValueError(f"run '{run_id}' not found") from exc

        run_dir = _ensure_run_directory(db, project, run, projects_root)
        destination = _resolve_artifact_path(run_dir, path)

        if destination == run_dir or destination.is_dir():
            raise ArtifactPathError("artifact path must reference a file")

        destination.parent.mkdir(parents=True, exist_ok=True)

        if destination.exists() and not overwrite:
            raise FileExistsError(str(destination))

        with open(destination, "wb") as handle:
            handle.write(data)

        stat = destination.stat()
        run.updated_at = datetime.now(tz=timezone.utc)
        relative_path = str(destination.relative_to(run_dir))
        record = _record_project_artifact(
            db,
            project,
            run=run,
            relative_path=relative_path,
            absolute_path=destination,
        )
        db.flush()

        return {
            "name": destination.name,
            "path": relative_path,
            "is_dir": False,
            "size": int(stat.st_size),
            "modified_at": format_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
            "artifact_id": record.id,
            "checksum": record.checksum,
            "media_type": record.media_type,
        }


def get_run_artifact_path(
    project_id: str,
    run_id: str,
    *,
    path: str,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Path:
    if not path:
        raise ArtifactPathError("path is required")

    with _get_session(session, db_path) as db:
        try:
            project, run = _get_project_and_run_or_raise(db, project_id, run_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        except ProjectRunNotFoundError as exc:
            raise ValueError(f"run '{run_id}' not found") from exc

        run_dir = _ensure_run_directory(db, project, run)
        destination = _resolve_artifact_path(run_dir, path)

        if not destination.exists() or not destination.is_file():
            raise FileNotFoundError(str(path))

        return destination


def delete_run_artifact(
    project_id: str,
    run_id: str,
    *,
    path: str,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> bool:
    if not path:
        raise ArtifactPathError("path is required")

    with _get_session(session, db_path) as db:
        try:
            project, run = _get_project_and_run_or_raise(db, project_id, run_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        except ProjectRunNotFoundError as exc:
            raise ValueError(f"run '{run_id}' not found") from exc

        run_dir = _ensure_run_directory(db, project, run)
        destination = _resolve_artifact_path(run_dir, path)

        if not destination.exists():
            return False
        if destination.is_dir():
            raise ArtifactPathError("cannot delete directory via artifact endpoint")

        relative_path = str(destination.relative_to(run_dir))
        destination.unlink()
        record = (
            db.execute(
                select(ProjectArtifact).where(
                    ProjectArtifact.project_id == project.id,
                    ProjectArtifact.run_id == run.id,
                    ProjectArtifact.relative_path == _normalise_relative_path(relative_path),
                )
            )
            .scalars()
            .first()
        )
        if record:
            db.delete(record)
        run.updated_at = datetime.now(tz=timezone.utc)
        db.flush()
        return True


def list_project_artifacts(
    project_id: str,
    *,
    run_id: str | None = None,
    limit: int = 200,
    cursor: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    limit = min(limit, 500)

    with _get_session(session, db_path) as db:
        try:
            _get_project_or_raise(db, project_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc

        cursor_record: ProjectArtifact | None = None
        if cursor:
            candidate = db.get(ProjectArtifact, cursor)
            if not candidate or candidate.project_id != project_id:
                raise ValueError("cursor does not reference a project artifact")
            if run_id and candidate.run_id != run_id:
                raise ValueError("cursor does not match requested run_id")
            cursor_record = candidate

        stmt = select(ProjectArtifact).where(ProjectArtifact.project_id == project_id)
        if run_id:
            stmt = stmt.where(ProjectArtifact.run_id == run_id)
        if cursor_record:
            stmt = stmt.where(
                or_(
                    ProjectArtifact.updated_at < cursor_record.updated_at,
                    and_(
                        ProjectArtifact.updated_at == cursor_record.updated_at,
                        ProjectArtifact.id < cursor_record.id,
                    ),
                )
            )
        stmt = stmt.order_by(ProjectArtifact.updated_at.desc(), ProjectArtifact.id.desc()).limit(limit + 1)
        fetched = list(db.execute(stmt).scalars())
        items = fetched[:limit]

        next_cursor: Optional[str] = None
        if items and len(fetched) > limit:
            next_cursor = items[-1].id

        count_stmt = select(func.count(ProjectArtifact.id)).where(ProjectArtifact.project_id == project_id)
        if run_id:
            count_stmt = count_stmt.where(ProjectArtifact.run_id == run_id)
        total_count = int(db.execute(count_stmt).scalar_one() or 0)

        return {
            "items": [record.to_dict() for record in items],
            "next_cursor": next_cursor,
            "total_count": total_count,
        }


def get_project_artifact(
    artifact_id: str,
    *,
    project_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        record = db.get(ProjectArtifact, artifact_id)
        if not record:
            return None
        if project_id and record.project_id != project_id:
            return None
        return record.to_dict()


def update_project_artifact(
    artifact_id: str,
    *,
    project_id: str,
    tags: Optional[List[str]] | None = None,
    metadata: Optional[Dict[str, Any]] | None = None,
    media_type: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        record = db.get(ProjectArtifact, artifact_id)
        if not record or record.project_id != project_id:
            return None
        if tags is not None:
            record.tags = _normalise_tags(tags)
        if metadata is not None:
            record.artifact_metadata = dict(metadata or {})
        if media_type is not None:
            record.media_type = media_type or None
        db.flush()
        return record.to_dict()


def sync_project_run_artifacts(
    project_id: str,
    run_id: str,
    *,
    projects_root: Path | None = None,
    prune_missing: bool = True,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, int]:
    with _get_session(session, db_path) as db:
        try:
            project, run = _get_project_and_run_or_raise(db, project_id, run_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        except ProjectRunNotFoundError as exc:
            raise ValueError(f"run '{run_id}' not found") from exc

        run_dir = _ensure_run_directory(db, project, run, projects_root)
        records_by_relative: Dict[str, ProjectArtifact] = {
            record.relative_path: record
            for record in db.execute(
                select(ProjectArtifact).where(
                    ProjectArtifact.project_id == project.id,
                    ProjectArtifact.run_id == run.id,
                )
            ).scalars()
        }
        processed: set[str] = set()
        added = 0
        updated = 0

        for file_path in run_dir.rglob("*"):
            if not file_path.is_file():
                continue
            relative = str(file_path.relative_to(run_dir))
            normalised = _normalise_relative_path(relative)
            existing = records_by_relative.get(normalised)
            record = _record_project_artifact(
                db,
                project,
                run=run,
                relative_path=relative,
                absolute_path=file_path,
            )
            records_by_relative[normalised] = record
            processed.add(normalised)
            if existing is None:
                added += 1
            else:
                updated += 1

        removed = 0
        if prune_missing:
            for relative, record in list(records_by_relative.items()):
                if relative not in processed:
                    db.delete(record)
                    removed += 1

        db.flush()
        return {
            "added": added,
            "updated": updated,
            "removed": removed,
            "files_indexed": len(processed),
        }


def list_generated_assets(
    project_id: str,
    *,
    limit: int = 200,
    cursor: str | None = None,
    include_versions: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    if limit <= 0:
        raise ValueError("limit must be greater than zero")
    limit = min(limit, 200)

    with _get_session(session, db_path) as db:
        cursor_asset: GeneratedAsset | None = None
        if cursor:
            candidate = db.get(GeneratedAsset, cursor)
            if not candidate or candidate.project_id != project_id:
                raise ValueError("cursor does not reference a project asset")
            cursor_asset = candidate

        stmt = select(GeneratedAsset).where(GeneratedAsset.project_id == project_id)
        if cursor_asset:
            stmt = stmt.where(
                or_(
                    GeneratedAsset.updated_at < cursor_asset.updated_at,
                    and_(
                        GeneratedAsset.updated_at == cursor_asset.updated_at,
                        GeneratedAsset.id < cursor_asset.id,
                    ),
                )
            )

        stmt = stmt.order_by(GeneratedAsset.updated_at.desc(), GeneratedAsset.id.desc()).limit(limit + 1)
        fetched = list(db.execute(stmt).scalars())
        items = fetched[:limit]

        next_cursor: Optional[str] = None
        if items and len(fetched) > limit:
            next_cursor = items[-1].id

        count_stmt = select(func.count(GeneratedAsset.id)).where(GeneratedAsset.project_id == project_id)
        total_count = int(db.execute(count_stmt).scalar_one() or 0)

        return {
            "items": [asset.to_dict(include_versions=include_versions) for asset in items],
            "next_cursor": next_cursor,
            "total_count": total_count,
        }


def get_project_overview(
    project_id: str,
    *,
    recent_assets: int = 3,
    include_metadata: bool = True,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    if recent_assets <= 0:
        raise ValueError("recent_assets must be greater than zero")
    with _get_session(session, db_path) as db:
        try:
            project = _get_project_or_raise(db, project_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc

        latest_run = (
            db.execute(
                select(ProjectRun)
                .where(ProjectRun.project_id == project_id)
                .order_by(ProjectRun.created_at.desc(), ProjectRun.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        run_count = int(
            db.execute(select(func.count(ProjectRun.id)).where(ProjectRun.project_id == project_id)).scalar_one() or 0
        )

        config_count = int(
            db.execute(select(func.count(ProjectConfig.id)).where(ProjectConfig.project_id == project_id)).scalar_one() or 0
        )

        default_config = (
            db.execute(
                select(ProjectConfig)
                .where(ProjectConfig.project_id == project_id, ProjectConfig.is_default.is_(True))
                .order_by(ProjectConfig.updated_at.desc(), ProjectConfig.id.desc())
                .limit(1)
            )
            .scalars()
            .first()
        )

        library_asset_count = int(
            db.execute(select(func.count(GeneratedAsset.id)).where(GeneratedAsset.project_id == project_id)).scalar_one() or 0
        )

        artifact_count = int(
            db.execute(select(func.count(ProjectArtifact.id)).where(ProjectArtifact.project_id == project_id)).scalar_one() or 0
        )

        latest_asset_updated = db.execute(
            select(func.max(GeneratedAsset.updated_at)).where(GeneratedAsset.project_id == project_id)
        ).scalar_one_or_none()
        latest_artifact_updated = db.execute(
            select(func.max(ProjectArtifact.updated_at)).where(ProjectArtifact.project_id == project_id)
        ).scalar_one_or_none()

        recent_assets_stmt = (
            select(GeneratedAsset)
            .where(GeneratedAsset.project_id == project_id)
            .order_by(GeneratedAsset.updated_at.desc(), GeneratedAsset.id.desc())
            .limit(recent_assets)
        )
        assets = [
            asset.to_dict(include_versions=False)
            for asset in db.execute(recent_assets_stmt).scalars()
        ]

        recent_artifacts_stmt = (
            select(ProjectArtifact)
            .where(ProjectArtifact.project_id == project_id)
            .order_by(ProjectArtifact.updated_at.desc(), ProjectArtifact.id.desc())
            .limit(recent_assets)
        )
        artifact_items = [artifact.to_dict() for artifact in db.execute(recent_artifacts_stmt).scalars()]

        metrics: Dict[str, Any] = {}
        if latest_run and latest_run.summary:
            summary_payload = dict(latest_run.summary or {})
            metrics = {
                "cost": summary_payload.get("cost"),
                "drift": summary_payload.get("drift"),
                "policy": summary_payload.get("policy"),
            }

        last_activity_candidates = [
            project.updated_at,
            latest_run.updated_at if latest_run else None,
        ]
        if latest_asset_updated:
            last_activity_candidates.append(latest_asset_updated)
        if latest_artifact_updated:
            last_activity_candidates.append(latest_artifact_updated)
        last_activity = max(
            (value for value in last_activity_candidates if value is not None),
            default=project.updated_at,
        )

        return {
            "project": project.to_dict(include_metadata=include_metadata),
            "run_count": run_count,
            "latest_run": latest_run.to_dict(include_parameters=False) if latest_run else None,
            "config_count": config_count,
            "default_config": default_config.to_dict(include_payload=False) if default_config else None,
            "library_asset_count": library_asset_count,
            "artifact_count": artifact_count,
            "recent_assets": assets,
            "recent_artifacts": artifact_items,
            "metrics": metrics,
            "last_activity_at": format_timestamp(last_activity),
        }


def get_generated_asset(
    asset_id: str,
    *,
    project_id: str | None = None,
    include_versions: bool = True,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            return None
        if project_id and asset.project_id != project_id:
            return None
        return asset.to_dict(include_versions=include_versions)


def register_generated_asset(
    project_id: str,
    *,
    name: str,
    asset_type: str,
    description: str | None = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    run_id: str | None = None,
    report_id: str | None = None,
    storage_filename: str | None = None,
    source_path: Path | str | None = None,
    data: bytes | None = None,
    media_type: str | None = None,
    notes: str | None = None,
    projects_root: Path | None = None,
    files: Optional[Sequence[Dict[str, Any]]] = None,
    version_metadata: Optional[Dict[str, Any]] = None,
    payload_fingerprint: str | None = None,
    validation_summary: Optional[Dict[str, Any]] = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    cleaned_name = name.strip()
    if not cleaned_name:
        raise ValueError("asset name cannot be empty")

    cleaned_type = asset_type.strip()
    if not cleaned_type:
        raise ValueError("asset type cannot be empty")

    tags_value = _normalise_tags(tags)
    metadata_value = dict(metadata or {})
    source_path_obj = Path(source_path).expanduser() if source_path else None
    file_payloads = _prepare_version_files(files)

    with _get_session(session, db_path) as db:
        project = _get_project_or_raise(db, project_id)
        run: ProjectRun | None = None
        if run_id:
            run = db.get(ProjectRun, run_id)
            if not run or run.project_id != project.id:
                raise ValueError(f"run '{run_id}' not found for project '{project_id}'")
        report: Report | None = None
        if report_id:
            report = db.get(Report, report_id)
            if not report:
                raise ValueError(f"report '{report_id}' not found")

        existing = db.execute(
            select(GeneratedAsset).where(
                GeneratedAsset.project_id == project.id,
                GeneratedAsset.name == cleaned_name,
            )
        ).scalar_one_or_none()
        if existing:
            raise ValueError(f"asset '{cleaned_name}' already exists in project '{project_id}'")

        asset = GeneratedAsset(
            project_id=project.id,
            name=cleaned_name,
            description=description.strip() if description else None,
            asset_type=cleaned_type,
            tags=tags_value,
            asset_metadata=metadata_value,
        )
        db.add(asset)
        db.flush()  # ensure asset.id is available

        resolved_storage_name = storage_filename
        if not resolved_storage_name:
            if source_path_obj:
                resolved_storage_name = source_path_obj.name
            else:
                resolved_storage_name = f"{_slugify(cleaned_name)}.txt"
        storage_name = _sanitize_storage_name(resolved_storage_name)

        content_bytes = _resolve_asset_bytes(source_path_obj, data)
        version = _create_asset_version(
            db,
            project,
            asset,
            run=run,
            report=report,
            storage_name=storage_name,
            content_bytes=content_bytes,
            media_type=media_type,
            notes=notes,
            projects_root=projects_root,
            files=file_payloads,
            version_metadata=version_metadata,
            validation_summary=validation_summary,
            payload_fingerprint=payload_fingerprint,
        )

        asset.latest_version_id = version.id
        db.flush()

        payload = asset.to_dict(include_versions=True)
        return {
            "asset": payload,
            "version": version.to_dict(include_blob=False),
        }


def update_generated_asset(
    asset_id: str,
    *,
    project_id: str | None = None,
    name: str | None = None,
    asset_type: str | None = None,
    description: str | None = None,
    tags: Optional[List[str]] = None,
    metadata: Optional[Dict[str, Any]] = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            return None
        if project_id and asset.project_id != project_id:
            return None

        if name is not None:
            trimmed = name.strip()
            if not trimmed:
                raise ValueError("asset name cannot be empty")
            if trimmed != asset.name:
                existing = db.execute(
                    select(GeneratedAsset).where(
                        GeneratedAsset.project_id == asset.project_id,
                        GeneratedAsset.name == trimmed,
                        GeneratedAsset.id != asset.id,
                    )
                ).scalar_one_or_none()
                if existing:
                    raise ValueError(f"asset '{trimmed}' already exists in this project")
                asset.name = trimmed

        if asset_type is not None:
            trimmed_type = asset_type.strip()
            if not trimmed_type:
                raise ValueError("asset type cannot be empty")
            asset.asset_type = trimmed_type

        if description is not None:
            asset.description = description.strip() or None

        if tags is not None:
            asset.tags = _normalise_tags(tags)

        if metadata is not None:
            if metadata and not isinstance(metadata, dict):
                raise ValueError("metadata must be a JSON object")
            asset.asset_metadata = dict(metadata or {})

        db.flush()
        return asset.to_dict(include_versions=True)


def add_generated_asset_version(
    asset_id: str,
    *,
    project_id: str | None = None,
    run_id: str | None = None,
    report_id: str | None = None,
    storage_filename: str | None = None,
    source_path: Path | str | None = None,
    data: bytes | None = None,
    media_type: str | None = None,
    notes: str | None = None,
    promote_latest: bool = True,
    projects_root: Path | None = None,
    files: Optional[Sequence[Dict[str, Any]]] = None,
    version_metadata: Optional[Dict[str, Any]] = None,
    payload_fingerprint: str | None = None,
    validation_summary: Optional[Dict[str, Any]] = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    source_path_obj = Path(source_path).expanduser() if source_path else None
    file_payloads = _prepare_version_files(files)

    with _get_session(session, db_path) as db:
        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            raise ValueError(f"asset '{asset_id}' not found")
        if project_id and asset.project_id != project_id:
            raise ValueError("asset does not belong to the specified project")

        project = db.get(Project, asset.project_id)
        if not project:
            raise ProjectNotFoundError(asset.project_id)

        run: ProjectRun | None = None
        if run_id:
            run = db.get(ProjectRun, run_id)
            if not run or run.project_id != project.id:
                raise ValueError(f"run '{run_id}' not found for project '{project.id}'")
        report: Report | None = None
        if report_id:
            report = db.get(Report, report_id)
            if not report:
                raise ValueError(f"report '{report_id}' not found")

        resolved_storage_name = storage_filename
        if not resolved_storage_name:
            if source_path_obj:
                resolved_storage_name = source_path_obj.name
            elif media_type:
                resolved_storage_name = f"{asset.id}-{uuid4().hex}"
            else:
                resolved_storage_name = f"{asset.id}-{uuid4().hex}.txt"
        storage_name = _sanitize_storage_name(resolved_storage_name)

        content_bytes = _resolve_asset_bytes(source_path_obj, data)
        version = _create_asset_version(
            db,
            project,
            asset,
            run=run,
            report=report,
            storage_name=storage_name,
            content_bytes=content_bytes,
            media_type=media_type,
            notes=notes,
            projects_root=projects_root,
            files=file_payloads,
            version_metadata=version_metadata,
            validation_summary=validation_summary,
            payload_fingerprint=payload_fingerprint,
        )

        if promote_latest or not asset.latest_version_id:
            asset.latest_version_id = version.id
        db.flush()

        payload = asset.to_dict(include_versions=True)
        return {
            "asset": payload,
            "version": version.to_dict(include_blob=False),
        }


def delete_generated_asset_version(
    asset_id: str,
    version_id: str,
    *,
    project_id: str | None = None,
    remove_files: bool = True,
    projects_root: Path | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        version = db.get(GeneratedAssetVersion, version_id)
        if not version or version.asset_id != asset_id:
            return False

        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            return False
        if project_id and asset.project_id != project_id:
            return False

        project = db.get(Project, asset.project_id)
        if not project:
            raise ProjectNotFoundError(asset.project_id)

        if remove_files and version.storage_path:
            file_path = Path(version.storage_path).expanduser()
            if file_path.exists():
                file_path.unlink()
                # remove empty parent directory (version folder)
                try:
                    parent_dir = file_path.parent
                    if parent_dir.is_dir() and not any(parent_dir.iterdir()):
                        parent_dir.rmdir()
                except OSError:
                    pass

        db.delete(version)
        db.flush()

        if asset.latest_version_id == version_id:
            next_version = (
                db.execute(
                    select(GeneratedAssetVersion)
                    .where(GeneratedAssetVersion.asset_id == asset.id)
                    .order_by(GeneratedAssetVersion.created_at.desc())
                )
                .scalars()
                .first()
            )
            asset.latest_version_id = next_version.id if next_version else None
        db.flush()
        return True


def delete_generated_asset(
    asset_id: str,
    *,
    project_id: str | None = None,
    remove_files: bool = False,
    projects_root: Path | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            return False

        if project_id and asset.project_id != project_id:
            return False

        project = db.get(Project, asset.project_id)
        if not project:
            raise ProjectNotFoundError(asset.project_id)

        if remove_files:
            asset_root = _get_asset_library_root(project, asset.id, projects_root)
            if asset_root.exists():
                shutil.rmtree(asset_root, ignore_errors=True)

        db.delete(asset)
        db.flush()
        return True


def get_generated_asset_version(
    asset_id: str,
    version_id: str,
    *,
    project_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            return None
        if project_id and asset.project_id != project_id:
            return None
        version = db.get(GeneratedAssetVersion, version_id)
        if not version or version.asset_id != asset_id:
            return None
        return version.to_dict(include_blob=False)


def get_generated_asset_version_path(
    asset_id: str,
    version_id: str,
    *,
    project_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Path:
    with _get_session(session, db_path) as db:
        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            raise ValueError("asset not found")
        if project_id and asset.project_id != project_id:
            raise ValueError("asset does not belong to the specified project")
        version = db.get(GeneratedAssetVersion, version_id)
        if not version or version.asset_id != asset_id:
            raise ValueError("version not found for asset")
        path = Path(version.storage_path).expanduser()
        if not path.exists() or not path.is_file():
            raise FileNotFoundError(str(path))
    return path


def diff_generated_asset_versions(
    asset_id: str,
    base_version_id: str,
    compare_version_id: str,
    *,
    project_id: str | None = None,
    max_bytes: int = MAX_VERSION_TEXT_BYTES,
    ignore_whitespace: bool = False,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    with _get_session(session, db_path) as db:
        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            raise ValueError("asset not found")
        if project_id and asset.project_id != project_id:
            raise ValueError("asset does not belong to the specified project")
        base_version = db.get(GeneratedAssetVersion, base_version_id)
        compare_version = db.get(GeneratedAssetVersion, compare_version_id)
        if not base_version or base_version.asset_id != asset_id:
            raise ValueError("base version not found for asset")
        if not compare_version or compare_version.asset_id != asset_id:
            raise ValueError("compare version not found for asset")

        base_files = _get_version_file_views(base_version)
        compare_files = _get_version_file_views(compare_version)
        diff_chunks: List[str] = []
        file_diffs: List[Dict[str, Any]] = []
        paired_paths: List[tuple[str, VersionFileView | None, VersionFileView | None]] = []
        all_paths = sorted(set(base_files.keys()) | set(compare_files.keys()))
        for path in all_paths:
            paired_paths.append((path, base_files.get(path), compare_files.get(path)))

        if not any(base and compare for _, base, compare in paired_paths):
            if base_files and compare_files and len(base_files) == 1 and len(compare_files) == 1:
                base_entry = next(iter(base_files.values()))
                compare_entry = next(iter(compare_files.values()))
                synthetic_path = compare_entry.path or base_entry.path or compare_version.display_path
                paired_paths.append((synthetic_path, base_entry, compare_entry))

        for path, base_entry, compare_entry in paired_paths:
            if base_entry and compare_entry:
                status = "modified"
            elif base_entry and not compare_entry:
                status = "removed"
            else:
                status = "added"

            file_diff_text: Optional[str] = None
            if base_entry and compare_entry:
                base_path = Path(base_entry.storage_path).expanduser()
                compare_path = Path(compare_entry.storage_path).expanduser()
                try:
                    base_text = _read_text_file(base_path, max_bytes=max_bytes)
                    compare_text = _read_text_file(compare_path, max_bytes=max_bytes)
                    if ignore_whitespace:
                        base_lines = [line.strip() for line in base_text.splitlines()]
                        compare_lines = [line.strip() for line in compare_text.splitlines()]
                    else:
                        base_lines = base_text.splitlines()
                        compare_lines = compare_text.splitlines()
                    diff_lines = difflib.unified_diff(
                        base_lines,
                        compare_lines,
                        fromfile=path,
                        tofile=path,
                        lineterm="",
                    )
                    file_diff_text = "\n".join(diff_lines)
                    if file_diff_text:
                        diff_chunks.append(file_diff_text)
                except (FileNotFoundError, ValueError):
                    file_diff_text = None

            file_diffs.append(
                {
                    "path": path,
                    "status": status,
                    "base": {
                        "storage_path": base_entry.storage_path,
                        "checksum": base_entry.checksum,
                        "size_bytes": base_entry.size_bytes,
                        "media_type": base_entry.media_type,
                    }
                    if base_entry
                    else None,
                    "compare": {
                        "storage_path": compare_entry.storage_path,
                        "checksum": compare_entry.checksum,
                        "size_bytes": compare_entry.size_bytes,
                        "media_type": compare_entry.media_type,
                    }
                    if compare_entry
                    else None,
                    "diff": file_diff_text,
                }
            )

        if not diff_chunks:
            raise ValueError("diff unavailable for the specified versions (no textual differences detected)")

        diff_text = "\n".join(diff_chunks)

        return {
            "base": base_version.to_dict(include_blob=False),
            "compare": compare_version.to_dict(include_blob=False),
            "diff": diff_text,
            "ignore_whitespace": ignore_whitespace,
            "files": file_diffs,
        }


def list_generated_asset_version_files(
    asset_id: str,
    version_id: str,
    *,
    project_id: str | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        asset = db.get(GeneratedAsset, asset_id)
        if not asset:
            raise ValueError("asset not found")
        if project_id and asset.project_id != project_id:
            raise ValueError("asset does not belong to the specified project")
        version = db.get(GeneratedAssetVersion, version_id)
        if not version or version.asset_id != asset_id:
            raise ValueError("version not found for asset")
        files = (
            db.execute(
                select(GeneratedAssetVersionFile)
                .where(GeneratedAssetVersionFile.version_id == version.id)
                .order_by(GeneratedAssetVersionFile.path.asc())
            )
            .scalars()
            .all()
        )
        return [file_record.to_dict() for file_record in files]


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialise database tables using SQLAlchemy metadata."""
    init_models(db_path)
    with session_scope(db_path) as db:
        _ensure_report_review_columns(db)


def upsert_config(
    name: str,
    payload: str,
    kind: str = "tfreview",
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> None:
    with _get_session(session, db_path) as db:
        config = db.get(Config, name)
        if config:
            config.kind = kind
            config.payload = payload
        else:
            db.add(Config(name=name, kind=kind, payload=payload))
        db.flush()


def get_config(
    name: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        config = db.get(Config, name)
        if not config:
            return None
        return config.as_dict()


def list_configs(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        stmt = (
            select(
                Config.name,
                Config.kind,
                func.length(Config.payload).label("size"),
                Config.created_at,
                Config.updated_at,
            )
            .order_by(Config.updated_at.desc())
        )
        rows = db.execute(stmt).all()
        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "name": row.name,
                    "kind": row.kind,
                    "size": int(row.size or 0),
                    "created_at": format_timestamp(row.created_at),
                    "updated_at": format_timestamp(row.updated_at),
                }
            )
        return results


def delete_config(
    name: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        config = db.get(Config, name)
        if not config:
            return False
        db.delete(config)
        db.flush()
        return True


def save_report(
    report_id: str,
    summary: Dict[str, Any],
    report: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
    review_metadata: Optional[Dict[str, Any]] = None,
) -> None:
    summary_json = json.dumps(summary)
    report_json = json.dumps(report)
    with _get_session(session, db_path) as db:
        existing = db.get(Report, report_id)
        if existing:
            existing.summary = summary_json
            existing.report = report_json
            existing.updated_at = datetime.now(timezone.utc)
            _apply_report_review_metadata(existing, review_metadata)
        else:
            record = Report(
                id=report_id,
                summary=summary_json,
                report=report_json,
                review_status=DEFAULT_REVIEW_STATUS,
            )
            db.add(record)
            _apply_report_review_metadata(record, review_metadata)
        db.flush()


def list_reports(
    limit: int = 50,
    offset: int = 0,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
    review_status: Optional[List[str] | str] = None,
    assignee: Optional[str] = None,
    created_after: Optional[datetime | str] = None,
    created_before: Optional[datetime | str] = None,
    search: Optional[str] = None,
    order: str = "desc",
    project_id: Optional[str] = None,
) -> Dict[str, Any]:
    parsed_created_after = _parse_datetime(created_after) if created_after is not None else None
    parsed_created_before = _parse_datetime(created_before) if created_before is not None else None

    status_values: Optional[List[str]] = None
    if review_status is not None:
        if isinstance(review_status, str):
            review_status = [review_status]
        status_values = []
        for value in review_status:
            normalised = _normalise_review_status(value)
            if normalised:
                status_values.append(normalised)
        if not status_values:
            status_values = None

    filters = []
    if status_values:
        filters.append(Report.review_status.in_(status_values))
    if assignee:
        filters.append(func.lower(Report.review_assignee) == assignee.lower())
    if parsed_created_after:
        filters.append(Report.created_at >= parsed_created_after)
    if parsed_created_before:
        filters.append(Report.created_at <= parsed_created_before)
    if search:
        term = f"%{search.lower()}%"
        filters.append(
            or_(
                func.lower(Report.id).like(term),
                func.lower(Report.review_assignee).like(term),
                func.lower(Report.review_notes).like(term),
            )
        )

    order_normalised = order.lower() if order else "desc"
    primary_order = Report.created_at.desc() if order_normalised != "asc" else Report.created_at.asc()
    secondary_order = Report.id.desc() if order_normalised != "asc" else Report.id.asc()

    with _get_session(session, db_path) as db:
        base = select(
            Report.id,
            Report.summary,
            Report.created_at,
            Report.updated_at,
            Report.review_status,
            Report.review_assignee,
            Report.review_due_at,
            Report.review_notes,
        )
        if project_id:
            try:
                _get_project_or_raise(db, project_id)
            except ProjectNotFoundError as exc:
                raise ValueError(f"project '{project_id}' not found") from exc
            base = base.join(ProjectRun, Report.id == ProjectRun.report_id).where(ProjectRun.project_id == project_id)
        if filters:
            base = base.where(*filters)

        total_stmt = select(func.count(func.distinct(Report.id))).select_from(Report)
        if project_id:
            total_stmt = total_stmt.join(ProjectRun, Report.id == ProjectRun.report_id).where(
                ProjectRun.project_id == project_id
            )
        if filters:
            total_stmt = total_stmt.where(*filters)
        total_count = int(db.execute(total_stmt).scalar_one())

        status_counts_stmt = select(Report.review_status, func.count()).select_from(Report).group_by(Report.review_status)
        if project_id:
            status_counts_stmt = status_counts_stmt.join(ProjectRun, Report.id == ProjectRun.report_id).where(
                ProjectRun.project_id == project_id
            )
        if filters:
            status_counts_stmt = status_counts_stmt.where(*filters)
        status_counts_rows = db.execute(status_counts_stmt).all()
        status_counts: Dict[str, int] = {row[0]: int(row[1] or 0) for row in status_counts_rows}

        summary_stmt = select(Report.summary).select_from(Report)
        if project_id:
            summary_stmt = summary_stmt.join(ProjectRun, Report.id == ProjectRun.report_id).where(
                ProjectRun.project_id == project_id
            )
        if filters:
            summary_stmt = summary_stmt.where(*filters)
        severity_counts: Dict[str, int] = {}
        for row in db.execute(summary_stmt):
            summary = _safe_json_load(row.summary, expect_mapping=True)
            counts = summary.get("severity_counts") if isinstance(summary, dict) else None
            if not counts:
                continue
            for severity, value in counts.items():
                try:
                    numeric = int(value or 0)
                except (TypeError, ValueError):
                    numeric = 0
                severity_counts[severity] = severity_counts.get(severity, 0) + numeric

        items_stmt = base.order_by(primary_order, secondary_order).offset(max(offset, 0)).limit(limit)
        rows = db.execute(items_stmt).all()
        items: List[Dict[str, Any]] = []
        for row in rows:
            items.append(
                {
                    "id": row.id,
                    "summary": _safe_json_load(row.summary, expect_mapping=True),
                    "created_at": format_timestamp(row.created_at),
                    "updated_at": format_timestamp(row.updated_at),
                    "review_status": row.review_status,
                    "review_assignee": row.review_assignee,
                    "review_due_at": format_timestamp(row.review_due_at),
                    "review_notes": row.review_notes,
                }
            )

        next_offset = offset + limit if offset + limit < total_count else None
        has_more = next_offset is not None

        return {
            "items": items,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
            "next_offset": next_offset,
            "has_more": has_more,
            "aggregates": {
                "status_counts": status_counts,
                "severity_counts": severity_counts,
            },
        }


def get_report(
    report_id: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        record = db.get(Report, report_id)
        if not record:
            return None
        return {
            "id": record.id,
            "summary": _safe_json_load(record.summary, expect_mapping=True),
            "report": _safe_json_load(record.report, expect_mapping=False),
            "review_status": record.review_status,
            "review_assignee": record.review_assignee,
            "review_due_at": format_timestamp(record.review_due_at),
            "review_notes": record.review_notes,
            "created_at": format_timestamp(record.created_at),
            "updated_at": format_timestamp(record.updated_at),
        }


def update_report_review(
    report_id: str,
    *,
    review_status: Optional[str] = None,
    review_assignee: Optional[str] = None,
    review_due_at: Optional[str | datetime] = None,
    review_notes: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    metadata: Dict[str, Any] = {}
    if review_status is not None:
        metadata["review_status"] = review_status
    if review_assignee is not None:
        metadata["review_assignee"] = review_assignee
    if review_due_at is not None:
        metadata["review_due_at"] = review_due_at
    if review_notes is not None:
        metadata["review_notes"] = review_notes

    with _get_session(session, db_path) as db:
        record = db.get(Report, report_id)
        if not record:
            return None
        _apply_report_review_metadata(record, metadata)
        db.flush()
        return {
            "id": record.id,
            "review_status": record.review_status,
            "review_assignee": record.review_assignee,
            "review_due_at": format_timestamp(record.review_due_at),
            "review_notes": record.review_notes,
            "updated_at": format_timestamp(record.updated_at),
        }


def create_report_comment(
    report_id: str,
    body: str,
    *,
    author: Optional[str] = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    cleaned_body = body.strip()
    if not cleaned_body:
        raise ValueError("comment body cannot be empty")
    cleaned_author = author.strip() if isinstance(author, str) else None

    with _get_session(session, db_path) as db:
        report = db.get(Report, report_id)
        if not report:
            raise ReportNotFoundError(report_id)
        comment = ReportComment(report_id=report_id, body=cleaned_body, author=cleaned_author)
        db.add(comment)
        report.updated_at = datetime.now(timezone.utc)
        db.flush()
        return comment.as_dict()


def list_report_comments(
    report_id: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        report = db.get(Report, report_id)
        if not report:
            raise ReportNotFoundError(report_id)
        stmt = (
            select(ReportComment)
            .where(ReportComment.report_id == report_id)
            .order_by(ReportComment.created_at.asc(), ReportComment.id.asc())
        )
        rows = db.execute(stmt).scalars().all()
        return [row.as_dict() for row in rows]


def delete_report_comment(
    report_id: str,
    comment_id: str,
    *,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        comment = db.get(ReportComment, comment_id)
        if not comment or comment.report_id != report_id:
            return False
        db.delete(comment)
        parent = db.get(Report, report_id)
        if parent:
            parent.updated_at = datetime.now(timezone.utc)
        db.flush()
        return True


def delete_report(
    report_id: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        record = db.get(Report, report_id)
        if not record:
            return False
        db.delete(record)
        db.flush()
        return True


def upsert_setting(
    key: str,
    value: Dict[str, Any] | str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> None:
    payload = value if isinstance(value, str) else json.dumps(value)
    with _get_session(session, db_path) as db:
        record = db.get(Setting, key)
        if record:
            record.value = payload
        else:
            db.add(Setting(key=key, value=payload))
        db.flush()


def get_setting(
    key: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> Optional[str]:
    with _get_session(session, db_path) as db:
        record = db.get(Setting, key)
        if not record:
            return None
        return record.value


def get_llm_settings(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> Dict[str, Any]:
    raw = get_setting("llm", db_path=db_path, session=session)
    if not raw:
        return {"provider": "off"}
    try:
        return json.loads(raw)
    except Exception:
        return {"provider": "off"}


def _safe_json_load(value: Optional[str], *, expect_mapping: bool) -> Any:
    if not value:
        return {} if expect_mapping else {}
    try:
        data = json.loads(value)
        if expect_mapping and not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {} if expect_mapping else {}


@contextmanager
def _get_session(existing: Session | None, db_path: Path) -> Iterator[Session]:
    if existing is not None:
        yield existing
        return
    with session_scope(db_path) as scoped:
        yield scoped
