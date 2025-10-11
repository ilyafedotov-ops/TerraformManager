from __future__ import annotations

import json
import os
import uuid
import tempfile
import zipfile
from io import BytesIO
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import FastAPI, HTTPException, Query, Depends, Header, UploadFile, File, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

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
from backend.generators.service import render_aws_s3_bucket, render_azure_storage_account


def require_api_token(x_api_token: str | None = Header(default=None, alias="X-API-Token"), authorization: str | None = Header(default=None)) -> None:
    required = os.getenv("TFM_API_TOKEN") or os.getenv("API_TOKEN")
    if not required:
        return
    provided = None
    if x_api_token:
        provided = x_api_token
    elif authorization and authorization.lower().startswith("bearer "):
        provided = authorization.split(" ", 1)[1]
    if provided != required:
        raise HTTPException(401, "invalid or missing API token")


app = FastAPI(title="Terraform Manager API", version=__version__)
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


@app.post("/scan")
def scan(req: ScanRequest, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
    path_objs = [Path(p) for p in req.paths]
    report = scan_paths(path_objs, use_terraform_validate=req.terraform_validate, llm_options=req.llm)
    if req.save:
        rid = str(uuid.uuid4())
        save_report(rid, report.get("summary", {}), report)
        report["id"] = rid
    return report


@app.get("/reports")
def reports(limit: int = Query(50, ge=1, le=500), _auth: None = Depends(require_api_token)) -> List[Dict[str, Any]]:
    return list_reports(limit=limit)


@app.get("/reports/{report_id}")
def get_report_json(report_id: str, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
    rec = get_report(report_id)
    if not rec:
        raise HTTPException(404, "report not found")
    return rec["report"]


@app.get("/reports/{report_id}/html", response_class=HTMLResponse)
def get_report_html(report_id: str) -> str:
    rec = get_report(report_id)
    if not rec:
        raise HTTPException(404, "report not found")
    return render_html_report(rec["report"])  # type: ignore[arg-type]


@app.delete("/reports/{report_id}")
def delete_report_api(report_id: str, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
    ok = delete_report(report_id)
    if not ok:
        raise HTTPException(404, "report not found")
    return {"status": "deleted", "id": report_id}


@app.post("/scan/upload")
async def scan_upload(
    files: List[UploadFile] = File(...),
    terraform_validate: bool = Form(False),
    save: bool = Form(True),
) -> Dict[str, Any]:
    if not files:
        raise HTTPException(400, "no files uploaded")

    with tempfile.TemporaryDirectory() as tmpdir:
        root = Path(tmpdir)
        targets: List[Path] = []

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

        if not targets:
            raise HTTPException(400, "no Terraform files found in upload")

        llm_opts = db_get_llm_settings()
        provider = (llm_opts.get("provider") or "off").lower()
        llm = llm_opts if provider in {"openai", "azure"} else None

        report = scan_paths(targets, use_terraform_validate=terraform_validate, llm_options=llm)

        report_id: Optional[str] = None
        if save:
            report_id = str(uuid.uuid4())
            save_report(report_id, report.get("summary", {}), report)
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
def configs_list(_auth: None = Depends(require_api_token)) -> List[Dict[str, Any]]:
    return list_configs()


@app.post("/configs")
def configs_upsert(cfg: ConfigPayload, _auth: None = Depends(require_api_token)) -> Dict[str, str]:
    upsert_config(cfg.name, cfg.payload, kind=cfg.kind)
    return {"status": "saved", "name": cfg.name}


@app.get("/configs/{name}")
def configs_get(name: str, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
    rec = get_config(name)
    if not rec:
        raise HTTPException(404, "config not found")
    return rec


@app.delete("/configs/{name}")
def configs_delete(name: str, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
    ok = delete_config(name)
    if not ok:
        raise HTTPException(404, "config not found")
    return {"status": "deleted", "name": name}


class PreviewRequest(BaseModel):
    config_name: Optional[str] = None
    paths: Optional[List[str]] = None
    report_id: Optional[str] = None


@app.post("/preview/config-application")
def preview_config(req: PreviewRequest, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
    # Determine findings source: existing report or fresh scan
    report: Optional[Dict[str, Any]] = None
    if req.report_id:
        rec = get_report(req.report_id)
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
        cfg = get_config(req.config_name)
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
def preview_config_html(report_id: str | None = None, config_name: str | None = None, paths: List[str] | None = Query(default=None)) -> str:
    # Build inputs similarly to the JSON preview
    report: Optional[Dict[str, Any]] = None
    if report_id:
        rec = get_report(report_id)
        if not rec:
            raise HTTPException(404, "report not found")
        report = rec["report"]
    elif paths:
        report = scan_paths([Path(p) for p in paths], use_terraform_validate=False)
    else:
        raise HTTPException(400, "either report_id or paths must be provided")

    findings = report.get("findings", []) if report else []
    if config_name:
        cfg = get_config(config_name)
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
def knowledge_sync(req: KnowledgeSyncRequest, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
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


class AwsS3BackendPayload(BaseModel):
    bucket: str
    key: str
    region: str
    dynamodb_table: str


class AwsS3GeneratorRequest(BaseModel):
    bucket_name: str
    region: str = "us-east-1"
    environment: str = "prod"
    owner_tag: str = "platform-team"
    cost_center_tag: str = "ENG-SRE"
    force_destroy: bool = False
    versioning: bool = True
    enforce_secure_transport: bool = True
    kms_key_id: Optional[str] = None
    backend: Optional[AwsS3BackendPayload] = None


class AzureStorageBackendPayload(BaseModel):
    resource_group: str
    storage_account: str
    container: str
    key: str


class AzureStoragePrivateEndpointPayload(BaseModel):
    name: str
    connection_name: str
    subnet_id: str
    private_dns_zone_id: Optional[str] = None
    dns_zone_group_name: Optional[str] = None


class AzureStorageGeneratorRequest(BaseModel):
    resource_group_name: str
    storage_account_name: str
    location: str
    environment: str = "prod"
    replication: str = "LRS"
    versioning: bool = True
    owner_tag: str = "platform-team"
    cost_center_tag: str = "ENG-SRE"
    restrict_network: bool = False
    allowed_ips: List[str] = []
    private_endpoint: Optional[AzureStoragePrivateEndpointPayload] = None
    backend: Optional[AzureStorageBackendPayload] = None


class GeneratorResponse(BaseModel):
    filename: str
    content: str


@app.post("/generators/aws/s3", response_model=GeneratorResponse)
def generate_aws_s3(payload: AwsS3GeneratorRequest) -> GeneratorResponse:
    try:
        output = render_aws_s3_bucket(payload.model_dump())
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.post("/generators/azure/storage-account", response_model=GeneratorResponse)
def generate_azure_storage(payload: AzureStorageGeneratorRequest) -> GeneratorResponse:
    try:
        output = render_azure_storage_account(payload.model_dump())
        return GeneratorResponse(**output)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc


@app.get("/settings/llm")
def get_llm_settings_api(_auth: None = Depends(require_api_token)) -> Dict[str, Any]:
    return db_get_llm_settings()


class LLMSettingsPayload(BaseModel):
    provider: str = "off"  # off|openai|azure
    model: Optional[str] = None
    enable_explanations: Optional[bool] = None
    enable_patches: Optional[bool] = None
    api_base: Optional[str] = None  # for OpenAI
    api_version: Optional[str] = None  # for Azure
    deployment_name: Optional[str] = None  # for Azure


@app.post("/settings/llm")
def save_llm_settings_api(payload: LLMSettingsPayload, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
    upsert_setting("llm", payload.model_dump(exclude_none=True))
    return {"status": "saved"}


class LLMTestPayload(BaseModel):
    live: bool = False


@app.post("/settings/llm/test")
def test_llm_settings_api(payload: LLMTestPayload, _auth: None = Depends(require_api_token)) -> Dict[str, Any]:
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
def get_report_csv(report_id: str):
    rec = get_report(report_id)
    if not rec:
        raise HTTPException(404, "report not found")
    csv_text = render_csv_report(rec["report"])  # type: ignore[arg-type]
    from fastapi import Response

    headers = {"Content-Disposition": f"attachment; filename=report-{report_id}.csv"}
    return Response(content=csv_text, media_type="text/csv", headers=headers)
