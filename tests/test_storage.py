from __future__ import annotations

from pathlib import Path
from typing import Dict

import pytest

from backend import storage


@pytest.fixture()
def db_path(tmp_path: Path) -> Path:
    db_file = tmp_path / "app.db"
    storage.init_db(db_file)
    return db_file


def test_config_crud(db_path: Path) -> None:
    assert storage.get_config("demo", db_path=db_path) is None

    storage.upsert_config("demo", payload="{}", db_path=db_path)
    cfg = storage.get_config("demo", db_path=db_path)
    assert cfg is not None
    assert cfg["payload"] == "{}"
    assert cfg["kind"] == "tfreview"
    assert cfg["created_at"] is not None
    assert cfg["updated_at"] is not None

    storage.upsert_config("demo", payload='{"foo": "bar"}', kind="custom", db_path=db_path)
    cfg_updated = storage.get_config("demo", db_path=db_path)
    assert cfg_updated is not None
    assert cfg_updated["payload"] == '{"foo": "bar"}'
    assert cfg_updated["kind"] == "custom"

    configs = storage.list_configs(db_path=db_path)
    assert len(configs) == 1
    assert configs[0]["size"] == len('{"foo": "bar"}')

    assert storage.delete_config("demo", db_path=db_path) is True
    assert storage.delete_config("demo", db_path=db_path) is False
    assert storage.get_config("demo", db_path=db_path) is None


def test_report_roundtrip(db_path: Path) -> None:
    summary: Dict[str, int] = {"count": 1}
    report_payload: Dict[str, object] = {"findings": [], "summary": summary}

    storage.save_report("r1", summary, report_payload, db_path=db_path)
    first = storage.get_report("r1", db_path=db_path)
    assert first is not None
    assert first["summary"] == summary
    assert first["report"] == report_payload
    created_at = first["created_at"]

    storage.save_report("r1", {"count": 2}, {"findings": [1], "summary": {"count": 2}}, db_path=db_path)
    second = storage.get_report("r1", db_path=db_path)
    assert second is not None
    assert second["summary"]["count"] == 2
    assert second["report"]["findings"] == [1]
    assert second["created_at"] == created_at

    reports = storage.list_reports(db_path=db_path)
    assert len(reports) == 1
    assert reports[0]["summary"]["count"] == 2

    assert storage.delete_report("missing", db_path=db_path) is False
    assert storage.delete_report("r1", db_path=db_path) is True
    assert storage.get_report("r1", db_path=db_path) is None


def test_settings_helpers(db_path: Path) -> None:
    assert storage.get_setting("llm", db_path=db_path) is None

    storage.upsert_setting("llm", {"provider": "openai"}, db_path=db_path)
    raw = storage.get_setting("llm", db_path=db_path)
    assert raw is not None
    assert '"provider": "openai"' in raw

    settings = storage.get_llm_settings(db_path=db_path)
    assert settings["provider"] == "openai"

    storage.upsert_setting("llm", '{"provider": "off"}', db_path=db_path)
    assert storage.get_llm_settings(db_path=db_path)["provider"] == "off"
