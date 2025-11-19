from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import Iterable, Tuple

from backend.db.session import DEFAULT_DB_PATH

USER_PROFILE_COLUMNS: Tuple[Tuple[str, str], ...] = (
    ("full_name", "TEXT"),
    ("job_title", "TEXT"),
    ("timezone", "TEXT"),
    ("avatar_url", "TEXT"),
    ("profile_preferences", "TEXT NOT NULL DEFAULT '{}'"),
)


def _column_exists(connection: sqlite3.Connection, table: str, column: str) -> bool:
    cursor = connection.execute(f"PRAGMA table_info('{table}')")
    return any(row[1] == column for row in cursor.fetchall())


def _add_column(connection: sqlite3.Connection, table: str, column: str, definition: str) -> None:
    connection.execute(f"ALTER TABLE {table} ADD COLUMN {column} {definition}")


def ensure_user_profile_columns(
    db_path: Path | str | None = None,
    *,
    columns: Iterable[Tuple[str, str]] = USER_PROFILE_COLUMNS,
) -> None:
    """Ensure new profile-related columns exist on the users table."""
    path = Path(db_path or DEFAULT_DB_PATH).expanduser()
    path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(path) as connection:
        connection.execute("PRAGMA foreign_keys=ON")
        for column, definition in columns:
            if _column_exists(connection, "users", column):
                continue
            _add_column(connection, "users", column, definition)
        connection.commit()
