---
title: Azure AKS Security Best Practices
provider: azure
service: aks
category: [security, kubernetes, container-orchestration]
tags: [aad, rbac, network-policy, private-cluster, managed-identity]
last_updated: 2025-01-18
difficulty: intermediate
---

# Azure AKS Security Best Practices

Azure Kubernetes Service (AKS) is a managed Kubernetes platform on Azure. This guide covers security, compliance, and operational best practices for production AKS clusters.

## Cluster Security

### Azure AD Integration

**Always use Azure AD for authentication (not X.509 certificates):**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  name                = "production-aks"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  dns_prefix          = "prod-aks"

  # Azure AD Integration (Managed)
  azure_active_directory_role_based_access_control {
    managed                = true
    admin_group_object_ids = [azurerm_azuread_group.aks_admins.id]
    azure_rbac_enabled     = true
  }

  identity {
    type = "SystemAssigned"
  }
}
```

**Benefits:**
- Centralized identity management
- MFA enforcement
- Conditional access policies
- Automatic credential rotation
- Integration with Azure RBAC

### Azure RBAC for Kubernetes

**Use Azure RBAC instead of Kubernetes RBAC:**

```terraform
# Assign built-in roles at cluster or namespace scope
resource "azurerm_role_assignment" "aks_user" {
  scope                = azurerm_kubernetes_cluster.main.id
  role_definition_name = "Azure Kubernetes Service Cluster User Role"
  principal_id         = azurerm_azuread_group.developers.id
}

# Namespace-scoped admin access
resource "azurerm_role_assignment" "namespace_admin" {
  scope                = "${azurerm_kubernetes_cluster.main.id}/namespaces/production"
  role_definition_name = "Azure Kubernetes Service RBAC Admin"
  principal_id         = azurerm_azuread_group.prod_admins.id
}
```

**Available Built-in Roles:**
- `Azure Kubernetes Service RBAC Cluster Admin` - Full cluster access
- `Azure Kubernetes Service RBAC Admin` - Namespace admin
- `Azure Kubernetes Service RBAC Writer` - Read/write within namespace
- `Azure Kubernetes Service RBAC Reader` - Read-only within namespace

### Private Cluster

**Use private clusters for production:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  private_cluster_enabled = true  # API server accessible only from VNet

  # Optional: Bring your own private DNS zone
  private_dns_zone_id = azurerm_private_dns_zone.aks.id

  network_profile {
    network_plugin    = "azure"
    network_policy    = "calico"      # Or "azure" for Azure Network Policy
    service_cidr      = "10.0.0.0/16"
    dns_service_ip    = "10.0.0.10"
    docker_bridge_cidr = "172.17.0.1/16"
  }
}

resource "azurerm_private_dns_zone" "aks" {
  name                = "privatelink.eastus.azmk8s.io"
  resource_group_name = azurerm_resource_group.main.name
}
```

**Benefits:**
- No public IP for API server
- Traffic stays within Azure backbone
- Reduced attack surface
- Compliance with private networking requirements

### API Server Authorized IP Ranges

**If private cluster isn't feasible, restrict API access by IP:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  # For public clusters only
  private_cluster_enabled = false

  api_server_access_profile {
    authorized_ip_ranges = [
      "203.0.113.0/24",  # Office network
      "198.51.100.0/24", # VPN CIDR
    ]
  }
}
```

## Network Security

### Azure CNI vs Kubenet

**Prefer Azure CNI for production:**

| Feature | Azure CNI | Kubenet |
|---------|-----------|---------|
| **Pod IP** | Routable Azure VNet IP | Node IP + NAT |
| **NSGs** | Apply directly to pods | Apply to nodes only |
| **Service Endpoints** | Pods can use directly | Requires NAT |
| **IP Consumption** | Higher (pod IPs from subnet) | Lower (only node IPs) |
| **Network Policies** | Full support | Limited |

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  network_profile {
    network_plugin = "azure"  # Azure CNI

    # Pod CIDR not needed with Azure CNI (uses VNet)
  }

  default_node_pool {
    vnet_subnet_id = azurerm_subnet.aks_nodes.id
  }
}

resource "azurerm_subnet" "aks_nodes" {
  name                 = "aks-nodes"
  resource_group_name  = azurerm_resource_group.main.name
  virtual_network_name = azurerm_virtual_network.main.name
  address_prefixes     = ["10.1.0.0/22"]  # Size for max_pods * max_nodes
}
```

### Network Policies

**Always enable network policies:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  network_profile {
    network_plugin = "azure"
    network_policy = "calico"  # Or "azure" for Azure Network Policy
  }
}
```

**Implement default deny policies:**

```yaml
# Deny all ingress/egress by default
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-all
  namespace: production
spec:
  podSelector: {}
  policyTypes:
    - Ingress
    - Egress
```

### NSG Configuration

**Secure NSGs for AKS subnet:**

```terraform
resource "azurerm_network_security_group" "aks" {
  name                = "nsg-aks"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

# Allow only necessary inbound traffic
resource "azurerm_network_security_rule" "allow_https_inbound" {
  name                        = "AllowHTTPSInbound"
  priority                    = 100
  direction                   = "Inbound"
  access                      = "Allow"
  protocol                    = "Tcp"
  source_port_range           = "*"
  destination_port_range      = "443"
  source_address_prefix       = "AzureLoadBalancer"
  destination_address_prefix  = "*"
  resource_group_name         = azurerm_resource_group.main.name
  network_security_group_name = azurerm_network_security_group.aks.name
}

# Deny all other inbound
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
  network_security_group_name = azurerm_network_security_group.aks.name
}

resource "azurerm_subnet_network_security_group_association" "aks" {
  subnet_id                 = azurerm_subnet.aks_nodes.id
  network_security_group_id = azurerm_network_security_group.aks.id
}
```

## Identity and Access

### Managed Identity

**Always use managed identity (never service principals):**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  identity {
    type = "SystemAssigned"
  }

  # Alternatively, user-assigned identity
  # identity {
  #   type         = "UserAssigned"
  #   identity_ids = [azurerm_user_assigned_identity.aks.id]
  # }
}
```

**Benefits:**
- No credential management
- Automatic rotation
- Azure AD integration
- Fine-grained RBAC

### Workload Identity (AAD Pod Identity v2)

**Use Workload Identity for pod-level Azure resource access:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  oidc_issuer_enabled       = true
  workload_identity_enabled = true
}

# Create managed identity for workload
resource "azurerm_user_assigned_identity" "app" {
  name                = "id-app-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
}

# Grant permissions to Azure resources
resource "azurerm_role_assignment" "app_storage" {
  scope                = azurerm_storage_account.main.id
  role_definition_name = "Storage Blob Data Contributor"
  principal_id         = azurerm_user_assigned_identity.app.principal_id
}

# Federate with Kubernetes service account
resource "azurerm_federated_identity_credential" "app" {
  name                = "fed-app-${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  audience            = ["api://AzureADTokenExchange"]
  issuer              = azurerm_kubernetes_cluster.main.oidc_issuer_url
  parent_id           = azurerm_user_assigned_identity.app.id
  subject             = "system:serviceaccount:${var.namespace}:${var.service_account_name}"
}
```

**Kubernetes service account:**

```yaml
apiVersion: v1
kind: ServiceAccount
metadata:
  name: app-sa
  namespace: production
  annotations:
    azure.workload.identity/client-id: "${azurerm_user_assigned_identity.app.client_id}"
---
apiVersion: apps/v1
kind: Deployment
metadata:
  name: app
spec:
  template:
    metadata:
      labels:
        azure.workload.identity/use: "true"
    spec:
      serviceAccountName: app-sa
      containers:
      - name: app
        image: myapp:1.0.0
```

### Local Accounts Disabled

**Disable local admin account:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  local_account_disabled = true  # Force Azure AD authentication

  azure_active_directory_role_based_access_control {
    managed = true
    admin_group_object_ids = [azurerm_azuread_group.aks_admins.id]
  }
}
```

## Container Security

### Azure Defender for Containers

**Enable Microsoft Defender for Containers:**

```terraform
resource "azurerm_security_center_subscription_pricing" "defender_containers" {
  tier          = "Standard"
  resource_type = "Containers"
}

resource "azurerm_kubernetes_cluster" "main" {
  microsoft_defender {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  }
}
```

**Features:**
- Vulnerability scanning (images in ACR)
- Runtime threat detection
- Kubernetes audit log analysis
- Security recommendations

### Image Security

**Use Azure Container Registry with scanning:**

```terraform
resource "azurerm_container_registry" "main" {
  name                = "acr${var.project}${var.environment}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
  sku                 = "Premium"  # Required for private endpoint
  admin_enabled       = false      # Use managed identity

  # Enable Defender scanning
  azure_container_registry_defender {
    enabled = true
  }
}

# Attach ACR to AKS
resource "azurerm_role_assignment" "aks_acr_pull" {
  scope                = azurerm_container_registry.main.id
  role_definition_name = "AcrPull"
  principal_id         = azurerm_kubernetes_cluster.main.kubelet_identity[0].object_id
}
```

### Pod Security

**Implement Pod Security Standards via Azure Policy:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  azure_policy_enabled = true
}

# Assign built-in policy initiative
resource "azurerm_resource_policy_assignment" "aks_restricted" {
  name                 = "aks-pod-security-restricted"
  resource_id          = azurerm_kubernetes_cluster.main.id
  policy_definition_id = "/providers/Microsoft.Authorization/policySetDefinitions/42b8ef37-b724-4e24-bbc8-7a7708edfe00"  # Pod Security Restricted

  parameters = jsonencode({
    effect = {
      value = "Audit"  # Start with Audit, then move to Deny
    }
  })
}
```

**Or use namespace labels (Kubernetes PSA):**

```yaml
apiVersion: v1
kind: Namespace
metadata:
  name: production
  labels:
    pod-security.kubernetes.io/enforce: restricted
    pod-security.kubernetes.io/audit: restricted
    pod-security.kubernetes.io/warn: restricted
```

## Secrets Management

### Azure Key Vault CSI Driver

**Use Key Vault for secrets (not Kubernetes secrets):**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  key_vault_secrets_provider {
    secret_rotation_enabled  = true
    secret_rotation_interval = "2m"
  }
}

# Grant AKS access to Key Vault
resource "azurerm_key_vault_access_policy" "aks" {
  key_vault_id = azurerm_key_vault.main.id
  tenant_id    = data.azurerm_client_config.current.tenant_id
  object_id    = azurerm_kubernetes_cluster.main.key_vault_secrets_provider[0].secret_identity[0].object_id

  secret_permissions = [
    "Get",
    "List",
  ]
}
```

**Use SecretProviderClass:**

```yaml
apiVersion: secrets-store.csi.x-k8s.io/v1
kind: SecretProviderClass
metadata:
  name: azure-kvname
  namespace: production
spec:
  provider: azure
  parameters:
    usePodIdentity: "false"
    useVMManagedIdentity: "true"
    userAssignedIdentityID: "${workload_identity_client_id}"
    keyvaultName: "${key_vault_name}"
    tenantId: "${tenant_id}"
    objects: |
      array:
        - |
          objectName: db-password
          objectType: secret
          objectVersion: ""
  secretObjects:
    - secretName: db-credentials
      type: Opaque
      data:
        - objectName: db-password
          key: password
```

## Monitoring and Logging

### Azure Monitor Container Insights

**Enable comprehensive monitoring:**

```terraform
resource "azurerm_log_analytics_workspace" "main" {
  name                = "law-aks-${var.environment}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018"
  retention_in_days   = 90
}

resource "azurerm_kubernetes_cluster" "main" {
  oms_agent {
    log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id
  }
}
```

**Enable diagnostic settings:**

```terraform
resource "azurerm_monitor_diagnostic_setting" "aks" {
  name                       = "aks-diagnostics"
  target_resource_id         = azurerm_kubernetes_cluster.main.id
  log_analytics_workspace_id = azurerm_log_analytics_workspace.main.id

  enabled_log {
    category = "kube-apiserver"
  }

  enabled_log {
    category = "kube-audit"
  }

  enabled_log {
    category = "kube-audit-admin"
  }

  enabled_log {
    category = "kube-controller-manager"
  }

  enabled_log {
    category = "kube-scheduler"
  }

  enabled_log {
    category = "cluster-autoscaler"
  }

  enabled_log {
    category = "guard"
  }

  metric {
    category = "AllMetrics"
    enabled  = true
  }
}
```

## Node Security

### OS SKU

**Use Azure Linux (CBL-Mariner) or Ubuntu:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  default_node_pool {
    name       = "system"
    node_count = 3
    vm_size    = "Standard_D4s_v5"
    os_sku     = "AzureLinux"  # Microsoft's hardened Linux distro

    # Or Ubuntu
    # os_sku = "Ubuntu"

    os_disk_type         = "Managed"
    os_disk_size_gb      = 128
    enable_auto_scaling  = true
    min_count            = 3
    max_count            = 10
  }
}
```

### Automatic Upgrades

**Enable automatic node image upgrades:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  automatic_channel_upgrade = "node-image"  # Or "patch", "rapid", "stable"

  maintenance_window {
    allowed {
      day   = "Sunday"
      hours = [2, 3, 4]  # 2 AM - 5 AM maintenance window
    }
  }

  maintenance_window_auto_upgrade {
    frequency    = "Weekly"
    interval     = 1
    duration     = 4
    day_of_week  = "Sunday"
    start_time   = "02:00"
    utc_offset   = "+00:00"
  }

  maintenance_window_node_os {
    frequency    = "Weekly"
    interval     = 1
    duration     = 4
    day_of_week  = "Sunday"
    start_time   = "03:00"
    utc_offset   = "+00:00"
  }
}
```

### Node Encryption

**Enable encryption at host:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  default_node_pool {
    enable_host_encryption = true  # Encrypt temp disk and OS cache
  }
}
```

## High Availability

### Availability Zones

**Deploy across availability zones:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  default_node_pool {
    zones      = ["1", "2", "3"]
    node_count = 3  # At least one per zone
  }
}
```

### System and User Node Pools

**Separate system and user workloads:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  default_node_pool {
    name    = "system"
    vm_size = "Standard_D4s_v5"
    zones   = ["1", "2", "3"]

    node_labels = {
      "workload" = "system"
    }

    node_taints = [
      "CriticalAddonsOnly=true:NoSchedule"
    ]
  }
}

resource "azurerm_kubernetes_cluster_node_pool" "user" {
  name                  = "user"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = "Standard_D8s_v5"
  zones                 = ["1", "2", "3"]

  enable_auto_scaling = true
  min_count           = 3
  max_count           = 20

  node_labels = {
    "workload" = "user"
  }
}
```

### Uptime SLA

**Enable uptime SLA for production:**

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  sku_tier = "Standard"  # Enables 99.95% uptime SLA (zone redundant)
  # vs "Free" tier with no SLA
}
```

## Cost Optimization

### Node Auto-Scaling

```terraform
resource "azurerm_kubernetes_cluster" "main" {
  default_node_pool {
    enable_auto_scaling = true
    min_count           = 3
    max_count           = 10
  }
}
```

### Spot Node Pools

**Use spot instances for fault-tolerant workloads:**

```terraform
resource "azurerm_kubernetes_cluster_node_pool" "spot" {
  name                  = "spot"
  kubernetes_cluster_id = azurerm_kubernetes_cluster.main.id
  vm_size               = "Standard_D8s_v5"
  priority              = "Spot"
  eviction_policy       = "Delete"
  spot_max_price        = -1  # Pay up to regular price

  node_labels = {
    "kubernetes.azure.com/scalesetpriority" = "spot"
  }

  node_taints = [
    "kubernetes.azure.com/scalesetpriority=spot:NoSchedule"
  ]
}
```

## Summary Checklist

- [ ] Azure AD integration enabled with managed RBAC
- [ ] Private cluster enabled (or authorized IP ranges)
- [ ] Azure CNI with network policies enabled
- [ ] Managed identity (system or user-assigned)
- [ ] Workload Identity enabled for pod-level access
- [ ] Local accounts disabled
- [ ] Microsoft Defender for Containers enabled
- [ ] ACR with vulnerability scanning
- [ ] Key Vault CSI driver for secrets
- [ ] Container Insights enabled
- [ ] Diagnostic settings configured
- [ ] Automatic upgrades enabled
- [ ] Availability zones configured
- [ ] System/user node pool separation
- [ ] Uptime SLA enabled (Standard SKU)
- [ ] Pod Security Standards enforced

## References

- [AKS Best Practices](https://docs.microsoft.com/en-us/azure/aks/best-practices)
- [AKS Security Best Practices](https://docs.microsoft.com/en-us/azure/aks/operator-best-practices-cluster-security)
- [Workload Identity](https://docs.microsoft.com/en-us/azure/aks/workload-identity-overview)
- [Azure Policy for AKS](https://docs.microsoft.com/en-us/azure/governance/policy/concepts/policy-for-kubernetes)
- [Azure Security Baseline for AKS](https://docs.microsoft.com/en-us/security/benchmark/azure/baselines/aks-security-baseline)
