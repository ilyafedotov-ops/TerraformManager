# TerraformManager Implementation Plan & Status

## Vision
- Provide secure-by-default templates (AWS/Azure/Kubernetes) across generators to accelerate infrastructure provisioning.
- Enforce best-practice policies via static analysis with clear remediation guidance.
- Support both interactive wizard generation and CLI/CI review pipelines with optional terraform validation.

---

# Phase Overview

## Phase A – Platform Core (✅ Completed)
- [x] Finalize `docs/report_schema.json` and CLI output format.
- [x] Add `tfreview.yaml` waivers + severity thresholds (config loader and CLI exit codes).
- [x] Harden initial generators (S3/Storage/K8s Deployment) with secure defaults, tagging, remote state toggles.
- [x] Refactor rule engine into provider modules with metadata registry and RAG explanations.
- [x] Seed knowledge base + link explanations in findings.

### Deliverables
- Streamlit wizard with AWS/Azure/K8s flows.
- CLI with Terraform validate integration.
- Initial policy coverage (S3 HTTPS/SSE, storage HTTPS, kube runAsNonRoot, etc.).
- Optional terraform validation in tests/CI via `TFM_RUN_TERRAFORM_VALIDATE`.

---

## Phase B – Coverage Expansion (🚧 In Progress)

### Generators (✅ done / 🔄 in progress / ☐ planned)
- **AWS**
  - ✅ `aws_vpc_networking.tf.j2`
  - ✅ `aws_observability_baseline.tf.j2`
  - ✅ `aws_rds_baseline.tf.j2`
  - ✅ `aws_alb_waf.tf.j2`
  - ✅ RDS read replicas / multi-region backups
  - ✅ ALB access logging support (S3 bucket + policy helper)
  - ✅ `aws_ecs_fargate_service.tf.j2`
  - ✅ `aws_eks_irsa_service.tf.j2`
- **Azure**
  - ✅ `azure_storage_account.tf.j2`
  - ✅ `azure_vnet_baseline.tf.j2`
  - ✅ `azure_key_vault.tf.j2`
  - ✅ `azure_diagnostics_baseline.tf.j2`
  - 🔄 Diagnostics bundle expansion:
    - ✅ Auto-attach diagnostic settings for NSGs, subnets, and VNets
    - ✅ Introduce private endpoint helper outputs for storage/account targets
- **Kubernetes**
  - ✅ `k8s_deployment.tf.j2`
  - ✅ `k8s_namespace_baseline.tf.j2`
  - ✅ `k8s_pod_security_baseline.tf.j2`
  - ✅ `k8s_psa_namespaces.tf.j2`
  - ✅ `k8s_argo_cd_baseline.tf.j2`
  - ✅ `k8s_hpa_pdb.tf.j2`
  - ✅ Add PodSecurity Standard (baseline/restricted) namespace templates at scale

### Policy Expansion
- **AWS** – DONE: CloudTrail, Config, RDS encryption/backups/PI, ALB HTTPS, WAF association.
  - ✅ EKS: enforce IMDSv2 + control plane logging coverage.
  - ✅ RDS: ensure deletion protection, enhanced monitoring.
  - ✅ S3: access logging, block public access per account.
  - ✅ ECS: detect Fargate services that assign public IPs to tasks.
  - ✅ EKS IRSA: require trust policies to bind to service accounts and the STS audience.
- **Azure** – DONE: storage HTTPS, KV purge/network, diagnostics.
  - ✅ Mirror diagnostics enforcement for NSGs, VNets, and subnets in reviewer (generator parity).
  - ✅ Storage private endpoint association check (generator + reviewer rule).
  - ✅ Log Analytics workspace health alert rule for diagnostics pipelines.
  - ✅ AKS: enforce Azure Policy add-on and control plane diagnostic log coverage.
- **Kubernetes** – DONE: namespace netpol, PDB, privileged/hostPath detection.
  - ✅ Container seccomp profiles / AppArmor annotations.
  - ✅ Horizontal coverage for DaemonSet/StatefulSet runAsNonRoot.

### Tooling / Validation
- ✅ Generator render tests for every template (includes optional terraform validate).
  - 🔄 Sample fixture library per rule for regression testing.
  - 🔄 Add golden fixtures for new generators (terraform plan/validate outputs).

---

## Phase C – Developer Experience & CI Controls (📝 Planned)
- PR comment bot / GitHub App that surfaces top findings with permalinks.
- ✅ Surface severity gating outcomes from `tfreview.yaml` in Streamlit Review tab.
- ✅ Baseline file generation to suppress legacy noise.
- ✅ `.patch` output for autofixable findings (S3 policies, ALB redirect snippets, etc.).
- ✅ Enhanced reporting (HTML summary) for CI artifacts (trend metrics still pending).

---

## Phase D – Pro Enhancements (📝 Planned)
- Offline embedding-based RAG for richer explanations while preserving air-gap.
- Graph-level checks (resource relationships, cross-stack validation).
- Diff-only scanning for PRs to reduce noise on large repos.
- Terraform Cloud/Atlantis integrations, optional remediation pipelines.

---

# Current Status Summary

### Frontend Migration (SvelteKit)
- ✅ Scaffolded SvelteKit workspace with Tailwind + Notus integration and environment-aware token storage synced via cookies/localStorage.
- ✅ Auth flows (login/register/forgot) now persist API tokens and honour redirect targets supplied by protected routes.
- ✅ App layout server load enforces token presence, surfaces sign-out control, and mirrors active token metadata in the UI.
- ✅ Implemented typed API client for FastAPI (`frontend/src/lib/api/client.ts`) and wired dashboard/reports views to live reviewer data.
- ✅ Review tab posts multipart uploads to the new `/scan/upload` endpoint and renders live severity summaries plus artifact download links.
- ✅ Knowledge tab now calls `/knowledge/search`, delivering real RAG snippets with score metadata and quick links to Markdown docs.
- ✅ LLM settings page reads/writes `/settings/llm`, supports configuration validation, and exposes live ping feedback.
- ✅ Knowledge tab now includes manual sync controls for `/knowledge/sync`, enabling GitHub Markdown ingestion without leaving the app.
- ✅ First generator (AWS S3 baseline) now available via `/generators/aws/s3` and a SvelteKit form with direct download/copy helpers.
- 🔄 Next: hook generator/review forms to new FastAPI endpoints, embed report viewer tables, and surface knowledge/doc metrics once APIs are exposed.

## Completed (Phase B to date)
- **AWS Generators**: `aws_vpc_networking`, `aws_observability_baseline`, `aws_rds_baseline`, `aws_alb_waf`, `aws_rds_multi_region`, `aws_ecs_fargate_service`, `aws_eks_irsa_service`.
- **Azure Generators**: `azure_storage_account`, `azure_vnet_baseline`, `azure_key_vault`, `azure_diagnostics_baseline`.
- **Kubernetes Generators**: `k8s_namespace_baseline`, `k8s_hpa_pdb`, `k8s_pod_security_baseline`.
- **Policy Engine**: Expanded AWS/Azure/K8s rule coverage with metadata + knowledge references.
- **CI/Test Enhancements**: Generator render tests with optional `terraform validate`, README updates.

## Active / Upcoming Work
- **Azure Diagnostics Sprint**: integration + CLI smoke tests now cover auto-target coverage via `tests/test_cli_integration.py`.
- **Kubernetes Hardening**: ensure policy rules remain robust for DaemonSet/StatefulSet (fixtures in integration tests complete) and explore namespace baseline coverage.
- **AWS Reliability Enhancements**: scanner covers RDS and S3 guardrails, including backup-plan copy enforcement and multi-region replica fixtures; next polish shared log bucket guidance and explore automated drift remediation samples.
- **Testing Enablement**: added Azure diagnostics integration fixtures (complete + missing, now covering health alerts) and prototyped combined-template `terraform validate` smoke tests (see `tests/test_terraform_validate_smoke.py`).

## Backlog / Future Ideas
- Azure AKS enhancements (Azure Policy add-on, diagnostics for control plane).
- Kubernetes GitOps add-ons (Flux/ArgoCD advanced scenarios) and additional multi-namespace policy automation.
- Phase C items: PR bots, severity gates, baseline file generator.
- Phase D items: embedding RAG, graph analytics, diff scanning.

---

# References
- **Knowledge Base**: `knowledge/` contains curated best practices referenced in findings.
- **Sample Fixtures**: `sample/` holds insecure snippets for regression testing.
- **CI Workflow**: `.github/workflows/terraform-review.yml` runs generator tests with `TFM_RUN_TERRAFORM_VALIDATE=1` and executes the reviewer CLI.

## Completed (as of now)
- **AWS Generators**
  - `aws_vpc_networking.tf.j2`: secure VPC with flow logs/NAT.
  - `aws_observability_baseline.tf.j2`: CloudTrail + Config baseline.
  - `aws_rds_baseline.tf.j2`: encrypted RDS with backups, Performance Insights.
  - `aws_rds_multi_region.tf.j2`: cross-region replica with AWS Backup copy rule.
  - `aws_alb_waf.tf.j2`: HTTPS ALB with ACM cert, HTTP redirect, WAFv2.
  - `aws_ecs_fargate_service.tf.j2`: private Fargate service with CloudWatch logs, ECS Exec, and IAM scaffolding.
  - `aws_eks_irsa_service.tf.j2`: namespace + IRSA role/service account pairing with pod security labels.
- **Azure Generators**
  - `azure_storage_account.tf.j2`: secure storage with firewall toggle and optional private endpoint generator.
  - `azure_vnet_baseline.tf.j2`: VNet + flow logs/diagnostics.
  - `azure_key_vault.tf.j2`: purge-protected KV with private endpoint.
  - `azure_diagnostics_baseline.tf.j2`: Log Analytics + diagnostic settings with optional ingestion health alert and archive storage.
- **Kubernetes Generators**
  - `k8s_namespace_baseline.tf.j2`: quotas, limit ranges, labels.
  - `k8s_hpa_pdb.tf.j2`: autoscaler and PDB.
  - `k8s_pod_security_baseline.tf.j2`: PSP/PSA labeling and RBAC.
- **Policy Engine**
  - AWS: Added rules for RDS encryption/backups/PI, CloudTrail, Config, ALB HTTPS, WAF association, ALB access logging, EKS IMDSv2 enforcement, ECS Fargate public IP detection, and EKS IRSA trust scoping.
  - Azure: Added rules for storage HTTPS, KV purge/network, diagnostics presence.
  - Kubernetes: Added rules for namespace network policy, PDB, privileged containers, hostPath, etc.
- **CI/Test Enhancements**
  - Generator render tests with optional `terraform validate` (controlled via `TFM_RUN_TERRAFORM_VALIDATE`).
  - README updated with new templates and validation instructions.

## In Progress / Next Targets
- Expand Azure baselines to include automated diagnostic coverage for NSGs/VNets/subnets and capture private endpoint requirements in the wizard.
- Add Kubernetes rules/tests for additional PodSecurity admission constraints (seccomp/AppArmor, DaemonSet/StatefulSet inheritance).
- Finalize AWS reliability work: polish shared-bucket access logging guidance and add doc/examples for centralized buckets.
- Explore auto-remediation or patch outputs for common findings (Phase C item).

## Backlog Ideas (beyond Phase B)
- Azure AKS advanced checks (Azure Policy add-on enforcement, diagnostics).
- AWS regional guardrails (config conformance packs) and extended ALB logging scenarios.
- Kubernetes PodSecurity admission baseline for multiple namespaces.
- Phase C/D items: PR comment bot, severity gating, embedding-based RAG, diff-only scanning.
