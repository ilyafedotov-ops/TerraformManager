# Azure Function App Baseline

Provision an Azure Linux Function App with managed identity, dedicated storage, Application Insights, and optional VNet integration and diagnostics.

## Metadata
- **Slug:** `azure/function-app`
- **Provider:** `azure`
- **Service:** `appservice`
- **Compliance:** `Azure Security Benchmark LT-1`, `CIS Microsoft Azure Foundations 3.11`
- **Provider Requirements:** hashicorp/azurerm >= 3.90
- **Features:** `includes_application_insights`=True, `supports_vnet_integration`=True

## Terraform Docs

## Providers

| Name | Version |
|------|---------|
| <a name="provider_azurerm"></a> [azurerm](#provider\_azurerm) | n/a |

## Resources

| Name | Type |
|------|------|
| [azurerm_application_insights.func_prod_ai](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/application_insights) | resource |
| [azurerm_linux_function_app.func_app_prod](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/linux_function_app) | resource |
| [azurerm_resource_group.rg_functions](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/resource_group) | resource |
| [azurerm_service_plan.plan_func_prod](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/service_plan) | resource |
| [azurerm_storage_account.stfuncprod](https://registry.terraform.io/providers/hashicorp/azurerm/latest/docs/resources/storage_account) | resource |

## Inputs

No inputs.

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_function_app_identity_principal_id"></a> [function\_app\_identity\_principal\_id](#output\_function\_app\_identity\_principal\_id) | Managed identity principal ID. |
| <a name="output_function_app_name"></a> [function\_app\_name](#output\_function\_app\_name) | Name of the Function App. |
