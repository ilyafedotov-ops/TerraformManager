from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, Any, Iterable, Optional


def _escape(value: Any) -> str:
    if value is None:
        return ""
    return html.escape(str(value), quote=True)


def _render_summary(summary: Dict[str, Any]) -> str:
    issues = summary.get("issues_found", 0)
    files = summary.get("files_scanned", 0)
    severity_counts = summary.get("severity_counts", {})
    thresholds = summary.get("thresholds", {})

    severity_rows = ""
    for severity, count in severity_counts.items():
        severity_rows += f"<tr><td>{_escape(severity)}</td><td>{_escape(count)}</td></tr>"

    severity_table = (
        f"<table class='severity'><thead><tr><th>Severity</th><th>Count</th></tr></thead><tbody>{severity_rows}</tbody></table>"
        if severity_rows
        else "<p>No findings.</p>"
    )

    threshold_block = ""
    if thresholds.get("configured"):
        fail_on = ", ".join(thresholds.get("fail_on", [])) or "configured severities"
        triggered = thresholds.get("triggered")
        violated = ", ".join(thresholds.get("violated_ids", [])) or "none"
        status = "triggered" if triggered else "not triggered"
        threshold_block = (
            f"<div class='thresholds'><strong>Severity gate:</strong> {status} (fail_on={_escape(fail_on)}, violated={_escape(violated)})</div>"
        )

    return (
        f"<section class='summary'>"
        f"<h2>Scan Summary</h2>"
        f"<p><strong>Issues Found:</strong> {_escape(issues)}<br>"
        f"<strong>Files Scanned:</strong> {_escape(files)}</p>"
        f"{threshold_block}"
        f"{severity_table}"
        f"</section>"
    )

def _format_currency(amount: Optional[float], currency: Optional[str]) -> str:
    if amount is None:
        return "—"
    if currency:
        return f"{currency} {amount:,.2f}"
    return f"{amount:,.2f}"


def _render_cost(cost: Dict[str, Any]) -> str:
    if not cost:
        return ""
    if cost.get("error"):
        return (
            "<section class='cost'>"
            "<h2>Cost Summary</h2>"
            f"<p class='error'>Cost analysis unavailable: {_escape(cost.get('error'))}</p>"
            "</section>"
        )

    currency = cost.get("currency")
    summary = cost.get("summary") or {}
    total_monthly = _format_currency(summary.get("total_monthly_cost"), currency)
    total_hourly = _format_currency(summary.get("total_hourly_cost"), currency)
    diff_monthly = _format_currency(summary.get("diff_monthly_cost"), currency)
    diff_hourly = _format_currency(summary.get("diff_hourly_cost"), currency)

    project_rows = ""
    for project in cost.get("projects", []):
        project_rows += (
            "<tr>"
            f"<td>{_escape(project.get('name'))}</td>"
            f"<td>{_escape(project.get('path'))}</td>"
            f"<td>{_format_currency(project.get('monthly_cost'), currency)}</td>"
            f"<td>{_format_currency(project.get('diff_monthly_cost'), currency)}</td>"
            "</tr>"
        )

    projects_table = (
        "<table class='projects'>"
        "<thead><tr><th>Project</th><th>Path</th><th>Monthly</th><th>Δ Monthly</th></tr></thead>"
        f"<tbody>{project_rows}</tbody></table>"
        if project_rows
        else "<p>No costed projects discovered.</p>"
    )

    errors_block = ""
    if cost.get("errors"):
        items = "".join(f"<li>{_escape(err)}</li>" for err in cost["errors"])
        errors_block = f"<details><summary>Infracost Warnings</summary><ul>{items}</ul></details>"

    return (
        "<section class='cost'>"
        "<h2>Cost Summary</h2>"
        f"<p><strong>Total Monthly:</strong> {total_monthly}<br>"
        f"<strong>Total Hourly:</strong> {total_hourly}<br>"
        f"<strong>Δ Monthly:</strong> {diff_monthly}<br>"
        f"<strong>Δ Hourly:</strong> {diff_hourly}</p>"
        f"{projects_table}"
        f"{errors_block}"
        "</section>"
    )


def _render_drift(drift: Dict[str, Any]) -> str:
    if not drift:
        return ""
    if drift.get("error"):
        return (
            "<section class='drift'>"
            "<h2>Terraform Plan</h2>"
            f"<p class='error'>Plan parsing failed: {_escape(drift.get('error'))}</p>"
            "</section>"
        )

    counts = drift.get("counts") or {}
    total_changes = drift.get("total_changes", 0)
    has_changes = drift.get("has_changes", False)
    status = "Detected" if has_changes else "No drift detected"

    counts_list = "".join(
        f"<li>{_escape(action.title())}: {_escape(counts.get(action, 0))}</li>"
        for action in ["create", "update", "delete", "replace"]
        if counts.get(action, 0)
    )
    if not counts_list:
        counts_list = "<li>No actionable changes</li>"

    change_rows = ""
    for change in drift.get("resource_changes", []):
        change_rows += (
            "<tr>"
            f"<td>{_escape(change.get('address'))}</td>"
            f"<td>{_escape(change.get('action'))}</td>"
            f"<td>{_escape(','.join(change.get('actions') or []))}</td>"
            "</tr>"
        )

    table_block = (
        "<table class='drift-table'>"
        "<thead><tr><th>Resource</th><th>Action</th><th>Raw Actions</th></tr></thead>"
        f"<tbody>{change_rows}</tbody></table>"
        if change_rows
        else ""
    )

    outputs_block = ""
    output_changes = drift.get("output_changes") or []
    if output_changes:
        output_rows = "".join(
            "<tr>"
            f"<td>{_escape(item.get('name'))}</td>"
            f"<td>{_escape(','.join(item.get('actions') or []))}</td>"
            f"<td>{_escape(item.get('before'))}</td>"
            f"<td>{_escape(item.get('after'))}</td>"
            "</tr>"
            for item in output_changes
        )
        outputs_block = (
            "<details><summary>Output Changes</summary>"
            "<table class='drift-table'>"
            "<thead><tr><th>Name</th><th>Actions</th><th>Before</th><th>After</th></tr></thead>"
            f"<tbody>{output_rows}</tbody>"
            "</table>"
            "</details>"
        )

    return (
        "<section class='drift'>"
        "<h2>Terraform Plan</h2>"
        f"<p><strong>Status:</strong> {_escape(status)} (Total changes: {_escape(total_changes)})</p>"
        f"<ul>{counts_list}</ul>"
        f"{table_block}"
        f"{outputs_block}"
        "</section>"
    )


def _render_finding(finding: Dict[str, Any]) -> str:
    snippet = finding.get("snippet") or ""
    suggested = finding.get("suggested_fix_snippet") or ""
    diff = finding.get("unified_diff") or ""
    knowledge = finding.get("knowledge_ref")

    snippet_block = (
        f"<details><summary>Snippet</summary><pre><code>{_escape(snippet)}</code></pre></details>"
        if snippet
        else ""
    )
    suggested_block = (
        f"<details><summary>Suggested Fix</summary><pre><code>{_escape(suggested)}</code></pre></details>"
        if suggested
        else ""
    )
    diff_block = (
        f"<details><summary>Diff</summary><pre><code>{_escape(diff)}</code></pre></details>"
        if diff
        else ""
    )
    knowledge_block = (
        f"<p><strong>Knowledge:</strong> {_escape(knowledge)}</p>"
        if knowledge
        else ""
    )

    return (
        "<article class='finding'>"
        f"<h3>{_escape(finding.get('severity'))}: {_escape(finding.get('title'))}</h3>"
        f"<p><strong>Rule:</strong> {_escape(finding.get('rule'))}<br>"
        f"<strong>ID:</strong> {_escape(finding.get('id'))}<br>"
        f"<strong>Location:</strong> {_escape(finding.get('file'))}:{_escape(finding.get('line'))}</p>"
        f"<p>{_escape(finding.get('description'))}</p>"
        f"<p><strong>Recommendation:</strong> {_escape(finding.get('recommendation'))}</p>"
        f"{knowledge_block}"
        f"{snippet_block}"
        f"{suggested_block}"
        f"{diff_block}"
        "</article>"
    )


def render_html_report(report: Dict[str, Any]) -> str:
    summary_section = _render_summary(report.get("summary", {}))
    findings = report.get("findings", [])
    findings_section = "".join(_render_finding(f) for f in findings)
    findings_wrapper = (
        f"<section class='findings'><h2>Active Findings ({len(findings)})</h2>{findings_section}</section>"
        if findings
        else "<section class='findings'><h2>Active Findings</h2><p>No active findings.</p></section>"
    )

    waived_section = ""
    waived = report.get("waived_findings", [])
    if waived:
        waived_items = "".join(
            f"<li>{_escape(f['id'])} – {_escape(f['title'])} (reason: {_escape(f.get('reason'))})</li>"
            for f in waived
        )
        waived_section = f"<section class='waived'><h2>Waived Findings ({len(waived)})</h2><ul>{waived_items}</ul></section>"

    cost_section = _render_cost(report.get("cost", {}))
    drift_section = _render_drift(report.get("drift", {}))

    html_doc = f"""<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>TerraformManager Report</title>
  <style>
    body {{ font-family: Arial, sans-serif; margin: 2rem; line-height: 1.5; }}
    h1 {{ margin-bottom: 0.5rem; }}
    h2 {{ border-bottom: 1px solid #ccc; padding-bottom: 0.25rem; }}
    article.finding {{ border: 1px solid #ddd; border-radius: 6px; padding: 1rem; margin-bottom: 1rem; }}
    table.severity {{ border-collapse: collapse; margin-top: 1rem; }}
    table.severity th, table.severity td {{ border: 1px solid #ccc; padding: 0.5rem 0.75rem; text-align: left; }}
    details summary {{ cursor: pointer; font-weight: bold; }}
    pre {{ background-color: #f7f7f7; padding: 0.5rem; border-radius: 4px; overflow-x: auto; }}
    .thresholds {{ margin: 0.5rem 0; padding: 0.5rem; background-color: #f2f5ff; border-left: 4px solid #4a67ff; }}
    section.cost, section.drift {{ margin-top: 2rem; }}
    section.cost table, section.drift table {{ border-collapse: collapse; width: 100%; }}
    section.cost th, section.cost td, section.drift th, section.drift td {{ border: 1px solid #e0e0e0; padding: 0.5rem; text-align: left; }}
    p.error {{ color: #b91c1c; }}
  </style>
</head>
<body>
  <h1>TerraformManager Findings</h1>
  {summary_section}
  {cost_section}
  {drift_section}
  {findings_wrapper}
  {waived_section}
</body>
</html>
"""
    return html_doc
