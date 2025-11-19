#!/usr/bin/env python3
"""SQLite migration that backfills user profile-related columns."""

from __future__ import annotations

import argparse
from pathlib import Path

from backend.db.migrations import ensure_user_profile_columns
from backend.db.session import DEFAULT_DB_PATH


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Add user profile columns to the users table.")
    parser.add_argument("--db-path", type=Path, default=DEFAULT_DB_PATH, help="Path to sqlite database file.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ensure_user_profile_columns(args.db_path)


if __name__ == "__main__":
    main()
