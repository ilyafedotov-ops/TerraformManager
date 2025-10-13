from __future__ import annotations

import os
from pathlib import Path
from typing import Iterable


def _candidate_paths() -> Iterable[Path]:
    # 1) explicit override via TERRAFORM_MANAGER_ENV
    override = os.getenv("TERRAFORM_MANAGER_ENV")
    if override:
        yield Path(override).expanduser()

    # 2) repository root relative to this file
    repo_root = Path(__file__).resolve().parent.parent.parent
    yield repo_root / ".env"

    # 3) current working directory (allows running from elsewhere)
    yield Path.cwd() / ".env"


def load_env_file() -> None:
    """
    Load key=value pairs from the first .env file we can find.

    Existing environment variables are left untouched so callers can override by
    exporting values before invoking the CLI, API, or web app.
    """

    for candidate in _candidate_paths():
        if candidate.exists():
            _apply_env(candidate)
            break


def _apply_env(path: Path) -> None:
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key:
            continue
        value = value.strip()
        if (value.startswith('"') and value.endswith('"')) or (value.startswith("'") and value.endswith("'")):
            value = value[1:-1]
        value = value.replace("\\n", "\n")
        os.environ.setdefault(key, value)
