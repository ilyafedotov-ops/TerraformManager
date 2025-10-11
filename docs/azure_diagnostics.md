# Azure Diagnostics Baseline Guide

TerraformManager ships a diagnostics baseline generator that wires common Azure resources to a central Log Analytics workspace and (optionally) long-term archival storage. This short guide shows how to get the most out of the wizard and the generated Terraform.

## Auto-target helpers

When generating the baseline you can provide:

- **Subscription ID** – used to assemble fully-qualified resource IDs.
- **Virtual Network name** – attaches diagnostics to the VNet itself.
- **Subnet names** – comma-separated list; each subnet gets its own `azurerm_monitor_diagnostic_setting`.
- **Network Security Groups** – diagnostics attach to each NSG in the resource group.
- **Existing storage accounts** – adds diagnostic settings for storage accounts you already manage.
- **Create storage account + attach diagnostics** – when enabled the template provisions a hardened log archive account and emits diagnostics for it automatically.

Manually entered resource IDs (one per line) are still honoured and you can mix them with auto-generated targets. Duplicate entries are deduplicated.

## Outputs

The generator now exports useful outputs:

| Output | Description |
| --- | --- |
| `log_analytics_workspace_id` | Resource ID for downstream modules (e.g., private endpoints). |
| `diagnostic_setting_ids` | Map of diagnostic setting names to their IDs. |
| `diagnostic_target_resource_ids` | Map of diagnostic setting names to the monitored resource IDs. |
| `diagnostics_storage_account_id` (optional) | Exposed when the template creates the storage account. |
| `diagnostics_storage_account_primary_blob_endpoint` (optional) | Helpful when configuring Private Endpoints or lifecycle policies. |
| `diagnostics_health_alert_id` (optional) | Present when you enable the ingestion health metric alert toggle. |

These outputs make it easier to link additional automation (e.g., private endpoints or alerts) without manual lookups.

## Ingestion health alerts

Enable **Create Log Analytics ingestion health alert** in the wizard to provision an `azurerm_monitor_metric_alert` that watches the workspace `SearchServiceAvailability` metric and pages your action groups if availability drops. The reviewer enforces this alert via rule `AZ-LAW-HEALTH-ALERT`, and the generator exposes the alert ID for downstream wiring. See `sample/azure_diagnostics_health_alert.tf` for a minimal example you can adapt to existing environments.

## Example command

```bash
streamlit run app.py  # open the wizard
```

In the Diagnostics Baseline form:

1. Supply the resource group and workspace details.
2. Paste any additional resource IDs that need coverage.
3. Enter your subscription ID plus VNet/NSG/subnet names.
4. Enable “Create storage account” if you need long-term archival.
5. Click **Generate diagnostics .tf** to review the combined output and download the file.

The reviewer already validates that VNets, subnets, NSGs, storage accounts, and Key Vaults have diagnostics attached, so the combination of generator + static checks keeps coverage enforced.
