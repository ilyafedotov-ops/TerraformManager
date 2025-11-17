from __future__ import annotations

import shutil
import subprocess
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Sequence


@dataclass
class TerraformSourceFile:
    path: str
    content: bytes


def _write_sources(root: Path, files: Sequence[TerraformSourceFile]) -> None:
    for file in files:
        relative = file.path.strip().lstrip("./")
        if not relative:
            relative = "main.tf"
        destination = (root / relative).resolve()
        destination.parent.mkdir(parents=True, exist_ok=True)
        with open(destination, "wb") as handle:
            handle.write(file.content)


def _run_command(command: Sequence[str], *, cwd: Path) -> Dict[str, Any]:
    proc = subprocess.run(
        command,
        cwd=str(cwd),
        capture_output=True,
        text=True,
        check=False,
    )
    return {
        "ok": proc.returncode == 0,
        "returncode": proc.returncode,
        "stdout": proc.stdout,
        "stderr": proc.stderr,
        "command": command,
    }


def validate_terraform_sources(files: Sequence[TerraformSourceFile]) -> Dict[str, Any]:
    """
    Run lightweight Terraform validation (fmt -check) for the provided source files.
    Returns a JSON-serializable summary including stdout/stderr for troubleshooting.
    """

    if not files:
        return {"status": "skipped", "reason": "no source files provided"}

    terraform_binary = shutil.which("terraform")
    if not terraform_binary:
        return {"status": "skipped", "reason": "terraform binary not available in PATH"}

    with tempfile.TemporaryDirectory() as tmpdir:
        workspace = Path(tmpdir)
        _write_sources(workspace, files)
        fmt_result = _run_command([terraform_binary, "fmt", "-check", "-recursive"], cwd=workspace)

        status = "passed" if fmt_result["ok"] else "failed"
        summary: Dict[str, Any] = {
            "status": status,
            "fmt": fmt_result,
            "validate": {
                "status": "skipped",
                "reason": "terraform validate not executed in this build",
            },
            "file_count": len(files),
        }
        return summary


__all__ = ["TerraformSourceFile", "validate_terraform_sources"]
