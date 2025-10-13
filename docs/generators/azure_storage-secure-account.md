# Azure Storage Account Baseline

Create an Azure Storage account with HTTPS-only access, optional firewall restrictions, blob versioning, and private endpoint scaffolding.

## Metadata
- **Slug:** `azure/storage-secure-account`
- **Provider:** `azure`
- **Service:** `storage`
- **Compliance:** `Azure Security Benchmark NS-1`, `CIS Microsoft Azure Foundations 3.2`
- **Provider Requirements:** hashicorp/azurerm >= 3.90
- **Features:** `supports_private_endpoint`=True, `supports_remote_state`=True

## Terraform Docs

## Providers

| Name | Version |
|------|---------|
| <a name="provider_azurerm"></a> [azurerm](#provider\_azurerm) | n/a |

## Resources

| Name | Type |
|------|------|
| [azurerm_resource_group.rg_app](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/resource_group) | resource |
| [azurerm_storage_account.stapp1234567890](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_account) | resource |

## Inputs

No inputs.

## Outputs

No outputs.
