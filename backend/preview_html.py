from __future__ import annotations

from html import escape
from typing import Any, Dict, List


def _row(cells: List[str]) -> str:
    return "<tr>" + "".join(f"<td>{c}</td>" for c in cells) + "</tr>"


def _finding_row(f: Dict[str, Any]) -> str:
    return _row([
        escape(str(f.get("id", ""))),
        escape(str(f.get("rule", ""))),
        escape(str(f.get("title", ""))),
        escape(str(f.get("severity", ""))),
        escape(str(f.get("file", ""))),
        escape(str(f.get("line", 1))),
    ])


def render_preview_html(applied: Dict[str, Any], original_summary: Dict[str, Any]) -> str:
    active = applied.get("active", [])
    waived = applied.get("waived", [])
    before = original_summary or {}

    html = [
        "<!doctype html>",
        "<html><head><meta charset='utf-8'><title>Config Preview</title>",
        "<style>body{font-family:system-ui,Segoe UI,Arial;margin:1.5rem}table{border-collapse:collapse;width:100%}td,th{border:1px solid #ddd;padding:.5rem}th{background:#f5f5f5;text-align:left}code{background:#f3f4f6;padding:.15rem .3rem;border-radius:4px}</style>",
        "</head><body>",
        "<h2>Config Application Preview</h2>",
        "<h3>Summary</h3>",
        "<ul>",
        f"<li>Before issues: <b>{escape(str(before.get('issues_found', 'N/A')))}</b></li>",
        f"<li>After issues: <b>{len(active)}</b></li>",
        "</ul>",
        "<h3>Waived Findings</h3>",
        "<table><thead><tr><th>ID</th><th>Rule</th><th>Title</th><th>Severity</th><th>File</th><th>Line</th></tr></thead><tbody>",
    ]
    for f in waived:
        html.append(_finding_row(f))
    if not waived:
        html.append("<tr><td colspan='6'><i>None</i></td></tr>")
    html.append("</tbody></table>")

    html.extend([
        "<h3>Active Findings</h3>",
        "<table><thead><tr><th>ID</th><th>Rule</th><th>Title</th><th>Severity</th><th>File</th><th>Line</th></tr></thead><tbody>",
    ])
    for f in active:
        html.append(_finding_row(f))
    if not active:
        html.append("<tr><td colspan='6'><i>None</i></td></tr>")
    html.append("</tbody></table>")

    html.append("</body></html>")
    return "\n".join(html)
