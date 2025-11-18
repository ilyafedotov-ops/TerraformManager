provider "azurerm" { features {} }

resource "azurerm_resource_group" "rg" {
  name     = "rg-insecure"
  location = "eastus"
}

resource "azurerm_storage_account" "sa" {
  name                     = "stexampleinsecure1234"
  resource_group_name      = azurerm_resource_group.rg.name
  location                 = azurerm_resource_group.rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
  https_traffic_only_enabled = false
  allow_nested_items_to_be_public  = true
  min_tls_version           = "TLS1_0"
}
