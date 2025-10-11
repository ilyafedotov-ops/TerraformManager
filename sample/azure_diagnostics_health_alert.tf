# Example diagnostics stack with ingestion health alert

resource "azurerm_resource_group" "rg" {
  name     = "rg-diag-health"
  location = "eastus"
}

resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-diag-health"
  location            = azurerm_resource_group.rg.location
  resource_group_name = azurerm_resource_group.rg.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
}

resource "azurerm_monitor_metric_alert" "law_health" {
  name                = "law-health-alert"
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
    action_group_id = "/subscriptions/00000000-0000-0000-0000-000000000000/resourceGroups/rg-diag/providers/Microsoft.Insights/actionGroups/secops-alerts"
  }
}
