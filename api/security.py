from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence

ACTIONS_LOG_PATH = Path(os.getenv("TFM_AUTH_AUDIT_LOG", "data/auth_audit.log"))

def record_auth_event(event: str, *, subject: str | None = None, scopes: Sequence[str] | None = None, details: dict | None = None) -> None:
    """Persist basic audit events for login/refresh/logout."""
    ACTIONS_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "event": event,
        "subject": subject,
        "scopes": list(scopes or []),
        "details": details or {},
        "timestamp": datetime.now(tz=timezone.utc).isoformat(),
    }
    with ACTIONS_LOG_PATH.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps(entry) + "\n")
