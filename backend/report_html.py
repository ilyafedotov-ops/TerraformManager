from __future__ import annotations

import html
from pathlib import Path
from typing import Dict, Any, Iterable


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
  </style>
</head>
<body>
  <h1>TerraformManager Findings</h1>
  {summary_section}
  {findings_wrapper}
  {waived_section}
</body>
</html>
"""
    return html_doc
