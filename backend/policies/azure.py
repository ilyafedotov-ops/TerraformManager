from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any, Set

from backend.policies.helpers import make_candidate, find_line_number, extract_block


def check_storage_https(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_storage_account"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 2000]
        https_setting = re.search(r'enable_https_traffic_only\s*=\s*(true|false)', block)
        if https_setting and https_setting.group(1) == "true":
            continue
        snippet = https_setting.group(0) if https_setting else match.group(0)
        findings.append(
            make_candidate(
                "AZ-STORAGE-HTTPS",
                file,
                line=find_line_number(text, snippet),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet='enable_https_traffic_only = true\n',
                unique_id=f"AZ-STORAGE-HTTPS::{name}",
            )
        )
    return findings


def check_storage_blob_public(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_storage_account"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 2000]
        public_access = re.search(r'allow_blob_public_access\s*=\s*(true|false)', block)
        if public_access and public_access.group(1) == "true":
            snippet = public_access.group(0)
            findings.append(
                make_candidate(
                    "AZ-STORAGE-BLOB-PUBLIC",
                    file,
                    line=find_line_number(text, snippet),
                    context={"resource": name},
                    snippet=snippet,
                    suggested_fix_snippet='allow_blob_public_access = false\n',
                    unique_id=f"AZ-STORAGE-BLOB-PUBLIC::{name}",
                )
            )
    return findings


def check_storage_min_tls(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_storage_account"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 2000]
        tls_version = re.search(r'min_tls_version\s*=\s*"(TLS1_[0-9])"', block)
        if tls_version and tls_version.group(1) in ("TLS1_2", "TLS1_3"):
            continue
        snippet = tls_version.group(0) if tls_version else match.group(0)
        findings.append(
            make_candidate(
                "AZ-STORAGE-MIN-TLS",
                file,
                line=find_line_number(text, snippet),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet='min_tls_version = "TLS1_2"\n',
                unique_id=f"AZ-STORAGE-MIN-TLS::{name}",
            )
            )
    return findings


def check_backend_azurerm_state(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'backend\s+"azurerm"\s*{', text):
        brace_index = text.find("{", match.start())
        if brace_index == -1:
            continue
        block = extract_block(text, brace_index)
        missing = []
        for field in ("resource_group_name", "storage_account_name", "container_name", "key"):
            if re.search(rf'{field}\s*=\s*', block) is None:
                missing.append(field)
        if not missing:
            continue
        snippet = 'backend "azurerm" ' + block[:200]
        findings.append(
            make_candidate(
                "TF-BACKEND-AZURE-STATE",
                file,
                line=find_line_number(text, match.group(0)),
                context={"missing": ", ".join(missing)},
                snippet=snippet,
                suggested_fix_snippet='  resource_group_name  = "rg-terraform-state"\n  storage_account_name = "ststate"\n  container_name       = "tfstate"\n  key                  = "env/app.tfstate"\n',
                unique_id=f"TF-BACKEND-AZURE-STATE::{file.name}:{match.start()}",
            )
        )
    return findings


def check_storage_private_endpoint(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    storage_names = [match.group(1) for match in re.finditer(r'resource\s+"azurerm_storage_account"\s+"([^"]+)"\s*{', text)]
    if not storage_names:
        return findings

    covered: Set[str] = set()
    for match in re.finditer(r'resource\s+"azurerm_private_endpoint"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 4000]
        storage_ref = re.search(r'private_connection_resource_id\s*=\s*azurerm_storage_account\.([A-Za-z0-9_]+)\.(id|primary_blob_endpoint)', block)
        if storage_ref:
            covered.add(storage_ref.group(1))

    for match in re.finditer(r'resource\s+"azurerm_storage_account"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        if name in covered:
            continue
        snippet = match.group(0)
        findings.append(
            make_candidate(
                "AZ-STORAGE-PRIVATE-ENDPOINT",
                file,
                line=find_line_number(text, snippet),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet=f'resource "azurerm_private_endpoint" "{name}_pe" {{\n  subnet_id = azurerm_subnet.private_endpoints.id\n  private_service_connection {{\n    name                           = "{name}-blob-pe"\n    private_connection_resource_id = azurerm_storage_account.{name}.id\n    subresource_names              = ["blob"]\n  }}\n}}\n',
                unique_id=f"AZ-STORAGE-PRIVATE-ENDPOINT::{name}",
            )
        )
    return findings


def check_log_analytics_health_alert(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    workspace_names = [match.group(1) for match in re.finditer(r'resource\s+"azurerm_log_analytics_workspace"\s+"([^"]+)"\s*{', text)]
    if not workspace_names:
        return findings

    covered: Set[str] = set()
    for match in re.finditer(r'resource\s+"azurerm_monitor_metric_alert"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 4000]
        scopes = re.search(r'scopes\s*=\s*\[([^\]]+)\]', block, re.DOTALL)
        if not scopes:
            continue
        for name in workspace_names:
            if re.search(rf'azurerm_log_analytics_workspace\.{re.escape(name)}\.id', scopes.group(1)):
                covered.add(name)

    for name in workspace_names:
        if name in covered:
            continue
        snippet = ""
        workspace_match = re.search(rf'resource\s+"azurerm_log_analytics_workspace"\s+"{re.escape(name)}"\s*{{', text)
        if workspace_match:
            snippet = workspace_match.group(0)
        findings.append(
            make_candidate(
                "AZ-LAW-HEALTH-ALERT",
                file,
                line=find_line_number(text, snippet) if snippet else 1,
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet=f'resource "azurerm_monitor_metric_alert" "{name}_health" {{\n  scopes     = [azurerm_log_analytics_workspace.{name}.id]\n  description = "Alert when ingestion availability drops below 99%."\n}}\n',
                unique_id=f"AZ-LAW-HEALTH-ALERT::{name}",
            )
        )
    return findings


def check_nsg_open_ssh(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_network_security_rule"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 2000]
        port_22 = re.search(r'destination_port_range\s*=\s*"22"', block)
        allow_rule = re.search(r'access\s*=\s*"Allow"', block)
        any_source = re.search(
            r'(source_address_prefix\s*=\s*"\*")|(source_address_prefixes\s*=\s*\[\s*"0\.0\.0\.0/0"\s*\])',
            block,
        )
        if port_22 and allow_rule and any_source:
            findings.append(
                make_candidate(
                    "AZ-NSG-OPEN-SSH",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='source_address_prefix = "10.0.0.0/24"\n',
                    unique_id=f"AZ-NSG-OPEN-SSH::{name}",
                )
            )
    return findings


def check_nsg_flow_logs(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_network_security_group"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        flow_log_pattern = re.compile(
            rf'resource\s+"azurerm_network_watcher_flow_log"\s+"[^"]*"\s*{{[^}}]*network_security_group_id\s*=\s*azurerm_network_security_group\.{re.escape(name)}\.id',
            re.DOTALL,
        )
        if flow_log_pattern.search(text):
            continue
        findings.append(
            make_candidate(
                "AZ-NET-FLOW-LOGS",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": name},
                snippet=match.group(0),
                suggested_fix_snippet=f'''resource "azurerm_network_watcher_flow_log" "{name}_flow_log" {{
  network_watcher_name     = azurerm_network_watcher.example.name
  resource_group_name      = azurerm_network_watcher.example.resource_group_name
  network_security_group_id = azurerm_network_security_group.{name}.id
  retention_policy {{
    enabled = true
    days    = 90
  }}
  traffic_analytics {{
    enabled               = true
    workspace_id          = azurerm_log_analytics_workspace.example.workspace_id
    workspace_region      = azurerm_log_analytics_workspace.example.location
    workspace_resource_id = azurerm_log_analytics_workspace.example.id
  }}
}}
''',
                unique_id=f"AZ-NET-FLOW-LOGS::{name}",
            )
        )
    return findings


def check_aks_private_cluster(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_kubernetes_cluster"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        private_cluster = re.search(r'private_cluster_enabled\s*=\s*(true|false)', block)
        public_access = re.search(r'public_network_access_enabled\s*=\s*(true|false)', block)
        private_ok = private_cluster and private_cluster.group(1) == "true"
        public_ok = public_access and public_access.group(1) == "false"
        if not (private_ok and public_ok):
            findings.append(
                make_candidate(
                    "AZ-AKS-PRIVATE-API",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='private_cluster_enabled = true\npublic_network_access_enabled = false\n',
                    unique_id=f"AZ-AKS-PRIVATE-API::{name}",
                )
            )
    return findings


def check_aks_azure_policy(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_kubernetes_cluster"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 5000]
        policy_block = re.search(r'(azure_policy\s*{[^}]*enabled\s*=\s*(true|false)[^}]*)', block, re.DOTALL)
        if policy_block and policy_block.group(2) == "true":
            continue
        if policy_block:
            snippet = policy_block.group(1)
            line_target = "azure_policy"
        else:
            snippet = block[:200]
            line_target = match.group(0).splitlines()[0]
        findings.append(
            make_candidate(
                "AZ-AKS-AZURE-POLICY",
                file,
                line=find_line_number(text, line_target),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet='addon_profile {\n  azure_policy {\n    enabled = true\n  }\n}\n',
                unique_id=f"AZ-AKS-AZURE-POLICY::{name}",
            )
        )
    return findings


def check_aks_diagnostic_categories(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    required_categories = {
        "kube-apiserver",
        "kube-audit",
        "kube-audit-admin",
        "kube-controller-manager",
        "kube-scheduler",
        "cluster-autoscaler",
        "guard",
    }

    clusters = {match.group(1): match for match in re.finditer(r'resource\s+"azurerm_kubernetes_cluster"\s+"([^"]+)"\s*{', text)}
    diag_blocks: Dict[str, List[str]] = {}

    for diag_match in re.finditer(r'resource\s+"azurerm_monitor_diagnostic_setting"\s+"([^"]+)"\s*{', text):
        diag_block = text[diag_match.start(): diag_match.start() + 5000]
        target = re.search(r'target_resource_id\s*=\s*azurerm_kubernetes_cluster\.([A-Za-z0-9_]+)\.id', diag_block)
        if not target:
            continue
        cluster_name = target.group(1)
        diag_blocks.setdefault(cluster_name, []).append(diag_block)

    for cluster_name, cluster_match in clusters.items():
        cluster_line = find_line_number(text, cluster_match.group(0).splitlines()[0])
        diag_for_cluster = diag_blocks.get(cluster_name)
        if not diag_for_cluster:
            findings.append(
                make_candidate(
                    "AZ-AKS-DIAGNOSTICS",
                    file,
                    line=cluster_line,
                    context={"resource": cluster_name, "missing_categories": ", ".join(sorted(required_categories))},
                    snippet=cluster_match.group(0)[:200],
                    suggested_fix_snippet='resource "azurerm_monitor_diagnostic_setting" "{name}_diag" {\n  target_resource_id         = azurerm_kubernetes_cluster.{name}.id\n  log_analytics_workspace_id = azurerm_log_analytics_workspace.example.id\n  log { category = "kube-apiserver"        enabled = true }\n}\n'.replace("{name}", cluster_name),
                    unique_id=f"AZ-AKS-DIAGNOSTICS::{cluster_name}",
                )
            )
            continue

        observed: Set[str] = set()
        for diag_block in diag_for_cluster:
            for log_block in re.finditer(r'log\s*{[^}]*}', diag_block, re.DOTALL):
                category = re.search(r'category\s*=\s*"([^"]+)"', log_block.group(0))
                enabled = re.search(r'enabled\s*=\s*(true|false)', log_block.group(0))
                if category and enabled and enabled.group(1) == "true":
                    observed.add(category.group(1))

        missing = sorted(required_categories - observed)
        if missing:
            diag_block_text = diag_for_cluster[0]
            target_line_match = re.search(r'target_resource_id[^\n]*', diag_block_text)
            diag_line = find_line_number(text, target_line_match.group(0)) if target_line_match else cluster_line
            diag_snippet = diag_block_text[:200]
            findings.append(
                make_candidate(
                    "AZ-AKS-DIAGNOSTICS",
                    file,
                    line=diag_line,
                    context={"resource": cluster_name, "missing_categories": ", ".join(missing)},
                    snippet=diag_snippet,
                    suggested_fix_snippet="\n".join(
                        f'log {{\n  category = "{category}"\n  enabled  = true\n}}'
                        for category in missing
                    )
                    + "\n",
                    unique_id=f"AZ-AKS-DIAGNOSTICS::{cluster_name}",
                )
            )
    return findings


def check_key_vault_purge_protection(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_key_vault"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 3000]
        purge = re.search(r'purge_protection_enabled\s*=\s*(true|false)', block)
        soft_delete = re.search(r'soft_delete_enabled\s*=\s*(true|false)', block)
        if not purge or purge.group(1) != "true" or not soft_delete or soft_delete.group(1) != "true":
            findings.append(
                make_candidate(
                    "AZ-KV-PURGE-PROTECTION",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='purge_protection_enabled = true\nsoft_delete_enabled = true\n',
                    unique_id=f"AZ-KV-PURGE-PROTECTION::{name}",
                )
            )
    return findings


def check_key_vault_network(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_key_vault"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 3000]
        public_access = re.search(r'public_network_access_enabled\s*=\s*(true|false)', block)
        has_network_acls = "network_acls" in block
        if not public_access or public_access.group(1) != "false" or not has_network_acls:
            findings.append(
                make_candidate(
                    "AZ-KV-NETWORK",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='public_network_access_enabled = false\nnetwork_acls { default_action = "Deny" }\n',
                    unique_id=f"AZ-KV-NETWORK::{name}",
                )
            )
    return findings


def check_diagnostic_settings(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    kv_names = set(match.group(1) for match in re.finditer(r'resource\s+"azurerm_key_vault"\s+"([^"]+)"\s*{', text))
    sa_names = set(match.group(1) for match in re.finditer(r'resource\s+"azurerm_storage_account"\s+"([^"]+)"\s*{', text))
    nsg_names = set(match.group(1) for match in re.finditer(r'resource\s+"azurerm_network_security_group"\s+"([^"]+)"\s*{', text))
    vnet_names = set(match.group(1) for match in re.finditer(r'resource\s+"azurerm_virtual_network"\s+"([^"]+)"\s*{', text))
    subnet_names = set(match.group(1) for match in re.finditer(r'resource\s+"azurerm_subnet"\s+"([^"]+)"\s*{', text))

    kv_with_diag = set()
    sa_with_diag = set()
    nsg_with_diag = set()
    vnet_with_diag = set()
    subnet_with_diag = set()

    for match in re.finditer(r'resource\s+"azurerm_monitor_diagnostic_setting"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 4000]
        kv_ref = re.search(r'target_resource_id\s*=\s*azurerm_key_vault\.([A-Za-z0-9_]+)\.id', block)
        sa_ref = re.search(r'target_resource_id\s*=\s*azurerm_storage_account\.([A-Za-z0-9_]+)\.id', block)
        nsg_ref = re.search(r'target_resource_id\s*=\s*azurerm_network_security_group\.([A-Za-z0-9_]+)\.id', block)
        vnet_ref = re.search(r'target_resource_id\s*=\s*azurerm_virtual_network\.([A-Za-z0-9_]+)\.id', block)
        subnet_ref = re.search(r'target_resource_id\s*=\s*azurerm_subnet\.([A-Za-z0-9_]+)\.id', block)
        has_law = "log_analytics_workspace_id" in block
        if kv_ref and has_law:
            kv_with_diag.add(kv_ref.group(1))
        if sa_ref and has_law:
            sa_with_diag.add(sa_ref.group(1))
        if nsg_ref and has_law:
            nsg_with_diag.add(nsg_ref.group(1))
        if vnet_ref and has_law:
            vnet_with_diag.add(vnet_ref.group(1))
        if subnet_ref and has_law:
            subnet_with_diag.add(subnet_ref.group(1))

    def append_finding(resource_type: str, names: Set[str], covered: Set[str]) -> None:
        for name in names:
            if name not in covered:
                findings.append(
                    make_candidate(
                        "AZ-DIAGNOSTICS-MISSING",
                        file,
                        line=1,
                        context={"resource": f"{resource_type}.{name}"},
                        snippet="",
                        suggested_fix_snippet=f'resource "azurerm_monitor_diagnostic_setting" "{name}_diag" {{\n  name               = "{name}-diagnostics"\n  target_resource_id = azurerm_{resource_type}.{name}.id\n  log_analytics_workspace_id = azurerm_log_analytics_workspace.example.id\n}}\n',
                        unique_id=f"AZ-DIAGNOSTICS-MISSING::{resource_type}.{name}",
                    )
                )

    append_finding("key_vault", kv_names, kv_with_diag)
    append_finding("storage_account", sa_names, sa_with_diag)
    append_finding("network_security_group", nsg_names, nsg_with_diag)
    append_finding("virtual_network", vnet_names, vnet_with_diag)
    append_finding("subnet", subnet_names, subnet_with_diag)
    return findings


CHECKS = [
    check_storage_https,
    check_storage_blob_public,
    check_storage_min_tls,
    check_backend_azurerm_state,
    check_storage_private_endpoint,
    check_log_analytics_health_alert,
    check_nsg_open_ssh,
    check_nsg_flow_logs,
    check_aks_private_cluster,
    check_aks_azure_policy,
    check_aks_diagnostic_categories,
    check_key_vault_purge_protection,
    check_key_vault_network,
    check_diagnostic_settings,
]
