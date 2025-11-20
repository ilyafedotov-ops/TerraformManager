from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence


class TerraformWorkspaceError(RuntimeError):
    """Base error for workspace operations."""


@dataclass
class TerraformCommandError(TerraformWorkspaceError):
    """Raised when a Terraform CLI command fails."""

    command: Sequence[str]
    returncode: int
    stdout: str
    stderr: str

    def __str__(self) -> str:
        rendered = " ".join(self.command)
        return f"{rendered} failed with code {self.returncode}: {self.stderr or self.stdout}"


class WorkspaceConflictError(TerraformWorkspaceError):
    """Raised when a workspace with the same name already exists."""


class WorkspaceNotFoundError(TerraformWorkspaceError):
    """Raised when a workspace or variable cannot be found."""
