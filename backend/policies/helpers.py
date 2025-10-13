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


def extract_block(text: str, brace_index: int) -> str:
    """
    Return the text block starting at the provided `{` index, accounting for nested braces.
    If the block is not properly closed, returns the remainder of the string.
    """
    depth = 0
    end = brace_index
    while end < len(text):
        char = text[end]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return text[brace_index : end + 1]
        end += 1
    return text[brace_index:]
