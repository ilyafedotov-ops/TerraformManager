"""Workspace management helpers (Terraform CLI + persistence)."""

from .errors import TerraformCommandError, TerraformWorkspaceError, WorkspaceConflictError, WorkspaceNotFoundError
from .manager import CommandResult, WorkspaceListResult, WorkspaceManager
from .variables import detect_sensitive_keys, import_tfvars_file, load_tfvars
from .comparator import (
    WorkspaceDifference,
    compare_variables_map,
    compare_state_metadata,
    compare_state_resource_sets,
    compare_states,
    load_workspace_variables,
    latest_states_for_workspaces,
    record_workspace_comparison,
)
from .storage import (
    create_workspace_record,
    delete_workspace_record,
    get_workspace_by_id,
    get_workspace_by_name,
    list_workspace_records,
    set_active_workspace,
    touch_workspace_scan,
    upsert_workspace_variable,
    list_workspace_variables,
    delete_workspace_variable,
)
from .scanner import MultiWorkspaceScanner, WorkspaceScanResult
from .services import (
    DiscoverResult,
    discover_and_sync_workspaces,
    resolve_working_directory,
    select_workspace_with_cli,
    create_workspace_with_cli,
    delete_workspace_with_cli,
)

__all__ = [
    "CommandResult",
    "WorkspaceListResult",
    "WorkspaceManager",
    "TerraformWorkspaceError",
    "TerraformCommandError",
    "WorkspaceConflictError",
    "WorkspaceNotFoundError",
    "detect_sensitive_keys",
    "import_tfvars_file",
    "load_tfvars",
    "WorkspaceDifference",
    "compare_variables_map",
    "compare_state_metadata",
    "compare_state_resource_sets",
    "compare_states",
    "load_workspace_variables",
    "latest_states_for_workspaces",
    "record_workspace_comparison",
    "create_workspace_record",
    "delete_workspace_record",
    "get_workspace_by_id",
    "get_workspace_by_name",
    "list_workspace_records",
    "set_active_workspace",
    "touch_workspace_scan",
    "upsert_workspace_variable",
    "list_workspace_variables",
    "delete_workspace_variable",
    "MultiWorkspaceScanner",
    "WorkspaceScanResult",
    "DiscoverResult",
    "discover_and_sync_workspaces",
    "resolve_working_directory",
    "select_workspace_with_cli",
    "create_workspace_with_cli",
    "delete_workspace_with_cli",
]
