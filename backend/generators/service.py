from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, List

from jinja2 import Template


@dataclass
class AwsS3BackendConfig:
    bucket: str
    key: str
    region: str
    dynamodb_table: str


BASE_DIR = Path(__file__).resolve().parent


def _sanitize_identifier(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^0-9A-Za-z_]", "_", value or "")
    cleaned = cleaned.strip("_") or fallback
    if cleaned[0].isdigit():
        cleaned = f"{fallback}_{cleaned}"
    return cleaned.lower()


def render_aws_s3_bucket(payload: Dict[str, Any]) -> Dict[str, str]:
    bucket_name = payload.get("bucket_name", "my-secure-bucket")
    region = payload.get("region", "us-east-1")
    environment = payload.get("environment", "prod")
    owner_tag = payload.get("owner_tag", "platform-team")
    cost_center_tag = payload.get("cost_center_tag", "ENG-SRE")
    force_destroy = bool(payload.get("force_destroy", False))
    versioning = bool(payload.get("versioning", True))
    enforce_secure_transport = bool(payload.get("enforce_secure_transport", True))
    kms_key_id = payload.get("kms_key_id") or None

    resource_name = _sanitize_identifier(bucket_name, "bucket")

    backend_payload = payload.get("backend") or None
    backend_context: Optional[Dict[str, str]] = None
    if backend_payload:
        required_keys = {"bucket", "key", "region", "dynamodb_table"}
        if not required_keys.issubset(backend_payload.keys()):
            missing = required_keys - set(backend_payload.keys())
            raise ValueError(f"backend missing keys: {', '.join(sorted(missing))}")
        backend_context = {
            "bucket": backend_payload["bucket"],
            "key": backend_payload["key"],
            "region": backend_payload["region"],
            "dynamodb_table": backend_payload["dynamodb_table"],
        }

    template_path = BASE_DIR / "aws_s3_bucket.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        region=region,
        name=resource_name,
        bucket_name=bucket_name,
        force_destroy=force_destroy,
        environment=environment,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        versioning=versioning,
        kms_key_id=kms_key_id,
        enforce_secure_transport=enforce_secure_transport,
        backend=backend_context,
    )

    filename = f"aws_s3_{resource_name}.tf"
    return {"filename": filename, "content": content}


def _parse_allowed_ips(raw_ips: Optional[List[str]]) -> List[str]:
    values: List[str] = []
    for item in raw_ips or []:
        candidate = (item or "").strip()
        if candidate:
            values.append(candidate)
    return values


def render_azure_storage_account(payload: Dict[str, Any]) -> Dict[str, str]:
    rg_actual_name = payload.get("resource_group_name", "rg-app")
    sa_actual_name = payload.get("storage_account_name", "stapp1234567890")
    location = payload.get("location", "eastus")
    environment = payload.get("environment", "prod")
    replication = payload.get("replication", "LRS")
    versioning = bool(payload.get("versioning", True))
    owner_tag = payload.get("owner_tag", "platform-team")
    cost_center_tag = payload.get("cost_center_tag", "ENG-SRE")
    restrict_network = bool(payload.get("restrict_network", False))
    allowed_ips = _parse_allowed_ips(payload.get("allowed_ips"))

    if restrict_network and not allowed_ips:
        raise ValueError("Allowed IP ranges required when network restriction is enabled.")

    backend_payload = payload.get("backend")
    backend_context: Optional[Dict[str, str]] = None
    if backend_payload:
        required_keys = {"resource_group", "storage_account", "container", "key"}
        missing = required_keys - set(backend_payload.keys())
        if missing:
            raise ValueError(f"backend missing keys: {', '.join(sorted(missing))}")
        backend_context = {
            "resource_group": backend_payload["resource_group"],
            "storage_account": backend_payload["storage_account"],
            "container": backend_payload["container"],
            "key": backend_payload["key"],
        }

    private_endpoint_payload = payload.get("private_endpoint") or None
    private_endpoint_context: Optional[Dict[str, Any]] = None
    if private_endpoint_payload:
        required = {"name", "connection_name", "subnet_id"}
        missing = required - set(private_endpoint_payload.keys())
        if missing:
            raise ValueError(f"private_endpoint missing keys: {', '.join(sorted(missing))}")
        pe_name = private_endpoint_payload.get("name", f"{sa_actual_name}-pe")
        private_endpoint_context = {
            "resource_name": _sanitize_identifier(pe_name, "pe"),
            "name": pe_name,
            "connection_name": private_endpoint_payload.get("connection_name", f"{sa_actual_name}-blob"),
            "subnet_id": private_endpoint_payload.get("subnet_id"),
            "private_dns_zone_id": private_endpoint_payload.get("private_dns_zone_id") or None,
            "dns_zone_group_name": private_endpoint_payload.get("dns_zone_group_name") or f"{sa_actual_name}-blob-zone",
        }

    rg_name = _sanitize_identifier(rg_actual_name, "rg")
    sa_name = _sanitize_identifier(sa_actual_name, "storage")
    ip_rules_literal = ""
    if restrict_network:
        ip_rules_literal = "[" + ", ".join(f'"{ip}"' for ip in allowed_ips) + "]"

    template_path = BASE_DIR / "azure_storage_account.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        rg_name=rg_name,
        rg_actual_name=rg_actual_name,
        sa_name=sa_name,
        sa_actual_name=sa_actual_name,
        location=location,
        environment=environment,
        replication=replication,
        versioning=versioning,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        restrict_network=restrict_network,
        ip_rules_literal=ip_rules_literal,
        private_endpoint=private_endpoint_context,
        backend=backend_context,
    )

    filename = f"azure_storage_{sa_name}.tf"
    return {"filename": filename, "content": content}
