from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Sequence
import json
import os

from backend.auth.tokens import (
    ACCESS_TOKEN_EXPIRE_MINUTES,
    REFRESH_TOKEN_EXPIRE_MINUTES,
    TokenError,
    TokenPayload,
    TokenType,
    create_access_token,
    create_refresh_token,
    decode_token,
    ensure_scopes,
)

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
