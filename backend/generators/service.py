from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Union

from jinja2 import Template

from .models import AwsS3GeneratorPayload, AzureStorageGeneratorPayload


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


AwsPayloadLike = Union[AwsS3GeneratorPayload, Dict[str, Any]]
AzurePayloadLike = Union[AzureStorageGeneratorPayload, Dict[str, Any]]


def _ensure_aws_payload(payload: AwsPayloadLike) -> AwsS3GeneratorPayload:
    if isinstance(payload, AwsS3GeneratorPayload):
        return payload
    return AwsS3GeneratorPayload.model_validate(payload)


def _ensure_azure_payload(payload: AzurePayloadLike) -> AzureStorageGeneratorPayload:
    if isinstance(payload, AzureStorageGeneratorPayload):
        return payload
    return AzureStorageGeneratorPayload.model_validate(payload)


def render_aws_s3_bucket(payload: AwsPayloadLike) -> Dict[str, str]:
    typed = _ensure_aws_payload(payload)

    bucket_name = typed.bucket_name
    region = typed.region
    environment = typed.environment
    owner_tag = typed.owner_tag
    cost_center_tag = typed.cost_center_tag
    force_destroy = typed.force_destroy
    versioning = typed.versioning
    enforce_secure_transport = typed.enforce_secure_transport
    kms_key_id = typed.kms_key_id

    resource_name = _sanitize_identifier(bucket_name, "bucket")

    backend_context: Optional[Dict[str, str]] = None
    if typed.backend:
        backend_context = typed.backend.model_dump()

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


def render_azure_storage_account(payload: AzurePayloadLike) -> Dict[str, str]:
    typed = _ensure_azure_payload(payload)

    rg_actual_name = typed.resource_group_name
    sa_actual_name = typed.storage_account_name
    location = typed.location
    environment = typed.environment
    replication = typed.replication
    versioning = typed.versioning
    owner_tag = typed.owner_tag
    cost_center_tag = typed.cost_center_tag
    restrict_network = typed.restrict_network
    allowed_ips = typed.allowed_ips

    backend_context: Optional[Dict[str, str]] = None
    if typed.backend:
        backend_context = typed.backend.model_dump()

    private_endpoint_payload = typed.private_endpoint or None
    private_endpoint_context: Optional[Dict[str, Any]] = None
    if private_endpoint_payload:
        pe_name = private_endpoint_payload.name or f"{sa_actual_name}-pe"
        private_endpoint_context = {
            "resource_name": _sanitize_identifier(pe_name, "pe"),
            "name": private_endpoint_payload.name,
            "connection_name": private_endpoint_payload.connection_name,
            "subnet_id": private_endpoint_payload.subnet_id,
            "private_dns_zone_id": private_endpoint_payload.private_dns_zone_id or None,
            "dns_zone_group_name": private_endpoint_payload.dns_zone_group_name or f"{sa_actual_name}-blob-zone",
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
