# Azure Service Bus Best Practices

## Managed Identities
- Configure `identity { type = "SystemAssigned" }` (or supply user-assigned IDs) on the namespace so workloads authenticate with Azure AD instead of storing shared keys.
- Grant the managed identity appropriate roles (Key Vault Crypto User, Storage Queue Data Contributor) to integrate downstream services securely.
- Capture the generated Terraform inputs from `/docs/generators/azure_servicebus-namespace.md` (accessible via the Docs panel) to understand managed identity and CMK options the generator supports.

## Diagnostics
- Create `azurerm_monitor_diagnostic_setting` covering the namespace with OperationalLogs and `AllMetrics` forwarded to Log Analytics.
- Retain diagnostic data to monitor throttling, authorization failures, and connection churn across environments.

## Networking
- Set `public_network_access_enabled = false` and publish the namespace via Private Endpoints scoped to trusted subnets.
- Link the private endpoint with Private DNS zones (for example `privatelink.servicebus.windows.net`) to guarantee name resolution inside the virtual network.

## Keys & Encryption
- Prefer customer-managed keys by referencing a Key Vault key and granting the namespace’s managed identity access to rotate encryption material.
- Limit Shared Access Signature usage to legacy integrations and rotate keys on a scheduled cadence when unavoidable.
