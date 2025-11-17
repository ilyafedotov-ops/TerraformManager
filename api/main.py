from __future__ import annotations

import base64
import json
import tempfile
import zipfile
import uuid
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional
from datetime import datetime

from fastapi import FastAPI, HTTPException, Query, Depends, UploadFile, File, Form, Response
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
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

app = FastAPI(title="Terraform Manager API", version=__version__)
app.include_router(auth_routes.router)
app.include_router(project_routes.router)
app.mount("/docs", StaticFiles(directory="docs"), name="docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestLoggingMiddleware)


def _require_project_record(session: Session, project_id: str | None, project_slug: str | None) -> Dict[str, Any]:
    if not project_id and not project_slug:
        raise HTTPException(400, "project_id or project_slug is required")
    record = get_project(project_id=project_id, slug=project_slug, session=session)
    if not record:
        raise HTTPException(404, "project not found")
    return record


def _project_workspace_root(project: Dict[str, Any]) -> Path:
    raw_root = project.get("root_path")
    if not raw_root:
        raise HTTPException(500, "project is missing workspace metadata")
    root = Path(raw_root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    return root


def _normalise_relative_token(value: Optional[str]) -> str:
    token = (value or "").strip()
    return token or "."


def _resolve_workspace_target(root: Path, token: Optional[str], *, label: str) -> Path:
    rel_value = _normalise_relative_token(token)
    rel_path = Path(rel_value)
    if rel_path.is_absolute():
        raise ValueError(f"{label} must be project-relative (got absolute path)")
    candidate = (root / rel_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError as exc:
        raise ValueError(f"{label} escapes the project workspace") from exc
    if not candidate.exists():
        raise ValueError(f"{label} '{rel_value}' not found in project workspace")
    return candidate


def _resolve_workspace_targets(root: Path, tokens: Optional[List[str]]) -> List[Path]:
    values = tokens or []
    if not values:
        values = ["."]
    resolved: List[Path] = []
    for index, token in enumerate(values, start=1):
        resolved.append(_resolve_workspace_target(root, token, label=f"path #{index}"))
    return resolved


def _resolve_workspace_file(root: Path, token: Optional[str], *, label: str) -> Path:
    path = _resolve_workspace_target(root, token, label=label)
    if not path.is_file():
        raise ValueError(f"{label} must refer to a file within the project workspace")
    return path


@app.on_event("startup")
def _startup() -> None:
    init_db(DEFAULT_DB_PATH)


@app.get("/health")
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


class ReportReviewUpdatePayload(BaseModel):
    review_status: Optional[str] = None
    review_assignee: Optional[str] = None
    review_due_at: Optional[str | datetime] = None
    review_notes: Optional[str] = None


class ReportCommentCreatePayload(BaseModel):
    body: str
    author: Optional[str] = None


@app.post("/scan")
def scan(
    req: ScanRequest,
    session: Session = Depends(get_session_dependency),
    current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    project = _require_project_record(session, req.project_id, req.project_slug)
    project_root = _project_workspace_root(project)
    try:
        path_objs = _resolve_workspace_targets(project_root, req.paths)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc

    cost_options = None
    if req.cost:
        cost_options = {}
        if req.cost_usage_file:
            try:
                usage_path = _resolve_workspace_file(
                    project_root, req.cost_usage_file, label="cost_usage_file"
                )
            except ValueError as exc:
                raise HTTPException(400, str(exc)) from exc
            cost_options["usage_file"] = usage_path

    plan_path: Optional[Path] = None
    if req.plan_path:
        try:
            plan_path = _resolve_workspace_file(project_root, req.plan_path, label="plan_path")
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    scan_context = {
        "source": "api.scan",
        "user": current_user.user.email if current_user.user else None,
        "project_id": project["id"],
        "project_slug": project.get("slug"),
    }
    report = scan_paths(
        path_objs,
        use_terraform_validate=req.terraform_validate,
        llm_options=req.llm,
        cost_options=cost_options,
        plan_path=plan_path,
        context=scan_context,
    )
    if req.save:
        rid = str(uuid.uuid4())
        save_report(rid, report.get("summary", {}), report, session=session)
        report["id"] = rid
    return report


@app.get("/reports")
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
            session=session,
        )
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/reports/{report_id}")
def get_report_json(
    report_id: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    rec = get_report(report_id, session=session)
    if not rec:
        raise HTTPException(404, "report not found")
    return rec


@app.patch("/reports/{report_id}")
def update_report_review_metadata(
    report_id: str,
    payload: ReportReviewUpdatePayload,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
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


@app.get("/reports/{report_id}/comments")
def list_report_comments_api(
    report_id: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    try:
        comments = list_report_comments(report_id, session=session)
    except ReportNotFoundError as exc:
        raise HTTPException(404, "report not found") from exc
    return {"items": comments}


@app.post("/reports/{report_id}/comments", status_code=201)
def create_report_comment_api(
    report_id: str,
    payload: ReportCommentCreatePayload,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
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


@app.delete("/reports/{report_id}/comments/{comment_id}")
def delete_report_comment_api(
    report_id: str,
    comment_id: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    deleted = delete_report_comment(report_id, comment_id, session=session)
    if not deleted:
        raise HTTPException(404, "comment not found")
    return {"status": "deleted", "id": comment_id}


@app.get("/reports/{report_id}/html", response_class=HTMLResponse)
def get_report_html(
    report_id: str,
    session: Session = Depends(get_session_dependency),
) -> str:
    rec = get_report(report_id, session=session)
    if not rec:
        raise HTTPException(404, "report not found")
    return render_html_report(rec["report"])  # type: ignore[arg-type]


@app.delete("/reports/{report_id}")
def delete_report_api(
    report_id: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    ok = delete_report(report_id, session=session)
    if not ok:
        raise HTTPException(404, "report not found")
    return {"status": "deleted", "id": report_id}


@app.post("/scan/upload")
async def scan_upload(
    files: List[UploadFile] = File(...),
    terraform_validate: bool = Form(False),
    save: bool = Form(True),
    include_cost: bool = Form(False),
    cost_usage_file: UploadFile | None = File(None),
    plan_file: UploadFile | None = File(None),
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    if not files:
        raise HTTPException(400, "no files uploaded")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        targets: List[Path] = []
        usage_path: Optional[Path] = None
        plan_path: Optional[Path] = None

        for upload in files:
            filename = Path(upload.filename or "upload.tf")
            data = await upload.read()
            dest = root / filename.name
            dest.parent.mkdir(parents=True, exist_ok=True)
            dest.write_bytes(data)

            suffix = dest.suffix.lower()
            if suffix == ".zip":
                extract_root = root / filename.stem
                extract_root.mkdir(parents=True, exist_ok=True)
                try:
                    with zipfile.ZipFile(BytesIO(data)) as zf:
                        zf.extractall(extract_root)
                except zipfile.BadZipFile as exc:
                    raise HTTPException(400, f"invalid zip archive: {filename}") from exc
                targets.append(extract_root)
            elif suffix == ".tf":
                targets.append(dest)
            elif suffix == ".json" and plan_path is None:
                plan_path = dest
            else:
                # ignore other file types by default
                continue

        if include_cost and cost_usage_file is not None:
            usage_bytes = await cost_usage_file.read()
            usage_filename = cost_usage_file.filename or "usage.yml"
            usage_path = root / usage_filename
            usage_path.write_bytes(usage_bytes)

        if plan_file is not None:
            plan_bytes = await plan_file.read()
            plan_filename = plan_file.filename or "plan.json"
            plan_path = root / plan_filename
            plan_path.write_bytes(plan_bytes)

        if not targets:
            raise HTTPException(400, "no Terraform files found in upload")

        llm_opts = db_get_llm_settings(session=session)
        provider = (llm_opts.get("provider") or "off").lower()
        llm = llm_opts if provider in {"openai", "azure"} else None

        cost_options: Optional[Dict[str, Any]] = None
        if include_cost:
            cost_options = {"usage_file": usage_path}

        scan_context = {
            "source": "api.scan_upload",
            "user": current_user.user.email if current_user.user else None,
        }
        report = scan_paths(
            targets,
            use_terraform_validate=terraform_validate,
            llm_options=llm,
            cost_options=cost_options,
            plan_path=plan_path,
            context=scan_context,
        )

        report_id: Optional[str] = None
        if save:
            report_id = str(uuid.uuid4())
            save_report(report_id, report.get("summary", {}), report, session=session)
            report["id"] = report_id

        return {
            "id": report_id,
            "summary": report.get("summary", {}),
            "report": report,
        }


class ConfigPayload(BaseModel):
    name: str
    payload: str  # YAML content for tfreview config
    kind: str = "tfreview"


@app.get("/configs")
def configs_list(
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> List[Dict[str, Any]]:
    return list_configs(session=session)


@app.post("/configs")
def configs_upsert(
    cfg: ConfigPayload,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, str]:
    upsert_config(cfg.name, cfg.payload, kind=cfg.kind, session=session)
    return {"status": "saved", "name": cfg.name}


@app.get("/configs/{name}")
def configs_get(
    name: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    rec = get_config(name, session=session)
    if not rec:
        raise HTTPException(404, "config not found")
    return rec


@app.delete("/configs/{name}")
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


@app.post("/preview/config-application")
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


@app.get("/preview/config-application/html", response_class=HTMLResponse)
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


@app.post("/knowledge/sync")
def knowledge_sync(
    req: KnowledgeSyncRequest,
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    sources = req.sources or [
        "https://github.com/hashicorp/policy-library-azure-storage-terraform",
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


@app.get("/knowledge/search")
def knowledge_search(q: str, top_k: int = Query(3, ge=1, le=10)) -> KnowledgeSearchResponse:
    snippets = retrieve_snippets(q, top_k=top_k, max_chars=800)
    return KnowledgeSearchResponse(items=[
        {
            "source": item["source"],
            "content": item["content"],
            "score": item.get("score", 0.0),
        }
        for item in snippets
    ])


@app.get("/knowledge/doc")
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


@app.get("/generators/metadata", response_model=List[GeneratorMetadataResponse])
def list_generators_metadata() -> List[GeneratorMetadataResponse]:
    return [GeneratorMetadataResponse(**item) for item in list_generator_metadata()]


@app.post("/generators/blueprints", response_model=BlueprintResponse)
def generate_blueprint(payload: BlueprintRequest) -> BlueprintResponse:
    result = render_blueprint_bundle(payload)
    files = [BlueprintFile(**item) for item in result["files"]]
    return BlueprintResponse(
        archive_name=result["archive_name"],
        archive_base64=result["archive_base64"],
        files=files,
    )


@app.post("/generators/aws/s3", response_model=GeneratorResponse)
def generate_aws_s3(payload: AwsS3GeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("aws/s3-secure-bucket")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/generators/azure/storage-account", response_model=GeneratorResponse)
def generate_azure_storage(payload: AzureStorageGeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("azure/storage-secure-account")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/generators/azure/servicebus", response_model=GeneratorResponse)
def generate_azure_servicebus(payload: AzureServiceBusGeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("azure/servicebus-namespace")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/generators/azure/function-app", response_model=GeneratorResponse)
def generate_azure_function_app(payload: AzureFunctionAppGeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("azure/function-app")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/generators/azure/api-management", response_model=GeneratorResponse)
def generate_azure_api_management(payload: AzureApiManagementGeneratorPayload) -> GeneratorResponse:
    generator = get_generator_definition("azure/api-management")
    try:
        output = generator.render(payload)
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/settings/llm")
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


@app.post("/settings/llm")
def save_llm_settings_api(
    payload: LLMSettingsPayload,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    upsert_setting("llm", payload.model_dump(exclude_none=True), session=session)
    return {"status": "saved"}


class LLMTestPayload(BaseModel):
    live: bool = False


@app.post("/settings/llm/test")
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


@app.get("/")
def index_root() -> Dict[str, str]:
    return {
        "message": "Terraform Manager API. The HTML dashboard has been retired; use the SvelteKit frontend or integrate directly with these endpoints.",
        "docs": "/docs",
    }


@app.get("/reports/{report_id}/csv")
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
