from __future__ import annotations

import base64
import json
import os
import uuid
import tempfile
import zipfile
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends, Header, UploadFile, File, Form, Response, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.orm import Session

from backend.auth import auth_settings
from backend.auth.tokens import TokenService, TokenPayload, TokenType, TokenError, ACCESS_TOKEN_EXPIRE_MINUTES
from backend.db import get_session_dependency
from backend.db.repositories import auth as auth_repo
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
)
from backend.preview_html import render_preview_html
from backend.report_csv import render_csv_report
from fastapi.staticfiles import StaticFiles
from api import ui as ui_routes
from backend.version import __version__
from backend.llm_service import validate_provider_config, live_ping
from backend.generators.blueprints import render_blueprint_bundle
from backend.generators.models import BlueprintRequest, AwsS3GeneratorPayload, AzureStorageGeneratorPayload
from backend.generators.registry import get_generator_definition, list_generator_metadata
from api.routes import auth as auth_routes

KNOWLEDGE_ROOT = Path("knowledge").resolve()
token_service = TokenService()
SERVICE_USER_EMAIL = os.getenv("TFM_SERVICE_USER_EMAIL", "service@local")


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _ensure_service_user(session: Session, email: str, password: str, scopes: List[str]) -> auth_repo.User:
    user = auth_repo.get_user_by_email(session, email)
    password_hash = token_service.hash_password(password)
    if user is None:
        user = auth_repo.create_user(
            session,
            email=email,
            password_hash=password_hash,
            scopes=scopes,
            is_superuser=True,
        )
    else:
        if not token_service.verify_password(password, user.password_hash):
            user.password_hash = password_hash
            session.add(user)
            session.flush()
        if not user.is_active:
            user.is_active = True
            session.add(user)
            session.flush()
    return user


def require_current_user(
    request: Request,
    authorization: str | None = Header(default=None, alias="Authorization"),
    x_api_token: str | None = Header(default=None, alias="X-API-Token"),
    session: Session = Depends(get_session_dependency),
) -> auth_routes.CurrentUser:
    bearer_token: str | None = None
    provided_token: str | None = None

    if authorization:
        auth_value = authorization.strip()
        if auth_value.lower().startswith("bearer "):
            bearer_token = auth_value.split(" ", 1)[1].strip()
        else:
            provided_token = auth_value

    if x_api_token:
        provided_token = x_api_token.strip()

    if bearer_token:
        try:
            payload = token_service.decode_access_token(bearer_token)
        except TokenError as exc:
            raise HTTPException(status_code=401, detail="invalid or missing API token") from exc

        user = auth_repo.get_user_by_email(session, payload.sub)
        if not user:
            raise HTTPException(status_code=401, detail="invalid or missing API token")
        return auth_routes.CurrentUser(user=user, token=payload)

    expected_api_token = auth_settings.expected_api_token()
    if expected_api_token and provided_token and provided_token == expected_api_token:
        scopes = list(auth_routes.DEFAULT_SCOPES)
        user = _ensure_service_user(session, SERVICE_USER_EMAIL, expected_api_token, scopes)
        now = _now()
        payload = TokenPayload(
            sub=user.email,
            scopes=scopes,
            api_token=expected_api_token,
            type=TokenType.ACCESS,
            exp=int((now + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)).timestamp()),
            iat=int(now.timestamp()),
            jti=str(uuid.uuid4()),
            sid=None,
            fam=None,
            iss=auth_settings.jwt_issuer,
            aud=auth_settings.jwt_audience,
        )
        return auth_routes.CurrentUser(user=user, token=payload)

    if expected_api_token:
        raise HTTPException(status_code=401, detail="invalid or missing API token")

    raise HTTPException(status_code=401, detail="Not authenticated")


app = FastAPI(title="Terraform Manager API", version=__version__)
app.include_router(auth_routes.router)
app.mount("/static", StaticFiles(directory="ui/static"), name="static")
app.include_router(ui_routes.router, prefix="/ui")
app.mount("/docs", StaticFiles(directory="docs"), name="docs")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


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


@app.post("/scan")
def scan(
    req: ScanRequest,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    path_objs = [Path(p) for p in req.paths]
    cost_options = None
    if req.cost:
        cost_options = {}
        if req.cost_usage_file:
            cost_options["usage_file"] = Path(req.cost_usage_file)

    plan_path = Path(req.plan_path) if req.plan_path else None

    report = scan_paths(
        path_objs,
        use_terraform_validate=req.terraform_validate,
        llm_options=req.llm,
        cost_options=cost_options,
        plan_path=plan_path,
    )
    if req.save:
        rid = str(uuid.uuid4())
        save_report(rid, report.get("summary", {}), report, session=session)
        report["id"] = rid
    return report


@app.get("/reports")
def reports(
    limit: int = Query(50, ge=1, le=500),
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> List[Dict[str, Any]]:
    return list_reports(limit=limit, session=session)


@app.get("/reports/{report_id}")
def get_report_json(
    report_id: str,
    session: Session = Depends(get_session_dependency),
    _current_user: auth_routes.CurrentUser = Depends(require_current_user),
) -> Dict[str, Any]:
    rec = get_report(report_id, session=session)
    if not rec:
        raise HTTPException(404, "report not found")
    return rec["report"]


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

        report = scan_paths(
            targets,
            use_terraform_validate=terraform_validate,
            llm_options=llm,
            cost_options=cost_options,
            plan_path=plan_path,
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
        report = scan_paths([Path(p) for p in req.paths], use_terraform_validate=False)
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
        report = scan_paths([Path(p) for p in paths], use_terraform_validate=False)
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


# Minimal HTML endpoint to keep things simple without a heavy frontend stack
INDEX_HTML = """
<!doctype html>
<html>
  <head>
    <meta charset="utf-8" />
    <title>Terraform Manager</title>
    <script src="https://unpkg.com/htmx.org@1.9.12"></script>
    <style>
      body { font-family: system-ui, -apple-system, Segoe UI, Roboto, sans-serif; margin: 2rem; }
      input, button { padding: 0.5rem; margin: 0.25rem; }
      pre { background: #111827; color: #e5e7eb; padding: 1rem; border-radius: 6px; overflow:auto; }
      .muted { color: #666; }
    </style>
  </head>
  <body>
    <h2>Terraform Manager (API-driven)</h2>
    <div>
      <form hx-post="/scan" hx-target="#scan-result" hx-encoding="json">
        <label>Paths (comma-separated):</label>
        <input type="text" name="paths" oninput="this.value=this.value" value="sample" />
        <input type="hidden" name="terraform_validate" value="false" />
        <input type="hidden" name="save" value="true" />
        <button type="submit" onclick="event.preventDefault(); this.closest('form').dispatchEvent(new Event('submit',{cancelable:true}));">Scan</button>
        <script>
          document.querySelector('form').addEventListener('htmx:configRequest', function(evt) {
            const form = evt.detail.elt;
            const paths = (form.querySelector('input[name=paths]').value || '').split(',').map(s => s.trim()).filter(Boolean);
            const payload = { paths, terraform_validate: false, save: true };
            evt.detail.headers['Content-Type'] = 'application/json';
            evt.detail.parameters = {};
            evt.detail.fetchOpts = { method: 'POST', body: JSON.stringify(payload) };
          });
        </script>
      </form>
      <div id="scan-result" class="muted">Scan results will appear here.</div>
    </div>

    <h3>Recent Reports</h3>
    <button hx-get="/reports" hx-target="#reports">Refresh</button>
    <div id="reports"></div>

    <script>
      document.body.addEventListener('htmx:afterOnLoad', function(ev) {
        if (ev.target.id === 'scan-result') {
          try {
            const data = JSON.parse(ev.detail.xhr.responseText);
            ev.target.innerHTML = `<p>Report ID: ${data.id || '(not saved)'} | Issues: ${data.summary?.issues_found}</p>` +
              `<pre>${JSON.stringify(data.summary, null, 2)}</pre>`;
          } catch (e) { ev.target.textContent = 'Scan done.'; }
        }
        if (ev.target.id === 'reports') {
          try {
            const items = JSON.parse(ev.detail.xhr.responseText);
            ev.target.innerHTML = items.map(it => `<div><a href="/reports/${it.id}/html" target="_blank">${it.id}</a> — ${new Date(it.created_at).toLocaleString()}</div>`).join('');
          } catch (e) { ev.target.textContent = 'No reports'; }
        }
      });
    </script>
  </body>
</html>
"""


@app.get("/")
def index_redirect() -> RedirectResponse:
    return RedirectResponse("/ui/dashboard")


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
