#!/usr/bin/env python3
"""Run all linting tasks for TerraformManager."""

from __future__ import annotations

import argparse
import shutil
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _run(cmd: list[str], *, cwd: Path | None = None) -> None:
    loc = cwd or REPO_ROOT
    print(f"$ {' '.join(cmd)}  (cwd={loc})")
    completed = subprocess.run(cmd, cwd=loc, check=False)
    if completed.returncode != 0:
        raise SystemExit(completed.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(description="Lint the backend (ruff) and frontend (pnpm).")
    parser.add_argument(
        "--fix",
        action="store_true",
        help="Apply autofixes where supported (ruff only).",
    )
    args = parser.parse_args()

    ruff_cmd = ["ruff", "check", "api", "backend", "scripts", "tests"]
    if args.fix:
        ruff_cmd.append("--fix")
    _run(ruff_cmd)

    frontend_dir = REPO_ROOT / "frontend"
    if frontend_dir.exists():
        pnpm = shutil.which("pnpm")
        if pnpm is None:
            raise SystemExit("pnpm is required to lint the frontend. Install it and re-run.")
        frontend_cmd = [pnpm, "lint"]
        _run(frontend_cmd, cwd=frontend_dir)


if __name__ == "__main__":
    main()
