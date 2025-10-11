from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Form, HTTPException, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from backend.scanner import scan_paths
from backend.report_html import render_html_report
from backend.policies.config import apply_config, load_config
from backend.storage import (
    get_config,
    list_configs,
    upsert_config,
    list_reports,
    get_report,
    save_report,
    delete_report as delete_report_record,
    delete_config as delete_config_record,
    get_llm_settings as db_get_llm_settings,
    upsert_setting as db_upsert_setting,
)
from backend.knowledge_sync import sync_many
from backend.version import __version__
from urllib.parse import quote_plus
from fastapi import Response
from backend.report_csv import render_csv_findings


TEMPLATES = Jinja2Templates(directory="ui/templates")
TEMPLATES.env.globals["APP_VERSION"] = __version__
TEMPLATES.env.globals["FOOTER_LINKS"] = [
    {"title": "Docs (report schema)", "href": "/docs/report_schema.json"},
    {"title": "HashiCorp Policy Library", "href": "https://github.com/hashicorp/policy-library-azure-storage-terraform"},
]
router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def root() -> RedirectResponse:
    return RedirectResponse("/ui/dashboard")


@router.get("/dashboard", response_class=HTMLResponse)
def dashboard(request: Request) -> HTMLResponse:
    reports = list_reports(limit=20)
    total = len(reports)
    last = reports[0] if reports else None
    sev_counts: Dict[str, int] = {}
    for r in reports:
        for sev, count in (r.get("summary", {}).get("severity_counts", {}) or {}).items():
            sev_counts[sev] = sev_counts.get(sev, 0) + int(count)
    sev_max = max(sev_counts.values()) if sev_counts else 0
    knowledge_files = sum(1 for _ in Path("knowledge").rglob("*.md"))
    return TEMPLATES.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "stats": {
                "reports": total,
                "last": last,
                "severity": sev_counts,
                "severity_max": sev_max,
                "knowledge_files": knowledge_files,
            },
        },
    )


@router.get("/scan", response_class=HTMLResponse)
def scan_page(request: Request) -> HTMLResponse:
    return TEMPLATES.TemplateResponse("scan.html", {"request": request})


@router.post("/scan/execute", response_class=HTMLResponse)
def scan_execute(request: Request, paths: str = Form(...), terraform_validate: Optional[bool] = Form(False)) -> HTMLResponse:
    path_list = [p.strip() for p in (paths or "").split(",") if p.strip()]
    if not path_list:
        raise HTTPException(400, "No paths provided")
    llm_opts = db_get_llm_settings()
    provider = (llm_opts.get("provider") or "off").lower()
    llm = None
    if provider in {"openai", "azure"}:
        llm = llm_opts
    report = scan_paths([Path(p) for p in path_list], use_terraform_validate=bool(terraform_validate), llm_options=llm)
    # Save report and show links
    import uuid
    import json

    rid = None
    try:
        rid = str(uuid.uuid4())
        save_report(rid, report.get("summary", {}), report)
    except Exception:
        pass
    summary_json = json.dumps(report.get("summary", {}), indent=2)
    severity_json = json.dumps(report.get("summary", {}).get("severity_counts", {}), indent=2)
    return TEMPLATES.TemplateResponse("partials/scan_result.html", {
        "request": request,
        "report": report,
        "report_id": rid,
        "summary_json": summary_json,
        "severity_json": severity_json,
    })


@router.get("/reports", response_class=HTMLResponse)
def reports_page(request: Request) -> HTMLResponse:
    items = list_reports(limit=100)
    return TEMPLATES.TemplateResponse("reports.html", {"request": request, "items": items})


@router.get("/reports/{report_id}", response_class=HTMLResponse)
def report_detail(request: Request, report_id: str) -> HTMLResponse:
    rec = get_report(report_id)
    if not rec:
        raise HTTPException(404, "report not found")
    # Embed the rendered HTML report within our frame
    html = render_html_report(rec["report"])  # type: ignore[arg-type]
    return TEMPLATES.TemplateResponse(
        "report_detail.html",
        {"request": request, "report_id": report_id, "report_html": html},
    )


@router.post("/reports/delete", response_class=HTMLResponse)
def reports_delete(request: Request, report_id: str = Form(...)) -> HTMLResponse:
    delete_report_record(report_id)
    items = list_reports(limit=100)
    return TEMPLATES.TemplateResponse("partials/reports_table.html", {"request": request, "items": items})


@router.get("/configs", response_class=HTMLResponse)
def configs_page(request: Request) -> HTMLResponse:
    configs = list_configs()
    return TEMPLATES.TemplateResponse("configs.html", {"request": request, "configs": configs})


@router.post("/configs/save", response_class=HTMLResponse)
def configs_save(request: Request, name: str = Form(...), payload: str = Form(...)) -> HTMLResponse:
    upsert_config(name, payload)
    configs = list_configs()
    return TEMPLATES.TemplateResponse("partials/configs_list.html", {"request": request, "configs": configs})


@router.post("/configs/delete", response_class=HTMLResponse)
def configs_delete(request: Request, name: str = Form(...)) -> HTMLResponse:
    delete_config_record(name)
    configs = list_configs()
    return TEMPLATES.TemplateResponse("partials/configs_list.html", {"request": request, "configs": configs})


@router.post("/configs/preview", response_class=HTMLResponse)
def configs_preview(request: Request, config_name: str = Form(...), report_id: Optional[str] = Form(None), paths: Optional[str] = Form(None)) -> HTMLResponse:
    if report_id:
        rec = get_report(report_id)
        if not rec:
            raise HTTPException(404, "report not found")
        report = rec["report"]
    else:
        path_list = [p.strip() for p in (paths or "").split(",") if p.strip()]
        if not path_list:
            raise HTTPException(400, "Provide either report_id or paths")
        report = scan_paths([Path(p) for p in path_list], use_terraform_validate=False)

    cfg = get_config(config_name)
    if not cfg:
        raise HTTPException(404, "config not found")
    tmp_path = Path("/tmp/tfreview.preview.yaml")
    tmp_path.write_text(cfg["payload"], encoding="utf-8")
    review_cfg = load_config([tmp_path])

    applied = apply_config(report.get("findings", []), review_cfg)
    from backend.preview_html import render_preview_html

    html = render_preview_html(applied, report.get("summary", {}))
    return HTMLResponse(html)


# Inline report viewer (filterable)
@router.get("/reports/{report_id}/viewer", response_class=HTMLResponse)
def report_viewer(request: Request, report_id: str) -> HTMLResponse:
    rec = get_report(report_id)
    if not rec:
        raise HTTPException(404, "report not found")
    return TEMPLATES.TemplateResponse("report_viewer.html", {"request": request, "report_id": report_id})


@router.get("/reports/{report_id}/viewer/table", response_class=HTMLResponse)
def report_viewer_table(request: Request, report_id: str, severity: Optional[str] = None, rule_contains: Optional[str] = None, q: Optional[str] = None, group_by: Optional[str] = None) -> HTMLResponse:
    rec = get_report(report_id)
    if not rec:
        raise HTTPException(404, "report not found")
    findings = list(rec["report"].get("findings", []))
    sev = (severity or "").strip().upper()
    rule_q = (rule_contains or q or "").strip().lower()
    if sev:
        findings = [f for f in findings if str(f.get("severity", "")).upper() == sev]
    if rule_q:
        findings = [f for f in findings if rule_q in str(f.get("rule", "")).lower() or rule_q in str(f.get("title", "")).lower()]
    rc = (rule_contains or q or "")
    template = "partials/report_viewer_grouped.html" if (group_by or "").lower() == "rule" else "partials/report_viewer_table.html"
    return TEMPLATES.TemplateResponse(template, {
        "request": request,
        "findings": findings,
        "report_id": report_id,
        "severity": (severity or "").upper(),
        "rule_contains": rc,
        "rule_contains_enc": quote_plus(rc),
    })


@router.get("/reports/{report_id}/viewer/csv")
def report_viewer_csv(report_id: str, severity: Optional[str] = None, rule_contains: Optional[str] = None, q: Optional[str] = None):
    rec = get_report(report_id)
    if not rec:
        raise HTTPException(404, "report not found")
    findings = list(rec["report"].get("findings", []))
    sev = (severity or "").strip().upper()
    rule_q = (rule_contains or q or "").strip().lower()
    if sev:
        findings = [f for f in findings if str(f.get("severity", "")).upper() == sev]
    if rule_q:
        findings = [f for f in findings if rule_q in str(f.get("rule", "")).lower() or rule_q in str(f.get("title", "")).lower()]
    csv_text = render_csv_findings(findings)
    headers = {"Content-Disposition": f"attachment; filename=report-{report_id}-filtered.csv"}
    return Response(content=csv_text, media_type="text/csv", headers=headers)


@router.get("/reports/export-zip")
def reports_export_zip(ids: Optional[str] = None):
    # ids: comma-separated report IDs
    id_list: List[str] = []
    if ids:
        id_list = [s for s in (ids.split(",") if ids else []) if s]
    id_list = list(dict.fromkeys(id_list))  # dedupe
    if not id_list:
        raise HTTPException(400, "No report ids provided")
    import io, zipfile, json as _json
    from backend.report_csv import render_csv_report
    from backend.report_html import render_html_report

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        found_any = False
        for rid in id_list:
            rec = get_report(rid)
            if not rec:
                continue
            found_any = True
            report = rec["report"]
            z.writestr(f"report-{rid}.json", _json.dumps(report, indent=2))
            z.writestr(f"report-{rid}.csv", render_csv_report(report))
            z.writestr(f"report-{rid}.html", render_html_report(report))
        if not found_any:
            raise HTTPException(404, "None of the requested reports were found")
    headers = {"Content-Disposition": "attachment; filename=reports-export.zip"}
    return Response(content=buf.getvalue(), media_type="application/zip", headers=headers)


@router.get("/reports/export-json")
def reports_export_json_zip(ids: Optional[str] = None):
    id_list: List[str] = []
    if ids:
        id_list = [s for s in (ids.split(",") if ids else []) if s]
    id_list = list(dict.fromkeys(id_list))
    if not id_list:
        raise HTTPException(400, "No report ids provided")
    import io, zipfile, json as _json
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        found_any = False
        for rid in id_list:
            rec = get_report(rid)
            if not rec:
                continue
            found_any = True
            report = rec["report"]
            z.writestr(f"report-{rid}.json", _json.dumps(report, indent=2))
        if not found_any:
            raise HTTPException(404, "None of the requested reports were found")
    headers = {"Content-Disposition": "attachment; filename=reports-json.zip"}
    return Response(content=buf.getvalue(), media_type="application/zip", headers=headers)


@router.get("/reports/export-html")
def reports_export_html_zip(ids: Optional[str] = None):
    id_list: List[str] = []
    if ids:
        id_list = [s for s in (ids.split(",") if ids else []) if s]
    id_list = list(dict.fromkeys(id_list))
    if not id_list:
        raise HTTPException(400, "No report ids provided")
    import io, zipfile
    from backend.report_html import render_html_report
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, mode="w", compression=zipfile.ZIP_DEFLATED) as z:
        found_any = False
        for rid in id_list:
            rec = get_report(rid)
            if not rec:
                continue
            found_any = True
            report = rec["report"]
            z.writestr(f"report-{rid}.html", render_html_report(report))
        if not found_any:
            raise HTTPException(404, "None of the requested reports were found")
    headers = {"Content-Disposition": "attachment; filename=reports-html.zip"}
    return Response(content=buf.getvalue(), media_type="application/zip", headers=headers)


@router.post("/reports/delete-bulk", response_class=HTMLResponse)
async def reports_delete_bulk(request: Request) -> HTMLResponse:
    form = await request.form()
    ids = form.getlist("report_id")
    for rid in ids:
        delete_report_record(str(rid))
    items = list_reports(limit=100)
    return TEMPLATES.TemplateResponse("partials/reports_table.html", {"request": request, "items": items})


@router.post("/configs/delete-bulk", response_class=HTMLResponse)
async def configs_delete_bulk(request: Request) -> HTMLResponse:
    form = await request.form()
    names = form.getlist("config_name")
    for name in names:
        delete_config_record(str(name))
    configs = list_configs()
    return TEMPLATES.TemplateResponse("partials/configs_list.html", {"request": request, "configs": configs})


@router.get("/knowledge", response_class=HTMLResponse)
def knowledge_page(request: Request) -> HTMLResponse:
    knowledge_files = [p for p in Path("knowledge").rglob("*.md")]
    return TEMPLATES.TemplateResponse(
        "knowledge.html",
        {
            "request": request,
            "files_count": len(knowledge_files),
            "default_repo": "https://github.com/hashicorp/policy-library-azure-storage-terraform",
        },
    )


@router.post("/knowledge/sync", response_class=HTMLResponse)
def knowledge_sync(request: Request, sources: str = Form(...)) -> HTMLResponse:
    repos = [s.strip() for s in (sources or "").splitlines() if s.strip()]
    results = sync_many(repos)
    knowledge_files = [p for p in Path("knowledge").rglob("*.md")]
    return TEMPLATES.TemplateResponse(
        "partials/knowledge_result.html",
        {"request": request, "results": results, "files_count": len(knowledge_files)},
    )


@router.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request) -> HTMLResponse:
    token_required = bool(os.getenv("TFM_API_TOKEN") or os.getenv("API_TOKEN"))
    port = os.getenv("TFM_PORT") or os.getenv("PORT") or "8787"
    llm_settings = db_get_llm_settings()
    return TEMPLATES.TemplateResponse("settings.html", {"request": request, "token_required": token_required, "port": port, "llm": llm_settings})


@router.post("/settings/llm/save", response_class=HTMLResponse)
def settings_llm_save(
    request: Request,
    provider: str = Form("off"),
    model: Optional[str] = Form(None),
    api_base: Optional[str] = Form(None),
    api_version: Optional[str] = Form(None),
    deployment_name: Optional[str] = Form(None),
    enable_explanations: Optional[str] = Form(None),
    enable_patches: Optional[str] = Form(None),
) -> HTMLResponse:
    payload = {
        "provider": provider.strip().lower() or "off",
    }
    if model:
        payload["model"] = model.strip()
    if api_base:
        payload["api_base"] = api_base.strip()
    if api_version:
        payload["api_version"] = api_version.strip()
    if deployment_name:
        payload["deployment_name"] = deployment_name.strip()
    if enable_explanations is not None:
        payload["enable_explanations"] = True
    if enable_patches is not None:
        payload["enable_patches"] = True
    db_upsert_setting("llm", payload)
    llm_settings = db_get_llm_settings()
    token_required = bool(os.getenv("TFM_API_TOKEN") or os.getenv("API_TOKEN"))
    port = os.getenv("TFM_PORT") or os.getenv("PORT") or "8787"
    return TEMPLATES.TemplateResponse("partials/settings_llm.html", {"request": request, "llm": llm_settings, "token_required": token_required, "port": port})
