from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Annotated, Literal, Union

from pydantic import BaseModel, Field, ValidationInfo, field_validator


_S3_BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-.]{1,61}[a-z0-9]$")
_AZURE_STORAGE_PATTERN = re.compile(r"^[a-z0-9]{3,24}$")
_AZURE_SERVICEBUS_NAMESPACE_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9-]{5,49}$")
_AZURE_SERVICEBUS_CHILD_NAME_PATTERN = re.compile(r"^[A-Za-z0-9-_.]{1,260}$")


def _strip_or_none(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    value = value.strip()
    return value or None


class AwsS3BackendSettings(BaseModel):
    bucket: str = Field(
        ...,
        description="Name of the existing S3 bucket that stores the Terraform state.",
        examples=["tfm-remote-state"],
    )
    key: str = Field(
        ...,
        description="Object key within the backend bucket (e.g. env/app.tfstate).",
        examples=["envs/prod/terraform.tfstate"],
    )
    region: str = Field(
        ...,
        description="AWS region where the remote state bucket and DynamoDB lock table reside.",
        examples=["us-east-1"],
    )
    dynamodb_table: str = Field(
        ...,
        description="DynamoDB table name used for state locking.",
        examples=["tfm-remote-locks"],
    )

    @field_validator("bucket")
    @classmethod
    def validate_bucket(cls, value: str) -> str:
        candidate = value.strip()
        if "{env}" in candidate:
            sample = candidate.replace("{env}", "prod")
            if not _S3_BUCKET_PATTERN.match(sample):
                raise ValueError(
                    "S3 backend bucket names must resolve to 3-63 lowercase characters (placeholders allowed via {env})."
                )
            return candidate.lower()
        candidate = candidate.lower()
        if not _S3_BUCKET_PATTERN.match(candidate):
            raise ValueError("S3 backend bucket names must be 3-63 characters, lowercase, and may include '-' or '.'.")
        return candidate

    @field_validator("key", "region", "dynamodb_table")
    @classmethod
    def strip_non_empty(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate


class AwsS3GeneratorPayload(BaseModel):
    bucket_name: str = Field(
        "my-secure-bucket",
        description="Name for the S3 bucket to provision.",
        min_length=3,
        max_length=63,
        examples=["platform-logs-prod"],
    )
    region: str = Field(
        "us-east-1",
        description="AWS region where resources will be created.",
        examples=["us-east-1", "us-west-2"],
    )
    environment: str = Field(
        "prod",
        description="Environment tag applied to all resources.",
        examples=["prod", "stage", "dev"],
    )
    owner_tag: str = Field(
        "platform-team",
        description="Owner tag value for traceability.",
        examples=["platform-team"],
    )
    cost_center_tag: str = Field(
        "ENG-SRE",
        description="Cost center tag value for chargeback or showback.",
        examples=["ENG-SRE"],
    )
    force_destroy: bool = Field(
        False,
        description="Permit bucket deletion even if objects remain (recommended only for non-prod).",
    )
    versioning: bool = Field(
        True,
        description="Enable bucket versioning for rollback and recovery support.",
    )
    enforce_secure_transport: bool = Field(
        True,
        description="Attach bucket policy enforcing TLS (aws:SecureTransport).",
    )
    kms_key_id: Optional[str] = Field(
        None,
        description="Optional KMS Key ARN for customer managed encryption.",
        examples=["arn:aws:kms:us-east-1:123456789012:key/abcd-1234"],
    )
    backend: Optional[AwsS3BackendSettings] = Field(
        None,
        description="Optional remote state backend configuration for Terraform.",
    )

    @field_validator("bucket_name", mode="before")
    @classmethod
    def normalize_bucket_name(cls, value: str) -> str:
        candidate = value.strip().lower()
        if not _S3_BUCKET_PATTERN.match(candidate):
            raise ValueError("Bucket name must be 3-63 characters, lowercase, and may include '-' or '.'.")
        return candidate

    @field_validator("environment", "owner_tag", "cost_center_tag", "region")
    @classmethod
    def ensure_non_empty(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("kms_key_id", mode="before")
    @classmethod
    def normalize_optional(cls, value: Optional[str]) -> Optional[str]:
        return _strip_or_none(value)


class AzureStorageBackendSettings(BaseModel):
    resource_group: str = Field(
        ...,
        description="Resource group that hosts the remote state storage account.",
        examples=["rg-terraform-state"],
    )
    storage_account: str = Field(
        ...,
        description="Storage account name that stores Terraform state.",
        examples=["ststate12345"],
    )
    container: str = Field(
        ...,
        description="Blob container containing Terraform state objects.",
        examples=["tfstate"],
    )
    key: str = Field(
        ...,
        description="Blob key within the container, typically env/app.tfstate.",
        examples=["prod/app.tfstate"],
    )

    @field_validator("resource_group", "container", "key")
    @classmethod
    def ensure_not_blank(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("storage_account")
    @classmethod
    def ensure_valid_storage_account(cls, value: str) -> str:
        candidate = value.strip().lower()
        if "{env}" in candidate:
            sample = candidate.replace("{env}", "prod")
            if not _AZURE_STORAGE_PATTERN.match(sample):
                raise ValueError(
                    "Storage account names must resolve to 3-24 lowercase alphanumeric characters (placeholders via {env})."
                )
            return candidate
        if not _AZURE_STORAGE_PATTERN.match(candidate):
            raise ValueError("Storage account names must be 3-24 characters, alphanumeric, and lowercase.")
        return candidate


class AzureStoragePrivateEndpointSettings(BaseModel):
    name: str = Field(
        ...,
        description="Name of the private endpoint resource.",
        examples=["stapp1234567890-pe"],
    )
    connection_name: str = Field(
        ...,
        description="Name assigned to the private link service connection.",
        examples=["stapp1234567890-blob"],
    )
    subnet_id: str = Field(
        ...,
        description="Resource ID of the subnet hosting the private endpoint.",
    )
    private_dns_zone_id: Optional[str] = Field(
        None,
        description="Optional Azure Private DNS zone ID for blob endpoint registration.",
    )
    dns_zone_group_name: Optional[str] = Field(
        None,
        description="Name for the private DNS zone group binding.",
        examples=["stapp1234567890-blob-zone"],
    )

    @field_validator("name", "connection_name", "subnet_id")
    @classmethod
    def ensure_not_empty(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("private_dns_zone_id", "dns_zone_group_name", mode="before")
    @classmethod
    def normalize_optional_str(cls, value: Optional[str]) -> Optional[str]:
        return _strip_or_none(value)


class AzureStorageGeneratorPayload(BaseModel):
    resource_group_name: str = Field(
        ...,
        description="Name of the resource group to create for the storage account.",
        examples=["rg-app"],
    )
    storage_account_name: str = Field(
        ...,
        description="Globally unique storage account name (lowercase, 3-24 chars).",
        examples=["stapp1234567890"],
    )
    location: str = Field(
        ...,
        description="Azure region (location) for the resources.",
        examples=["eastus"],
    )
    environment: str = Field(
        "prod",
        description="Environment tag applied to created resources.",
        examples=["prod", "stage", "dev"],
    )
    replication: str = Field(
        "LRS",
        description="Storage account replication setting (LRS, GRS, ZRS, etc.).",
        examples=["LRS", "GRS"],
    )
    versioning: bool = Field(
        True,
        description="Enable blob versioning.",
    )
    owner_tag: str = Field(
        "platform-team",
        description="Owner tag value for traceability.",
        examples=["platform-team"],
    )
    cost_center_tag: str = Field(
        "ENG-SRE",
        description="Cost center tag value for chargeback/showback.",
        examples=["ENG-SRE"],
    )
    restrict_network: bool = Field(
        False,
        description="Toggle to enable storage firewall rules restricting access to specific public IP ranges.",
    )
    allowed_ips: List[str] = Field(
        default_factory=list,
        description="List of public IP CIDR blocks allowed when storage firewall rules are enabled.",
        examples=[["52.160.0.0/24", "52.161.0.0/24"]],
    )
    private_endpoint: Optional[AzureStoragePrivateEndpointSettings] = Field(
        None,
        description="Optional configuration for a private endpoint targeting blob subresource.",
    )
    backend: Optional[AzureStorageBackendSettings] = Field(
        None,
        description="Optional remote state backend configuration.",
    )

    @field_validator("resource_group_name", "location", "environment", "owner_tag", "cost_center_tag", "replication")
    @classmethod
    def ensure_trimmed(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("storage_account_name", mode="before")
    @classmethod
    def validate_storage_account_name(cls, value: str) -> str:
        candidate = value.strip().lower()
        if not _AZURE_STORAGE_PATTERN.match(candidate):
            raise ValueError("Storage account names must be lowercase alphanumeric, 3-24 characters.")
        return candidate

    @field_validator("allowed_ips", mode="before")
    @classmethod
    def normalize_allowed_ips(cls, values: List[str]) -> List[str]:
        if not values:
            return []
        cleaned = []
        for entry in values:
            if not entry:
                continue
            candidate = entry.strip()
            if candidate:
                cleaned.append(candidate)
        return cleaned

    @field_validator("allowed_ips")
    @classmethod
    def validate_allowed_ips(cls, values: List[str], info: ValidationInfo) -> List[str]:
        restrict = bool(info.data.get("restrict_network"))
        if restrict and not values:
            raise ValueError("allowed_ips must include at least one CIDR when restrict_network is true.")
        return values


class AzureServiceBusQueueSettings(BaseModel):
    name: str = Field(
        ...,
        description="Queue name (1-260 characters, letters/numbers/hyphen/underscore/period).",
        examples=["orders"],
    )
    enable_partitioning: bool = Field(
        True,
        description="Enable partitioning to increase throughput.",
    )
    lock_duration: str = Field(
        "PT1M",
        description="ISO8601 duration for message lock (e.g., PT1M).",
    )
    max_delivery_count: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum delivery attempts before moving message to the dead-letter queue.",
    )
    requires_duplicate_detection: bool = Field(
        False,
        description="Enable duplicate detection for queue messages.",
    )
    duplicate_detection_history_time_window: str = Field(
        "PT10M",
        description="Window for duplicate detection (ISO8601 duration).",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        candidate = value.strip()
        if not _AZURE_SERVICEBUS_CHILD_NAME_PATTERN.match(candidate):
            raise ValueError(
                "Queue name must be 1-260 characters and may include letters, numbers, hyphen, underscore, or period."
            )
        return candidate


class AzureServiceBusSubscriptionSettings(BaseModel):
    name: str = Field(
        ...,
        description="Subscription name (1-260 characters).",
        examples=["critical"],
    )
    requires_session: bool = Field(
        False,
        description="Enable sessions for ordered message processing.",
    )
    lock_duration: str = Field(
        "PT1M",
        description="Message lock duration (ISO8601).",
    )
    max_delivery_count: int = Field(
        10,
        ge=1,
        le=100,
        description="Maximum delivery attempts before dead-lettering.",
    )
    forward_to: Optional[str] = Field(
        None,
        description="Optional queue or topic name for auto-forwarding.",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        candidate = value.strip()
        if not _AZURE_SERVICEBUS_CHILD_NAME_PATTERN.match(candidate):
            raise ValueError(
                "Subscription name must be 1-260 characters and may include letters, numbers, hyphen, underscore, or period."
            )
        return candidate

    @field_validator("forward_to")
    @classmethod
    def validate_forward_to(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        candidate = value.strip()
        if not _AZURE_SERVICEBUS_CHILD_NAME_PATTERN.match(candidate):
            raise ValueError("forward_to must match Azure Service Bus entity naming rules.")
        return candidate


class AzureServiceBusTopicSettings(BaseModel):
    name: str = Field(
        ...,
        description="Topic name (1-260 characters).",
        examples=["events"],
    )
    enable_partitioning: bool = Field(
        True,
        description="Enable partitioning for the topic.",
    )
    default_message_ttl: str = Field(
        "P7D",
        description="Default message time-to-live (ISO8601).",
    )
    subscriptions: List[AzureServiceBusSubscriptionSettings] = Field(
        default_factory=list,
        description="Subscriptions to provision for this topic.",
    )
    requires_duplicate_detection: bool = Field(
        False,
        description="Enable duplicate detection for the topic.",
    )
    duplicate_detection_history_time_window: str = Field(
        "PT10M",
        description="Window for duplicate detection (ISO8601 duration).",
    )

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        candidate = value.strip()
        if not _AZURE_SERVICEBUS_CHILD_NAME_PATTERN.match(candidate):
            raise ValueError(
                "Topic name must be 1-260 characters and may include letters, numbers, hyphen, underscore, or period."
            )
        return candidate


class AzureServiceBusPrivateEndpointSettings(BaseModel):
    name: str = Field(
        ...,
        description="Private endpoint resource name.",
        examples=["sb-namespace-pe"],
    )
    subnet_id: str = Field(
        ...,
        description="Subnet resource ID for the private endpoint.",
    )
    group_ids: List[str] = Field(
        default_factory=lambda: ["namespace"],
        description="Service Bus subresource group IDs (default: namespace).",
    )
    private_dns_zone_ids: List[str] = Field(
        default_factory=list,
        description="Optional private DNS zone resource IDs.",
    )

    @field_validator("name")
    @classmethod
    def ensure_name(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("name cannot be empty.")
        return candidate

    @field_validator("group_ids", "private_dns_zone_ids")
    @classmethod
    def clean_list(cls, values: List[str]) -> List[str]:
        cleaned = []
        for entry in values or []:
            candidate = (entry or "").strip()
            if candidate:
                cleaned.append(candidate)
        return cleaned


class AzureServiceBusDiagnosticSettings(BaseModel):
    workspace_resource_id: str = Field(
        ...,
        description="Log Analytics workspace resource ID.",
    )
    log_categories: List[str] = Field(
        default_factory=lambda: ["OperationalLogs"],
        description="Log categories to enable (defaults to OperationalLogs).",
    )
    metric_categories: List[str] = Field(
        default_factory=lambda: ["AllMetrics"],
        description="Metric categories to emit (defaults to AllMetrics).",
    )

    @field_validator("workspace_resource_id")
    @classmethod
    def ensure_workspace(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("workspace_resource_id cannot be empty.")
        return candidate

    @field_validator("log_categories", "metric_categories")
    @classmethod
    def clean_categories(cls, values: List[str]) -> List[str]:
        cleaned = []
        for entry in values or []:
            candidate = (entry or "").strip()
            if candidate:
                cleaned.append(candidate)
        return cleaned


class AzureServiceBusIdentitySettings(BaseModel):
    type: Literal["SystemAssigned", "UserAssigned", "SystemAssigned, UserAssigned"] = Field(
        "SystemAssigned",
        description="Managed identity type.",
    )
    user_assigned_identity_ids: List[str] = Field(
        default_factory=list,
        description="User-assigned identity resource IDs when using user-assigned identities.",
    )

    @field_validator("user_assigned_identity_ids")
    @classmethod
    def clean_id_list(cls, values: List[str]) -> List[str]:
        cleaned = []
        for entry in values or []:
            candidate = (entry or "").strip()
            if candidate:
                cleaned.append(candidate)
        return cleaned

    @field_validator("type")
    @classmethod
    def validate_type(cls, value: str, info: ValidationInfo) -> str:
        normalized = value.strip()
        if normalized in {"UserAssigned", "SystemAssigned, UserAssigned"} and not info.data.get("user_assigned_identity_ids"):
            raise ValueError("user_assigned_identity_ids must be provided when using user-assigned identities.")
        return normalized


class AzureServiceBusCustomerManagedKeySettings(BaseModel):
    key_vault_key_id: str = Field(
        ...,
        description="Key Vault key ID for customer-managed key encryption.",
    )
    user_assigned_identity_id: Optional[str] = Field(
        None,
        description="Identity ID that has access to the Key Vault key.",
    )

    @field_validator("key_vault_key_id")
    @classmethod
    def ensure_key(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("key_vault_key_id cannot be empty.")
        return candidate

    @field_validator("user_assigned_identity_id")
    @classmethod
    def normalize_identity(cls, value: Optional[str]) -> Optional[str]:
        if value is None:
            return None
        candidate = value.strip()
        if not candidate:
            raise ValueError("user_assigned_identity_id cannot be empty when provided.")
        return candidate


class AzureServiceBusGeneratorPayload(BaseModel):
    resource_group_name: str = Field(
        ...,
        description="Resource group that will host the namespace.",
        examples=["rg-integration"],
    )
    namespace_name: str = Field(
        ...,
        description="Service Bus namespace name (6-50 chars, letters/numbers/hyphen).",
        examples=["sb-platform-dev"],
    )
    location: str = Field(
        ...,
        description="Azure region for the namespace.",
        examples=["eastus2"],
    )
    environment: str = Field(
        "prod",
        description="Environment tag applied to created resources.",
        examples=["dev", "test", "prod"],
    )
    sku: str = Field(
        "Premium",
        description="Service Bus SKU (Basic, Standard, Premium).",
        examples=["Premium"],
    )
    capacity: Optional[int] = Field(
        None,
        description="Optional messaging units (required for Premium availability zones).",
    )
    zone_redundant: bool = Field(
        True,
        description="Enable zone redundancy where supported.",
    )
    owner_tag: str = Field(
        "platform-team",
        description="Owner tag value for traceability.",
        examples=["platform-team"],
    )
    cost_center_tag: str = Field(
        "ENG-SRE",
        description="Cost center tag value for showback/chargeback.",
        examples=["ENG-SRE"],
    )
    restrict_network: bool = Field(
        True,
        description="Disable public network access and rely on private endpoints.",
    )
    identity: AzureServiceBusIdentitySettings = Field(
        default_factory=AzureServiceBusIdentitySettings,
        description="Managed identity configuration.",
    )
    customer_managed_key: Optional[AzureServiceBusCustomerManagedKeySettings] = Field(
        None,
        description="Optional customer-managed key configuration.",
    )
    private_endpoint: Optional[AzureServiceBusPrivateEndpointSettings] = Field(
        None,
        description="Optional private endpoint configuration.",
    )
    diagnostics: Optional[AzureServiceBusDiagnosticSettings] = Field(
        None,
        description="Optional diagnostic settings forwarding logs to Log Analytics.",
    )
    queues: List[AzureServiceBusQueueSettings] = Field(
        default_factory=list,
        description="Queues to create inside the namespace.",
    )
    topics: List[AzureServiceBusTopicSettings] = Field(
        default_factory=list,
        description="Topics (and optional subscriptions) to create inside the namespace.",
    )
    backend: Optional[AzureStorageBackendSettings] = Field(
        None,
        description="Optional remote state backend configuration.",
    )

    @field_validator("resource_group_name", "location", "environment", "owner_tag", "cost_center_tag", "sku")
    @classmethod
    def ensure_trimmed(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("namespace_name", mode="before")
    @classmethod
    def validate_namespace_name(cls, value: str) -> str:
        candidate = value.strip()
        if not _AZURE_SERVICEBUS_NAMESPACE_PATTERN.match(candidate):
            raise ValueError(
                "Namespace name must be 6-50 characters, start with a letter, and may contain letters, numbers, or hyphen."
            )
        return candidate

    @field_validator("capacity")
    @classmethod
    def validate_capacity(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value < 1:
            raise ValueError("capacity must be a positive integer when provided.")
        return value


class AzureFunctionAppDiagnosticsSettings(BaseModel):
    workspace_resource_id: str = Field(
        ...,
        description="Log Analytics workspace to receive Function App diagnostics.",
    )
    log_categories: List[str] = Field(
        default_factory=lambda: ["FunctionAppLogs"],
        description="Diagnostic log categories.",
    )
    metric_categories: List[str] = Field(
        default_factory=lambda: ["AllMetrics"],
        description="Diagnostic metric categories.",
    )

    @field_validator("workspace_resource_id")
    @classmethod
    def ensure_workspace(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("workspace_resource_id cannot be empty.")
        return candidate

    @field_validator("log_categories", "metric_categories")
    @classmethod
    def clean_categories(cls, values: List[str]) -> List[str]:
        cleaned = []
        for entry in values or []:
            candidate = (entry or "").strip()
            if candidate:
                cleaned.append(candidate)
        return cleaned


class AzureFunctionAppGeneratorPayload(BaseModel):
    resource_group_name: str = Field(..., description="Resource group for the Function App.")
    function_app_name: str = Field(..., description="Function App name (globally unique).")
    storage_account_name: str = Field(..., description="Storage account for Function runtime artifacts.")
    app_service_plan_name: str = Field(..., description="App Service plan name backing the Function App.")
    location: str = Field(..., description="Azure region.")
    environment: str = Field("prod", description="Environment tag applied to all resources.")
    runtime: str = Field("dotnet", description="Functions worker runtime (dotnet, node, python).")
    runtime_version: str = Field("8", description="Runtime version (e.g. 8, 20, 3.11).")
    app_service_plan_sku: str = Field("EP1", description="App Service plan SKU (e.g. EP1, P1v3).")
    storage_replication: str = Field("LRS", description="Storage account replication.")
    enable_vnet_integration: bool = Field(False, description="Enable VNet integration for outbound traffic.")
    vnet_subnet_id: Optional[str] = Field(
        None,
        description="Subnet resource ID used for VNet integration (required when enable_vnet_integration is true).",
    )
    enable_application_insights: bool = Field(True, description="Provision Application Insights for telemetry.")
    application_insights_name: str = Field(
        "func-ai",
        description="Application Insights component name (used when enable_application_insights is true).",
    )
    diagnostics: Optional[AzureFunctionAppDiagnosticsSettings] = Field(
        None,
        description="Optional diagnostic settings forwarding logs/metrics to Log Analytics.",
    )
    owner_tag: str = Field("platform-team", description="Owner tag value.")
    cost_center_tag: str = Field("ENG-SRE", description="Cost center tag value.")

    @field_validator(
        "resource_group_name",
        "function_app_name",
        "storage_account_name",
        "app_service_plan_name",
        "location",
        "environment",
        "runtime",
        "runtime_version",
        "app_service_plan_sku",
        "storage_replication",
        "application_insights_name",
        "owner_tag",
        "cost_center_tag",
    )
    @classmethod
    def ensure_trimmed(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("storage_account_name", mode="before")
    @classmethod
    def validate_storage_name(cls, value: str) -> str:
        candidate = value.strip().lower()
        if not _AZURE_STORAGE_PATTERN.match(candidate):
            raise ValueError("Storage account names must be lowercase alphanumeric, 3-24 characters.")
        return candidate

    @field_validator("function_app_name")
    @classmethod
    def validate_function_name(cls, value: str) -> str:
        candidate = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9\-]{2,60}", candidate):
            raise ValueError("Function App name must be 2-60 characters and alphanumeric with optional hyphen.")
        return candidate

    @field_validator("vnet_subnet_id")
    @classmethod
    def validate_subnet(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        if info.data.get("enable_vnet_integration") and not (value or "").strip():
            raise ValueError("vnet_subnet_id is required when enable_vnet_integration is true.")
        return value.strip() if value else None


class AzureApiManagementDiagnostics(BaseModel):
    workspace_resource_id: str = Field(
        ...,
        description="Log Analytics workspace resource ID for diagnostics.",
    )
    log_categories: List[str] = Field(
        default_factory=lambda: ["GatewayLogs"],
        description="Diagnostic log categories.",
    )
    metric_categories: List[str] = Field(
        default_factory=lambda: ["AllMetrics"],
        description="Diagnostic metric categories.",
    )

    @field_validator("workspace_resource_id")
    @classmethod
    def ensure_workspace(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("workspace_resource_id cannot be empty.")
        return candidate

    @field_validator("log_categories", "metric_categories")
    @classmethod
    def clean_categories(cls, values: List[str]) -> List[str]:
        cleaned = []
        for entry in values or []:
            candidate = (entry or "").strip()
            if candidate:
                cleaned.append(candidate)
        return cleaned


class AzureApiManagementGeneratorPayload(BaseModel):
    resource_group_name: str = Field(..., description="Resource group for API Management.")
    name: str = Field(..., description="API Management service name.")
    location: str = Field(..., description="Azure region.")
    environment: str = Field("prod", description="Environment tag applied to resources.")
    publisher_name: str = Field(..., description="Publisher display name.")
    publisher_email: str = Field(..., description="Publisher contact email.")
    sku_name: str = Field("Premium_1", description="API Management SKU (e.g., Developer_1, Premium_1).")
    capacity: Optional[int] = Field(None, description="Optional capacity override (Premium/Isolated tiers).")
    zones: List[str] = Field(default_factory=list, description="Optional availability zones (Premium tier).")
    virtual_network_type: str = Field(
        "None",
        description="Virtual network type (None, External, Internal).",
    )
    subnet_id: Optional[str] = Field(
        None,
        description="Subnet resource ID required when virtual_network_type != None.",
    )
    identity_type: Literal["SystemAssigned", "UserAssigned", "SystemAssigned, UserAssigned"] = Field(
        "SystemAssigned",
        description="Managed identity configuration.",
    )
    custom_properties: Dict[str, str] = Field(
        default_factory=dict,
        description="Optional custom properties applied to the service.",
    )
    diagnostics: Optional[AzureApiManagementDiagnostics] = Field(
        None,
        description="Optional diagnostic settings streaming to Log Analytics.",
    )
    owner_tag: str = Field("platform-team", description="Owner tag value.")
    cost_center_tag: str = Field("ENG-SRE", description="Cost center tag value.")

    @field_validator(
        "resource_group_name",
        "name",
        "location",
        "environment",
        "publisher_name",
        "publisher_email",
        "sku_name",
        "owner_tag",
        "cost_center_tag",
    )
    @classmethod
    def ensure_trimmed(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("publisher_email")
    @classmethod
    def validate_email(cls, value: str) -> str:
        candidate = value.strip()
        if "@" not in candidate:
            raise ValueError("publisher_email must be a valid email address.")
        return candidate

    @field_validator("name")
    @classmethod
    def validate_apim_name(cls, value: str) -> str:
        candidate = value.strip()
        if not re.fullmatch(r"[A-Za-z0-9\-]{2,50}", candidate):
            raise ValueError("API Management name must be 2-50 characters and alphanumeric with optional hyphen.")
        return candidate

    @field_validator("capacity")
    @classmethod
    def validate_capacity(cls, value: Optional[int]) -> Optional[int]:
        if value is None:
            return None
        if value < 1:
            raise ValueError("capacity must be at least 1 when provided.")
        return value

    @field_validator("zones", mode="before")
    @classmethod
    def clean_zones(cls, values: List[str]) -> List[str]:
        if not values:
            return []
        cleaned = []
        for entry in values:
            if entry:
                cleaned.append(entry.strip())
        return cleaned

    @field_validator("subnet_id")
    @classmethod
    def validate_subnet(cls, value: Optional[str], info: ValidationInfo) -> Optional[str]:
        vnet_type = info.data.get("virtual_network_type", "None")
        if vnet_type.lower() != "none" and not (value or "").strip():
            raise ValueError("subnet_id is required when virtual_network_type is External or Internal.")
        return value.strip() if value else None


class BlueprintComponent(BaseModel):
    slug: str = Field(..., description="Registered generator slug (e.g., aws/s3-secure-bucket).")
    payload: Dict[str, Any] = Field(default_factory=dict, description="Generator payload (supports {env} placeholders).")
    target_subdir: Optional[str] = Field(
        None,
        description="Optional nested folder under each environment to place rendered files.",
    )

    @field_validator("slug")
    @classmethod
    def ensure_slug_not_empty(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("slug cannot be empty.")
        return candidate


class _BlueprintRemoteStateBase(BaseModel):
    type: Literal["aws_s3", "azurerm"]


class BlueprintRemoteStateS3(_BlueprintRemoteStateBase):
    type: Literal["aws_s3"] = "aws_s3"
    default: AwsS3BackendSettings
    overrides: Dict[str, AwsS3BackendSettings] = Field(default_factory=dict)

    def resolve(self, environment: str) -> AwsS3BackendSettings:
        return self.overrides.get(environment, self.default)


class BlueprintRemoteStateAzure(_BlueprintRemoteStateBase):
    type: Literal["azurerm"] = "azurerm"
    default: AzureStorageBackendSettings
    overrides: Dict[str, AzureStorageBackendSettings] = Field(default_factory=dict)

    def resolve(self, environment: str) -> AzureStorageBackendSettings:
        return self.overrides.get(environment, self.default)


BlueprintRemoteStateConfig = Annotated[
    Union[BlueprintRemoteStateS3, BlueprintRemoteStateAzure],
    Field(discriminator="type"),
]


class BlueprintRequest(BaseModel):
    name: str = Field(..., description="Human-friendly blueprint name (used for archive naming).")
    environments: List[str] = Field(
        default_factory=lambda: ["prod"],
        description="List of environment identifiers to generate (e.g., dev, stage, prod).",
    )
    components: List[BlueprintComponent] = Field(..., min_length=1, description="Collection of generator components.")
    remote_state: Optional[BlueprintRemoteStateConfig] = Field(
        None,
        description="Optional remote state backend configuration applied per environment.",
    )
    include_readme: bool = Field(True, description="Emit a README summarizing the blueprint.")
    include_variables_stub: bool = Field(
        True,
        description="Generate environment-specific variables stub files.",
    )

    @field_validator("name")
    @classmethod
    def ensure_name(cls, value: str) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError("name cannot be empty.")
        return candidate

    @field_validator("environments", mode="before")
    @classmethod
    def default_environments(cls, value: Optional[List[str]]) -> List[str]:
        if not value:
            return ["prod"]
        return value

    @field_validator("environments")
    @classmethod
    def validate_environments(cls, environments: List[str]) -> List[str]:
        cleaned = []
        for env in environments:
            candidate = (env or "").strip()
            if not candidate:
                raise ValueError("environment names cannot be empty.")
            cleaned.append(candidate)
        return cleaned


class AwsVpcGeneratorPayload(BaseModel):
    name_prefix: str = Field(
        ...,
        description="Prefix for all resource names (VPC, subnets, etc.).",
        examples=["prod-vpc"],
    )
    region: str = Field(
        "us-east-1",
        description="AWS region where resources will be created.",
        examples=["us-east-1", "us-west-2"],
    )
    environment: str = Field(
        "prod",
        description="Environment tag applied to all resources.",
        examples=["prod", "stage", "dev"],
    )
    owner_tag: str = Field(
        "platform-team",
        description="Owner tag value for traceability.",
        examples=["platform-team"],
    )
    cost_center_tag: str = Field(
        "ENG-SRE",
        description="Cost center tag value for chargeback or showback.",
        examples=["ENG-SRE"],
    )
    vpc_cidr: str = Field(
        "10.0.0.0/16",
        description="CIDR block for the VPC.",
        examples=["10.0.0.0/16", "172.16.0.0/16"],
    )
    public_subnet_cidr: str = Field(
        "10.0.1.0/24",
        description="CIDR block for the public subnet.",
        examples=["10.0.1.0/24"],
    )
    public_subnet_az: str = Field(
        "us-east-1a",
        description="Availability zone for the public subnet.",
        examples=["us-east-1a", "us-west-2a"],
    )
    private_subnet_cidr: str = Field(
        "10.0.2.0/24",
        description="CIDR block for the private subnet.",
        examples=["10.0.2.0/24"],
    )
    private_subnet_az: str = Field(
        "us-east-1b",
        description="Availability zone for the private subnet.",
        examples=["us-east-1b", "us-west-2b"],
    )
    flow_logs_retention_days: int = Field(
        90,
        ge=1,
        le=365,
        description="CloudWatch Logs retention period for VPC Flow Logs.",
    )
    backend: Optional[AwsS3BackendSettings] = Field(
        None,
        description="Optional remote state backend configuration for Terraform.",
    )

    @field_validator("name_prefix", "environment", "owner_tag", "cost_center_tag", "region")
    @classmethod
    def ensure_non_empty(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate


class AwsEksGeneratorPayload(BaseModel):
    cluster_name: str = Field(
        ...,
        description="Name for the EKS cluster.",
        examples=["prod-eks"],
    )
    region: str = Field(
        "us-east-1",
        description="AWS region where resources will be created.",
        examples=["us-east-1", "us-west-2"],
    )
    environment: str = Field(
        "prod",
        description="Environment tag applied to all resources.",
        examples=["prod", "stage", "dev"],
    )
    owner_tag: str = Field(
        "platform-team",
        description="Owner tag value for traceability.",
        examples=["platform-team"],
    )
    cost_center_tag: str = Field(
        "ENG-SRE",
        description="Cost center tag value for chargeback or showback.",
        examples=["ENG-SRE"],
    )
    vpc_id: str = Field(
        ...,
        description="VPC ID where the EKS cluster will be deployed.",
        examples=["vpc-abc123"],
    )
    private_subnet_ids: List[str] = Field(
        ...,
        description="List of private subnet IDs for the EKS cluster.",
        examples=[["subnet-abc123", "subnet-def456"]],
    )
    kubernetes_version: str = Field(
        "1.28",
        description="Kubernetes version for the EKS cluster.",
        examples=["1.28", "1.29"],
    )
    allow_public_api: bool = Field(
        False,
        description="Allow public access to the EKS API server endpoint.",
    )
    public_access_cidrs: List[str] = Field(
        default_factory=lambda: ["0.0.0.0/0"],
        description="CIDR blocks allowed to access the public API endpoint (if enabled).",
        examples=[["203.0.113.0/24", "198.51.100.0/24"]],
    )
    kms_key_arn: Optional[str] = Field(
        None,
        description="Optional KMS Key ARN for envelope encryption of Kubernetes secrets.",
        examples=["arn:aws:kms:us-east-1:123456789012:key/abcd-1234"],
    )
    node_instance_type: str = Field(
        "t3.medium",
        description="EC2 instance type for EKS managed node group.",
        examples=["t3.medium", "m5.large"],
    )
    node_desired_size: int = Field(
        2,
        ge=1,
        le=10,
        description="Desired number of nodes in the managed node group.",
    )
    node_min_size: int = Field(
        2,
        ge=1,
        le=10,
        description="Minimum number of nodes in the managed node group.",
    )
    node_max_size: int = Field(
        4,
        ge=1,
        le=20,
        description="Maximum number of nodes in the managed node group.",
    )
    backend: Optional[AwsS3BackendSettings] = Field(
        None,
        description="Optional remote state backend configuration for Terraform.",
    )

    @field_validator("cluster_name", "environment", "owner_tag", "cost_center_tag", "region", "vpc_id")
    @classmethod
    def ensure_non_empty(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("private_subnet_ids")
    @classmethod
    def ensure_subnet_ids(cls, values: List[str]) -> List[str]:
        if not values:
            raise ValueError("At least one private subnet ID is required.")
        cleaned = [v.strip() for v in values if v.strip()]
        if not cleaned:
            raise ValueError("private_subnet_ids cannot be empty.")
        return cleaned


class AwsRdsGeneratorPayload(BaseModel):
    db_identifier: str = Field(
        ...,
        description="Identifier for the RDS instance.",
        examples=["prod-db"],
    )
    region: str = Field(
        "us-east-1",
        description="AWS region where resources will be created.",
        examples=["us-east-1", "us-west-2"],
    )
    environment: str = Field(
        "prod",
        description="Environment tag applied to all resources.",
        examples=["prod", "stage", "dev"],
    )
    owner_tag: str = Field(
        "platform-team",
        description="Owner tag value for traceability.",
        examples=["platform-team"],
    )
    cost_center_tag: str = Field(
        "ENG-SRE",
        description="Cost center tag value for chargeback or showback.",
        examples=["ENG-SRE"],
    )
    subnet_ids: List[str] = Field(
        ...,
        description="List of subnet IDs for the DB subnet group.",
        examples=[["subnet-abc123", "subnet-def456"]],
    )
    security_group_ids: List[str] = Field(
        ...,
        description="List of security group IDs for the RDS instance.",
        examples=[["sg-abc123"]],
    )
    engine: str = Field(
        "postgres",
        description="Database engine (postgres, mysql, mariadb, oracle-ee, sqlserver-ex).",
        examples=["postgres", "mysql"],
    )
    engine_version: str = Field(
        "15.4",
        description="Database engine version.",
        examples=["15.4", "8.0.35"],
    )
    instance_class: str = Field(
        "db.t3.micro",
        description="RDS instance class.",
        examples=["db.t3.micro", "db.r6i.large"],
    )
    allocated_storage: int = Field(
        20,
        ge=20,
        le=65536,
        description="Initial allocated storage in GB.",
    )
    max_allocated_storage: int = Field(
        100,
        ge=20,
        le=65536,
        description="Maximum storage for autoscaling in GB.",
    )
    multi_az: bool = Field(
        True,
        description="Enable Multi-AZ deployment for high availability.",
    )
    backup_retention: int = Field(
        7,
        ge=1,
        le=35,
        description="Automated backup retention period in days.",
    )
    backup_window: str = Field(
        "03:00-04:00",
        description="Daily backup window (UTC).",
        examples=["03:00-04:00"],
    )
    preferred_maintenance_window: str = Field(
        "sun:04:00-sun:05:00",
        description="Weekly maintenance window (UTC).",
        examples=["sun:04:00-sun:05:00"],
    )
    db_name: str = Field(
        "mydb",
        description="Initial database name.",
        examples=["mydb", "appdb"],
    )
    kms_key_id: Optional[str] = Field(
        None,
        description="Optional KMS Key ARN for RDS encryption.",
        examples=["arn:aws:kms:us-east-1:123456789012:key/abcd-1234"],
    )
    logs_exports: List[str] = Field(
        default_factory=lambda: ["postgresql"],
        description="CloudWatch Logs exports (engine-specific).",
        examples=[["postgresql"], ["error", "general", "slowquery"]],
    )
    backend: Optional[AwsS3BackendSettings] = Field(
        None,
        description="Optional remote state backend configuration for Terraform.",
    )

    @field_validator("db_identifier", "environment", "owner_tag", "cost_center_tag", "region", "engine", "db_name")
    @classmethod
    def ensure_non_empty(cls, value: str, info: ValidationInfo) -> str:
        candidate = value.strip()
        if not candidate:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return candidate

    @field_validator("subnet_ids", "security_group_ids")
    @classmethod
    def ensure_ids(cls, values: List[str], info: ValidationInfo) -> List[str]:
        if not values:
            raise ValueError(f"{info.field_name} must include at least one ID.")
        cleaned = [v.strip() for v in values if v.strip()]
        if not cleaned:
            raise ValueError(f"{info.field_name} cannot be empty.")
        return cleaned


__all__ = [
    "AwsS3BackendSettings",
    "AwsS3GeneratorPayload",
    "AwsVpcGeneratorPayload",
    "AwsEksGeneratorPayload",
    "AwsRdsGeneratorPayload",
    "AzureStorageBackendSettings",
    "AzureStorageGeneratorPayload",
    "AzureServiceBusQueueSettings",
    "AzureServiceBusSubscriptionSettings",
    "AzureServiceBusTopicSettings",
    "AzureServiceBusPrivateEndpointSettings",
    "AzureServiceBusDiagnosticSettings",
    "AzureServiceBusIdentitySettings",
    "AzureServiceBusCustomerManagedKeySettings",
    "AzureServiceBusGeneratorPayload",
    "AzureFunctionAppDiagnosticsSettings",
    "AzureFunctionAppGeneratorPayload",
    "AzureApiManagementDiagnostics",
    "AzureApiManagementGeneratorPayload",
    "AzureStoragePrivateEndpointSettings",
    "BlueprintComponent",
    "BlueprintRemoteStateConfig",
    "BlueprintRemoteStateS3",
    "BlueprintRemoteStateAzure",
    "BlueprintRequest",
]
