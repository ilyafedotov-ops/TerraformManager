from __future__ import annotations

import json
import os
import shutil
import zipfile
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone

from fastapi import APIRouter, FastAPI, HTTPException, Query, Depends, UploadFile, File, Form, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from backend.db import get_session_dependency
from backend.scanner import scan_paths
from backend.report_html import render_html_report
from backend.policies.config import apply_config, load_config
from backend.knowledge_sync import sync_many
from backend.rag import retrieve_snippets
from backend.storage import (
    DEFAULT_DB_PATH,
    get_config,
    list_configs,
    upsert_config,
    init_db,
    save_report,
    list_reports,
    get_report,
    delete_config,
    delete_report,
    upsert_setting,
    get_llm_settings as db_get_llm_settings,
    update_report_review,
    create_report_comment,
    list_report_comments,
    delete_report_comment,
    ReportNotFoundError,
    get_project,
    get_project_workspace,
    resolve_workspace_paths,
    resolve_workspace_file,
    WorkspacePathError,
    create_project_run,
    update_project_run,
    save_run_artifact,
    register_generated_asset,
    report_belongs_to_project,
)
from backend.preview_html import render_preview_html
from backend.report_csv import render_csv_report
from fastapi.staticfiles import StaticFiles
from backend.version import __version__
from backend.llm_service import validate_provider_config, live_ping
from backend.generators.blueprints import render_blueprint_bundle
from backend.generators.models import (
    BlueprintRequest,
    AwsS3GeneratorPayload,
    AzureApiManagementGeneratorPayload,
    AzureFunctionAppGeneratorPayload,
    AzureServiceBusGeneratorPayload,
    AzureStorageGeneratorPayload,
)
from backend.generators.registry import get_generator_definition, list_generator_metadata
from backend.utils.logging import setup_logging
from api.dependencies import require_current_user
from api.middleware.logging import RequestLoggingMiddleware
from api.routes import auth as auth_routes
from api.routes import projects as project_routes

KNOWLEDGE_ROOT = Path("knowledge").resolve()

setup_logging(service="terraform-manager-api")

DEFAULT_ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://127.0.0.1:5173",
    "http://localhost:4173",
    "http://127.0.0.1:4173",
]
DEFAULT_ALLOWED_ORIGIN_REGEX = r"^https?://[^\s/$.?#].[^\s]*$"


def _parse_env_list(var_name: str) -> List[str]:
    raw = os.getenv(var_name)
    if not raw:
        return []
    items = [value.strip() for value in raw.split(",")]
    unique = []
    for item in items:
        if not item or item in unique:
            continue
        unique.append(item)
    return unique


def _allowed_origins() -> List[str]:
    configured = _parse_env_list("TFM_ALLOWED_ORIGINS")
    if configured:
        return configured
    return list(DEFAULT_ALLOWED_ORIGINS)


def _allowed_origin_regex(explicit_origins_defined: bool) -> Optional[str]:
    override = os.getenv("TFM_ALLOWED_ORIGIN_REGEX")
    if override:
        return override
    if explicit_origins_defined:
        return None
    return DEFAULT_ALLOWED_ORIGIN_REGEX


def _trusted_hosts() -> List[str]:
    return _parse_env_list("TFM_TRUSTED_HOSTS")


api_router = APIRouter()


def _startup() -> None:
    init_db(DEFAULT_DB_PATH)


def create_app() -> FastAPI:
    application = FastAPI(title="Terraform Manager API", version=__version__)
    application.include_router(auth_routes.router)
    application.include_router(project_routes.router)
    application.include_router(api_router)
    application.mount("/docs", StaticFiles(directory="docs"), name="docs")
    allowed_origins = _allowed_origins()
    origin_regex = _allowed_origin_regex(bool(_parse_env_list("TFM_ALLOWED_ORIGINS")))
    application.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_origin_regex=origin_regex,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    trusted_hosts = _trusted_hosts()
    if trusted_hosts:
        application.add_middleware(TrustedHostMiddleware, allowed_hosts=trusted_hosts)
    application.add_middleware(RequestLoggingMiddleware)
    application.add_event_handler("startup", _startup)
    return application


def _require_project_record(session: Session, project_id: str | None, project_slug: str | None) -> Dict[str, Any]:
    if not project_id and not project_slug:
        raise HTTPException(400, "project_id or project_slug is required")
    record = get_project(project_id=project_id, slug=project_slug, session=session)
    if not record:
        identifier = project_id or project_slug or "<missing>"
        raise HTTPException(404, f"project '{identifier}' not found")
    return record


def _require_report_project_context(
    session: Session,
    report_id: str,
    project_id: str | None,
    project_slug: str | None,
) -> Dict[str, Any]:
    project = _require_project_record(session, project_id, project_slug)
    if not report_belongs_to_project(report_id, project["id"], session=session):
        raise HTTPException(404, "report not found in the specified project")
    return project


def _merge_tags(*tag_groups: Optional[List[str]]) -> List[str]:
    merged: List[str] = []
    seen: set[str] = set()
    for tags in tag_groups:
        for tag in tags or []:
            cleaned = (tag or "").strip()
            if not cleaned or cleaned in seen:
                continue
            merged.append(cleaned)
            seen.add(cleaned)
    return merged


def _start_scan_run(
    project: Dict[str, Any],
    *,
    run_label: str | None,
    run_kind: str | None,
    paths: List[str],
    terraform_validate: bool,
    cost_enabled: bool,
    plan_path: str | None,
    session: Session,
) -> Dict[str, Any]:
    label = (run_label or "").strip() or f"API scan {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S')}"
    kind = (run_kind or "").strip() or "review"
    parameters = {
        "paths": paths,
        "terraform_validate": terraform_validate,
        "cost_enabled": cost_enabled,
        "plan_path": plan_path,
    }
    return create_project_run(
        project_id=project["id"],
        label=label,
        kind=kind,
        status="running",
        parameters=parameters,
        session=session,
    )


def _mark_scan_run_failure(
    run_id: str,
    project_id: str,
    *,
    message: str,
    session: Session,
) -> None:
    update_project_run(
        run_id,
        project_id=project_id,
        status="failed",
        summary={"error": message},
        finished_at=datetime.now(timezone.utc),
        session=session,
    )


def _persist_scan_outputs(
    project: Dict[str, Any],
    run: Dict[str, Any],
    *,
    report: Dict[str, Any],
    paths: List[str],
    asset_name: str | None,
    asset_description: str | None,
    asset_tags: Optional[List[str]],
    asset_metadata: Optional[Dict[str, Any]],
    source: str,
    session: Session,
) -> Dict[str, Any]:
    summary = dict(report.get("summary", {}))
    report_id = report.get("id") or str(uuid.uuid4())
    save_report(report_id, summary, report, session=session)
    report["id"] = report_id

    json_bytes = json.dumps(report, indent=2).encode("utf-8")
    json_artifact_path = f"reports/{report_id}.json"
    save_run_artifact(
        project_id=project["id"],
        run_id=run["id"],
        path=json_artifact_path,
        data=json_bytes,
        session=session,
    )

    html_text = render_html_report(report)
    html_bytes = html_text.encode("utf-8")
    html_artifact_path = f"reports/{report_id}.html"
    save_run_artifact(
        project_id=project["id"],
        run_id=run["id"],
        path=html_artifact_path,
        data=html_bytes,
        session=session,
    )

    generated_at = datetime.now(timezone.utc)
    resolved_asset_name = (asset_name or "").strip() or f"Scan report {generated_at.strftime('%Y-%m-%d %H:%M:%S')}"
    tags = _merge_tags(["scan", "report", source], asset_tags)
    metadata = dict(asset_metadata or {})
    metadata.setdefault("summary", summary)
    metadata.setdefault("source", source)
    metadata.setdefault("paths", paths)

    asset_result = register_generated_asset(
        project_id=project["id"],
        name=resolved_asset_name,
        asset_type="scan_report",
        description=asset_description.strip() if asset_description else None,
        tags=tags,
        metadata=metadata,
        run_id=run["id"],
        storage_filename=f"{report_id}.json",
        data=json_bytes,
        media_type="application/json",
        notes="Saved automatically from API scan.",
        files=[
            {
                "path": f"{report_id}.html",
                "content": html_bytes,
                "media_type": "text/html",
            }
        ],
        version_metadata={"report_id": report_id, "source": source},
        session=session,
    )

    summary["asset_id"] = asset_result["asset"]["id"]
    summary["version_id"] = asset_result["version"]["id"]
    summary["asset_name"] = asset_result["asset"].get("name")
    summary["asset_type"] = asset_result["asset"].get("asset_type")
    summary["artifacts"] = [json_artifact_path, html_artifact_path]
    report["summary"] = summary

    return {
        "report_id": report_id,
        "asset": asset_result["asset"],
        "version": asset_result["version"],
        "artifacts": [json_artifact_path, html_artifact_path],
        "summary": summary,
    }

@api_router.get("/health")
def health() -> Dict[str, str]:
    return {"status": "ok"}


class ScanRequest(BaseModel):
    paths: List[str]
    terraform_validate: bool = False
    save: bool = True
    llm: Optional[Dict[str, Any]] = None
    cost: bool = False
    cost_usage_file: Optional[str] = None
    plan_path: Optional[str] = None
    project_id: Optional[str] = None
    project_slug: Optional[str] = None
    run_label: Optional[str] = None
    run_kind: Optional[str] = None
    asset_name: Optional[str] = None
    asset_description: Optional[str] = None
    asset_tags: List[str] = Field(default_factory=list)
    asset_metadata: Optional[Dict[str, Any]] = None


class ReportReviewUpdatePayload(BaseModel):
    review_status: Optional[str] = None
    review_assignee: Optional[str] = None
    review_due_at: Optional[str | datetime] = None
    review_notes: Optional[str] = None


class ReportCommentCreatePayload(BaseModel):
    body: str
    author: Optional[str] = None


@api_router.post("/scan")
def scan(
    req: ScanRequest,
    session: Session = Depends(get_session_dependency),
    current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    project = _require_project_record(session, req.project_id, req.project_slug)
    try:
        project_root = get_project_workspace(project)
        path_objs = resolve_workspace_paths(project_root, req.paths)
    except WorkspacePathError as exc:
        raise HTTPException(400, str(exc)) from exc

    cost_options = None
    if req.cost:
        cost_options = {}
        if req.cost_usage_file:
            try:
                usage_path = resolve_workspace_file(
                    project_root, req.cost_usage_file, label="cost usage file"
                )
            except WorkspacePathError as exc:
                raise HTTPException(400, str(exc)) from exc
            cost_options["usage_file"] = usage_path

    plan_path: Optional[Path] = None
    if req.plan_path:
        try:
            plan_path = resolve_workspace_file(project_root, req.plan_path, label="plan file")
        except WorkspacePathError as exc:
            raise HTTPException(400, str(exc)) from exc

    run_record: Optional[Dict[str, Any]] = None
    if req.save:
        try:
            run_record = _start_scan_run(
                project,
                run_label=req.run_label,
                run_kind=req.run_kind,
                paths=req.paths,
                terraform_validate=req.terraform_validate,
                cost_enabled=req.cost,
                plan_path=req.plan_path,
                session=session,
            )
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    scan_context = {
        "source": "api.scan",
        "user": current_user.user.email if current_user.user else None,
        "project_id": project["id"],
        "project_slug": project.get("slug"),
    }
    try:
        report = scan_paths(
            path_objs,
            use_terraform_validate=req.terraform_validate,
            llm_options=req.llm,
            cost_options=cost_options,
            plan_path=plan_path,
            context=scan_context,
        )
    except Exception as exc:  # noqa: BLE001
        if run_record:
            _mark_scan_run_failure(run_record["id"], project["id"], message=str(exc), session=session)
        raise

    if req.save and run_record:
        try:
            persist = _persist_scan_outputs(
                project,
                run_record,
                report=report,
                paths=req.paths,
                asset_name=req.asset_name,
                asset_description=req.asset_description,
                asset_tags=req.asset_tags,
                asset_metadata=req.asset_metadata,
                source="api.scan",
                session=session,
            )
        except Exception as exc:  # noqa: BLE001
            _mark_scan_run_failure(run_record["id"], project["id"], message=str(exc), session=session)
            raise

        summary_payload = dict(persist["summary"])
        summary_payload.update(
            {
                "report_id": persist["report_id"],
                "asset_id": persist["asset"]["id"],
                "version_id": persist["version"]["id"],
                "artifacts": persist["artifacts"],
            }
        )
        update_project_run(
            run_record["id"],
            project_id=project["id"],
            status="completed",
            summary=summary_payload,
            finished_at=datetime.now(timezone.utc),
            session=session,
            report_id=persist["report_id"],
        )
        report["id"] = persist["report_id"]
    return report


@api_router.get("/reports")
def reports(
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    status: Optional[List[str]] = Query(None, description="Filter by review status"),
    assignee: Optional[str] = Query(None, description="Filter by review assignee"),
    created_after: Optional[str] = Query(None, description="ISO timestamp lower bound"),
    created_before: Optional[str] = Query(None, description="ISO timestamp upper bound"),
    search: Optional[str] = Query(None, description="Case-insensitive search across id, assignee, notes"),
    order: str = Query("desc", description="Sort direction: asc or desc"),
    project_id: Optional[str] = Query(None, description="Restrict results to a specific project"),
    project_slug: Optional[str] = Query(None, description="Restrict results to a project slug"),
    session: Session = Depends(get_session_dependency),
    current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    order_normalised = order.lower()
    if order_normalised not in {"asc", "desc"}:
        raise HTTPException(400, "order must be 'asc' or 'desc'")
    try:
        return list_reports(
            limit=limit,
            offset=offset,
            review_status=status,
            assignee=assignee,
            created_after=created_after,
            created_before=created_before,
            search=search,
            order=order_normalised,
            project_id=project_id,
            project_slug=project_slug,
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@api_router.get("/reports/{report_id}")
def get_report_json(
    report_id: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    rec = get_report(report_id, session=session)
    if not rec:
        raise HTTPException(404, "report not found")
    return rec


@api_router.patch("/reports/{report_id}")
def update_report_review_metadata(
    report_id: str,
    payload: ReportReviewUpdatePayload,
    project_id: Optional[str] = Query(None, description="Owning project id"),
    project_slug: Optional[str] = Query(None, description="Owning project slug"),
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    _require_report_project_context(session, report_id, project_id, project_slug)
    data = payload.dict(exclude_unset=True)
    if not data:
        existing = get_report(report_id, session=session)
        if not existing:
            raise HTTPException(404, "report not found")
        return {
            "id": existing["id"],
            "review_status": existing["review_status"],
            "review_assignee": existing["review_assignee"],
            "review_due_at": existing["review_due_at"],
            "review_notes": existing["review_notes"],
            "updated_at": existing["updated_at"],
        }
    try:
        result = update_report_review(
            report_id,
            session=session,
            **data,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not result:
        raise HTTPException(404, "report not found")
    return result


@api_router.get("/reports/{report_id}/comments")
def list_report_comments_api(
    report_id: str,
    project_id: Optional[str] = Query(None, description="Owning project id"),
    project_slug: Optional[str] = Query(None, description="Owning project slug"),
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    _require_report_project_context(session, report_id, project_id, project_slug)
    try:
        comments = list_report_comments(report_id, session=session)
    except ReportNotFoundError as exc:
        raise HTTPException(404, "report not found") from exc
    return {"items": comments}


@api_router.post("/reports/{report_id}/comments", status_code=201)
def create_report_comment_api(
    report_id: str,
    payload: ReportCommentCreatePayload,
    project_id: Optional[str] = Query(None, description="Owning project id"),
    project_slug: Optional[str] = Query(None, description="Owning project slug"),
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    _require_report_project_context(session, report_id, project_id, project_slug)
    try:
        return create_report_comment(
            report_id,
            payload.body,
            author=payload.author,
            session=session,
        )
    except ReportNotFoundError as exc:
        raise HTTPException(404, "report not found") from exc
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@api_router.delete("/reports/{report_id}/comments/{comment_id}")
def delete_report_comment_api(
    report_id: str,
    comment_id: str,
    project_id: Optional[str] = Query(None, description="Owning project id"),
    project_slug: Optional[str] = Query(None, description="Owning project slug"),
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    _require_report_project_context(session, report_id, project_id, project_slug)
    deleted = delete_report_comment(report_id, comment_id, session=session)
    if not deleted:
        raise HTTPException(404, "comment not found")
    return {"status": "deleted", "id": comment_id}


@api_router.get("/reports/{report_id}/html", response_class=HTMLResponse)
def get_report_html(
    report_id: str,
    session: Session = Depends(get_session_dependency),
) -> str:
    rec = get_report(report_id, session=session)
    if not rec:
        raise HTTPException(404, "report not found")
    return render_html_report(rec["report"])  # type: ignore[arg-type]


@api_router.delete("/reports/{report_id}")
def delete_report_api(
    report_id: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    ok = delete_report(report_id, session=session)
    if not ok:
        raise HTTPException(404, "report not found")
    return {"status": "deleted", "id": report_id}


def _safe_extract_zip(data: bytes, destination: Path) -> None:
    with zipfile.ZipFile(BytesIO(data)) as zf:
        for member in zf.infolist():
            name = member.filename
            if not name or name.endswith("/"):
                continue
            target = destination / name
            resolved = target.resolve()
            try:
                resolved.relative_to(destination)
            except ValueError as exc:
                raise HTTPException(400, f"zip entry '{name}' escapes workspace") from exc
            resolved.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(member, "r") as src, resolved.open("wb") as handle:
                shutil.copyfileobj(src, handle)


@api_router.post("/scan/upload")
async def scan_upload(
    files: List[UploadFile] = File(...),
    terraform_validate: bool = Form(False),
    save: bool = Form(True),
    include_cost: bool = Form(False),
    cost_usage_file: UploadFile | None = File(None),
    plan_file: UploadFile | None = File(None),
    project_id: str | None = Form(None),
    project_slug: str | None = Form(None),
    run_label: str | None = Form(None),
    run_kind: str | None = Form(None),
    asset_name: str | None = Form(None),
    asset_description: str | None = Form(None),
    asset_tags: str | None = Form(None, description="Comma-separated list of tags for the saved report asset"),
    asset_metadata: str | None = Form(None, description="JSON object describing custom asset metadata"),
    session: Session = Depends(get_session_dependency),
    current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    if not files:
        raise HTTPException(400, "no files uploaded")

    project = _require_project_record(session, project_id, project_slug)
    try:
        project_root = get_project_workspace(project)
    except WorkspacePathError as exc:
        raise HTTPException(400, str(exc)) from exc

    upload_root = project_root / "uploads" / f"scan-{uuid.uuid4().hex}"
    upload_root.mkdir(parents=True, exist_ok=True)

    targets: List[Path] = []
    usage_path: Optional[Path] = None
    plan_path: Optional[Path] = None
    report_id: Optional[str] = None

    parsed_asset_tags: List[str] = []
    if asset_tags:
        parsed_asset_tags = [tag.strip() for tag in asset_tags.split(",") if tag.strip()]
    parsed_asset_metadata: Dict[str, Any] = {}
    if asset_metadata:
        try:
            parsed_asset_metadata = json.loads(asset_metadata)
        except json.JSONDecodeError as exc:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "asset_metadata must be valid JSON") from exc
        if not isinstance(parsed_asset_metadata, dict):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "asset_metadata must be a JSON object")

    run_record: Optional[Dict[str, Any]] = None

    try:
        for upload in files:
            filename = Path(upload.filename or "upload.tf")
            data = await upload.read()
            dest = upload_root / filename.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

            suffix = dest.suffix.lower()
            if suffix == ".zip":
                extract_root = upload_root / f"{filename.stem}-{uuid.uuid4().hex[:8]}"
                extract_root.mkdir(parents=True, exist_ok=True)
                try:
                    _safe_extract_zip(data, extract_root)
                except zipfile.BadZipFile as exc:
                    raise HTTPException(400, f"invalid zip archive: {filename}") from exc
                targets.append(extract_root)
            elif suffix == ".tf":
                targets.append(dest)
            elif suffix == ".json" and plan_path is None:
                plan_path = dest
            else:
                continue

        if include_cost and cost_usage_file is not None:
            usage_bytes = await cost_usage_file.read()
            usage_filename = cost_usage_file.filename or "usage.yml"
            usage_path = upload_root / usage_filename
            usage_path.write_bytes(usage_bytes)

        if plan_file is not None:
            plan_bytes = await plan_file.read()
            plan_filename = plan_file.filename or "plan.json"
            plan_path = upload_root / plan_filename
            plan_path.write_bytes(plan_bytes)

        if not targets:
            raise HTTPException(400, "no Terraform files found in upload")

        llm_opts = db_get_llm_settings(session=session)
        provider = (llm_opts.get("provider") or "off").lower()
        llm = llm_opts if provider in {"openai", "azure"} else None

        cost_options: Optional[Dict[str, Any]] = None
        if include_cost:
            cost_options = {"usage_file": usage_path}

        run_paths = [str(path) for path in targets]
        if save:
            try:
                run_record = _start_scan_run(
                    project,
                    run_label=run_label,
                    run_kind=run_kind,
                    paths=run_paths,
                    terraform_validate=terraform_validate,
                    cost_enabled=include_cost,
                    plan_path=str(plan_path) if plan_path else None,
                    session=session,
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc

        scan_context = {
            "source": "api.scan_upload",
            "user": current_user.user.email if current_user.user else None,
            "project_id": project["id"],
            "project_slug": project.get("slug"),
        }
        try:
            report = scan_paths(
                targets,
                use_terraform_validate=terraform_validate,
                llm_options=llm,
                cost_options=cost_options,
                plan_path=plan_path,
                context=scan_context,
            )
        except Exception as exc:  # noqa: BLE001
            if run_record:
                _mark_scan_run_failure(run_record["id"], project["id"], message=str(exc), session=session)
            raise

        if save and run_record:
            try:
                persist = _persist_scan_outputs(
                    project,
                    run_record,
                    report=report,
                    paths=run_paths,
                    asset_name=asset_name,
                    asset_description=asset_description,
                    asset_tags=parsed_asset_tags,
                    asset_metadata=parsed_asset_metadata,
                    source="api.scan_upload",
                    session=session,
                )
            except Exception as exc:  # noqa: BLE001
                _mark_scan_run_failure(run_record["id"], project["id"], message=str(exc), session=session)
                raise

            report_id = persist["report_id"]
            summary_payload = dict(persist["summary"])
            summary_payload.update(
                {
                    "report_id": persist["report_id"],
                    "asset_id": persist["asset"]["id"],
                    "version_id": persist["version"]["id"],
                    "artifacts": persist["artifacts"],
                }
            )
            update_project_run(
                run_record["id"],
                project_id=project["id"],
                status="completed",
                summary=summary_payload,
                finished_at=datetime.now(timezone.utc),
                session=session,
                report_id=report_id,
            )
            report["id"] = report_id
    finally:
        shutil.rmtree(upload_root, ignore_errors=True)

    return {
        "id": report_id,
        "summary": report.get("summary", {}),
        "report": report,
    }


class ConfigPayload(BaseModel):
    name: str
    payload: str  # YAML content for tfreview config
    kind: str = "tfreview"


@api_router.get("/configs")
def configs_list(
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> List[Dict[str, Any]]:
    return list_configs(session=session)


@api_router.post("/configs")
def configs_upsert(
    cfg: ConfigPayload,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, str]:
    upsert_config(cfg.name, cfg.payload, kind=cfg.kind, session=session)
    return {"status": "saved", "name": cfg.name}


@api_router.get("/configs/{name}")
def configs_get(
    name: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    rec = get_config(name, session=session)
    if not rec:
        raise HTTPException(404, "config not found")
    return rec


@api_router.delete("/configs/{name}")
def configs_delete(
    name: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    ok = delete_config(name, session=session)
    if not ok:
        raise HTTPException(404, "config not found")
    return {"status": "deleted", "name": name}


class PreviewRequest(BaseModel):
    config_name: Optional[str] = None
    paths: Optional[List[str]] = None
    report_id: Optional[str] = None


@api_router.post("/preview/config-application")
def preview_config(
    req: PreviewRequest,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    # Determine findings source: existing report or fresh scan
    report: Optional[Dict[str, Any]] = None
    if req.report_id:
        rec = get_report(req.report_id, session=session)
        if not rec:
            raise HTTPException(404, "report not found")
        report = rec["report"]
    elif req.paths:
        report = scan_paths(
            [Path(p) for p in req.paths],
            use_terraform_validate=False,
            context={"source": "api.preview", "path_count": len(req.paths)},
        )
    else:
        raise HTTPException(400, "either report_id or paths must be provided")

    findings = report.get("findings", []) if report else []

    # Load config: explicit saved config name takes precedence, else discover from paths
    if req.config_name:
        cfg = get_config(req.config_name, session=session)
        if not cfg:
            raise HTTPException(404, "config not found")
        tmp_path = Path("/tmp/tfreview.preview.yaml")
        tmp_path.write_text(cfg["payload"], encoding="utf-8")
        review_cfg = load_config([tmp_path])
    else:
        review_cfg = load_config([Path(p) for p in (req.paths or [])])

    applied = apply_config(findings, review_cfg)
    return {
        "summary": {
            "before": report.get("summary", {}),
            "after": {
                "issues_found": len(applied["active"]),
                "severity_counts": applied.get("severity_counts", {}),
                "thresholds": applied.get("thresholds", {}),
            },
        },
        "waived": applied.get("waived", []),
        "active": applied.get("active", []),
    }


@api_router.get("/preview/config-application/html", response_class=HTMLResponse)
def preview_config_html(
    report_id: str | None = None,
    config_name: str | None = None,
    paths: List[str] | None = Query(default=None),
    session: Session = Depends(get_session_dependency),
) -> str:
    # Build inputs similarly to the JSON preview
    report: Optional[Dict[str, Any]] = None
    if report_id:
        rec = get_report(report_id, session=session)
        if not rec:
            raise HTTPException(404, "report not found")
        report = rec["report"]
    elif paths:
        report = scan_paths(
            [Path(p) for p in paths],
            use_terraform_validate=False,
            context={"source": "api.preview_html", "path_count": len(paths)},
        )
    else:
        raise HTTPException(400, "either report_id or paths must be provided")

    findings = report.get("findings", []) if report else []
    if config_name:
        cfg = get_config(config_name, session=session)
        if not cfg:
            raise HTTPException(404, "config not found")
        tmp_path = Path("/tmp/tfreview.preview.yaml")
        tmp_path.write_text(cfg["payload"], encoding="utf-8")
        review_cfg = load_config([tmp_path])
    else:
        review_cfg = load_config([Path(p) for p in (paths or [])])

    applied = apply_config(findings, review_cfg)
    return render_preview_html(applied, report.get("summary", {}))


class KnowledgeSyncRequest(BaseModel):
    sources: Optional[List[str]] = None


@api_router.post("/knowledge/sync")
def knowledge_sync(
    req: KnowledgeSyncRequest,
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    sources = req.sources or [
        "https://github.com/hashicorp/policy-library-azure-storage-terraform",
        "https://github.com/terraform-aws-modules/terraform-aws-vpc",
        "https://github.com/terraform-aws-modules/terraform-aws-eks",
        "https://github.com/terraform-aws-modules/terraform-aws-rds",
        "https://github.com/terraform-aws-modules/terraform-aws-security-group",
        "https://github.com/Azure/terraform-azurerm-aks",
        "https://github.com/Azure/terraform-azurerm-network",
        "https://github.com/Azure/terraform-azurerm-storage",
        "https://github.com/kubernetes/examples",
        "https://github.com/argoproj/argo-cd",
    ]
    results = sync_many(sources)
    return {
        "synced": [
            {
                "source": r.source,
                "dest_dir": str(r.dest_dir),
                "files": [str(p) for p in r.files],
                "note": r.note,
            }
            for r in results
        ]
    }


class KnowledgeSearchResponse(BaseModel):
    items: List[Dict[str, Any]]


@api_router.get("/knowledge/search")
def knowledge_search(
    q: str,
    top_k: int = Query(3, ge=1, le=10),
    provider: Optional[str] = Query(None, description="Filter by provider: aws, azure, kubernetes")
) -> KnowledgeSearchResponse:
    snippets = retrieve_snippets(q, top_k=top_k, max_chars=800, provider=provider)
    return KnowledgeSearchResponse(items=[
        {
            "source": item["source"],
            "content": item["content"],
            "score": item.get("score", 0.0),
            "provider": item.get("provider"),
            "service": item.get("service"),
            "category": item.get("category"),
        }
        for item in snippets
    ])


@api_router.get("/knowledge/doc")
def knowledge_doc(
    path: str,
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    try:
        candidate = (KNOWLEDGE_ROOT / path).resolve()
    except OSError as exc:
        raise HTTPException(400, "invalid path") from exc
    if not str(candidate).startswith(str(KNOWLEDGE_ROOT)):
        raise HTTPException(403, "access denied")
    if not candidate.is_file():
        raise HTTPException(404, "document not found")
    if candidate.suffix.lower() != ".md":
        raise HTTPException(400, "unsupported document type")
    try:
        content = candidate.read_text(encoding="utf-8")
    except OSError as exc:
        raise HTTPException(500, "unable to read document") from exc
    relative_path = candidate.relative_to(KNOWLEDGE_ROOT)
    return {
        "path": str(relative_path),
        "title": relative_path.stem.replace("-", " ").replace("_", " ").title(),
        "content": content,
    }


class GeneratorResponse(BaseModel):
    filename: str
    content: str


class GeneratorOutputMetadata(BaseModel):
    name: str
    description: str
    conditional: bool = False


class GeneratorMetadataResponse(BaseModel):
    slug: str
    title: str
    description: str
    provider: str
    service: str
    compliance: List[str]
    tags: List[str]
    template_path: str
    requirements: List[str]
    features: Dict[str, Any]
    outputs: List[GeneratorOutputMetadata]
    schema: Dict[str, Any]
    example_payload: Dict[str, Any]
    presets: List[Dict[str, Any]] = []


class BlueprintFile(BaseModel):
    path: str
    content: str


class BlueprintResponse(BaseModel):
    archive_name: str
    archive_base64: str
    files: List[BlueprintFile]


@api_router.get("/generators/metadata", response_model=List[GeneratorMetadataResponse])
def list_generators_metadata() -> List[GeneratorMetadataResponse]:
    return [GeneratorMetadataResponse(**item) for item in list_generator_metadata()]


@api_router.post("/generators/blueprints", response_model=BlueprintResponse)
def generate_blueprint(payload: BlueprintRequest) -> BlueprintResponse:
    result = render_blueprint_bundle(payload)
    files = [BlueprintFile(**item) for item in result["files"]]
    return BlueprintResponse(
        archive_name=result["archive_name"],
        archive_base64=result["archive_base64"],
        files=files,
    )


@api_router.post("/generators/aws/s3", response_model=GeneratorResponse)
def generate_aws_s3(payload: AwsS3GeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("aws/s3-secure-bucket")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@api_router.post("/generators/azure/storage-account", response_model=GeneratorResponse)
def generate_azure_storage(payload: AzureStorageGeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("azure/storage-secure-account")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@api_router.post("/generators/azure/servicebus", response_model=GeneratorResponse)
def generate_azure_servicebus(payload: AzureServiceBusGeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("azure/servicebus-namespace")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@api_router.post("/generators/azure/function-app", response_model=GeneratorResponse)
def generate_azure_function_app(payload: AzureFunctionAppGeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("azure/function-app")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@api_router.post("/generators/azure/api-management", response_model=GeneratorResponse)
def generate_azure_api_management(payload: AzureApiManagementGeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("azure/api-management")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@api_router.get("/settings/llm")
def get_llm_settings_api(
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    return db_get_llm_settings(session=session)


class LLMSettingsPayload(BaseModel):
    provider: str = "off"  # off|openai|azure
    model: Optional[str] = None
    enable_explanations: Optional[bool] = None
    enable_patches: Optional[bool] = None
    api_base: Optional[str] = None  # for OpenAI
    api_version: Optional[str] = None  # for Azure
    deployment_name: Optional[str] = None  # for Azure


@api_router.post("/settings/llm")
def save_llm_settings_api(
    payload: LLMSettingsPayload,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    upsert_setting("llm", payload.model_dump(exclude_none=True), session=session)
    return {"status": "saved"}


class LLMTestPayload(BaseModel):
    live: bool = False


@api_router.post("/settings/llm/test")
def test_llm_settings_api(
    payload: LLMTestPayload,
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    base = validate_provider_config()
    if not base.get("ok"):
        return {"ok": False, "stage": "validate", "error": base.get("error")}
    if not payload.live:
        return {"ok": True, "stage": "validate", "provider": base.get("provider"), "model": base.get("model")}
    probe = live_ping()
    if not probe.get("ok"):
        return {"ok": False, "stage": "ping", "error": probe.get("error")}
    return {"ok": True, "stage": "ping", "response": probe.get("response")}


@api_router.get("/")
def index_root() -> Dict[str, str]:
    return {
        "message": "Terraform Manager API. The HTML dashboard has been retired; use the SvelteKit frontend or integrate directly with these endpoints.",
        "docs": "/docs",
    }


@api_router.get("/reports/{report_id}/csv")
def get_report_csv(
    report_id: str,
    session: Session = Depends(get_session_dependency),
) -> Response:
    rec = get_report(report_id, session=session)
    if not rec:
        raise HTTPException(404, "report not found")
    csv_text = render_csv_report(rec["report"])  # type: ignore[arg-type]
    headers = {"Content-Disposition": f"attachment; filename=report-{report_id}.csv"}
    return Response(content=csv_text, media_type="text/csv", headers=headers)


app = create_app()
