from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type, Union

from pydantic import BaseModel

from .models import AwsS3GeneratorPayload, AzureStorageGeneratorPayload
from .service import render_aws_s3_bucket, render_azure_storage_account


Payload = Union[BaseModel, Dict[str, Any]]
Renderer = Callable[[Payload], Dict[str, str]]


@dataclass(frozen=True)
class GeneratorDefinition:
    slug: str
    title: str
    description: str
    provider: str
    service: str
    compliance: List[str]
    tags: List[str]
    template_path: str
    outputs: List[Dict[str, Any]]
    requirements: List[str]
    model: Type[BaseModel]
    renderer: Renderer
    features: Dict[str, Any] = field(default_factory=dict)
    example_payload: Dict[str, Any] = field(default_factory=dict)

    def schema(self) -> Dict[str, Any]:
        return self.model.model_json_schema()

    def to_metadata(self) -> Dict[str, Any]:
        metadata = {
            "slug": self.slug,
            "title": self.title,
            "description": self.description,
            "provider": self.provider,
            "service": self.service,
            "compliance": self.compliance,
            "tags": self.tags,
            "template_path": self.template_path,
            "outputs": self.outputs,
            "requirements": self.requirements,
            "features": self.features,
            "schema": self.schema(),
            "example_payload": self.example_payload,
        }
        return metadata

    def render(self, payload: Payload) -> Dict[str, str]:
        return self.renderer(payload)


_REGISTRY: Dict[str, GeneratorDefinition] = {
    "aws/s3-secure-bucket": GeneratorDefinition(
        slug="aws/s3-secure-bucket",
        title="AWS S3 Secure Bucket",
        description=(
            "Provision an Amazon S3 bucket hardened with versioning, encryption defaults, "
            "public access blocking, and an optional remote state backend."
        ),
        provider="aws",
        service="s3",
        compliance=[
            "CIS AWS Foundations 2.1.1",
            "NIST SP 800-53 SC-13",
        ],
        tags=["storage", "encryption", "logging"],
        template_path="backend/generators/aws_s3_bucket.tf.j2",
        outputs=[],
        requirements=["hashicorp/aws >= 5.0"],
        model=AwsS3GeneratorPayload,
        renderer=render_aws_s3_bucket,
        features={
            "supports_remote_state": True,
            "enforces_secure_transport": True,
        },
        example_payload={
            "bucket_name": "platform-logs-prod",
            "environment": "prod",
            "owner_tag": "platform-team",
            "cost_center_tag": "ENG-SRE",
        },
    ),
    "azure/storage-secure-account": GeneratorDefinition(
        slug="azure/storage-secure-account",
        title="Azure Storage Account Baseline",
        description=(
            "Create an Azure Storage account with HTTPS-only access, optional firewall restrictions, "
            "blob versioning, and private endpoint scaffolding."
        ),
        provider="azure",
        service="storage",
        compliance=[
            "Azure Security Benchmark NS-1",
            "CIS Microsoft Azure Foundations 3.2",
        ],
        tags=["storage", "networking", "private-endpoint"],
        template_path="backend/generators/azure_storage_account.tf.j2",
        outputs=[
            {
                "name": "storage_private_endpoint_id",
                "description": "Resource ID of the private endpoint (emitted when private endpoints are enabled).",
                "conditional": True,
            }
        ],
        requirements=["hashicorp/azurerm >= 3.90"],
        model=AzureStorageGeneratorPayload,
        renderer=render_azure_storage_account,
        features={
            "supports_remote_state": True,
            "supports_private_endpoint": True,
        },
        example_payload={
            "resource_group_name": "rg-app",
            "storage_account_name": "stapp1234567890",
            "location": "eastus",
            "environment": "prod",
            "replication": "LRS",
        },
    ),
}


def list_generator_definitions() -> List[GeneratorDefinition]:
    return sorted(_REGISTRY.values(), key=lambda item: item.slug)


def list_generator_metadata() -> List[Dict[str, Any]]:
    return [definition.to_metadata() for definition in list_generator_definitions()]


def get_generator_definition(slug: str) -> GeneratorDefinition:
    try:
        return _REGISTRY[slug]
    except KeyError as exc:
        raise KeyError(f"Generator '{slug}' is not registered.") from exc


__all__ = [
    "GeneratorDefinition",
    "get_generator_definition",
    "list_generator_definitions",
    "list_generator_metadata",
]
