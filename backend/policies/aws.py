from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any, Set

from backend.policies.helpers import make_candidate, find_line_number


def check_s3_sse(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_s3_bucket"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        sse_present = re.search(
            rf'resource\s+"aws_s3_bucket_server_side_encryption_configuration"\s+"{re.escape(name)}"', text
        )
        if sse_present:
            continue
        snippet = match.group(0)
        findings.append(
            make_candidate(
                "AWS-S3-SSE",
                file,
                line=find_line_number(text, snippet),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet=f'''resource "aws_s3_bucket_server_side_encryption_configuration" "{name}" {{
  bucket = aws_s3_bucket.{name}.id
  rule {{
    apply_server_side_encryption_by_default {{
      sse_algorithm = "AES256"
    }}
  }}
}}
''',
                unique_id=f"AWS-S3-SSE::{name}",
            )
        )
    return findings


def check_s3_public_acl(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_s3_bucket"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        window = text[match.start(): match.start() + 500]
        acl_match = re.search(r'acl\s*=\s*"(public-read|public-read-write)"', window)
        if not acl_match:
            continue
        acl_value = acl_match.group(1)
        acl_text = acl_match.group(0)
        findings.append(
            make_candidate(
                "AWS-S3-PUBLIC-ACL",
                file,
                line=find_line_number(text, acl_text),
                context={"resource": name, "acl": acl_value},
                snippet=acl_text,
                suggested_fix_snippet='acl = "private"\n',
                unique_id=f"AWS-S3-PUBLIC-ACL::{name}",
            )
        )
    return findings


def check_sg_open_ssh(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_security_group"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 1200]
        port_22 = re.search(r'from_port\s*=\s*22', block)
        cidr_any = re.search(r'cidr_blocks\s*=\s*\[\s*"0\.0\.0\.0/0"\s*\]', block)
        if not (port_22 and cidr_any):
            continue
        findings.append(
            make_candidate(
                "AWS-SG-OPEN-SSH",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": name},
                snippet=block[:200],
                suggested_fix_snippet='cidr_blocks = ["10.0.0.0/16"]\n',
                unique_id=f"AWS-SG-OPEN-SSH::{name}",
            )
        )
    return findings


def check_iam_wildcards(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_iam_policy"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 1600]
        if re.search(r'"Action"\s*:\s*"\*"', block) or re.search(r'"Resource"\s*:\s*"\*"', block):
            findings.append(
                make_candidate(
                    "AWS-IAM-WILDCARD",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='"Action": ["s3:GetObject"], "Resource": ["arn:aws:s3:::example/*"]\n',
                    unique_id=f"AWS-IAM-WILDCARD::{name}",
                )
            )
    return findings


def check_vpc_flow_logs(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_vpc"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        flow_log_pattern = re.compile(
            rf'resource\s+"aws_flow_log"\s+"[^"]*"\s*{{[^}}]*vpc_id\s*=\s*aws_vpc\.{re.escape(name)}\.id',
            re.DOTALL,
        )
        if flow_log_pattern.search(text):
            continue
        snippet = match.group(0)
        findings.append(
            make_candidate(
                "AWS-VPC-FLOW-LOGS",
                file,
                line=find_line_number(text, snippet),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet=f'''resource "aws_flow_log" "{name}_flow_logs" {{
  vpc_id = aws_vpc.{name}.id
  traffic_type = "ALL"
  log_destination_type = "cloud-watch-logs"
  log_destination = aws_cloudwatch_log_group.{name}_flow_logs.arn
  iam_role_arn = aws_iam_role.{name}_flow_logs_role.arn
}}
''',
                unique_id=f"AWS-VPC-FLOW-LOGS::{name}",
            )
        )
    return findings


def check_s3_secure_transport(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    bucket_policies = list(re.finditer(r'resource\s+"aws_s3_bucket_policy"\s+"([^"]+)"\s*{', text))
    for bucket_match in re.finditer(r'resource\s+"aws_s3_bucket"\s+"([^"]+)"\s*{', text):
        bucket_name = bucket_match.group(1)
        policy_found = False
        for policy_match in bucket_policies:
            policy_block = text[policy_match.start(): policy_match.start() + 4000]
            if re.search(rf'aws_s3_bucket\.{re.escape(bucket_name)}\.arn', policy_block):
                if "aws:SecureTransport" in policy_block:
                    policy_found = True
                    break
        if not policy_found:
            snippet = bucket_match.group(0)
            findings.append(
                make_candidate(
                    "AWS-S3-SECURE-TRANSPORT",
                    file,
                    line=find_line_number(text, snippet),
                    context={"resource": bucket_name},
                    snippet=snippet,
                    suggested_fix_snippet=f'''resource "aws_s3_bucket_policy" "{bucket_name}_secure_transport" {{
  bucket = aws_s3_bucket.{bucket_name}.id
  policy = <<POLICY
{{
  "Version": "2012-10-17",
  "Statement": [
    {{
      "Sid": "EnforceTLS",
      "Effect": "Deny",
      "Principal": "*",
      "Action": ["s3:*"],
      "Resource": [
        "${{aws_s3_bucket.{bucket_name}.arn}}",
        "${{aws_s3_bucket.{bucket_name}.arn}}/*"
      ],
      "Condition": {{
        "Bool": {{ "aws:SecureTransport": "false" }}
      }}
    }}
  ]
}}
POLICY
}}
''',
                    unique_id=f"AWS-S3-SECURE-TRANSPORT::{bucket_name}",
                )
            )
    return findings


def check_s3_access_logging(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    bucket_entries = []
    inline_logging: Set[str] = set()
    for match in re.finditer(r'resource\s+"aws_s3_bucket"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        bucket_entries.append((name, match))
        block = text[match.start(): match.start() + 4000]
        if re.search(r'logging\s*{[^}]*target_bucket\s*=', block, re.DOTALL):
            inline_logging.add(name)

    logging_resources: Set[str] = set()
    for match in re.finditer(r'resource\s+"aws_s3_bucket_logging"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 2000]
        bucket_ref = re.search(r'bucket\s*=\s*aws_s3_bucket\.([A-Za-z0-9_]+)\.(id|arn)', block)
        if bucket_ref:
            logging_resources.add(bucket_ref.group(1))

    for name, bucket_match in bucket_entries:
        if name in inline_logging or name in logging_resources:
            continue
        snippet = bucket_match.group(0)
        findings.append(
            make_candidate(
                "AWS-S3-ACCESS-LOGGING",
                file,
                line=find_line_number(text, snippet),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet=f'''resource "aws_s3_bucket_logging" "{name}_logging" {{
  bucket        = aws_s3_bucket.{name}.id
  target_bucket = "my-centralized-log-bucket"
  target_prefix = "{name}/"
}}
''',
                unique_id=f"AWS-S3-ACCESS-LOGGING::{name}",
            )
        )
    return findings


def check_s3_account_public_block(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    bucket_exists = bool(re.search(r'resource\s+"aws_s3_bucket"\s+"([^"]+)"', text))
    block_resources = list(re.finditer(r'resource\s+"aws_s3_account_public_access_block"\s+"([^"]+)"\s*{', text))
    required_flags = (
        "block_public_acls",
        "ignore_public_acls",
        "block_public_policy",
        "restrict_public_buckets",
    )

    if not block_resources:
        if bucket_exists:
            findings.append(
                make_candidate(
                    "AWS-S3-ACCOUNT-BLOCK",
                    file,
                    line=1,
                    context={},
                    snippet="",
                    suggested_fix_snippet='''resource "aws_s3_account_public_access_block" "main" {
  account_id              = data.aws_caller_identity.current.account_id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}
''',
                    unique_id="AWS-S3-ACCOUNT-BLOCK::missing",
                )
            )
        return findings

    for match in block_resources:
        name = match.group(1)
        block = text[match.start(): match.start() + 2000]
        missing = []
        for flag in required_flags:
            flag_match = re.search(rf'{flag}\s*=\s*(true|false)', block)
            if not flag_match or flag_match.group(1) != "true":
                missing.append(flag)
        if missing:
            findings.append(
                make_candidate(
                    "AWS-S3-ACCOUNT-BLOCK",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name, "missing_flags": ", ".join(missing)},
                    snippet=block[:200],
                    suggested_fix_snippet='\n'.join(f"{flag} = true" for flag in required_flags) + "\n",
                    unique_id=f"AWS-S3-ACCOUNT-BLOCK::{name}",
                )
            )
    return findings


def check_cloudtrail_multi_region(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_cloudtrail"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 2500]
        multi_region = re.search(r'is_multi_region_trail\s*=\s*(true|false)', block)
        validation = re.search(r'enable_log_file_validation\s*=\s*(true|false)', block)
        if not multi_region or multi_region.group(1) != "true" or not validation or validation.group(1) != "true":
            findings.append(
                make_candidate(
                    "AWS-CLOUDTRAIL-MULTI-REGION",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='is_multi_region_trail = true\nenable_log_file_validation = true\n',
                    unique_id=f"AWS-CLOUDTRAIL-MULTI-REGION::{name}",
                )
            )
    return findings


def check_config_recorder(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    delivery_channels = bool(re.search(r'resource\s+"aws_config_delivery_channel"', text))
    for match in re.finditer(r'resource\s+"aws_config_configuration_recorder"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 3000]
        all_supported = re.search(r'all_supported\s*=\s*(true|false)', block)
        include_global = re.search(r'include_global_resource_types\s*=\s*(true|false)', block)
        issues = []
        if not all_supported or all_supported.group(1) != "true":
            issues.append('all_supported = true')
        if not include_global or include_global.group(1) != "true":
            issues.append('include_global_resource_types = true')
        if not delivery_channels:
            issues.append("configure aws_config_delivery_channel")
        if issues:
            findings.append(
                make_candidate(
                    "AWS-CONFIG-RECORDER",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet="\n".join(issues) + "\n",
                    unique_id=f"AWS-CONFIG-RECORDER::{name}",
                )
            )
    return findings


def check_rds_encryption(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_db_instance"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        encrypted = re.search(r'storage_encrypted\s*=\s*(true|false)', block)
        kms = re.search(r'kms_key_id\s*=\s*["\']', block)
        if not encrypted or encrypted.group(1) != "true":
            findings.append(
                make_candidate(
                    "AWS-RDS-ENCRYPTION",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='storage_encrypted = true\nkms_key_id        = "arn:aws:kms:region:account:key/your-key-id"\n',
                    unique_id=f"AWS-RDS-ENCRYPTION::{name}",
                )
            )
        elif encrypted.group(1) == "true" and not kms:
            findings.append(
                make_candidate(
                    "AWS-RDS-ENCRYPTION",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='kms_key_id = "arn:aws:kms:region:account:key/your-key-id"\n',
                    unique_id=f"AWS-RDS-ENCRYPTION::{name}",
                )
            )
    return findings


def check_rds_backup_retention(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_db_instance"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        retention = re.search(r'backup_retention_period\s*=\s*(\d+)', block)
        if not retention or int(retention.group(1)) < 7:
            findings.append(
                make_candidate(
                    "AWS-RDS-BACKUP",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='backup_retention_period = 7\npreferred_backup_window = "03:00-04:00"\n',
                    unique_id=f"AWS-RDS-BACKUP::{name}",
                )
            )
    return findings


def check_rds_deletion_protection(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_db_instance"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        deletion = re.search(r'deletion_protection\s*=\s*(true|false)', block)
        if not deletion or deletion.group(1) != "true":
            findings.append(
                make_candidate(
                    "AWS-RDS-DELETION-PROTECTION",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet="deletion_protection = true\n",
                    unique_id=f"AWS-RDS-DELETION-PROTECTION::{name}",
                )
            )
    return findings


def check_rds_enhanced_monitoring(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_db_instance"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        interval = re.search(r'monitoring_interval\s*=\s*(\d+)', block)
        has_monitoring = interval and int(interval.group(1)) > 0
        if not has_monitoring:
            findings.append(
                make_candidate(
                    "AWS-RDS-ENHANCED-MONITORING",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet="monitoring_interval = 60\n",
                    unique_id=f"AWS-RDS-ENHANCED-MONITORING::{name}",
                )
            )
    return findings


def check_rds_performance_insights(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_db_instance"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        pi_enabled = re.search(r'performance_insights_enabled\s*=\s*(true|false)', block)
        if not pi_enabled or pi_enabled.group(1) != "true":
            findings.append(
                make_candidate(
                    "AWS-RDS-PERF-INSIGHTS",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='performance_insights_enabled = true\nperformance_insights_kms_key_id = "arn:aws:kms:region:account:key/your-key-id"\n',
                    unique_id=f"AWS-RDS-PERF-INSIGHTS::{name}",
                )
            )
    return findings


def check_backup_plan_copy_action(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_backup_plan"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        copy_action = re.search(r'copy_action\s*{', block)
        if copy_action:
            continue
        findings.append(
            make_candidate(
                "AWS-BACKUP-CROSS-REGION",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": name},
                snippet=block[:200],
                suggested_fix_snippet='copy_action {\n  destination_vault_arn = aws_backup_vault.replica.arn\n}\n',
                unique_id=f"AWS-BACKUP-CROSS-REGION::{name}",
            )
        )
    return findings


def check_alb_https(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    https_listeners = set()
    alb_names = set(match.group(1) for match in re.finditer(r'resource\s+"aws_lb"\s+"([^"]+)"\s*{', text))
    for match in re.finditer(r'resource\s+"aws_lb_listener"\s+"([^"]+)"\s*{', text):
        listener_name = match.group(1)
        block = text[match.start(): match.start() + 2500]
        protocol = re.search(r'protocol\s*=\s*"([A-Z]+)"', block)
        if not protocol:
            continue
        protocol = protocol.group(1)
        if protocol == "HTTPS":
            https_listeners.add(listener_name)
            if 'certificate_arn' not in block or 'ssl_policy' not in block:
                findings.append(
                    make_candidate(
                        "AWS-ALB-HTTPS",
                        file,
                        line=find_line_number(text, match.group(0)),
                        context={"resource": listener_name},
                        snippet=block[:200],
                        suggested_fix_snippet='certificate_arn = "arn:aws:acm:region:account:certificate/example"\nssl_policy     = "ELBSecurityPolicy-TLS13-1-2-2021-06"\n',
                        unique_id=f"AWS-ALB-HTTPS::{listener_name}",
                    )
                )
        elif protocol == "HTTP":
            if "redirect" not in block:
                findings.append(
                    make_candidate(
                        "AWS-ALB-HTTPS",
                        file,
                        line=find_line_number(text, match.group(0)),
                        context={"resource": listener_name},
                        snippet=block[:200],
                        suggested_fix_snippet='default_action {\n  type = "redirect"\n  redirect {\n    status_code = "HTTP_301"\n    protocol    = "HTTPS"\n    port        = "443"\n  }\n}\n',
                        unique_id=f"AWS-ALB-HTTPS::{listener_name}",
                    )
                )
    return findings


def check_waf_association(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    alb_names = set(match.group(1) for match in re.finditer(r'resource\s+"aws_lb"\s+"([^"]+)"\s*{', text))
    association_targets = set()
    for match in re.finditer(r'resource\s+"aws_wafv2_web_acl_association"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 2000]
        lb_ref = re.search(r'resource_arn\s*=\s*aws_lb\.([A-Za-z0-9_]+)\.arn', block)
        if lb_ref:
            association_targets.add(lb_ref.group(1))
    for lb_name in alb_names:
        if lb_name not in association_targets:
            findings.append(
                make_candidate(
                    "AWS-WAF-ASSOCIATION",
                    file,
                    line=1,
                    context={"resource": lb_name},
                    snippet="",
                    suggested_fix_snippet=f'resource "aws_wafv2_web_acl_association" "{lb_name}_assoc" {{\n  resource_arn = aws_lb.{lb_name}.arn\n  web_acl_arn  = aws_wafv2_web_acl.example.arn\n}}\n',
                    unique_id=f"AWS-WAF-ASSOCIATION::{lb_name}",
                )
            )
    return findings


def check_eks_imdsv2(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    launch_template_security: Dict[str, bool] = {}

    for match in re.finditer(r'resource\s+"aws_launch_template"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 5000]
        metadata_required = re.search(
            r'metadata_options\s*{[^}]*http_tokens\s*=\s*"required"',
            block,
            re.DOTALL,
        )
        launch_template_security[name] = bool(metadata_required)

    for match in re.finditer(r'resource\s+"aws_eks_node_group"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 5000]
        lt_block = re.search(r'launch_template\s*{([^}]*)}', block, re.DOTALL)
        if not lt_block:
            findings.append(
                make_candidate(
                    "AWS-EKS-IMDSV2",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='launch_template {\n  name    = aws_launch_template.example.name\n  version = "$Latest"\n}\n',
                    unique_id=f"AWS-EKS-IMDSV2::{name}",
                )
            )
            continue
        ref = re.search(r'aws_launch_template\.([A-Za-z0-9_]+)\.(name|id)', lt_block.group(1))
        if not ref:
            findings.append(
                make_candidate(
                    "AWS-EKS-IMDSV2",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='launch_template {\n  name = aws_launch_template.example.name\n}\n',
                    unique_id=f"AWS-EKS-IMDSV2::{name}",
                )
            )
            continue
        lt_name = ref.group(1)
        if not launch_template_security.get(lt_name, False):
            findings.append(
                make_candidate(
                    "AWS-EKS-IMDSV2",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='metadata_options {\n  http_endpoint = "enabled"\n  http_tokens   = "required"\n}\n',
                    unique_id=f"AWS-EKS-IMDSV2::{name}",
                )
            )
    return findings


def check_eks_control_plane_logging(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    required = {"api", "audit", "authenticator", "controllerManager", "scheduler"}

    for match in re.finditer(r'resource\s+"aws_eks_cluster"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        logs_match = re.search(r'enabled_cluster_log_types\s*=\s*\[([^\]]*)\]', block, re.DOTALL)
        if not logs_match:
            findings.append(
                make_candidate(
                    "AWS-EKS-CONTROL-LOGS",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]\n',
                    unique_id=f"AWS-EKS-CONTROL-LOGS::{name}",
                )
            )
            continue
        configured = set(re.findall(r'"([^"]+)"', logs_match.group(1)))
        if not required.issubset(configured):
            missing = ", ".join(sorted(required - configured))
            findings.append(
                make_candidate(
                    "AWS-EKS-CONTROL-LOGS",
                    file,
                    line=find_line_number(text, logs_match.group(0)),
                    context={"resource": name, "missing_logs": missing},
                    snippet=logs_match.group(0),
                    suggested_fix_snippet='enabled_cluster_log_types = ["api", "audit", "authenticator", "controllerManager", "scheduler"]\n',
                    unique_id=f"AWS-EKS-CONTROL-LOGS::{name}",
                )
            )
    return findings


def check_alb_access_logging(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_lb"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        lb_type = re.search(r'load_balancer_type\s*=\s*"([^"]+)"', block)
        if lb_type and lb_type.group(1) not in ("application", "network"):
            continue
        access_block = re.search(r'access_logs\s*{[^}]*enabled\s*=\s*(true|false)', block, re.DOTALL)
        attribute_enabled = re.search(r'access_logs\.s3\.enabled\s*=\s*"?(true|1)"?', block)
        has_logging = False
        if access_block and "true" in access_block.group(0):
            has_logging = True
        if attribute_enabled and attribute_enabled.group(1) in ("true", "1"):
            has_logging = True
        if not has_logging:
            findings.append(
                make_candidate(
                    "AWS-ALB-ACCESS-LOGS",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='access_logs {\n  enabled = true\n  bucket  = "my-alb-log-bucket"\n  prefix  = "alb"\n}\n',
                    unique_id=f"AWS-ALB-ACCESS-LOGS::{name}",
                )
            )
    return findings


def check_ecs_public_ip(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_ecs_service"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        if "FARGATE" not in block:
            continue
        assign_match = re.search(
            r'assign_public_ip\s*=\s*(?:"(ENABLED|DISABLED)"|(true|false))',
            block,
            re.IGNORECASE,
        )
        if not assign_match:
            continue
        value = assign_match.group(1) or assign_match.group(2) or ""
        normalized = value.lower()
        if normalized in ("enabled", "true"):
            snippet = assign_match.group(0)
            findings.append(
                make_candidate(
                    "AWS-ECS-PUBLIC-IP",
                    file,
                    line=find_line_number(text, snippet),
                    context={"resource": name},
                    snippet=snippet,
                    suggested_fix_snippet='assign_public_ip = "DISABLED"\n',
                    unique_id=f"AWS-ECS-PUBLIC-IP::{name}",
                )
            )
    return findings


def check_eks_irsa_trust(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"aws_iam_role"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        if "sts:AssumeRoleWithWebIdentity" not in block or "oidc-provider" not in block:
            continue
        assume_match = re.search(
            r'assume_role_policy\s*=\s*(jsonencode\((.*?)\)|<<EOF.*?EOF)',
            block,
            re.DOTALL,
        )
        assume_policy = assume_match.group(0) if assume_match else block[:400]
        missing_parts = []
        if "system:serviceaccount:" not in assume_policy or ":sub" not in assume_policy:
            missing_parts.append("StringEquals condition locking :sub to namespace/service account")
        if ":aud" not in assume_policy or "sts.amazonaws.com" not in assume_policy:
            missing_parts.append("StringLike condition ensuring :aud is sts.amazonaws.com")
        if missing_parts:
            snippet = assume_policy[:200]
            findings.append(
                make_candidate(
                    "AWS-EKS-IRSA-TRUST",
                    file,
                    line=find_line_number(text, assume_policy),
                    context={"resource": name, "missing": "; ".join(missing_parts)},
                    snippet=snippet,
                    suggested_fix_snippet='''Condition = {\n  "StringEquals" = {\n    "<OIDC_HOST>:sub" = "system:serviceaccount:<namespace>:<serviceAccount>"\n  }\n  "StringLike" = {\n    "<OIDC_HOST>:aud" = "sts.amazonaws.com"\n  }\n}\n''',
                    unique_id=f"AWS-EKS-IRSA-TRUST::{name}",
                )
            )
    return findings


CHECKS = [
    check_s3_sse,
    check_s3_public_acl,
    check_sg_open_ssh,
    check_iam_wildcards,
    check_vpc_flow_logs,
    check_s3_secure_transport,
    check_s3_access_logging,
    check_s3_account_public_block,
    check_cloudtrail_multi_region,
    check_config_recorder,
    check_rds_encryption,
    check_rds_backup_retention,
    check_rds_deletion_protection,
    check_rds_enhanced_monitoring,
    check_rds_performance_insights,
    check_backup_plan_copy_action,
    check_alb_https,
    check_waf_association,
    check_ecs_public_ip,
    check_eks_imdsv2,
    check_eks_control_plane_logging,
    check_eks_irsa_trust,
    check_alb_access_logging,
]
