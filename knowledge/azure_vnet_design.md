---
title: Azure Virtual Network Design Best Practices
provider: azure
service: networking
category: [networking, security, architecture]
tags: [vnet, nsg, service-endpoints, private-link, peering]
last_updated: 2025-01-18
difficulty: intermediate
---

# Azure Virtual Network Design Best Practices

Azure Virtual Networks (VNets) provide isolated network environments for Azure resources. Proper VNet design is critical for security, performance, and scalability.

## Address Space Planning

### CIDR Block Selection

**Plan for growth and avoid overlaps:**

```terraform
resource "azurerm_virtual_network" "main" {
  name                = "vnet-prod-eastus"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  # Use RFC 1918 private address space
  address_space = ["10.0.0.0/16"]  # 65,536 IPs

  tags = {
    Environment = "production"
  }
}
```

**Recommended Address Ranges:**
- **Hub VNet:** `10.0.0.0/16` (65K IPs)
- **Production VNet:** `10.1.0.0/16`
- **Staging VNet:** `10.2.0.0/16`
- **Development VNet:** `10.3.0.0/16`

**Avoid:**
- `172.16.0.0/12` (commonly used by on-prem networks)
- Overlapping ranges between VNets you plan to peer
- Too small ranges (e.g., /24) that limit growth

### Subnet Design

**Segment by function and security requirements:**

```terraform
resource "azurerm_subnet" "gateway" {
  name                 = "GatewaySubnet"  # Required name for VPN Gateway
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.0.0/27"]  # 32 IPs, minimum /27
}

resource "azurerm_subnet" "bastion" {
  name                 = "AzureBastionSubnet"  # Required name
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.0.32/27"]  # Minimum /26 recommended
}

resource "azurerm_subnet" "firewall" {
  name                 = "AzureFirewallSubnet"  # Required name
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.0.64/26"]  # Minimum /26
}

resource "azurerm_subnet" "app" {
  name                 = "snet-app"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.1.0/24"]  # 256 IPs

  service_endpoints = [
    "Microsoft.Storage",
    "Microsoft.Sql",
    "Microsoft.KeyVault",
  ]

  delegation {
    name = "aks-delegation"
    service_delegation {
      name = "Microsoft.ContainerService/managedClusters"
      actions = [
        "Microsoft.Network/virtualNetworks/subnets/join/action",
      ]
    }
  }
}

resource "azurerm_subnet" "data" {
  name                 = "snet-data"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.2.0/24"]

  service_endpoints = [
    "Microsoft.Sql",
  ]
}

resource "azurerm_subnet" "private_endpoints" {
  name                 = "snet-private-endpoints"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.0.3.0/24"]

  private_endpoint_network_policies_enabled = false
}
```

## Network Security Groups (NSGs)

### Subnet-Level NSGs

**Apply NSGs at subnet level for defense in depth:**

```terraform
resource "azurerm_network_security_group" "app" {
  name                = "nsg-app"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  tags = {
    Environment = "production"
  }
}

# Default deny all inbound
resource "azurerm_network_security_rule" "deny_all_inbound" {
  name                        = "DenyAllInbound"
  priority                    = 4096
  direction                   = "Inbound"
  access                      = "Deny"
  protocol                    = "*"
  source_port_range           = "*"
  destination_port_range      = "*"
  source_address_prefix       = "*"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.app.name
}

# Allow specific traffic
resource "azurerm_network_security_rule" "allow_https_from_lb" {
  name                        = "AllowHTTPSFromLB"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "AzureLoadBalancer"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.app.name
}

# Associate NSG with subnet
resource "azurerm_subnet_network_security_group_association" "app" {
  subnet_id                 = azurerm_subnet.app.id
  network_security_group_id = azurerm_network_security_group.app.id
}
```

### Application Security Groups (ASGs)

**Group VMs by application tier:**

```terraform
resource "azurerm_application_security_group" "web" {
  name                = "asg-web"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_application_security_group" "app" {
  name                = "asg-app"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

# Allow web tier to communicate with app tier
resource "azurerm_network_security_rule" "web_to_app" {
  name                                       = "AllowWebToApp"
  priority                                   = 100
  direction                                  = "Inbound"
  access                                     = "Allow"
  protocol                                   = "Tcp"
  source_port_range                          = "*"
  destination_port_ranges                    = ["8080", "8443"]
  source_application_security_group_ids      = [azurerm_application_security_group.web.id]
  destination_application_security_group_ids = [azurerm_application_security_group.app.id]
  resource_group_name                        = azurerm_resource_group.main.name
  network_security_group_name                = azurerm_network_security_group.app.name
}
```

## Service Endpoints

### Enable for PaaS Services

**Secure traffic to Azure services within VNet:**

```terraform
resource "azurerm_subnet" "app" {
  name = "snet-app"

  service_endpoints = [
    "Microsoft.Storage",      # Storage Accounts
    "Microsoft.Sql",          # Azure SQL
    "Microsoft.KeyVault",     # Key Vault
    "Microsoft.ContainerRegistry", # ACR
    "Microsoft.ServiceBus",   # Service Bus
    "Microsoft.EventHub",     # Event Hub
  ]
}

# Configure service firewall to allow VNet
resource "azurerm_storage_account" "main" {
  name                = "st${var.project}${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  account_tier             = "Standard"
  account_replication_type = "LRS"

  network_rules {
    default_action = "Deny"  # Deny all by default

    # Allow from specific subnets with service endpoint
    virtual_network_subnet_ids = [
      azurerm_subnet.app.id,
    ]

    # Allow from specific public IPs (office, CI/CD)
    ip_rules = ["203.0.113.0/24"]

    bypass = ["AzureServices"]  # Allow other Azure services
  }
}
```

**Benefits:**
- Traffic stays on Azure backbone
- No public internet traversal
- Improved security
- Better performance
- Lower latency

## Private Endpoints

### Fully Private Connectivity

**Use for critical PaaS services:**

```terraform
resource "azurerm_private_endpoint" "storage" {
  name                = "pe-storage"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  subnet_id           = azurerm_subnet.private_endpoints.id

  private_service_connection {
    name                           = "psc-storage"
    private_connection_resource_id = azurerm_storage_account.main.id
    is_manual_connection           = false
    subresource_names              = ["blob"]  # blob, file, table, queue
  }

  private_dns_zone_group {
    name                 = "default"
    private_dns_zone_ids = [azurerm_private_dns_zone.blob.id]
  }
}

# Private DNS Zone for resolution
resource "azurerm_private_dns_zone" "blob" {
  name                = "privatelink.blob.core.windows.net"
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "blob" {
  name                  = "blob-vnet-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = azurerm_private_dns_zone.blob.name
  virtual_network_id    = azurerm_virtual_network.main.id
}
```

**When to use Private Endpoints vs Service Endpoints:**

| Feature | Private Endpoint | Service Endpoint |
|---------|------------------|------------------|
| **Dedicated IP** | Yes (in your VNet) | No |
| **Public access** | Can disable | Still has public IP |
| **Scope** | Specific resource | All resources of type |
| **Cross-region** | Yes | No |
| **Cost** | Charged per endpoint | Free |
| **Use case** | Production critical | Dev/test, cost-sensitive |

## VNet Peering

### Hub-and-Spoke Topology

**Central hub for shared services:**

```terraform
# Hub VNet
resource "azurerm_virtual_network" "hub" {
  name                = "vnet-hub"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.0.0.0/16"]
}

# Spoke VNets
resource "azurerm_virtual_network" "spoke_prod" {
  name                = "vnet-spoke-prod"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.1.0.0/16"]
}

resource "azurerm_virtual_network" "spoke_staging" {
  name                = "vnet-spoke-staging"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  address_space       = ["10.2.0.0/16"]
}

# Peering: Hub to Prod Spoke
resource "azurerm_virtual_network_peering" "hub_to_prod" {
  name                      = "hub-to-prod"
  resource_group_name       = azurerm_resource_group.main.name
  virtual_network_name      = azurerm_virtual_network.hub.name
  remote_virtual_network_id = azurerm_virtual_network.spoke_prod.id

  allow_virtual_network_access = true
  allow_forwarded_traffic      = true  # Allow traffic via firewall
  allow_gateway_transit        = true  # Share VPN/ExpressRoute
}

# Peering: Prod Spoke to Hub
resource "azurerm_virtual_network_peering" "prod_to_hub" {
  name                      = "prod-to-hub"
  resource_group_name       = azurerm_resource_group.main.name
  virtual_network_name      = azurerm_virtual_network.spoke_prod.name
  remote_virtual_network_id = azurerm_virtual_network.hub.id

  allow_virtual_network_access = true
  allow_forwarded_traffic      = true
  use_remote_gateways          = true  # Use hub's gateway
}
```

**Hub-and-Spoke Benefits:**
- Centralized security (Azure Firewall in hub)
- Shared services (DNS, monitoring)
- Cost optimization (single gateway)
- Simplified management
- Spoke isolation (no direct spoke-to-spoke)

### Global VNet Peering

**Connect VNets across regions:**

```terraform
resource "azurerm_virtual_network_peering" "eastus_to_westus" {
  name                      = "eastus-to-westus"
  resource_group_name       = azurerm_resource_group.eastus.name
  virtual_network_name      = azurerm_virtual_network.eastus.name
  remote_virtual_network_id = azurerm_virtual_network.westus.id

  allow_virtual_network_access = true
}
```

## Azure Firewall

### Central Security Control

**Deploy in hub VNet:**

```terraform
resource "azurerm_subnet" "firewall" {
  name                 = "AzureFirewallSubnet"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.hub.name
  address_prefixes     = ["10.0.0.64/26"]
}

resource "azurerm_public_ip" "firewall" {
  name                = "pip-firewall"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  allocation_method   = "Static"
  sku                 = "Standard"
}

resource "azurerm_firewall" "main" {
  name                = "afw-hub"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku_name            = "AZFW_VNet"
  sku_tier            = "Standard"  # Or "Premium" for TLS inspection

  ip_configuration {
    name                 = "configuration"
    subnet_id            = azurerm_subnet.firewall.id
    public_ip_address_id = azurerm_public_ip.firewall.id
  }
}

# Application rule collection
resource "azurerm_firewall_application_rule_collection" "allow_https" {
  name                = "allow-https"
  azure_firewall_name = azurerm_firewall.main.name
  resource_group_name = azurerm_resource_group.main.name
  priority            = 100
  action              = "Allow"

  rule {
    name = "allow-microsoft-services"
    source_addresses = ["10.1.0.0/16"]  # Spoke VNet
    target_fqdns = [
      "*.microsoft.com",
      "*.azure.com",
      "*.windows.net",
    ]
    protocol {
      port = "443"
      type = "Https"
    }
  }
}
```

### User-Defined Routes (UDR)

**Force traffic through firewall:**

```terraform
resource "azurerm_route_table" "spoke" {
  name                = "rt-spoke"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name

  disable_bgp_route_propagation = false
}

# Default route to firewall
resource "azurerm_route" "default" {
  name                   = "default-via-firewall"
  resource_group_name    = azurerm_resource_group.main.name
  route_table_name       = azurerm_route_table.spoke.name
  address_prefix         = "0.0.0.0/0"
  next_hop_type          = "VirtualAppliance"
  next_hop_in_ip_address = azurerm_firewall.main.ip_configuration[0].private_ip_address
}

# Associate with subnet
resource "azurerm_subnet_route_table_association" "spoke_app" {
  subnet_id      = azurerm_subnet.spoke_app.id
  route_table_id = azurerm_route_table.spoke.id
}
```

## DNS Configuration

### Private DNS Zones

**Resolve Azure private endpoints:**

```terraform
# Common private DNS zones
locals {
  private_dns_zones = {
    blob         = "privatelink.blob.core.windows.net"
    sql          = "privatelink.database.windows.net"
    vault        = "privatelink.vaultcore.azure.net"
    acr          = "privatelink.azurecr.io"
    aks          = "privatelink.eastus.azmk8s.io"
    servicebus   = "privatelink.servicebus.windows.net"
  }
}

resource "azurerm_private_dns_zone" "zones" {
  for_each            = local.private_dns_zones
  name                = each.value
  resource_group_name = azurerm_resource_group.main.name
}

resource "azurerm_private_dns_zone_virtual_network_link" "zones" {
  for_each              = azurerm_private_dns_zone.zones
  name                  = "${each.key}-vnet-link"
  resource_group_name   = azurerm_resource_group.main.name
  private_dns_zone_name = each.value.name
  virtual_network_id    = azurerm_virtual_network.main.id
}
```

## Monitoring and Diagnostics

### NSG Flow Logs

**Track network traffic:**

```terraform
resource "azurerm_storage_account" "flow_logs" {
  name                = "stflowlogs${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  account_tier             = "Standard"
  account_replication_type = "LRS"
}

resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-network"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
}

resource "azurerm_network_watcher_flow_log" "nsg" {
  network_watcher_name = "NetworkWatcher_eastus"
  resource_group_name  = "NetworkWatcherRG"

  network_security_group_id = azurerm_network_security_group.app.id
  storage_account_id        = azurerm_storage_account.flow_logs.id
  enabled                   = true

  retention_policy {
    enabled = true
    days    = 90
  }

  traffic_analytics {
    enabled               = true
    workspace_id          = azurerm_log_analytics_workspace.main.workspace_id
    workspace_region      = azurerm_log_analytics_workspace.main.location
    workspace_resource_id = azurerm_log_analytics_workspace.main.id
    interval_in_minutes   = 10
  }
}
```

## Summary Checklist

- [ ] Address space planned to avoid overlaps
- [ ] Subnets sized appropriately with growth buffer
- [ ] NSGs applied to all subnets
- [ ] Default deny rules configured
- [ ] Service endpoints enabled for applicable PaaS
- [ ] Private endpoints for critical services
- [ ] Hub-and-spoke topology for multi-VNet
- [ ] VNet peering configured correctly
- [ ] Azure Firewall deployed in hub
- [ ] UDRs force traffic through firewall
- [ ] Private DNS zones configured
- [ ] NSG flow logs enabled
- [ ] Traffic Analytics enabled

## References

- [Azure VNet Documentation](https://docs.microsoft.com/en-us/azure/virtual-network/)
- [Hub-Spoke Topology](https://docs.microsoft.com/en-us/azure/architecture/reference-architectures/hybrid-networking/hub-spoke)
- [Azure Firewall Architecture](https://docs.microsoft.com/en-us/azure/architecture/example-scenario/firewalls/)
- [Private Link Documentation](https://docs.microsoft.com/en-us/azure/private-link/)
- [Azure Security Baseline](https://docs.microsoft.com/en-us/security/benchmark/azure/baselines/virtual-network-security-baseline)
