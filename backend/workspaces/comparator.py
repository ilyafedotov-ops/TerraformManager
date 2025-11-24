from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Iterable, List, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from backend.db.models import TerraformState, TerraformStateResource, WorkspaceVariable, WorkspaceComparison


@dataclass
class WorkspaceDifference:
    category: str  # e.g. "variables"
    item: str
    workspace_a_value: Any
    workspace_b_value: Any
    severity: str  # critical, warning, info


def _normalize_value(record: WorkspaceVariable) -> Any:
    if record.sensitive:
        return "<redacted>"
    return record.value


def compare_variables_map(
    workspace_a: Dict[str, WorkspaceVariable],
    workspace_b: Dict[str, WorkspaceVariable],
    *,
    info_keys: Sequence[str] | None = None,
) -> List[WorkspaceDifference]:
    keys = set(workspace_a.keys()) | set(workspace_b.keys())
    differences: List[WorkspaceDifference] = []
    info_set = set(info_keys or [])
    for key in sorted(keys):
        left = workspace_a.get(key)
        right = workspace_b.get(key)
        left_val = _normalize_value(left) if left else None
        right_val = _normalize_value(right) if right else None
        forced_diff = bool(left and right and (left.sensitive or right.sensitive))
        if not forced_diff and left_val == right_val:
            continue
        severity = "warning"
        if key in info_set:
            severity = "info"
        elif key.lower().find("secret") != -1 or key.lower().find("password") != -1:
            severity = "critical"
        differences.append(
            WorkspaceDifference(
                category="variables",
                item=key,
                workspace_a_value=left_val,
                workspace_b_value=right_val,
                severity=severity,
            )
        )
    return differences


def load_workspace_variables(session: Session, workspace_id: str) -> Dict[str, WorkspaceVariable]:
    rows = session.execute(
        select(WorkspaceVariable).where(WorkspaceVariable.workspace_id == workspace_id).order_by(WorkspaceVariable.key.asc())
    ).scalars()
    return {row.key: row for row in rows}


def _latest_state_for_workspace(session: Session, project_id: str, workspace_name: str) -> TerraformState | None:
    stmt = (
        select(TerraformState)
        .where(TerraformState.project_id == project_id, TerraformState.workspace == workspace_name)
        .order_by(TerraformState.imported_at.desc().nullslast(), TerraformState.created_at.desc().nullslast())
        .limit(1)
    )
    return session.execute(stmt).scalars().first()


def gather_state_resources(session: Session, state_id: str) -> List[str]:
    rows = session.execute(select(TerraformStateResource.address).where(TerraformStateResource.state_id == state_id)).scalars()
    return list(rows)


def compare_state_metadata(state_a: TerraformState, state_b: TerraformState) -> List[WorkspaceDifference]:
    differences: List[WorkspaceDifference] = []
    fields = {
        "backend_type": "critical",
        "terraform_version": "warning",
        "lineage": "warning",
        "serial": "info",
    }
    for field, severity in fields.items():
        value_a = getattr(state_a, field, None)
        value_b = getattr(state_b, field, None)
        if value_a != value_b:
            differences.append(
                WorkspaceDifference(
                    category="config",
                    item=field,
                    workspace_a_value=value_a,
                    workspace_b_value=value_b,
                    severity=severity,
                )
            )
    return differences


def compare_state_resource_sets(resources_a: Iterable[str], resources_b: Iterable[str]) -> List[WorkspaceDifference]:
    set_a = set(resources_a)
    set_b = set(resources_b)
    differences: List[WorkspaceDifference] = []
    for address in sorted(set_a - set_b):
        differences.append(
            WorkspaceDifference(
                category="state",
                item=f"resource.{address}",
                workspace_a_value="present",
                workspace_b_value="absent",
                severity="warning",
            )
        )
    for address in sorted(set_b - set_a):
        differences.append(
            WorkspaceDifference(
                category="state",
                item=f"resource.{address}",
                workspace_a_value="absent",
                workspace_b_value="present",
                severity="warning",
            )
        )
    return differences


def compare_states(session: Session, state_a: TerraformState, state_b: TerraformState) -> List[WorkspaceDifference]:
    resources_a = gather_state_resources(session, state_a.id)
    resources_b = gather_state_resources(session, state_b.id)
    differences = compare_state_metadata(state_a, state_b)
    differences.extend(compare_state_resource_sets(resources_a, resources_b))
    return differences


def latest_states_for_workspaces(
    session: Session,
    project_id: str,
    workspace_a_name: str,
    workspace_b_name: str,
) -> tuple[TerraformState | None, TerraformState | None]:
    return (
        _latest_state_for_workspace(session, project_id, workspace_a_name),
        _latest_state_for_workspace(session, project_id, workspace_b_name),
    )


def record_workspace_comparison(
    session: Session,
    *,
    project_id: str,
    workspace_a_id: str,
    workspace_b_id: str,
    comparison_type: str,
    differences: List[WorkspaceDifference],
) -> WorkspaceComparison:
    payload = [
        {
            "category": diff.category,
            "item": diff.item,
            "workspace_a_value": diff.workspace_a_value,
            "workspace_b_value": diff.workspace_b_value,
            "severity": diff.severity,
        }
        for diff in differences
    ]
    record = WorkspaceComparison(
        project_id=project_id,
        workspace_a_id=workspace_a_id,
        workspace_b_id=workspace_b_id,
        comparison_type=comparison_type,
        differences_count=len(differences),
        differences=payload,
    )
    session.add(record)
    session.flush()
    session.refresh(record)
    return record
