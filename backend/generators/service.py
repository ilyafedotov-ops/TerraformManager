from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Dict, Any, Union, List

from jinja2 import Template

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
AzureStoragePayloadLike = Union[AzureStorageGeneratorPayload, Dict[str, Any]]
AzureServiceBusPayloadLike = Union[AzureServiceBusGeneratorPayload, Dict[str, Any]]
AzureFunctionAppPayloadLike = Union[AzureFunctionAppGeneratorPayload, Dict[str, Any]]
AzureApiManagementPayloadLike = Union[AzureApiManagementGeneratorPayload, Dict[str, Any]]


def _ensure_aws_payload(payload: AwsPayloadLike) -> AwsS3GeneratorPayload:
    if isinstance(payload, AwsS3GeneratorPayload):
        return payload
    return AwsS3GeneratorPayload.model_validate(payload)


def _ensure_azure_storage_payload(payload: AzureStoragePayloadLike) -> AzureStorageGeneratorPayload:
    if isinstance(payload, AzureStorageGeneratorPayload):
        return payload
    return AzureStorageGeneratorPayload.model_validate(payload)


def _ensure_servicebus_payload(payload: AzureServiceBusPayloadLike) -> AzureServiceBusGeneratorPayload:
    if isinstance(payload, AzureServiceBusGeneratorPayload):
        return payload
    return AzureServiceBusGeneratorPayload.model_validate(payload)


def _ensure_function_app_payload(payload: AzureFunctionAppPayloadLike) -> AzureFunctionAppGeneratorPayload:
    if isinstance(payload, AzureFunctionAppGeneratorPayload):
        return payload
    return AzureFunctionAppGeneratorPayload.model_validate(payload)


def _ensure_api_management_payload(payload: AzureApiManagementPayloadLike) -> AzureApiManagementGeneratorPayload:
    if isinstance(payload, AzureApiManagementGeneratorPayload):
        return payload
    return AzureApiManagementGeneratorPayload.model_validate(payload)


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


def render_azure_storage_account(payload: AzureStoragePayloadLike) -> Dict[str, str]:
    typed = _ensure_azure_storage_payload(payload)

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


def render_azure_servicebus_namespace(payload: AzureServiceBusPayloadLike) -> Dict[str, str]:
    typed = _ensure_servicebus_payload(payload)

    rg_actual_name = typed.resource_group_name
    namespace_actual_name = typed.namespace_name
    location = typed.location
    environment = typed.environment
    sku = typed.sku
    capacity = typed.capacity
    zone_redundant = typed.zone_redundant
    owner_tag = typed.owner_tag
    cost_center_tag = typed.cost_center_tag
    restrict_network = typed.restrict_network

    backend_context: Optional[Dict[str, str]] = None
    if typed.backend:
        backend_context = typed.backend.model_dump()

    identity_context = typed.identity.model_dump()
    cmk_context = typed.customer_managed_key.model_dump() if typed.customer_managed_key else None

    private_endpoint_context: Optional[Dict[str, Any]] = None
    if typed.private_endpoint:
        private_endpoint_context = typed.private_endpoint.model_dump()
        group_ids = private_endpoint_context.pop("group_ids")
        private_dns_zones = private_endpoint_context.pop("private_dns_zone_ids")
        private_endpoint_context["group_ids_literal"] = "[" + ", ".join(f'"{gid}"' for gid in group_ids) + "]"
        private_endpoint_context["private_dns_zone_ids_literal"] = (
            "[" + ", ".join(f'"{zone}"' for zone in private_dns_zones) + "]" if private_dns_zones else "[]"
        )

    diagnostics_context: Optional[Dict[str, Any]] = None
    if typed.diagnostics:
        diagnostics_context = typed.diagnostics.model_dump()
        diagnostics_context["log_categories_literal"] = "[" + ", ".join(f'"{cat}"' for cat in diagnostics_context.pop("log_categories")) + "]"
        diagnostics_context["metric_categories_literal"] = "[" + ", ".join(f'"{cat}"' for cat in diagnostics_context.pop("metric_categories")) + "]"

    rg_name = _sanitize_identifier(rg_actual_name, "rg")
    namespace_name = _sanitize_identifier(namespace_actual_name, "namespace")

    queues_context: List[Dict[str, Any]] = []
    for queue in typed.queues:
        queues_context.append(
            {
                "resource_name": _sanitize_identifier(queue.name, "queue"),
                "name": queue.name,
                "enable_partitioning": queue.enable_partitioning,
                "lock_duration": queue.lock_duration,
                "max_delivery_count": queue.max_delivery_count,
                "requires_duplicate_detection": queue.requires_duplicate_detection,
                "duplicate_detection_history_time_window": queue.duplicate_detection_history_time_window,
            }
        )

    topics_context: List[Dict[str, Any]] = []
    for topic in typed.topics:
        topic_context = {
            "resource_name": _sanitize_identifier(topic.name, "topic"),
            "name": topic.name,
            "enable_partitioning": topic.enable_partitioning,
            "default_message_ttl": topic.default_message_ttl,
            "requires_duplicate_detection": topic.requires_duplicate_detection,
            "duplicate_detection_history_time_window": topic.duplicate_detection_history_time_window,
            "subscriptions": [],
        }
        for subscription in topic.subscriptions:
            subscription_context = {
                "resource_name": _sanitize_identifier(f"{topic.name}_{subscription.name}", "subscription"),
                "name": subscription.name,
                "requires_session": subscription.requires_session,
                "lock_duration": subscription.lock_duration,
                "max_delivery_count": subscription.max_delivery_count,
                "forward_to": subscription.forward_to,
            }
            topic_context["subscriptions"].append(subscription_context)
        topics_context.append(topic_context)

    template_path = BASE_DIR / "azure_servicebus_namespace.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        rg_name=rg_name,
        rg_actual_name=rg_actual_name,
        namespace_name=namespace_name,
        namespace_actual_name=namespace_actual_name,
        location=location,
        environment=environment,
        sku=sku,
        capacity=capacity,
        zone_redundant=zone_redundant,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        restrict_network=restrict_network,
        identity=identity_context,
        customer_managed_key=cmk_context,
        private_endpoint=private_endpoint_context,
        diagnostics=diagnostics_context,
        backend=backend_context,
        queues=queues_context,
        topics=topics_context,
    )

    filename = f"azure_servicebus_{namespace_name}.tf"
    return {"filename": filename, "content": content}


def render_azure_function_app(payload: AzureFunctionAppPayloadLike) -> Dict[str, str]:
    typed = _ensure_function_app_payload(payload)

    rg_actual_name = typed.resource_group_name
    function_actual_name = typed.function_app_name
    storage_actual_name = typed.storage_account_name
    plan_actual_name = typed.app_service_plan_name
    location = typed.location
    environment = typed.environment
    runtime = typed.runtime
    runtime_version = typed.runtime_version
    app_service_plan_sku = typed.app_service_plan_sku
    storage_replication = typed.storage_replication
    enable_vnet_integration = typed.enable_vnet_integration
    vnet_subnet_id = typed.vnet_subnet_id or ""
    enable_application_insights = typed.enable_application_insights
    application_insights_name = typed.application_insights_name
    owner_tag = typed.owner_tag
    cost_center_tag = typed.cost_center_tag

    rg_name = _sanitize_identifier(rg_actual_name, "rg")
    function_name = _sanitize_identifier(function_actual_name, "func")
    storage_name = _sanitize_identifier(storage_actual_name, "storage")
    plan_name = _sanitize_identifier(plan_actual_name, "plan")
    insights_name = _sanitize_identifier(application_insights_name, "insights")

    diagnostics_context: Optional[Dict[str, Any]] = None
    if typed.diagnostics:
        diag = typed.diagnostics
        diagnostics_context = {
            "workspace_resource_id": diag.workspace_resource_id,
            "log_categories_literal": "[" + ", ".join(f'"{item}"' for item in diag.log_categories) + "]",
            "metric_categories_literal": "[" + ", ".join(f'"{item}"' for item in diag.metric_categories) + "]",
        }

    application_stack: Dict[str, Optional[str]] = {
        "dotnet_version": None,
        "node_version": None,
        "python_version": None,
        "java_version": None,
    }
    runtime_lower = runtime.lower()
    if runtime_lower in {"dotnet", "dotnet-isolated"}:
        application_stack["dotnet_version"] = runtime_version
    elif runtime_lower in {"node", "nodejs"}:
        application_stack["node_version"] = runtime_version
    elif runtime_lower in {"python"}:
        application_stack["python_version"] = runtime_version
    elif runtime_lower in {"java"}:
        application_stack["java_version"] = runtime_version

    template_path = BASE_DIR / "azure_function_app.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        rg_name=rg_name,
        rg_actual_name=rg_actual_name,
        location=location,
        environment=environment,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        storage_name=storage_name,
        storage_actual_name=storage_actual_name,
        storage_replication=storage_replication,
        enable_application_insights=enable_application_insights,
        insights_name=insights_name,
        insights_actual_name=application_insights_name,
        plan_name=plan_name,
        plan_actual_name=plan_actual_name,
        app_service_plan_sku=app_service_plan_sku,
        function_name=function_name,
        function_actual_name=function_actual_name,
        runtime=runtime,
        application_stack=application_stack,
        enable_vnet_integration=enable_vnet_integration,
        vnet_subnet_id=vnet_subnet_id,
        diagnostics=diagnostics_context,
    )

    filename = f"azure_function_app_{function_name}.tf"
    return {"filename": filename, "content": content}


def render_azure_api_management(payload: AzureApiManagementPayloadLike) -> Dict[str, str]:
    typed = _ensure_api_management_payload(payload)

    rg_actual_name = typed.resource_group_name
    apim_actual_name = typed.name
    location = typed.location
    environment = typed.environment
    publisher_name = typed.publisher_name
    publisher_email = typed.publisher_email
    sku_name = typed.sku_name
    capacity = typed.capacity
    zones = typed.zones
    virtual_network_type = typed.virtual_network_type
    subnet_id = typed.subnet_id or ""
    identity_type = typed.identity_type
    custom_properties = typed.custom_properties or {}
    owner_tag = typed.owner_tag
    cost_center_tag = typed.cost_center_tag

    rg_name = _sanitize_identifier(rg_actual_name, "rg")
    apim_name = _sanitize_identifier(apim_actual_name, "apim")

    diagnostics_context: Optional[Dict[str, Any]] = None
    if typed.diagnostics:
        diag = typed.diagnostics
        diagnostics_context = {
            "workspace_resource_id": diag.workspace_resource_id,
            "log_categories_literal": "[" + ", ".join(f'"{item}"' for item in diag.log_categories) + "]",
            "metric_categories_literal": "[" + ", ".join(f'"{item}"' for item in diag.metric_categories) + "]",
        }

    zones_literal = ""
    if zones:
        zones_literal = "[" + ", ".join(f'"{zone}"' for zone in zones) + "]"

    template_path = BASE_DIR / "azure_api_management.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        rg_name=rg_name,
        rg_actual_name=rg_actual_name,
        location=location,
        environment=environment,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        apim_name=apim_name,
        apim_actual_name=apim_actual_name,
        publisher_name=publisher_name,
        publisher_email=publisher_email,
        sku_name=sku_name,
        capacity=capacity,
        zones_literal=zones_literal,
        virtual_network_type=virtual_network_type,
        subnet_id=subnet_id,
        identity_type=identity_type,
        custom_properties=custom_properties,
        diagnostics=diagnostics_context,
    )

    filename = f"azure_api_management_{apim_name}.tf"
    return {"filename": filename, "content": content}


AwsVpcPayloadLike = Union[AwsVpcGeneratorPayload, Dict[str, Any]]
AwsEksPayloadLike = Union[AwsEksGeneratorPayload, Dict[str, Any]]
AwsRdsPayloadLike = Union[AwsRdsGeneratorPayload, Dict[str, Any]]


def _ensure_vpc_payload(payload: AwsVpcPayloadLike) -> AwsVpcGeneratorPayload:
    if isinstance(payload, AwsVpcGeneratorPayload):
        return payload
    return AwsVpcGeneratorPayload.model_validate(payload)


def _ensure_eks_payload(payload: AwsEksPayloadLike) -> AwsEksGeneratorPayload:
    if isinstance(payload, AwsEksGeneratorPayload):
        return payload
    return AwsEksGeneratorPayload.model_validate(payload)


def _ensure_rds_payload(payload: AwsRdsPayloadLike) -> AwsRdsGeneratorPayload:
    if isinstance(payload, AwsRdsGeneratorPayload):
        return payload
    return AwsRdsGeneratorPayload.model_validate(payload)


def render_aws_vpc_networking(payload: AwsVpcPayloadLike) -> Dict[str, str]:
    typed = _ensure_vpc_payload(payload)

    name_prefix = typed.name_prefix
    region = typed.region
    environment = typed.environment
    owner_tag = typed.owner_tag
    cost_center_tag = typed.cost_center_tag
    vpc_cidr = typed.vpc_cidr
    public_subnet_cidr = typed.public_subnet_cidr
    public_subnet_az = typed.public_subnet_az
    private_subnet_cidr = typed.private_subnet_cidr
    private_subnet_az = typed.private_subnet_az
    flow_logs_retention_days = typed.flow_logs_retention_days

    vpc_name = _sanitize_identifier(name_prefix, "vpc")
    private_subnet_name = _sanitize_identifier(f"{name_prefix}_subnet", "subnet")

    backend_context: Optional[Dict[str, str]] = None
    if typed.backend:
        backend_context = typed.backend.model_dump()

    template_path = BASE_DIR / "aws_vpc_networking.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        region=region,
        environment=environment,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        name_prefix=name_prefix,
        vpc_name=vpc_name,
        vpc_cidr=vpc_cidr,
        private_subnet_name=private_subnet_name,
        public_subnet_cidr=public_subnet_cidr,
        public_subnet_az=public_subnet_az,
        private_subnet_cidr=private_subnet_cidr,
        private_subnet_az=private_subnet_az,
        flow_logs_retention_days=flow_logs_retention_days,
        backend=backend_context,
    )

    filename = f"aws_vpc_{vpc_name}.tf"
    return {"filename": filename, "content": content}


def render_aws_eks_cluster(payload: AwsEksPayloadLike) -> Dict[str, str]:
    typed = _ensure_eks_payload(payload)

    cluster_name = typed.cluster_name
    region = typed.region
    environment = typed.environment
    owner_tag = typed.owner_tag
    cost_center_tag = typed.cost_center_tag
    vpc_id = typed.vpc_id
    private_subnet_ids = typed.private_subnet_ids
    kubernetes_version = typed.kubernetes_version
    allow_public_api = typed.allow_public_api
    public_access_cidrs = typed.public_access_cidrs
    kms_key_arn = typed.kms_key_arn
    node_instance_type = typed.node_instance_type
    node_desired_size = typed.node_desired_size
    node_min_size = typed.node_min_size
    node_max_size = typed.node_max_size

    private_subnet_ids_literal = "[" + ", ".join(f'"{subnet_id}"' for subnet_id in private_subnet_ids) + "]"
    public_access_cidrs_literal = "[" + ", ".join(f'"{cidr}"' for cidr in public_access_cidrs) + "]"

    backend_context: Optional[Dict[str, str]] = None
    if typed.backend:
        backend_context = typed.backend.model_dump()

    template_path = BASE_DIR / "aws_eks_cluster.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        region=region,
        environment=environment,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        cluster_name=cluster_name,
        vpc_id=vpc_id,
        private_subnet_ids_literal=private_subnet_ids_literal,
        kubernetes_version=kubernetes_version,
        allow_public_api=allow_public_api,
        public_access_cidrs_literal=public_access_cidrs_literal,
        kms_key_arn=kms_key_arn,
        node_instance_type=node_instance_type,
        node_desired_size=node_desired_size,
        node_min_size=node_min_size,
        node_max_size=node_max_size,
        backend=backend_context,
    )

    filename = f"aws_eks_{cluster_name}.tf"
    return {"filename": filename, "content": content}


def render_aws_rds_baseline(payload: AwsRdsPayloadLike) -> Dict[str, str]:
    typed = _ensure_rds_payload(payload)

    db_identifier = typed.db_identifier
    region = typed.region
    environment = typed.environment
    owner_tag = typed.owner_tag
    cost_center_tag = typed.cost_center_tag
    subnet_ids = typed.subnet_ids
    security_group_ids = typed.security_group_ids
    engine = typed.engine
    engine_version = typed.engine_version
    instance_class = typed.instance_class
    allocated_storage = typed.allocated_storage
    max_allocated_storage = typed.max_allocated_storage
    multi_az = typed.multi_az
    backup_retention = typed.backup_retention
    backup_window = typed.backup_window
    preferred_maintenance_window = typed.preferred_maintenance_window
    db_name = typed.db_name
    kms_key_id = typed.kms_key_id
    logs_exports = typed.logs_exports

    subnet_group_name = _sanitize_identifier(f"{db_identifier}_subnet_group", "subnet_group")
    subnet_ids_literal = "[" + ", ".join(f'"{subnet_id}"' for subnet_id in subnet_ids) + "]"
    security_group_ids_literal = "[" + ", ".join(f'"{sg_id}"' for sg_id in security_group_ids) + "]"
    logs_exports_literal = "[" + ", ".join(f'"{log}"' for log in logs_exports) + "]"

    backend_context: Optional[Dict[str, str]] = None
    if typed.backend:
        backend_context = typed.backend.model_dump()

    template_path = BASE_DIR / "aws_rds_baseline.tf.j2"
    template = Template(template_path.read_text())
    content = template.render(
        region=region,
        environment=environment,
        owner_tag=owner_tag,
        cost_center_tag=cost_center_tag,
        db_identifier=db_identifier,
        subnet_group_name=subnet_group_name,
        subnet_ids_literal=subnet_ids_literal,
        security_group_ids_literal=security_group_ids_literal,
        engine=engine,
        engine_version=engine_version,
        instance_class=instance_class,
        allocated_storage=allocated_storage,
        max_allocated_storage=max_allocated_storage,
        multi_az=multi_az,
        backup_retention=backup_retention,
        backup_window=backup_window,
        preferred_maintenance_window=preferred_maintenance_window,
        db_name=db_name,
        kms_key_id=kms_key_id,
        logs_exports_literal=logs_exports_literal,
        backend=backend_context,
    )

    filename = f"aws_rds_{db_identifier}.tf"
    return {"filename": filename, "content": content}
