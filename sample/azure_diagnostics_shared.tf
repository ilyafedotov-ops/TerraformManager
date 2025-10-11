# Example: Diagnostics baseline referencing shared storage account

locals {
  subscription_id = "00000000-0000-0000-0000-000000000000"
}

module "diagnostics" {
  source = "../generated/azure_diagnostics_law_prod.tf"

  # The generated module already exposes outputs for the workspace and diagnostic IDs.
}

# Example of attaching additional diagnostics to an existing storage account.
resource "azurerm_monitor_diagnostic_setting" "storage_shared" {
  name                       = "diag-storage-shared"
  target_resource_id         = "/subscriptions/${local.subscription_id}/resourceGroups/rg-shared/providers/Microsoft.Storage/storageAccounts/sharedlogs"
  log_analytics_workspace_id = module.diagnostics.log_analytics_workspace_id

  enabled_log {
    category = "StorageRead"
  }

  enabled_log {
    category = "StorageWrite"
  }

  enabled_log {
    category = "StorageDelete"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}
