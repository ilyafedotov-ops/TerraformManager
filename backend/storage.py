from __future__ import annotations

import json
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Dict, Iterator, List, Optional

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from backend.db.models import Config, Report, Setting, format_timestamp
from backend.db.session import DEFAULT_DB_PATH as _DEFAULT_DB_PATH, init_models, session_scope

DEFAULT_DB_PATH = _DEFAULT_DB_PATH


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    """Initialise database tables using SQLAlchemy metadata."""
    init_models(db_path)


def upsert_config(
    name: str,
    payload: str,
    kind: str = "tfreview",
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> None:
    with _get_session(session, db_path) as db:
        config = db.get(Config, name)
        if config:
            config.kind = kind
            config.payload = payload
        else:
            db.add(Config(name=name, kind=kind, payload=payload))
        db.flush()


def get_config(
    name: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        config = db.get(Config, name)
        if not config:
            return None
        return config.as_dict()


def list_configs(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        stmt = (
            select(
                Config.name,
                Config.kind,
                func.length(Config.payload).label("size"),
                Config.created_at,
                Config.updated_at,
            )
            .order_by(Config.updated_at.desc())
        )
        rows = db.execute(stmt).all()
        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "name": row.name,
                    "kind": row.kind,
                    "size": int(row.size or 0),
                    "created_at": format_timestamp(row.created_at),
                    "updated_at": format_timestamp(row.updated_at),
                }
            )
        return results


def delete_config(
    name: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        config = db.get(Config, name)
        if not config:
            return False
        db.delete(config)
        db.flush()
        return True


def save_report(
    report_id: str,
    summary: Dict[str, Any],
    report: Dict[str, Any],
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> None:
    summary_json = json.dumps(summary)
    report_json = json.dumps(report)
    with _get_session(session, db_path) as db:
        existing = db.get(Report, report_id)
        if existing:
            existing.summary = summary_json
            existing.report = report_json
        else:
            db.add(Report(id=report_id, summary=summary_json, report=report_json))
        db.flush()


def list_reports(
    limit: int = 50,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> List[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        stmt = (
            select(Report.id, Report.summary, Report.created_at)
            .order_by(Report.created_at.desc())
            .limit(limit)
        )
        rows = db.execute(stmt).all()
        results: List[Dict[str, Any]] = []
        for row in rows:
            results.append(
                {
                    "id": row.id,
                    "summary": _safe_json_load(row.summary, expect_mapping=True),
                    "created_at": format_timestamp(row.created_at),
                }
            )
        return results


def get_report(
    report_id: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> Optional[Dict[str, Any]]:
    with _get_session(session, db_path) as db:
        record = db.get(Report, report_id)
        if not record:
            return None
        return {
            "id": record.id,
            "summary": _safe_json_load(record.summary, expect_mapping=True),
            "report": _safe_json_load(record.report, expect_mapping=False),
            "created_at": format_timestamp(record.created_at),
        }


def delete_report(
    report_id: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> bool:
    with _get_session(session, db_path) as db:
        record = db.get(Report, report_id)
        if not record:
            return False
        db.delete(record)
        db.flush()
        return True


def upsert_setting(
    key: str,
    value: Dict[str, Any] | str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> None:
    payload = value if isinstance(value, str) else json.dumps(value)
    with _get_session(session, db_path) as db:
        record = db.get(Setting, key)
        if record:
            record.value = payload
        else:
            db.add(Setting(key=key, value=payload))
        db.flush()


def get_setting(
    key: str,
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> Optional[str]:
    with _get_session(session, db_path) as db:
        record = db.get(Setting, key)
        if not record:
            return None
        return record.value


def get_llm_settings(
    db_path: Path = DEFAULT_DB_PATH,
    *,
    session: Session | None = None,
) -> Dict[str, Any]:
    raw = get_setting("llm", db_path=db_path, session=session)
    if not raw:
        return {"provider": "off"}
    try:
        return json.loads(raw)
    except Exception:
        return {"provider": "off"}


def _safe_json_load(value: Optional[str], *, expect_mapping: bool) -> Any:
    if not value:
        return {} if expect_mapping else {}
    try:
        data = json.loads(value)
        if expect_mapping and not isinstance(data, dict):
            return {}
        return data
    except Exception:
        return {} if expect_mapping else {}


@contextmanager
def _get_session(existing: Session | None, db_path: Path) -> Iterator[Session]:
    if existing is not None:
        yield existing
        return
    with session_scope(db_path) as scoped:
        yield scoped
