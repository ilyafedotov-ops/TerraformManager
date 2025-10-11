from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


DEFAULT_DB_PATH = Path("data/app.db")


def _ensure_parent(path: Path) -> None:
    if path.parent and not path.parent.exists():
        path.parent.mkdir(parents=True, exist_ok=True)


def _connect(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    _ensure_parent(db_path)
    conn = sqlite3.connect(str(db_path))
    conn.row_factory = sqlite3.Row
    return conn


def init_db(db_path: Path = DEFAULT_DB_PATH) -> None:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        # configs: named YAML/JSON blobs for scanner config (waivers/thresholds)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS configs (
                name TEXT PRIMARY KEY,
                kind TEXT NOT NULL DEFAULT 'tfreview',
                payload TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # reports: persisted scan results for advanced reporting
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS reports (
                id TEXT PRIMARY KEY,
                summary TEXT NOT NULL,
                report TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        # settings: simple key/value store (JSON encoded values)
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            );
            """
        )
        conn.commit()
    finally:
        conn.close()


def upsert_config(name: str, payload: str, kind: str = "tfreview", db_path: Path = DEFAULT_DB_PATH) -> None:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO configs(name, kind, payload)
            VALUES(?, ?, ?)
            ON CONFLICT(name) DO UPDATE SET
              kind=excluded.kind,
              payload=excluded.payload,
              updated_at=CURRENT_TIMESTAMP
            ;
            """,
            (name, kind, payload),
        )
        conn.commit()
    finally:
        conn.close()


def get_config(name: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT name, kind, payload, created_at, updated_at FROM configs WHERE name=?", (name,)).fetchone()
        if not row:
            return None
        return {
            "name": row["name"],
            "kind": row["kind"],
            "payload": row["payload"],
            "created_at": row["created_at"],
            "updated_at": row["updated_at"],
        }
    finally:
        conn.close()


def list_configs(db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        rows = cur.execute("SELECT name, kind, length(payload) as size, created_at, updated_at FROM configs ORDER BY updated_at DESC").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def delete_config(name: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM configs WHERE name=?", (name,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def save_report(report_id: str, summary: Dict[str, Any], report: Dict[str, Any], db_path: Path = DEFAULT_DB_PATH) -> None:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            "INSERT OR REPLACE INTO reports(id, summary, report, created_at) VALUES(?, ?, ?, COALESCE((SELECT created_at FROM reports WHERE id=?), CURRENT_TIMESTAMP))",
            (report_id, json.dumps(summary), json.dumps(report), report_id),
        )
        conn.commit()
    finally:
        conn.close()


def list_reports(limit: int = 50, db_path: Path = DEFAULT_DB_PATH) -> List[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        rows = cur.execute("SELECT id, summary, created_at FROM reports ORDER BY created_at DESC LIMIT ?", (limit,)).fetchall()
        results: List[Dict[str, Any]] = []
        for row in rows:
            try:
                summary = json.loads(row["summary"]) if row["summary"] else {}
            except Exception:
                summary = {}
            results.append({"id": row["id"], "summary": summary, "created_at": row["created_at"]})
        return results
    finally:
        conn.close()


def get_report(report_id: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[Dict[str, Any]]:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT id, summary, report, created_at FROM reports WHERE id=?", (report_id,)).fetchone()
        if not row:
            return None
        try:
            summary = json.loads(row["summary"]) if row["summary"] else {}
        except Exception:
            summary = {}
        try:
            report = json.loads(row["report"]) if row["report"] else {}
        except Exception:
            report = {}
        return {"id": row["id"], "summary": summary, "report": report, "created_at": row["created_at"]}
    finally:
        conn.close()


def delete_report(report_id: str, db_path: Path = DEFAULT_DB_PATH) -> bool:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute("DELETE FROM reports WHERE id=?", (report_id,))
        conn.commit()
        return cur.rowcount > 0
    finally:
        conn.close()


def upsert_setting(key: str, value: Dict[str, Any] | str, db_path: Path = DEFAULT_DB_PATH) -> None:
    import json as _json
    if not isinstance(value, str):
        payload = _json.dumps(value)
    else:
        payload = value
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        cur.execute(
            """
            INSERT INTO settings(key, value) VALUES(?, ?) ON CONFLICT(key) DO UPDATE SET value=excluded.value, updated_at=CURRENT_TIMESTAMP
            """,
            (key, payload),
        )
        conn.commit()
    finally:
        conn.close()


def get_setting(key: str, db_path: Path = DEFAULT_DB_PATH) -> Optional[str]:
    conn = _connect(db_path)
    try:
        cur = conn.cursor()
        row = cur.execute("SELECT value FROM settings WHERE key=?", (key,)).fetchone()
        if not row:
            return None
        return row["value"]
    finally:
        conn.close()


def get_llm_settings(db_path: Path = DEFAULT_DB_PATH) -> Dict[str, Any]:
    import json as _json
    raw = get_setting("llm", db_path=db_path)
    if not raw:
        return {"provider": "off"}
    try:
        return _json.loads(raw)
    except Exception:
        return {"provider": "off"}
