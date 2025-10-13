from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Any


class _SafeDict(dict):
    """Allow str.format_map to ignore missing keys."""

    def __missing__(self, key: str) -> str:
        return "{" + key + "}"


@dataclass(frozen=True)
class RuleMetadata:
    rule_id: str
    title: str
    severity: str
    description: str
    recommendation: str
    knowledge_ref: str | None = None

    def render(self, context: Dict[str, Any], overrides: Dict[str, Any] | None = None) -> Dict[str, Any]:
        overrides = overrides or {}
        safe_ctx = _SafeDict(context or {})
        rendered = {
            "rule": self.rule_id,
            "title": overrides.get("title", self.title).format_map(safe_ctx),
            "severity": overrides.get("severity", self.severity),
            "description": overrides.get("description", self.description).format_map(safe_ctx),
            "recommendation": overrides.get("recommendation", self.recommendation).format_map(safe_ctx),
            "knowledge_ref": overrides.get("knowledge_ref", self.knowledge_ref),
        }
        return rendered


RULES_REGISTRY: Dict[str, RuleMetadata] = {
    # Syntax
    "SYNTAX-HCL-PARSE": RuleMetadata(
        rule_id="SYNTAX-HCL-PARSE",
        title="Terraform file '{file}' failed to parse",
        severity="HIGH",
        description="Terraform configuration must be valid HCL to be evaluated by terraform.",
        recommendation="Open the file `{file}` and fix the syntax errors, then run `terraform fmt` and `terraform validate`.",
        knowledge_ref="knowledge/terraform_language.md#terraform-language-quick-reference",
    ),
    "SYNTAX-TERRAFORM-VALIDATE": RuleMetadata(
        rule_id="SYNTAX-TERRAFORM-VALIDATE",
        title="`terraform validate` reported errors",
        severity="HIGH",
        description="`terraform validate` surfaced issues in the configuration copied to the temporary workspace.",
        recommendation="Inspect the validate output and fix the reported resources. Re-run `terraform validate` locally before committing.",
        knowledge_ref="knowledge/terraform_language.md#terraform-language-quick-reference",
    ),
    # AWS
    "AWS-S3-SSE": RuleMetadata(
        rule_id="AWS-S3-SSE",
        title="S3 bucket '{resource}' lacks server-side encryption",
        severity="HIGH",
        description="Unencrypted S3 buckets can expose data at rest. Enforce SSE with AES256 or KMS.",
        recommendation="Add `aws_s3_bucket_server_side_encryption_configuration` referencing bucket `{resource}` with SSE defaults.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-S3-PUBLIC-ACL": RuleMetadata(
        rule_id="AWS-S3-PUBLIC-ACL",
        title="S3 bucket '{resource}' uses a public ACL",
        severity="CRITICAL",
        description="Public ACLs make bucket objects readable on the internet. Use block public access controls instead.",
        recommendation="Set `acl = \"private\"` and configure `aws_s3_bucket_public_access_block` for bucket `{resource}`.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-S3-SECURE-TRANSPORT": RuleMetadata(
        rule_id="AWS-S3-SECURE-TRANSPORT",
        title="S3 bucket '{resource}' policy does not enforce HTTPS-only access",
        severity="HIGH",
        description="Bucket policies should require `aws:SecureTransport` to ensure clients use TLS.",
        recommendation="Update the bucket policy for '{resource}' to deny requests where `aws:SecureTransport` is false.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-SG-OPEN-SSH": RuleMetadata(
        rule_id="AWS-SG-OPEN-SSH",
        title="Security group '{resource}' exposes SSH to any source",
        severity="CRITICAL",
        description="Inbound SSH (22/tcp) from `0.0.0.0/0` invites scanning and brute force attacks.",
        recommendation="Restrict SSH on '{resource}' to known CIDR ranges or rely on AWS Systems Manager Session Manager.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-IAM-WILDCARD": RuleMetadata(
        rule_id="AWS-IAM-WILDCARD",
        title="IAM policy '{resource}' uses wildcard permissions",
        severity="HIGH",
        description="Wildcard `Action` or `Resource` in IAM policies grants more access than necessary.",
        recommendation="Replace `*` in IAM policy '{resource}' with specific actions and resource ARNs.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-CLOUDTRAIL-MULTI-REGION": RuleMetadata(
        rule_id="AWS-CLOUDTRAIL-MULTI-REGION",
        title="CloudTrail trail '{resource}' is not multi-region with log validation",
        severity="HIGH",
        description="CloudTrail should capture events across all regions and enable log file validation to detect tampering.",
        recommendation="Set `is_multi_region_trail = true` and `enable_log_file_validation = true` for trail '{resource}'.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-CONFIG-RECORDER": RuleMetadata(
        rule_id="AWS-CONFIG-RECORDER",
        title="AWS Config recorder '{resource}' does not record all resources globally",
        severity="HIGH",
        description="AWS Config should record all resource types, including global resources, with an active delivery channel.",
        recommendation="Ensure `recording_group` for '{resource}' sets `all_supported = true` and `include_global_resource_types = true`, and configure a delivery channel.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-RDS-ENCRYPTION": RuleMetadata(
        rule_id="AWS-RDS-ENCRYPTION",
        title="RDS instance '{resource}' is not encrypted at rest",
        severity="HIGH",
        description="Production RDS instances must enable storage encryption with KMS keys to protect data at rest.",
        recommendation="Set `storage_encrypted = true` and provide `kms_key_id` for RDS instance '{resource}'.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-RDS-BACKUP": RuleMetadata(
        rule_id="AWS-RDS-BACKUP",
        title="RDS instance '{resource}' lacks sufficient backup retention",
        severity="MEDIUM",
        description="Automated backups should be retained for at least 7 days to support recovery objectives.",
        recommendation="Increase `backup_retention_period` to meet your policy (e.g., 7+ days) for RDS instance '{resource}'.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-RDS-PERF-INSIGHTS": RuleMetadata(
        rule_id="AWS-RDS-PERF-INSIGHTS",
        title="RDS instance '{resource}' does not enable Performance Insights",
        severity="LOW",
        description="Performance Insights helps detect query bottlenecks. Enable it for production workloads.",
        recommendation="Set `performance_insights_enabled = true` and specify `performance_insights_kms_key_id` if you manage your own keys.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-ALB-HTTPS": RuleMetadata(
        rule_id="AWS-ALB-HTTPS",
        title="ALB listener '{resource}' is not enforcing HTTPS",
        severity="HIGH",
        description="Application Load Balancers should present HTTPS listeners with certificates and redirect HTTP to HTTPS.",
        recommendation="Ensure HTTPS listeners define `certificate_arn` and `ssl_policy`, and HTTP listeners issue a 301 redirect to HTTPS.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-WAF-ASSOCIATION": RuleMetadata(
        rule_id="AWS-WAF-ASSOCIATION",
        title="ALB '{resource}' is not associated with a WAF web ACL",
        severity="MEDIUM",
        description="Attaching AWS WAF to internet-facing ALBs blocks malicious requests before they reach workloads.",
        recommendation="Create an `aws_wafv2_web_acl_association` referencing ALB '{resource}' and a regional web ACL.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-CW-LOG-RETENTION": RuleMetadata(
        rule_id="AWS-CW-LOG-RETENTION",
        title="CloudWatch log group '{resource}' does not set retention",
        severity="MEDIUM",
        description="Without retention limits, CloudWatch Logs store data indefinitely, driving up storage costs and complicating lifecycle management.",
        recommendation="Set `retention_in_days` (for example 90) on CloudWatch log group '{resource}' to enforce log lifecycle policies.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-VPC-FLOW-LOGS": RuleMetadata(
        rule_id="AWS-VPC-FLOW-LOGS",
        title="VPC '{resource}' is missing flow logs",
        severity="HIGH",
        description="VPC flow logs should capture all traffic for auditing and threat detection.",
        recommendation="Create an `aws_flow_log` targeting VPC '{resource}' that publishes to CloudWatch Logs or S3.",
        knowledge_ref="knowledge/aws_best_practices.md#aws-best-practices-selected",
    ),
    "AWS-ECS-PUBLIC-IP": RuleMetadata(
        rule_id="AWS-ECS-PUBLIC-IP",
        title="ECS service '{resource}' assigns public IPs to tasks",
        severity="HIGH",
        description="Fargate tasks should run in private subnets without public IPs to avoid direct internet exposure.",
        recommendation="Set `assign_public_ip = \"DISABLED\"` within the service `network_configuration` block and route egress through NAT gateways.",
        knowledge_ref="knowledge/aws_ecs_eks_service_hardening.md#ecs-fargate-networking",
    ),
    "AWS-EKS-IRSA-TRUST": RuleMetadata(
        rule_id="AWS-EKS-IRSA-TRUST",
        title="IAM role '{resource}' does not lock IRSA trust to a service account",
        severity="HIGH",
        description="IRSA trust policies must scope `sts:AssumeRoleWithWebIdentity` to a specific namespace/service account and require the `sts.amazonaws.com` audience.",
        recommendation="Add `StringEquals` on `<OIDC_HOST>:sub` for the target service account and `StringLike` on `<OIDC_HOST>:aud` equaling `sts.amazonaws.com`.",
        knowledge_ref="knowledge/aws_ecs_eks_service_hardening.md#eks-irsa-trust-policies",
    ),
    "TF-BACKEND-S3-ENCRYPT": RuleMetadata(
        rule_id="TF-BACKEND-S3-ENCRYPT",
        title="S3 backend is missing encryption or state locking",
        severity="HIGH",
        description="Terraform remote state stored in S3 should enable `encrypt = true` and use a DynamoDB table for state locking.",
        recommendation="Within the `backend \"s3\"` block, set `encrypt = true` and `dynamodb_table` referencing the state lock table.",
        knowledge_ref="knowledge/terraform_language.md#remote-state-basics",
    ),
    # Azure
    "AZ-STORAGE-HTTPS": RuleMetadata(
        rule_id="AZ-STORAGE-HTTPS",
        title="Storage account '{resource}' does not enforce HTTPS",
        severity="HIGH",
        description="Allowing HTTP exposes traffic to downgrade and interception attacks.",
        recommendation="Set `enable_https_traffic_only = true` on storage account '{resource}'.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-STORAGE-BLOB-PUBLIC": RuleMetadata(
        rule_id="AZ-STORAGE-BLOB-PUBLIC",
        title="Storage account '{resource}' allows blob public access",
        severity="HIGH",
        description="Account-level public access makes blobs readable by anyone on the internet.",
        recommendation="Set `allow_blob_public_access = false` for storage account '{resource}'.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-STORAGE-MIN-TLS": RuleMetadata(
        rule_id="AZ-STORAGE-MIN-TLS",
        title="Storage account '{resource}' does not require TLS 1.2+",
        severity="MEDIUM",
        description="Older TLS versions are deprecated and vulnerable; enforce TLS 1.2 or higher.",
        recommendation="Set `min_tls_version = \"TLS1_2\"` for storage account '{resource}'.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "TF-BACKEND-AZURE-STATE": RuleMetadata(
        rule_id="TF-BACKEND-AZURE-STATE",
        title="Azure backend is missing required remote state settings",
        severity="HIGH",
        description="Remote state stored in Azure Storage must include explicit resource group, storage account, container, and key settings to avoid default buckets.",
        recommendation="Specify `resource_group_name`, `storage_account_name`, `container_name`, and `key` inside the `backend \"azurerm\"` block to point at the correct state store.",
        knowledge_ref="knowledge/terraform_language.md#remote-state-basics",
    ),
    "AZ-NSG-OPEN-SSH": RuleMetadata(
        rule_id="AZ-NSG-OPEN-SSH",
        title="NSG rule '{resource}' allows SSH from any source",
        severity="CRITICAL",
        description="Inbound SSH (22/tcp) from `*` or `0.0.0.0/0` is a high-risk exposure.",
        recommendation="Restrict the NSG rule '{resource}' source prefixes to trusted ranges or use Just-in-Time access.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-NET-FLOW-LOGS": RuleMetadata(
        rule_id="AZ-NET-FLOW-LOGS",
        title="NSG '{resource}' is not sending flow logs to Log Analytics",
        severity="HIGH",
        description="NSG flow logs provide network visibility and should be enabled for critical subnets.",
        recommendation="Configure `azurerm_network_watcher_flow_log` for NSG '{resource}' with retention and traffic analytics enabled.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-AKS-PRIVATE-API": RuleMetadata(
        rule_id="AZ-AKS-PRIVATE-API",
        title="AKS cluster '{resource}' exposes a public API endpoint",
        severity="HIGH",
        description="Private clusters reduce attack surface; disable public API access unless explicitly required.",
        recommendation="Set `private_cluster_enabled = true` and `public_network_access_enabled = false` for AKS cluster '{resource}'.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-AKS-AZURE-POLICY": RuleMetadata(
        rule_id="AZ-AKS-AZURE-POLICY",
        title="AKS cluster '{resource}' does not enable the Azure Policy add-on",
        severity="HIGH",
        description="The Azure Policy add-on enforces Kubernetes guardrails (baseline/restricted PSP, pod security, workload identity).",
        recommendation="Ensure the `addon_profile.azure_policy.enabled` flag is set to `true` for AKS cluster '{resource}'.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-AKS-DIAGNOSTICS": RuleMetadata(
        rule_id="AZ-AKS-DIAGNOSTICS",
        title="AKS cluster '{resource}' is missing control plane diagnostic logs",
        severity="HIGH",
        description="Capture `kube-apiserver`, `kube-audit`, `kube-audit-admin`, control-plane, and Azure Policy guard logs to Log Analytics for incident response.",
        recommendation="Add diagnostic settings for cluster '{resource}' that enable all required log categories and stream metrics to Log Analytics.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-KV-PURGE-PROTECTION": RuleMetadata(
        rule_id="AZ-KV-PURGE-PROTECTION",
        title="Key Vault '{resource}' is missing purge protection",
        severity="HIGH",
        description="Purge protection guards against permanent deletion; disablement can lead to data loss.",
        recommendation="Set `purge_protection_enabled = true` and `soft_delete_enabled = true` for key vault '{resource}'.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-KV-NETWORK": RuleMetadata(
        rule_id="AZ-KV-NETWORK",
        title="Key Vault '{resource}' allows public network access",
        severity="HIGH",
        description="Key Vaults should restrict access via private endpoints or trusted IPs; disable public network access.",
        recommendation="Set `public_network_access_enabled = false` and configure network ACLs/private endpoints for key vault '{resource}'.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    "AZ-DIAGNOSTICS-MISSING": RuleMetadata(
        rule_id="AZ-DIAGNOSTICS-MISSING",
        title="Resource '{resource}' lacks diagnostic settings to Log Analytics",
        severity="MEDIUM",
        description="Critical Azure resources should forward logs and metrics to a Log Analytics workspace for auditing and monitoring.",
        recommendation="Add `azurerm_monitor_diagnostic_setting` for '{resource}' with log/metric categories forwarding to Log Analytics.",
        knowledge_ref="knowledge/azure_best_practices.md#azure-best-practices-selected",
    ),
    # Kubernetes
    "K8S-IMAGE-NO-LATEST": RuleMetadata(
        rule_id="K8S-IMAGE-NO-LATEST",
        title="Deployment '{resource}' uses the :latest image tag",
        severity="MEDIUM",
        description="`:latest` prevents reproducible deployments and can pull untested images.",
        recommendation="Pin deployment '{resource}' to a specific image tag or digest.",
        knowledge_ref="knowledge/kubernetes_best_practices.md#kubernetes-best-practices-terraform-kubernetes-provider",
    ),
    "K8S-POD-RUN-AS-NON-ROOT": RuleMetadata(
        rule_id="K8S-POD-RUN-AS-NON-ROOT",
        title="Deployment '{resource}' does not enforce run_as_non_root",
        severity="HIGH",
        description="Running containers as root increases blast radius if compromised.",
        recommendation="Add `security_context { run_as_non_root = true, read_only_root_filesystem = true }` for deployment '{resource}'.",
        knowledge_ref="knowledge/kubernetes_best_practices.md#kubernetes-best-practices-terraform-kubernetes-provider",
    ),
    "K8S-POD-RESOURCES-LIMITS": RuleMetadata(
        rule_id="K8S-POD-RESOURCES-LIMITS",
        title="Deployment '{resource}' lacks resource limits/requests",
        severity="MEDIUM",
        description="Resource limits and requests prevent noisy-neighbor issues and enable scheduling guarantees.",
        recommendation="Define both `limits` and `requests` for CPU and memory on containers in deployment '{resource}'.",
        knowledge_ref="knowledge/kubernetes_best_practices.md#kubernetes-best-practices-terraform-kubernetes-provider",
    ),
    "K8S-NAMESPACE-NETPOL": RuleMetadata(
        rule_id="K8S-NAMESPACE-NETPOL",
        title="Namespace '{resource}' lacks a default NetworkPolicy",
        severity="HIGH",
        description="Without a default deny NetworkPolicy, workloads can communicate freely across namespaces.",
        recommendation="Add a namespace-scoped `kubernetes_network_policy` that defaults ingress/egress to allow-listed sources only.",
        knowledge_ref="knowledge/kubernetes_best_practices.md#kubernetes-best-practices-terraform-kubernetes-provider",
    ),
    "K8S-PDB-REQUIRED": RuleMetadata(
        rule_id="K8S-PDB-REQUIRED",
        title="Deployment '{resource}' with multiple replicas lacks a PodDisruptionBudget",
        severity="HIGH",
        description="PodDisruptionBudgets protect highly-available workloads during voluntary disruptions.",
        recommendation="Create a `kubernetes_pod_disruption_budget` that matches deployment '{resource}' labels.",
        knowledge_ref="knowledge/kubernetes_best_practices.md#kubernetes-best-practices-terraform-kubernetes-provider",
    ),
    "K8S-POD-PRIVILEGED": RuleMetadata(
        rule_id="K8S-POD-PRIVILEGED",
        title="Workload '{resource}' allows privileged containers",
        severity="CRITICAL",
        description="Privileged containers grant host-level access and should be avoided in secure clusters.",
        recommendation="Set `privileged = false` (or remove) in security contexts for '{resource}'.",
        knowledge_ref="knowledge/kubernetes_best_practices.md#kubernetes-best-practices-terraform-kubernetes-provider",
    ),
    "K8S-POD-HOSTPATH": RuleMetadata(
        rule_id="K8S-POD-HOSTPATH",
        title="Workload '{resource}' mounts hostPath volumes",
        severity="HIGH",
        description="HostPath volumes bypass storage isolation and can expose host filesystem data.",
        recommendation="Replace `host_path` volumes in '{resource}' with Kubernetes abstractions (PVC, emptyDir) unless absolutely required.",
        knowledge_ref="knowledge/kubernetes_best_practices.md#kubernetes-best-practices-terraform-kubernetes-provider",
    ),
}


def get_rule_metadata(rule_id: str) -> RuleMetadata:
    return RULES_REGISTRY.get(rule_id, RuleMetadata(
        rule_id=rule_id,
        title=rule_id,
        severity="INFO",
        description="",
        recommendation="",
        knowledge_ref=None,
    ))
