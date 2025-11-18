from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Callable, Dict, List, Type, Union

from pydantic import BaseModel

from .models import (
    AwsS3GeneratorPayload,
    AwsVpcGeneratorPayload,
    AwsEksGeneratorPayload,
    AwsRdsGeneratorPayload,
    AzureApiManagementGeneratorPayload,
    AzureFunctionAppGeneratorPayload,
    AzureServiceBusGeneratorPayload,
    AzureStorageGeneratorPayload,
)
from .service import (
    render_aws_s3_bucket,
    render_aws_vpc_networking,
    render_aws_eks_cluster,
    render_aws_rds_baseline,
    render_azure_api_management,
    render_azure_function_app,
    render_azure_servicebus_namespace,
    render_azure_storage_account,
)


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
    presets: List[Dict[str, Any]] = field(default_factory=list)

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
            "presets": self.presets,
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
    "aws/vpc-networking": GeneratorDefinition(
        slug="aws/vpc-networking",
        title="AWS VPC Networking Baseline",
        description=(
            "Provision a production-ready AWS VPC with public and private subnets, NAT gateway, "
            "Internet Gateway, VPC Flow Logs, and baseline security groups."
        ),
        provider="aws",
        service="vpc",
        compliance=[
            "CIS AWS Foundations 5.1",
            "CIS AWS Foundations 5.3",
            "NIST SP 800-53 AC-4",
        ],
        tags=["networking", "vpc", "flow-logs", "nat-gateway"],
        template_path="backend/generators/aws_vpc_networking.tf.j2",
        outputs=[],
        requirements=["hashicorp/aws >= 5.0"],
        model=AwsVpcGeneratorPayload,
        renderer=render_aws_vpc_networking,
        features={
            "supports_remote_state": True,
            "includes_flow_logs": True,
            "includes_nat_gateway": True,
        },
        example_payload={
            "name_prefix": "prod-vpc",
            "region": "us-east-1",
            "environment": "prod",
            "owner_tag": "platform-team",
            "cost_center_tag": "ENG-SRE",
            "vpc_cidr": "10.0.0.0/16",
            "public_subnet_cidr": "10.0.1.0/24",
            "public_subnet_az": "us-east-1a",
            "private_subnet_cidr": "10.0.2.0/24",
            "private_subnet_az": "us-east-1b",
            "flow_logs_retention_days": 90,
        },
    ),
    "aws/eks-cluster": GeneratorDefinition(
        slug="aws/eks-cluster",
        title="AWS EKS Cluster Baseline",
        description=(
            "Provision an Amazon EKS cluster with control plane logging, envelope encryption, "
            "private API endpoint, managed node group, and IAM roles following best practices."
        ),
        provider="aws",
        service="eks",
        compliance=[
            "CIS EKS Benchmark 3.2.1",
            "CIS EKS Benchmark 3.2.7",
            "NIST SP 800-53 SC-13",
        ],
        tags=["kubernetes", "container-orchestration", "eks", "encryption"],
        template_path="backend/generators/aws_eks_cluster.tf.j2",
        outputs=[],
        requirements=["hashicorp/aws >= 5.0"],
        model=AwsEksGeneratorPayload,
        renderer=render_aws_eks_cluster,
        features={
            "supports_remote_state": True,
            "supports_envelope_encryption": True,
            "includes_control_plane_logging": True,
            "includes_managed_node_group": True,
        },
        example_payload={
            "cluster_name": "prod-eks",
            "region": "us-east-1",
            "environment": "prod",
            "owner_tag": "platform-team",
            "cost_center_tag": "ENG-SRE",
            "vpc_id": "vpc-abc123",
            "private_subnet_ids": ["subnet-abc123", "subnet-def456"],
            "kubernetes_version": "1.28",
            "allow_public_api": False,
            "node_instance_type": "t3.medium",
            "node_desired_size": 2,
            "node_min_size": 2,
            "node_max_size": 4,
        },
    ),
    "aws/rds-baseline": GeneratorDefinition(
        slug="aws/rds-baseline",
        title="AWS RDS Instance Baseline",
        description=(
            "Provision an Amazon RDS instance with Multi-AZ, encryption at rest, automated backups, "
            "Performance Insights, and CloudWatch Logs integration."
        ),
        provider="aws",
        service="rds",
        compliance=[
            "CIS AWS Foundations 2.3.1",
            "NIST SP 800-53 SC-13",
            "NIST SP 800-53 CP-9",
        ],
        tags=["database", "rds", "multi-az", "encryption", "backup"],
        template_path="backend/generators/aws_rds_baseline.tf.j2",
        outputs=[],
        requirements=["hashicorp/aws >= 5.0"],
        model=AwsRdsGeneratorPayload,
        renderer=render_aws_rds_baseline,
        features={
            "supports_remote_state": True,
            "supports_multi_az": True,
            "includes_encryption": True,
            "includes_performance_insights": True,
        },
        example_payload={
            "db_identifier": "prod-db",
            "region": "us-east-1",
            "environment": "prod",
            "owner_tag": "platform-team",
            "cost_center_tag": "ENG-SRE",
            "subnet_ids": ["subnet-abc123", "subnet-def456"],
            "security_group_ids": ["sg-abc123"],
            "engine": "postgres",
            "engine_version": "15.4",
            "instance_class": "db.t3.micro",
            "allocated_storage": 20,
            "max_allocated_storage": 100,
            "multi_az": True,
            "backup_retention": 7,
            "db_name": "mydb",
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
    "azure/servicebus-namespace": GeneratorDefinition(
        slug="azure/servicebus-namespace",
        title="Azure Service Bus Namespace",
        description=(
            "Provision an Azure Service Bus namespace with managed identities, optional customer-managed keys, "
            "private endpoints, diagnostic settings, and queue/topic scaffolding."
        ),
        provider="azure",
        service="servicebus",
        compliance=[
            "Azure Security Benchmark DP-4",
            "CIS Microsoft Azure Foundations 4.5",
        ],
        tags=["messaging", "private-endpoint", "diagnostics"],
        template_path="backend/generators/azure_servicebus_namespace.tf.j2",
        outputs=[],
        requirements=["hashicorp/azurerm >= 3.90"],
        model=AzureServiceBusGeneratorPayload,
        renderer=render_azure_servicebus_namespace,
        features={
            "supports_private_endpoint": True,
            "supports_diagnostics": True,
        },
        example_payload={
            "resource_group_name": "rg-integration",
            "namespace_name": "sb-platform-prod",
            "location": "eastus2",
            "environment": "prod",
            "sku": "Premium",
            "queues": [
                {
                    "name": "orders",
                    "enable_partitioning": True,
                    "requires_duplicate_detection": True,
                    "duplicate_detection_history_time_window": "PT10M",
                },
                {"name": "deadletter"},
            ],
            "topics": [
                {
                    "name": "events",
                    "subscriptions": [
                        {
                            "name": "critical",
                            "requires_session": True,
                            "lock_duration": "PT2M",
                            "max_delivery_count": 20,
                        }
                    ],
                }
            ],
        },
        presets=[
            {
                "id": "ingress-fanout",
                "label": "Ingress queue + fan-out topic",
                "description": "Creates dedicated ingress and dead-letter queues alongside an events topic with a critical subscription.",
                "payload": {
                    "queues": [
                        {
                            "name": "ingress",
                            "enable_partitioning": True,
                            "requires_duplicate_detection": True,
                        },
                        {"name": "deadletter"},
                    ],
                    "topics": [
                        {
                            "name": "events",
                            "subscriptions": [
                                {
                                    "name": "critical",
                                    "requires_session": True,
                                    "lock_duration": "PT2M",
                                }
                            ],
                        }
                    ],
                },
            },
            {
                "id": "orders-retry",
                "label": "Orders queue with retry",
                "description": "Primary orders queue paired with a retry queue for poison message reprocessing.",
                "payload": {
                    "queues": [
                        {"name": "orders", "requires_duplicate_detection": True},
                        {"name": "orders-retry"},
                    ],
                    "topics": [],
                },
            },
        ],
    ),
    "azure/function-app": GeneratorDefinition(
        slug="azure/function-app",
        title="Azure Function App Baseline",
        description=(
            "Provision an Azure Linux Function App with managed identity, dedicated storage, Application Insights, "
            "and optional VNet integration and diagnostics."
        ),
        provider="azure",
        service="appservice",
        compliance=[
            "Azure Security Benchmark LT-1",
            "CIS Microsoft Azure Foundations 3.11",
        ],
        tags=["functions", "serverless", "observability"],
        template_path="backend/generators/azure_function_app.tf.j2",
        outputs=[
            {
                "name": "function_app_identity_principal_id",
                "description": "Managed identity principal ID for role assignments.",
                "conditional": False,
            }
        ],
        requirements=["hashicorp/azurerm >= 3.90"],
        model=AzureFunctionAppGeneratorPayload,
        renderer=render_azure_function_app,
        features={
            "supports_vnet_integration": True,
            "includes_application_insights": True,
        },
        example_payload={
            "resource_group_name": "rg-functions",
            "function_app_name": "func-app-prod",
            "storage_account_name": "stfuncprod",
            "app_service_plan_name": "plan-func-prod",
            "location": "eastus2",
            "environment": "prod",
            "runtime": "dotnet",
            "runtime_version": "8",
            "app_service_plan_sku": "EP1",
            "storage_replication": "LRS",
            "enable_vnet_integration": False,
            "enable_application_insights": True,
            "application_insights_name": "func-prod-ai",
            "owner_tag": "platform-team",
            "cost_center_tag": "ENG-SRE",
        },
        presets=[
            {
                "id": "http-api",
                "label": "HTTP API",
                "description": "Optimised for HTTP-triggered workloads using Elastic Premium and Application Insights.",
                "payload": {
                    "runtime": "dotnet",
                    "runtime_version": "8",
                    "app_service_plan_sku": "EP1",
                    "enable_vnet_integration": False,
                },
            },
            {
                "id": "queue-worker",
                "label": "Queue worker",
                "description": "Configures a Python worker suitable for Service Bus queue processing.",
                "payload": {
                    "runtime": "python",
                    "runtime_version": "3.11",
                    "app_service_plan_sku": "EP2",
                },
            },
        ],
    ),
    "azure/api-management": GeneratorDefinition(
        slug="azure/api-management",
        title="Azure API Management Premium Baseline",
        description=(
            "Deploy Azure API Management with managed identity, optional zone redundancy, diagnostics, and VNet integration."
        ),
        provider="azure",
        service="apim",
        compliance=[
            "Azure Security Benchmark NS-1",
            "CIS Microsoft Azure Foundations 6.4",
        ],
        tags=["gateway", "api", "security"],
        template_path="backend/generators/azure_api_management.tf.j2",
        outputs=[
            {
                "name": "api_management_gateway_url",
                "description": "Gateway URL for routing traffic through the service.",
                "conditional": False,
            }
        ],
        requirements=["hashicorp/azurerm >= 3.90"],
        model=AzureApiManagementGeneratorPayload,
        renderer=render_azure_api_management,
        features={
            "supports_private_networking": True,
            "supports_diagnostics": True,
        },
        example_payload={
            "resource_group_name": "rg-apim",
            "name": "apim-platform-prod",
            "location": "eastus2",
            "environment": "prod",
            "publisher_name": "Platform Team",
            "publisher_email": "platform@example.com",
            "sku_name": "Premium_1",
            "virtual_network_type": "None",
            "identity_type": "SystemAssigned",
            "owner_tag": "platform-team",
            "cost_center_tag": "ENG-SRE",
        },
        presets=[
            {
                "id": "internal-gateway",
                "label": "Internal gateway",
                "description": "Configures API Management for internal traffic via VNet integration.",
                "payload": {
                    "virtual_network_type": "Internal",
                },
            },
            {
                "id": "global-premium",
                "label": "Premium with zones",
                "description": "Premium tier with zone redundancy for production workloads.",
                "payload": {
                    "sku_name": "Premium_1",
                    "zones": ["1", "2", "3"],
                },
            },
        ],
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
