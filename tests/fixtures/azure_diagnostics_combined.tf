resource "azurerm_resource_group" "rg" {
  name     = "rg-diag"
  location = "eastus"
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-diag"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_virtual_network" "vnet" {
  name                = "diag-vnet"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
  address_space       = ["10.0.0.0/16"]
}

resource "azurerm_subnet" "subnet_app" {
  name                 = "app"
  resource_group_name  = azurerm_resource_group.rg.name
  virtual_network_name = azurerm_virtual_network.vnet.name
  address_prefixes     = ["10.0.1.0/24"]
}

resource "azurerm_network_security_group" "app" {
  name                = "app-nsg"
  resource_group_name = azurerm_resource_group.rg.name
  location            = azurerm_resource_group.rg.location
}

resource "azurerm_storage_account" "logs" {
  name                     = "diaglogsacct"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  min_tls_version          = "TLS1_2"
  allow_nested_items_to_be_public = false
  https_traffic_only_enabled      = true
}

resource "azurerm_monitor_diagnostic_setting" "subnet_diag" {
  name                       = "diag-subnet-app"
  target_resource_id         = azurerm_subnet.subnet_app.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

  enabled_log {
    category = "VMProtectionAlerts"
  }
  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "nsg_diag" {
  name                       = "diag-nsg"
  target_resource_id         = azurerm_network_security_group.app.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

  enabled_log {
    category = "NetworkSecurityGroupEvent"
  }
  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_monitor_diagnostic_setting" "storage_diag" {
  name                       = "diag-storage"
  target_resource_id         = azurerm_storage_account.logs.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

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

resource "azurerm_private_endpoint" "logs_pe" {
  name                = "logs-private-endpoint"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  subnet_id           = azurerm_subnet.subnet_app.id

  private_service_connection {
    name                           = "logs-blob-pe"
    private_connection_resource_id = azurerm_storage_account.logs.id
    subresource_names              = ["blob"]
  }
}

resource "azurerm_monitor_diagnostic_setting" "vnet_diag" {
  name                       = "diag-vnet"
  target_resource_id         = azurerm_virtual_network.vnet.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id

  enabled_log {
    category = "VMProtectionAlerts"
  }

  enabled_log {
    category = "VMProtectionEvents"
  }

  enabled_metric {
    category = "AllMetrics"
  }
}

resource "azurerm_network_watcher" "diag" {
  name                = "diag-nw"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
}

resource "azurerm_network_watcher_flow_log" "diag" {
  name                 = "diag-flow"
  network_watcher_name = azurerm_network_watcher.diag.name
  resource_group_name  = azurerm_network_watcher.diag.resource_group_name
  network_security_group_id = azurerm_network_security_group.app.id

  retention_policy {
    enabled = true
    days    = 30
  }

  traffic_analytics {
    enabled               = true
    workspace_id          = azurerm_log_analytics_workspace.law.workspace_id
    workspace_region      = azurerm_log_analytics_workspace.law.location
    workspace_resource_id = azurerm_log_analytics_workspace.law.id
    interval_in_minutes   = 10
  }
}

resource "azurerm_monitor_metric_alert" "law_health" {
  name                = "law-ingestion-alert"
  resource_group_name = azurerm_resource_group.rg.name
  scopes              = [azurerm_log_analytics_workspace.law.id]
  description         = "Alert when Log Analytics ingestion availability drops below 99%."
  severity            = 2
  frequency           = "PT5M"
  window_size         = "PT5M"

  criteria {
    metric_namespace = "microsoft.operationalinsights/workspaces"
    metric_name      = "SearchServiceAvailability"
    aggregation      = "Average"
    operator         = "LessThan"
    threshold        = 99
  }

  action {
    action_group_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-diag/providers/Microsoft.Insights/actionGroups/diag-alerts"
  }
}
