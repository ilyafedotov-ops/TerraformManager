from __future__ import annotations

import json
import logging
import os
from copy import deepcopy
from pathlib import Path
from typing import Any, Dict

from backend.llm_service import DEFAULT_OPENAI_MODEL

LOGGER = logging.getLogger(__name__)

DEFAULT_SETTINGS: Dict[str, Any] = {
    "llm": {
        "provider": "off",
        "model": DEFAULT_OPENAI_MODEL,
        "enable_explanations": False,
        "enable_patches": False,
    }
}


def _settings_path() -> Path:
    override = os.getenv("TERRAFORM_MANAGER_SETTINGS")
    if override:
        return Path(override).expanduser()
    xdg_home = os.getenv("XDG_CONFIG_HOME")
    if xdg_home:
        base = Path(xdg_home)
    else:
        base = Path.home() / ".config"
    return base / "terraform_manager" / "settings.json"


def _ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _deep_merge(base: Dict[str, Any], incoming: Dict[str, Any]) -> Dict[str, Any]:
    result = deepcopy(base)
    for key, value in incoming.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def load_settings() -> Dict[str, Any]:
    path = _settings_path()
    if not path.exists():
        return deepcopy(DEFAULT_SETTINGS)
    try:
        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)
        if not isinstance(payload, dict):
            LOGGER.warning("Ignoring malformed settings file %s (not an object).", path)
            return deepcopy(DEFAULT_SETTINGS)
        return _deep_merge(DEFAULT_SETTINGS, payload)
    except json.JSONDecodeError as exc:
        LOGGER.warning("Settings file %s is not valid JSON: %s", path, exc)
        return deepcopy(DEFAULT_SETTINGS)
    except Exception as exc:
        LOGGER.warning("Failed to read settings file %s: %s", path, exc)
        return deepcopy(DEFAULT_SETTINGS)


def save_settings(settings: Dict[str, Any]) -> None:
    path = _settings_path()
    _ensure_parent(path)
    tmp_path = path.with_suffix(".tmp")
    try:
        with tmp_path.open("w", encoding="utf-8") as handle:
            json.dump(settings, handle, indent=2)
        tmp_path.replace(path)
    except Exception as exc:
        LOGGER.warning("Failed to write settings file %s: %s", path, exc)
        if tmp_path.exists():
            tmp_path.unlink(missing_ok=True)


def get_llm_settings() -> Dict[str, Any]:
    settings = load_settings()
    llm = deepcopy(settings.get("llm", {}))
    return _deep_merge(DEFAULT_SETTINGS["llm"], llm)


def update_llm_settings(partial: Dict[str, Any]) -> None:
    current = load_settings()
    llm = _deep_merge(DEFAULT_SETTINGS["llm"], current.get("llm", {}))
    changed = False
    for key, value in partial.items():
        if key not in llm:
            continue
        if llm[key] != value:
            llm[key] = value
            changed = True
    if not changed:
        return
    current["llm"] = llm
    save_settings(current)
