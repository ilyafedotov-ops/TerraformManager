from __future__ import annotations

import re
from typing import Any, Dict, List, Optional, Annotated, Literal, Union

from pydantic import BaseModel, Field, ValidationInfo, field_validator


_S3_BUCKET_PATTERN = re.compile(r"^[a-z0-9][a-z0-9\-.]{1,61}[a-z0-9]$")
_AZURE_STORAGE_PATTERN = re.compile(r"^[a-z0-9]{3,24}$")


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
        description="Toggle to enable network rules restricting public access.",
    )
    allowed_ips: List[str] = Field(
        default_factory=list,
        description="List of CIDR blocks allowed when network restrictions are enabled.",
        examples=[["10.0.0.0/24", "10.0.1.0/24"]],
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


__all__ = [
    "AwsS3BackendSettings",
    "AwsS3GeneratorPayload",
    "AzureStorageBackendSettings",
    "AzureStorageGeneratorPayload",
    "AzureStoragePrivateEndpointSettings",
    "BlueprintComponent",
    "BlueprintRemoteStateConfig",
    "BlueprintRemoteStateS3",
    "BlueprintRemoteStateAzure",
    "BlueprintRequest",
]
