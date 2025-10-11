from __future__ import annotations

import io
from pathlib import Path
from typing import List, Dict, Any

from backend.policies.helpers import make_candidate

try:
    import hcl2  # type: ignore
except Exception:  # pragma: no cover - optional dependency
    hcl2 = None


def check_hcl_parse(file: Path, text: str) -> List[Dict[str, Any]]:
    if hcl2 is None:
        return []
    try:
        hcl2.load(io.StringIO(text))
    except Exception:
        return [
            make_candidate(
                "SYNTAX-HCL-PARSE",
                file,
                line=1,
                context={"file": file.name},
                snippet=text[:160],
                unique_id=f"SYNTAX-HCL-PARSE::{file.name}",
            )
        ]
    return []


CHECKS = [check_hcl_parse]
