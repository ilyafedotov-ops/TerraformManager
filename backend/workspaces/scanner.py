from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, List, Sequence

from backend.scanner import scan_paths

from .errors import TerraformWorkspaceError
from .manager import WorkspaceManager
from .storage import touch_workspace_scan


@dataclass
class WorkspaceScanResult:
    status: str
    workspace: str
    result: Dict[str, object] | None = None
    error: str | None = None


class MultiWorkspaceScanner:
    """Scan Terraform directories across multiple workspaces."""

    def __init__(self, manager: WorkspaceManager | None = None) -> None:
        self.manager = manager or WorkspaceManager()

    def scan(
        self,
        working_dir: Path,
        workspaces: Sequence[str],
        *,
        use_terraform_validate: bool = False,
        context: Dict[str, object] | None = None,
        update_ids: Iterable[str] | None = None,
        session=None,
    ) -> Dict[str, WorkspaceScanResult]:
        if not workspaces:
            return {}

        results: Dict[str, WorkspaceScanResult] = {}
        original: str | None = None
        try:
            try:
                original = self.manager.show_current(working_dir)
            except TerraformWorkspaceError:
                original = None

            for name in workspaces:
                try:
                    self.manager.select_workspace(working_dir, name)
                except TerraformWorkspaceError as exc:
                    results[name] = WorkspaceScanResult(status="error", workspace=name, error=str(exc))
                    continue

                scan_result = scan_paths(
                    [working_dir],
                    use_terraform_validate=use_terraform_validate,
                    context={**(context or {}), "workspace": name},
                )
                results[name] = WorkspaceScanResult(status="ok", workspace=name, result=scan_result)
        finally:
            if original:
                try:
                    self.manager.select_workspace(working_dir, original)
                except TerraformWorkspaceError:
                    pass

        if session and update_ids:
            touch_workspace_scan(session, update_ids)
            session.commit()
        return results
