from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, ConfigDict
from typing_extensions import Annotated


class LocalBackendConfig(BaseModel):
    """Configuration for reading a state file from the local filesystem."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["local"] = "local"
    path: str = Field(..., description="Absolute or project-relative path to the terraform.tfstate file.")


class S3BackendConfig(BaseModel):
    """Configuration for retrieving state from an S3 backend."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["s3"] = "s3"
    bucket: str = Field(..., description="S3 bucket that stores the Terraform state file.")
    key: str = Field(..., description="Object key within the S3 bucket.")
    region: Optional[str] = Field(None, description="AWS region containing the state bucket.")
    profile: Optional[str] = Field(None, description="AWS named profile to use for authentication.")
    endpoint_url: Optional[str] = Field(None, description="Custom S3-compatible endpoint URL (e.g., MinIO).")
    session_token: Optional[str] = Field(None, description="Optional AWS session token.")


class AzureBackendConfig(BaseModel):
    """Azure backend configuration using storage accounts or SAS tokens."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["azurerm"] = "azurerm"
    storage_account: str = Field(..., description="Azure Storage account name.")
    container: str = Field(..., description="Blob container storing the Terraform state.")
    key: str = Field(..., description="Blob key inside the container.")
    sas_token: Optional[str] = Field(None, description="Optional SAS token appended to the blob URL.")
    connection_string: Optional[str] = Field(None, description="Optional connection string to authenticate.")


class GCSBackendConfig(BaseModel):
    """Google Cloud Storage backend configuration."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["gcs"] = "gcs"
    bucket: str = Field(..., description="GCS bucket storing the Terraform state.")
    prefix: str = Field(..., description="Object prefix / key.")
    credentials_file: Optional[str] = Field(None, description="Optional service account JSON file.")
    project: Optional[str] = Field(None, description="Optional Google Cloud project identifier.")


class TerraformCloudBackendConfig(BaseModel):
    """Terraform Cloud/Enterprise remote backend configuration."""

    model_config = ConfigDict(extra="forbid")

    type: Literal["remote"] = "remote"
    hostname: Optional[str] = Field(None, description="Terraform Cloud hostname (default: app.terraform.io).")
    organization: str = Field(..., description="Terraform Cloud organization.")
    workspace: str = Field(..., description="Workspace name.")
    token: Optional[str] = Field(None, description="User or team access token.")
    include_outputs: bool = Field(
        default=False,
        description="Fetch full state payload instead of the abbreviated metadata.",
    )


StateBackendConfig = Annotated[
    Union[
        LocalBackendConfig,
        S3BackendConfig,
        AzureBackendConfig,
        GCSBackendConfig,
        TerraformCloudBackendConfig,
    ],
    Field(discriminator="type"),
]


class TerraformStateResourceModel(BaseModel):
    """Normalized Terraform state resource instance."""

    model_config = ConfigDict(extra="forbid")

    address: str = Field(..., description="Fully-qualified Terraform resource address.")
    module_address: Optional[str] = Field(None, description="Module path when the resource lives inside a module.")
    mode: str = Field(..., description="Terraform resource mode (managed or data).")
    type: str = Field(..., description="Resource type, e.g. aws_instance.")
    name: str = Field(..., description="Resource name.")
    provider: Optional[str] = Field(None, description="Provider address recorded in the state file.")
    index: Optional[str] = Field(None, description="Collection index (count or for_each).")
    schema_version: Optional[int] = Field(None, description="Resource schema version recorded by Terraform.")
    attributes: Dict[str, Any] = Field(default_factory=dict, description="Resource attributes from the state file.")
    sensitive_attributes: List[str] = Field(default_factory=list, description="Paths marked as sensitive by Terraform.")
    dependencies: List[str] = Field(default_factory=list, description="Addresses this resource depends on.")


class TerraformStateOutputModel(BaseModel):
    """Normalized Terraform output entry."""

    model_config = ConfigDict(extra="forbid")

    name: str
    value: Any
    sensitive: bool = False
    type: Optional[Any] = None


class TerraformStateDocument(BaseModel):
    """Representation of a parsed Terraform state file along with derived metadata."""

    model_config = ConfigDict(extra="forbid")

    serial: Optional[int] = None
    terraform_version: Optional[str] = Field(None, description="Terraform version recorded in the state file.")
    lineage: Optional[str] = Field(None, description="State lineage UUID.")
    backend_type: Optional[str] = None
    resource_count: int = 0
    output_count: int = 0
    checksum: str
    size_bytes: int
    resources: List[TerraformStateResourceModel] = Field(default_factory=list)
    outputs: List[TerraformStateOutputModel] = Field(default_factory=list)
    raw_state: Dict[str, Any] = Field(default_factory=dict)


class StateImportRequest(BaseModel):
    """Payload for API-driven state imports."""

    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = Field(None, description="Target project identifier.")
    project_slug: Optional[str] = Field(None, description="Target project slug.")
    workspace: str = Field(default="default", description="Logical workspace identifier.")
    backend: StateBackendConfig = Field(..., description="Backend configuration describing how to read the state.")


class StateListResponse(BaseModel):
    """List view for Terraform state entries."""

    model_config = ConfigDict(extra="forbid")

    items: List[Dict[str, Any]]


class DriftSummary(BaseModel):
    """Summary produced by comparing state with a Terraform plan."""

    model_config = ConfigDict(extra="forbid")

    state_resource_count: int
    plan_resource_count: int
    resources_added: int
    resources_changed: int
    resources_destroyed: int
    state_only_resources: int
    plan_only_resources: int
    details: Dict[str, Any] = Field(default_factory=dict)


class StateRemoveRequest(BaseModel):
    """Request payload for removing addresses from a stored state."""

    model_config = ConfigDict(extra="forbid")

    addresses: List[str] = Field(..., min_length=1)


class StateMoveRequest(BaseModel):
    """Request payload for moving a resource address."""

    model_config = ConfigDict(extra="forbid")

    source: str = Field(..., min_length=1)
    destination: str = Field(..., min_length=1)


class WorkspaceCreateRequest(BaseModel):
    """Payload for creating or updating Terraform workspaces."""

    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = Field(default=None)
    project_slug: Optional[str] = Field(default=None)
    name: str
    working_directory: str
    is_default: bool = False
    is_active: bool = False


class WorkspaceResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    name: str
    working_directory: str
    is_default: bool
    is_active: bool
    created_at: Optional[str] = None
    selected_at: Optional[str] = None
    last_scanned_at: Optional[str] = None


class WorkspaceListResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: List[WorkspaceResponse]


class PlanCreateRequest(BaseModel):
    """Payload for tracking Terraform plan metadata."""

    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = Field(default=None)
    project_slug: Optional[str] = Field(default=None)
    workspace: str = Field(default="default")
    working_directory: str
    plan_type: str
    target_resources: Optional[List[str]] = None
    has_changes: bool = False
    resource_changes: Optional[Dict[str, Any]] = None
    resource_changes_detail: Optional[List[Dict[str, Any]]] = None
    output_changes: Optional[Dict[str, Any]] = None
    plan_file_path: Optional[str] = None
    plan_json_path: Optional[str] = None
    plan_output: Optional[str] = None
    cost_estimate: Optional[Dict[str, Any]] = None
    security_impact: Optional[Dict[str, Any]] = None
    approval_status: Optional[str] = None
    run_id: Optional[str] = None


class PlanResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    project_id: str
    run_id: Optional[str]
    workspace: str
    working_directory: str
    plan_type: str
    has_changes: bool
    total_resources: int
    resources_to_add: int
    resources_to_change: int
    resources_to_destroy: int
    approval_status: str
    created_at: Optional[str] = None
