# Azure API Management Premium Baseline

Deploy Azure API Management with managed identity, optional zone redundancy, diagnostics, and VNet integration.

## Metadata
- **Slug:** `azure/api-management`
- **Provider:** `azure`
- **Service:** `apim`
- **Compliance:** `Azure Security Benchmark NS-1`, `CIS Microsoft Azure Foundations 6.4`
- **Provider Requirements:** hashicorp/azurerm >= 3.90
- **Features:** `supports_diagnostics`=True, `supports_private_networking`=True

## Terraform Docs

## Providers

| Name | Version |
|------|---------|
| <a name="provider_azurerm"></a> [azurerm](#provider\_azurerm) | n/a |

## Resources

| Name | Type |
|------|------|
| [azurerm_api_management.apim_platform_prod](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/api_management) | resource |
| [azurerm_resource_group.rg_apim](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/resource_group) | resource |

## Inputs

No inputs.

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_api_management_gateway_url"></a> [api\_management\_gateway\_url](#output\_api\_management\_gateway\_url) | Gateway URL for the API Management service. |
| <a name="output_api_management_identity_principal_id"></a> [api\_management\_identity\_principal\_id](#output\_api\_management\_identity\_principal\_id) | Managed identity principal ID. |
