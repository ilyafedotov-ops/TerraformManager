# Integration Fixtures Overview

TerraformManager includes curated Terraform snippets under `tests/fixtures/` that can be consumed by higher-level integration or CLI smoke tests.

## Azure diagnostics (`tests/fixtures/azure_diagnostics_combined.tf`)

This fixture models a diagnostics baseline similar to what the wizard generates when auto-target helpers are used:

- Creates a resource group, Log Analytics workspace, virtual network, subnet, NSG, and storage account.

- `tests/fixtures/azure_diagnostics_incomplete.tf` — intentionally omits diagnostics for VNet/subnet/NSG/storage to verify missing findings match expectations (now also surfaces `AZ-LAW-HEALTH-ALERT` and `AZ-STORAGE-PRIVATE-ENDPOINT`).
- Attaches diagnostic settings to the subnet, NSG, storage account, and adds a private endpoint plus a Log Analytics ingestion health alert.
- Mirrors the categories suggested by the generator (`VMProtectionAlerts`, `NetworkSecurityGroupEvent`, `StorageRead/Write/Delete`, `AllMetrics`).

The companion config in `tests/data/azure_diagnostics_config.yaml` lists fixture scenarios and expected findings (see `tests/data/azure_diagnostics_missing.json`). Downstream integration tests can load this manifest, run the reviewer, and diff actual findings against the expected set.

### Sample health alert (`sample/azure_diagnostics_health_alert.tf`)

Lightweight example showing only the Log Analytics workspace and the `SearchServiceAvailability` metric alert. Useful when you need to attach the alert to an existing workspace without regenerating the full diagnostics baseline.

## Usage ideas

- CLI smoke: `python -m backend.cli scan --path tests/fixtures/azure_diagnostics_combined.tf --out out.json` and compare to `tests/data/azure_diagnostics_missing.json`.
- Regression detection: expand the JSON expectation file when new diagnostics requirements are added (e.g., private endpoint resources, Azure Firewall).

Keeping fixtures under version control makes it easy to share realistic code snippets across policy, generator, and integration test suites.

- `tests/fixtures/k8s_secure_workloads.tf` / `k8s_insecure_workloads.tf` — secure vs insecure Kubernetes DaemonSet/StatefulSet workloads used for namespace hardening tests (`tests/data/k8s_security_config.yaml`).
- `tests/fixtures/aws_s3_secure.tf` / `aws_s3_insecure.tf` — S3 secure vs insecure baselines covering SSE, secure transport policies, access logging, and account public access blocks (`tests/data/aws_s3_config.yaml`).
- `tests/fixtures/aws_rds_secure.tf`, `aws_rds_multi_region_secure.tf`, `aws_rds_insecure.tf`, and `aws_rds_multi_region_insecure.tf` — RDS healthy vs misconfigured instances validating encryption, backup retention, deletion protection, enhanced monitoring, Performance Insights, and multi-region replica/backups (`tests/data/aws_rds_config.yaml`).
- `tests/fixtures/aws_iam_insecure.tf`, `aws_vpc_no_flow_logs.tf`, and `aws_vpc_secure.tf` — IAM wildcard/flow-log coverage for core AWS policies (`tests/data/aws_misc_config.yaml`).
- `tests/fixtures/k8s_insecure_seccomp.tf / k8s_secure_workloads.tf` complements existing Kubernetes samples for seccomp/AppArmor enforcement.
