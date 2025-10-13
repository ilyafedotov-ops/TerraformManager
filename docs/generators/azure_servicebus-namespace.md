# Azure Service Bus Namespace

Provision an Azure Service Bus namespace with managed identities, optional customer-managed keys, private endpoints, diagnostic settings, and queue/topic scaffolding.

## Metadata
- **Slug:** `azure/servicebus-namespace`
- **Provider:** `azure`
- **Service:** `servicebus`
- **Compliance:** `Azure Security Benchmark DP-4`, `CIS Microsoft Azure Foundations 4.5`
- **Provider Requirements:** hashicorp/azurerm >= 3.90
- **Features:** `supports_diagnostics`=True, `supports_private_endpoint`=True

## Terraform Docs

## Providers

| Name | Version |
|------|---------|
| <a name="provider_azurerm"></a> [azurerm](#provider\_azurerm) | n/a |

## Resources

| Name | Type |
|------|------|
| [azurerm_resource_group.rg_integration](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/resource_group) | resource |
| [azurerm_servicebus_namespace.sb_platform_prod](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/servicebus_namespace) | resource |
| [azurerm_servicebus_queue.deadletter](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/servicebus_queue) | resource |
| [azurerm_servicebus_queue.orders](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/servicebus_queue) | resource |
| [azurerm_servicebus_subscription.events_critical](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/servicebus_subscription) | resource |
| [azurerm_servicebus_topic.events](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/servicebus_topic) | resource |

## Inputs

No inputs.

## Outputs

No outputs.
