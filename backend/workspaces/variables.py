from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, Iterable, List, Sequence

from sqlalchemy.orm import Session

try:
    import hcl2  # type: ignore
except Exception:  # noqa: BLE001
    hcl2 = None

from .storage import upsert_workspace_variable


SENSITIVE_KEYWORDS = {"password", "secret", "token", "key", "credential", "api_key", "access_key", "private_key"}


def _serialize_value(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (str, int, float, bool)):
        return str(value)
    try:
        return json.dumps(value)
    except Exception:  # noqa: BLE001
        return str(value)


def load_tfvars(tfvars_path: Path) -> Dict[str, Any]:
    """Load variables from a .tfvars/.tfvars.json file."""
    if not tfvars_path.exists():
        return {}

    text = tfvars_path.read_text(encoding="utf-8")

    if hcl2:
        try:
            with tfvars_path.open("r") as handle:
                parsed = hcl2.load(handle)
            return parsed or {}
        except Exception:  # noqa: BLE001
            pass

    try:
        return json.loads(text)
    except Exception:  # noqa: BLE001
        return {}


def detect_sensitive_keys(variables: Iterable[str], extra_sensitive: Sequence[str] | None = None) -> List[str]:
    sensitive = set(extra_sensitive or [])
    for key in variables:
        lowered = key.lower()
        if any(token in lowered for token in SENSITIVE_KEYWORDS):
            sensitive.add(key)
    return sorted(sensitive)


def import_tfvars_file(
    session: Session,
    *,
    workspace_id: str,
    tfvars_path: Path,
    extra_sensitive: Sequence[str] | None = None,
) -> Dict[str, Any]:
    """Import variables from a tfvars file into the DB."""
    data = load_tfvars(tfvars_path)
    if not data:
        return {"imported": 0, "sensitive_keys": []}

    sensitive_keys = detect_sensitive_keys(data.keys(), extra_sensitive=extra_sensitive)
    imported = 0
    for key, value in data.items():
        upsert_workspace_variable(
            session,
            workspace_id=workspace_id,
            key=key,
            value=_serialize_value(value),
            sensitive=key in sensitive_keys,
            source="tfvars",
            description=None,
        )
        imported += 1
    session.flush()
    return {"imported": imported, "sensitive_keys": sensitive_keys}
