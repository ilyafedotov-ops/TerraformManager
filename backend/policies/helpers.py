from __future__ import annotations

from pathlib import Path
from typing import Any, Dict


def make_candidate(
    rule_id: str,
    file: Path,
    line: int,
    *,
    context: Dict[str, Any] | None = None,
    snippet: str = "",
    suggested_fix_snippet: str = "",
    unique_id: str | None = None,
    overrides: Dict[str, Any] | None = None,
) -> Dict[str, Any]:
    return {
        "rule_id": rule_id,
        "file": str(file),
        "line": line,
        "context": context or {},
        "snippet": snippet,
        "suggested_fix_snippet": suggested_fix_snippet,
        "unique_id": unique_id,
        "overrides": overrides or {},
    }


def find_line_number(text: str, target: str) -> int:
    for idx, line in enumerate(text.splitlines(), start=1):
        if target in line:
            return idx
    return 1
