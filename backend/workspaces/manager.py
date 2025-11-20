from __future__ import annotations

import os
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Sequence

from .errors import TerraformCommandError, TerraformWorkspaceError


@dataclass
class CommandResult:
    ok: bool
    command: Sequence[str]
    returncode: int
    stdout: str
    stderr: str


@dataclass
class WorkspaceListResult:
    names: List[str]
    current: str | None
    raw_output: str


class WorkspaceManager:
    """Thin wrapper around Terraform workspace commands."""

    def __init__(self, terraform_bin: str | None = None) -> None:
        self.terraform_bin = terraform_bin or shutil.which("terraform")

    def _require_binary(self) -> str:
        if not self.terraform_bin:
            raise TerraformWorkspaceError("terraform binary not found in PATH")
        return self.terraform_bin

    def _run(self, args: Sequence[str], *, cwd: Path) -> CommandResult:
        binary = self._require_binary()
        command = [binary, *args]
        proc = subprocess.run(
            command,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            env={**os.environ, "TF_IN_AUTOMATION": "true"},
            check=False,
        )
        result = CommandResult(
            ok=proc.returncode == 0,
            command=command,
            returncode=proc.returncode,
            stdout=proc.stdout,
            stderr=proc.stderr,
        )
        if not result.ok:
            raise TerraformCommandError(command=command, returncode=proc.returncode, stdout=proc.stdout, stderr=proc.stderr)
        return result

    def list_workspaces(self, working_dir: Path) -> WorkspaceListResult:
        """Return available workspaces and the current one for a directory."""
        result = self._run(["workspace", "list"], cwd=working_dir)
        names: List[str] = []
        current: str | None = None
        for line in result.stdout.splitlines():
            text = line.strip()
            if not text:
                continue
            active = text.startswith("*")
            name = text.lstrip("*").strip()
            names.append(name)
            if active:
                current = name
        return WorkspaceListResult(names=names, current=current, raw_output=result.stdout)

    def show_current(self, working_dir: Path) -> str:
        """Return the current workspace name."""
        result = self._run(["workspace", "show"], cwd=working_dir)
        return result.stdout.strip()

    def create_workspace(self, working_dir: Path, name: str) -> CommandResult:
        """Create a new workspace in the directory."""
        return self._run(["workspace", "new", name], cwd=working_dir)

    def select_workspace(self, working_dir: Path, name: str) -> CommandResult:
        """Select an existing workspace."""
        return self._run(["workspace", "select", name], cwd=working_dir)

    def delete_workspace(self, working_dir: Path, name: str) -> CommandResult:
        """Delete a workspace (default is not allowed)."""
        if name == "default":
            raise TerraformWorkspaceError("Cannot delete the default workspace")
        return self._run(["workspace", "delete", name], cwd=working_dir)

    def ensure_workspace(self, working_dir: Path, name: str) -> WorkspaceListResult:
        """Create the workspace if missing, then select it."""
        listing = self.list_workspaces(working_dir)
        if name not in listing.names:
            self.create_workspace(working_dir, name)
            listing.names.append(name)
        self.select_workspace(working_dir, name)
        return listing

    def discover_workspaces(self, project_root: Path, *, max_depth: int = 5) -> Dict[str, List[str]]:
        """Attempt to list workspaces across Terraform directories within a project."""
        self._require_binary()
        discovered: Dict[str, List[str]] = {}
        seen: set[Path] = set()
        for tf_file in project_root.rglob("*.tf"):
            depth = len(tf_file.relative_to(project_root).parts)
            if depth > max_depth:
                continue
            candidate = tf_file.parent
            if ".terraform" in candidate.parts or "node_modules" in candidate.parts:
                continue
            if candidate in seen:
                continue
            seen.add(candidate)
            try:
                listing = self.list_workspaces(candidate)
            except TerraformWorkspaceError:
                continue
            relative = candidate.relative_to(project_root)
            discovered[str(relative) if str(relative) else "."] = listing.names
        return discovered
