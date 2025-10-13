from __future__ import annotations

import json
import re
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional, Tuple
from uuid import uuid4

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import (
    Config,
    Report,
    Setting,
    Project,
    ProjectRun,
    format_timestamp,
)
from backend.db.session import DEFAULT_DB_PATH as _DEFAULT_DB_PATH, init_models, session_scope

DEFAULT_DB_PATH = _DEFAULT_DB_PATH
DEFAULT_PROJECTS_ROOT = Path("data/projects")


class ProjectNotFoundError(Exception):
    """Raised when a project cannot be located in the database."""


class ProjectRunNotFoundError(Exception):
    """Raised when a project run cannot be located or is mismatched."""


class ArtifactPathError(Exception):
    """Raised when a requested artifact path is invalid or escapes the run root."""


def get_projects_root(base_path: Path | None = None) -> Path:
    root = (base_path or DEFAULT_PROJECTS_ROOT).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


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


def _ensure_run_directory(
    db: Session,
    project: Project,
    run: ProjectRun,
    projects_root: Path | None = None,
) -> Path:
    root_base = get_projects_root(projects_root)
    project_root = Path(project.root_path) if project.root_path else root_base / project.slug
    project_root.mkdir(parents=True, exist_ok=True)
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
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        projects = db.execute(
            select(Project).order_by(Project.updated_at.desc(), Project.created_at.desc())
        ).scalars()
        return [project.to_dict(include_metadata=False) for project in projects]


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


def create_project_run(
    project_id: str,
    label: str,
    *,
    kind: str,
    status: str = "queued",
    triggered_by: str | None = None,
    parameters: Dict[str, Any] | None = None,
    projects_root: Path | None = None,
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> Dict[str, Any]:
    metadata = dict(parameters or {})
    with _get_session(session, db_path) as db:
        try:
            project = _get_project_or_raise(db, project_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        run = ProjectRun(
            project_id=project.id,
            label=label,
            kind=kind,
            status=status,
            triggered_by=triggered_by,
            parameters=metadata,
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
    db_path: Path = DEFAULT_DB_PATH,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        try:
            _get_project_or_raise(db, project_id)
        except ProjectNotFoundError as exc:
            raise ValueError(f"project '{project_id}' not found") from exc
        stmt = (
            select(ProjectRun)
            .where(ProjectRun.project_id == project_id)
            .order_by(ProjectRun.created_at.desc())
            .limit(limit)
        )
        runs = db.execute(stmt).scalars()
        return [run.to_dict(include_parameters=False) for run in runs]


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
        target = _resolve_artifact_path(run_dir, path)
        if not target.exists():
            raise FileNotFoundError(str(path or ""))
        if not target.is_dir():
            raise ArtifactPathError("path must reference a directory")

        entries: List[Dict[str, Any]] = []
        for child in sorted(target.iterdir(), key=lambda item: (not item.is_dir(), item.name.lower())):
            stat = child.stat()
            modified = datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)
            entries.append(
                {
                    "name": child.name,
                    "path": str(child.relative_to(run_dir)),
                    "is_dir": child.is_dir(),
                    "size": int(stat.st_size) if child.is_file() else None,
                    "modified_at": format_timestamp(modified),
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
        db.flush()

        return {
            "name": destination.name,
            "path": str(destination.relative_to(run_dir)),
            "is_dir": False,
            "size": int(stat.st_size),
            "modified_at": format_timestamp(datetime.fromtimestamp(stat.st_mtime, tz=timezone.utc)),
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

        destination.unlink()
        run.updated_at = datetime.now(tz=timezone.utc)
        db.flush()
        return True


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialise database tables using SQLAlchemy metadata."""
    init_models(db_path)


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
) -> None:
    summary_json = json.dumps(summary)
    report_json = json.dumps(report)
    with _get_session(session, db_path) as db:
        existing = db.get(Report, report_id)
        if existing:
            existing.summary = summary_json
            existing.report = report_json
        else:
            db.add(Report(id=report_id, summary=summary_json, report=report_json))
        db.flush()


def list_reports(
    limit: int = 50,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        stmt = (
            select(Report.id, Report.summary, Report.created_at)
            .order_by(Report.created_at.desc())
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "id": row.id,
                    "summary": _safe_json_load(row.summary, expect_mapping=True),
                    "created_at": format_timestamp(row.created_at),
                }
            )
        return results


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
            "created_at": format_timestamp(record.created_at),
        }


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
