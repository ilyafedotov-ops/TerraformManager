from __future__ import annotations

import hashlib
import json
from typing import Any, Dict, Iterable, List, Set, Tuple

from .models import (
    DriftSummary,
    TerraformStateDocument,
    TerraformStateOutputModel,
    TerraformStateResourceModel,
)


def parse_state_bytes(data: bytes, *, backend_type: str | None = None) -> TerraformStateDocument:
    """Parse raw state bytes into a structured document with derived metadata."""

    try:
        raw_state = json.loads(data.decode("utf-8"))
    except Exception as exc:  # noqa: BLE001
        raise ValueError(f"Unable to parse Terraform state JSON: {exc}") from exc

    resources = _extract_resources(raw_state)
    outputs = _extract_outputs(raw_state)

    checksum = hashlib.sha256(data).hexdigest()
    size_bytes = len(data)

    return TerraformStateDocument(
        serial=raw_state.get("serial"),
        terraform_version=raw_state.get("terraform_version") or raw_state.get("terraform_version_required"),
        lineage=raw_state.get("lineage"),
        backend_type=backend_type,
        resource_count=len(resources),
        output_count=len(outputs),
        checksum=checksum,
        size_bytes=size_bytes,
        resources=resources,
        outputs=outputs,
        raw_state=raw_state,
    )


def compare_state_to_plan(state: TerraformStateDocument, plan_json: Dict[str, Any]) -> DriftSummary:
    """Detect drift by comparing state resources to the planned values and resource changes."""

    plan_resources, plan_resource_count = _collect_plan_resources(plan_json)
    state_addresses = {resource.address for resource in state.resources}

    state_only = sorted(state_addresses - plan_resources)
    plan_only = sorted(plan_resources - state_addresses)

    action_summary = _summarize_plan_actions(plan_json.get("resource_changes") or [])

    return DriftSummary(
        state_resource_count=len(state_addresses),
        plan_resource_count=plan_resource_count,
        resources_added=action_summary["create"],
        resources_changed=action_summary["update"],
        resources_destroyed=action_summary["delete"],
        state_only_resources=len(state_only),
        plan_only_resources=len(plan_only),
        details={
            "state_only": state_only[:100],
            "plan_only": plan_only[:100],
            "plan_actions": action_summary,
        },
    )


def _extract_resources(raw_state: Dict[str, Any]) -> List[TerraformStateResourceModel]:
    """Flatten Terraform state resources into addressable instances."""

    normalized: List[TerraformStateResourceModel] = []
    for resource in raw_state.get("resources", []):
        address = resource.get("address")
        module_address = resource.get("module")
        mode = resource.get("mode") or "managed"
        resource_type = resource.get("type") or "unknown"
        name = resource.get("name") or "unnamed"
        provider = resource.get("provider")
        instances = resource.get("instances") or []

        if not instances:
            normalized.append(
                TerraformStateResourceModel(
                    address=address or _compose_address(module_address, resource_type, name, None),
                    module_address=module_address,
                    mode=mode,
                    type=resource_type,
                    name=name,
                    provider=provider,
                    index=None,
                    schema_version=None,
                    attributes={},
                    sensitive_attributes=[],
                    dependencies=[],
                )
            )
            continue

        for instance in instances:
            index = instance.get("index_key")
            schema_version = instance.get("schema_version")
            attributes = instance.get("attributes") or {}
            sensitive = instance.get("sensitive_attributes") or []
            dependencies = instance.get("dependencies") or []
            instance_address = _compose_instance_address(address, module_address, mode, resource_type, name, index)
            normalized.append(
                TerraformStateResourceModel(
                    address=instance_address,
                    module_address=module_address,
                    mode=mode,
                    type=resource_type,
                    name=name,
                    provider=provider,
                    index=str(index) if index is not None else None,
                    schema_version=schema_version,
                    attributes=attributes,
                    sensitive_attributes=_normalize_sensitive_attributes(sensitive),
                    dependencies=[str(dep) for dep in dependencies],
                )
            )
    return normalized


def _normalize_sensitive_attributes(items: Any) -> List[str]:
    paths: List[str] = []
    if not items:
        return paths
    for item in items:
        if isinstance(item, str):
            paths.append(item)
        elif isinstance(item, (tuple, list)):
            parts = [str(part) for part in item]
            paths.append(".".join(parts))
        else:
            paths.append(str(item))
    return paths


def _extract_outputs(raw_state: Dict[str, Any]) -> List[TerraformStateOutputModel]:
    outputs_block = raw_state.get("outputs") or {}
    outputs: List[TerraformStateOutputModel] = []
    for name, payload in outputs_block.items():
        outputs.append(
            TerraformStateOutputModel(
                name=name,
                value=payload.get("value"),
                sensitive=bool(payload.get("sensitive")),
                type=payload.get("type"),
            )
        )
    return outputs


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
        address = _compose_address(module_address, resource_type, name, None, mode=mode)
    if index is None:
        return address

    index_suffix = f"[{index}]"
    if address.endswith(index_suffix):
        return address
    return f"{address}{index_suffix}"


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


def _collect_plan_resources(plan_json: Dict[str, Any]) -> Tuple[Set[str], int]:
    planned_values = plan_json.get("planned_values") or {}
    root_module = planned_values.get("root_module") or {}
    addresses = _collect_module_addresses(root_module, prefix=None)
    return addresses, len(addresses)


def _collect_module_addresses(module: Dict[str, Any], prefix: str | None) -> Set[str]:
    addresses: Set[str] = set()
    for resource in module.get("resources") or []:
        address = resource.get("address")
        if address:
            addresses.add(address)
    for child in module.get("child_modules") or []:
        addresses |= _collect_module_addresses(child, prefix=child.get("address"))
    return addresses


def _summarize_plan_actions(resource_changes: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    summary = {"create": 0, "update": 0, "delete": 0}
    for change in resource_changes:
        actions = change.get("change", {}).get("actions") or []
        normalized_actions = [action for action in actions if action in {"create", "update", "delete"}]
        if not normalized_actions:
            continue
        if normalized_actions == ["create"]:
            summary["create"] += 1
        elif normalized_actions == ["delete"]:
            summary["delete"] += 1
        else:
            summary["update"] += 1
    return summary
