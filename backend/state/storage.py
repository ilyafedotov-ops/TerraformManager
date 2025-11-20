from __future__ import annotations

import json
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from backend.db.models import (
    DriftDetection,
    PlanApproval,
    PlanResourceChange,
    TerraformPlan,
    TerraformState,
    TerraformStateOutput,
    TerraformStateResource,
    TerraformWorkspace,
    WorkspaceVariable,
    WorkspaceComparison,
)
from .models import DriftSummary, StateBackendConfig, TerraformStateDocument
from .reader import load_state_from_bytes


class StateNotFoundError(Exception):
    """Raised when the requested Terraform state entry is missing."""


class StateMutationError(Exception):
    """Raised when a mutation request could not be applied."""


class WorkspaceNotFoundError(Exception):
    """Raised when a workspace is missing."""


class PlanNotFoundError(Exception):
    """Raised when a plan record is missing."""


def persist_state_document(
    *,
    session: Session,
    project_id: str,
    workspace: str,
    backend: StateBackendConfig,
    document: TerraformStateDocument,
) -> TerraformState:
    """Persist the parsed Terraform state and its resources/outputs."""

    snapshot = json.dumps(document.raw_state, sort_keys=True)
    record = TerraformState(
        project_id=project_id,
        workspace=workspace,
        backend_type=backend.type,
        backend_config=backend.model_dump(exclude_none=True),
        serial=document.serial,
        terraform_version=document.terraform_version,
        lineage=document.lineage,
        resource_count=document.resource_count,
        output_count=document.output_count,
        state_snapshot=snapshot,
        checksum=document.checksum,
    )
    session.add(record)
    session.flush()

    for resource in document.resources:
        session.add(
            TerraformStateResource(
                state_id=record.id,
                address=resource.address,
                module_address=resource.module_address,
                mode=resource.mode,
                type=resource.type,
                name=resource.name,
                provider=resource.provider,
                schema_version=resource.schema_version,
                attributes=resource.attributes,
                sensitive_attributes=resource.sensitive_attributes,
                dependencies=resource.dependencies,
            )
        )

    for output in document.outputs:
        session.add(
            TerraformStateOutput(
                state_id=record.id,
                name=output.name,
                value=output.value,
                sensitive=output.sensitive,
                type=_serialize_type_hint(output.type),
            )
        )

    session.flush()
    return record


def list_states(session: Session, *, project_id: str, workspace: str | None = None) -> List[Dict[str, Any]]:
    query = session.query(TerraformState).filter(TerraformState.project_id == project_id)
    if workspace:
        query = query.filter(TerraformState.workspace == workspace)
    query = query.order_by(TerraformState.imported_at.desc())
    return [record.to_dict(include_snapshot=False) for record in query.all()]


def get_state(session: Session, *, state_id: str, include_snapshot: bool = False) -> Dict[str, Any]:
    record = session.get(TerraformState, state_id)
    if not record:
        raise StateNotFoundError(f"State '{state_id}' not found")
    return record.to_dict(include_snapshot=include_snapshot)


def get_state_snapshot(session: Session, *, state_id: str) -> str:
    record = session.get(TerraformState, state_id)
    if not record:
        raise StateNotFoundError(f"State '{state_id}' not found")
    return record.state_snapshot


def list_state_resources(
    session: Session,
    *,
    state_id: str,
    limit: int = 200,
    offset: int = 0,
) -> List[Dict[str, Any]]:
    query = (
        session.query(TerraformStateResource)
        .filter(TerraformStateResource.state_id == state_id)
        .order_by(TerraformStateResource.address)
    )
    if offset:
        query = query.offset(offset)
    if limit:
        query = query.limit(limit)
    return [resource.to_dict() for resource in query.all()]


def list_state_outputs(session: Session, *, state_id: str) -> List[Dict[str, Any]]:
    query = (
        session.query(TerraformStateOutput)
        .filter(TerraformStateOutput.state_id == state_id)
        .order_by(TerraformStateOutput.name)
    )
    return [output.to_dict() for output in query.all()]


def record_drift_detection(
    session: Session,
    *,
    project_id: str,
    workspace: str,
    method: str,
    summary: DriftSummary,
    state_id: str | None,
) -> DriftDetection:
    total_drifted = summary.resources_added + summary.resources_changed + summary.resources_destroyed
    record = DriftDetection(
        project_id=project_id,
        state_id=state_id,
        workspace=workspace,
        detection_method=method,
        total_drifted=total_drifted,
        resources_added=summary.resources_added,
        resources_modified=summary.resources_changed,
        resources_deleted=summary.resources_destroyed,
        drift_details=summary.details,
    )
    session.add(record)
    session.flush()
    return record


def create_workspace(
    session: Session,
    *,
    project_id: str,
    name: str,
    working_directory: str,
    is_default: bool = False,
    is_active: bool = False,
) -> TerraformWorkspace:
    workspace = TerraformWorkspace(
        project_id=project_id,
        name=name,
        working_directory=working_directory,
        is_default=is_default,
        is_active=is_active,
    )
    session.add(workspace)
    session.flush()
    return workspace


def list_workspaces(session: Session, *, project_id: str) -> List[Dict[str, Any]]:
    query = (
        session.query(TerraformWorkspace)
        .filter(TerraformWorkspace.project_id == project_id)
        .order_by(TerraformWorkspace.created_at.is_(None), TerraformWorkspace.created_at.desc())
    )
    return [workspace.to_dict() for workspace in query.all()]


def create_plan_record(
    session: Session,
    *,
    project_id: str,
    workspace: str,
    working_directory: str,
    plan_type: str,
    has_changes: bool,
    target_resources: Optional[List[str]] = None,
    resource_changes: Optional[Dict[str, Any]] = None,
    resource_changes_detail: Optional[List[Dict[str, Any]]] = None,
    output_changes: Optional[Dict[str, Any]] = None,
    plan_file_path: Optional[str] = None,
    plan_json_path: Optional[str] = None,
    plan_output: Optional[str] = None,
    cost_estimate: Optional[Dict[str, Any]] = None,
    security_impact: Optional[Dict[str, Any]] = None,
    approval_status: Optional[str] = None,
    run_id: Optional[str] = None,
) -> TerraformPlan:
    plan = TerraformPlan(
        project_id=project_id,
        workspace=workspace,
        working_directory=working_directory,
        plan_type=plan_type,
        target_resources=target_resources,
        has_changes=has_changes or bool(resource_changes_detail),
        resource_changes=resource_changes,
        output_changes=output_changes,
        plan_file_path=plan_file_path,
        plan_json_path=plan_json_path,
        plan_output=plan_output,
        cost_estimate=cost_estimate,
        security_impact=security_impact,
        approval_status=approval_status or "pending",
        run_id=run_id,
    )
    session.add(plan)
    session.flush()

    if resource_changes_detail:
        action_counts = {"add": 0, "change": 0, "destroy": 0, "replace": 0}
        for change in resource_changes_detail:
            action = str(change.get("action") or "").lower()
            if "replace" in action:
                action_counts["replace"] += 1
            elif action in {"create", "add"}:
                action_counts["add"] += 1
            elif action in {"delete", "destroy"}:
                action_counts["destroy"] += 1
            else:
                action_counts["change"] += 1
            session.add(
                PlanResourceChange(
                    plan_id=plan.id,
                    resource_address=str(change.get("resource_address") or change.get("address") or ""),
                    module_address=change.get("module_address"),
                    mode=str(change.get("mode") or "managed"),
                    type=str(change.get("type") or "unknown"),
                    name=str(change.get("name") or "unnamed"),
                    provider=change.get("provider"),
                    action=action or "update",
                    action_reason=change.get("action_reason"),
                    before_attributes=change.get("before"),
                    after_attributes=change.get("after"),
                    before_sensitive=change.get("before_sensitive"),
                    after_sensitive=change.get("after_sensitive"),
                    attribute_changes=change.get("attributes"),
                    security_impact_score=change.get("security_impact_score"),
                    cost_impact=change.get("cost_impact"),
                )
            )
        plan.resources_to_add = action_counts["add"]
        plan.resources_to_change = action_counts["change"]
        plan.resources_to_destroy = action_counts["destroy"]
        plan.resources_to_replace = action_counts["replace"]
        plan.total_resources = sum(action_counts.values())
    session.flush()
    return plan


def list_plans(
    session: Session,
    *,
    project_id: str,
    workspace: Optional[str] = None,
) -> List[Dict[str, Any]]:
    query = session.query(TerraformPlan).filter(TerraformPlan.project_id == project_id)
    if workspace:
        query = query.filter(TerraformPlan.workspace == workspace)
    query = query.order_by(TerraformPlan.created_at.desc().nullslast())
    return [plan.to_dict() for plan in query.all()]


def remove_state_addresses(
    session: Session,
    *,
    state_id: str,
    addresses: List[str],
) -> Dict[str, Any]:
    state = session.get(TerraformState, state_id)
    if not state:
        raise StateNotFoundError(f"State '{state_id}' not found")
    snapshot = json.loads(state.state_snapshot)
    changed = _remove_addresses_from_snapshot(snapshot, set(addresses))
    if not changed:
        raise StateMutationError("None of the requested addresses were found in the state snapshot.")
    _persist_state_snapshot(session, state, snapshot)
    return state.to_dict(include_snapshot=False)


def move_state_address(
    session: Session,
    *,
    state_id: str,
    source: str,
    destination: str,
) -> Dict[str, Any]:
    state = session.get(TerraformState, state_id)
    if not state:
        raise StateNotFoundError(f"State '{state_id}' not found")
    snapshot = json.loads(state.state_snapshot)
    changed = _rename_snapshot_address(snapshot, source, destination)
    if not changed:
        raise StateMutationError(f"Address '{source}' not found in the state snapshot.")
    _persist_state_snapshot(session, state, snapshot)
    return state.to_dict(include_snapshot=False)


def _persist_state_snapshot(session: Session, state: TerraformState, snapshot: Dict[str, Any]) -> None:
    data = json.dumps(snapshot, sort_keys=True)
    document = load_state_from_bytes(data.encode("utf-8"), backend_type=state.backend_type)
    session.query(TerraformStateResource).filter(TerraformStateResource.state_id == state.id).delete()
    session.query(TerraformStateOutput).filter(TerraformStateOutput.state_id == state.id).delete()

    state.serial = document.serial
    state.terraform_version = document.terraform_version
    state.lineage = document.lineage
    state.resource_count = document.resource_count
    state.output_count = document.output_count
    state.state_snapshot = data
    state.checksum = document.checksum

    for resource in document.resources:
        session.add(
            TerraformStateResource(
                state_id=state.id,
                address=resource.address,
                module_address=resource.module_address,
                mode=resource.mode,
                type=resource.type,
                name=resource.name,
                provider=resource.provider,
                schema_version=resource.schema_version,
                attributes=resource.attributes,
                sensitive_attributes=resource.sensitive_attributes,
                dependencies=resource.dependencies,
            )
        )
    for output in document.outputs:
        session.add(
            TerraformStateOutput(
                state_id=state.id,
                name=output.name,
                value=output.value,
                sensitive=output.sensitive,
                type=_serialize_type_hint(output.type),
            )
        )
    session.flush()


def _remove_addresses_from_snapshot(snapshot: Dict[str, Any], targets: set[str]) -> bool:
    resources = snapshot.get("resources") or []
    updated_resources = []
    removed = False
    for resource in resources:
        entry_addresses = list(_iter_resource_addresses(resource))
        remaining_instances = []
        if not entry_addresses:
            current_address = _resolve_resource_address(resource)
            if current_address in targets:
                removed = True
                continue
        for entry_address, instance in entry_addresses:
            if entry_address in targets:
                removed = True
                continue
            remaining_instances.append(instance)
        if entry_addresses:
            if not remaining_instances:
                continue
            resource["instances"] = remaining_instances
        updated_resources.append(resource)
    if removed:
        snapshot["resources"] = updated_resources
    return removed


def _rename_snapshot_address(snapshot: Dict[str, Any], source: str, destination: str) -> bool:
    normalized_source = _normalize_resource_identifier(source)
    normalized_destination = _normalize_resource_identifier(destination)
    resources = snapshot.get("resources") or []
    for resource in resources:
        current_address = _resolve_resource_address(resource)
        if current_address == normalized_source:
            resource["address"] = normalized_destination
            return True
    return False


def _iter_resource_addresses(resource: Dict[str, Any]):
    instances = resource.get("instances") or []
    if not instances:
        return
    module_address = resource.get("module")
    mode = resource.get("mode") or "managed"
    resource_type = resource.get("type") or "unknown"
    name = resource.get("name") or "unnamed"
    explicit_address = resource.get("address")
    for instance in instances:
        index = instance.get("index_key")
        yield _compose_instance_address(explicit_address, module_address, mode, resource_type, name, index), instance


def _resolve_resource_address(resource: Dict[str, Any]) -> str:
    explicit = resource.get("address")
    if explicit:
        return explicit
    module_address = resource.get("module")
    mode = resource.get("mode") or "managed"
    resource_type = resource.get("type") or "unknown"
    name = resource.get("name") or "unnamed"
    return _compose_address(module_address, resource_type, name, mode=mode)


def _normalize_resource_identifier(value: str) -> str:
    base = value.split("[", 1)[0]
    return base.strip()


def _compose_instance_address(
    explicit_address: str | None,
    module_address: str | None,
    mode: str,
    resource_type: str,
    name: str,
    index: Any,
) -> str:
    if explicit_address:
        address = explicit_address
    else:
        address = _compose_address(module_address, resource_type, name, mode=mode)
    if index is None:
        return address
    suffix = f"[{index}]"
    if address.endswith(suffix):
        return address
    return f"{address}{suffix}"


def _compose_address(
    module_address: str | None,
    resource_type: str,
    name: str,
    index: Any = None,
    *,
    mode: str = "managed",
) -> str:
    base = f"{mode}.{resource_type}.{name}"
    if module_address:
        base = f"{module_address}.{base}"
    if index is not None:
        return f"{base}[{index}]"
    return base


def _serialize_type_hint(value: Any) -> Optional[str]:
    if value is None:
        return None
    if isinstance(value, str):
        return value
    try:
        return json.dumps(value)
    except Exception:  # noqa: BLE001
        return str(value)
