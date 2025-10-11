from __future__ import annotations

import csv
import io
from typing import Any, Dict, List


CSV_FIELDS = [
    "id",
    "rule",
    "title",
    "severity",
    "file",
    "line",
    "description",
    "recommendation",
]


def render_csv_findings(findings: List[Dict[str, Any]]) -> str:
    """Render a list of findings to CSV with a stable header."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=CSV_FIELDS, extrasaction="ignore")
    writer.writeheader()
    for f in findings:
        writer.writerow({k: f.get(k, "") for k in CSV_FIELDS})
    return buf.getvalue()


def render_csv_report(report: Dict[str, Any]) -> str:
    findings: List[Dict[str, Any]] = report.get("findings", [])
    return render_csv_findings(findings)
