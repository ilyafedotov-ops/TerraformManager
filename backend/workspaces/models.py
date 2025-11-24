from __future__ import annotations

from typing import Any, Dict, List, Optional, Sequence

from pydantic import BaseModel, ConfigDict, Field


class WorkspaceCreatePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = None
    project_slug: Optional[str] = None
    name: str
    working_directory: str
    is_default: bool = False
    is_active: bool = False
    skip_terraform: bool = False


class WorkspaceSelectPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = None
    project_slug: Optional[str] = None


class WorkspaceScanPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = None
    project_slug: Optional[str] = None
    working_directory: str
    workspaces: Optional[List[str]] = None
    use_terraform_validate: bool = False


class WorkspaceVariablePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str
    value: Any | None = None
    sensitive: bool = False
    source: Optional[str] = None
    description: Optional[str] = None


class WorkspaceComparePayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = None
    project_slug: Optional[str] = None
    workspace_a_id: str
    workspace_b_id: str
    comparison_types: Sequence[str] = Field(default_factory=lambda: ["variables", "state", "config"])


class WorkspaceVariableImportPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    project_id: Optional[str] = None
    project_slug: Optional[str] = None
    file: str
    extra_sensitive_keys: Sequence[str] | None = None
