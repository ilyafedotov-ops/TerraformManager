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
        https_setting = re.search(r'(?:enable_https_traffic_only|https_traffic_only_enabled)\s*=\s*(true|false)', block)
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
                suggested_fix_snippet='https_traffic_only_enabled = true\n',
                unique_id=f"AZ-STORAGE-HTTPS::{name}",
            )
        )
    return findings


def check_storage_blob_public(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_storage_account"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 2000]
        public_access = re.search(r'(?:allow_blob_public_access|allow_nested_items_to_be_public)\s*=\s*(true|false)', block)
        if public_access and public_access.group(1) == "true":
            snippet = public_access.group(0)
            findings.append(
                make_candidate(
                    "AZ-STORAGE-BLOB-PUBLIC",
                    file,
                    line=find_line_number(text, snippet),
                    context={"resource": name},
                    snippet=snippet,
                    suggested_fix_snippet='allow_nested_items_to_be_public = false\n',
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


def check_servicebus_identity(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_servicebus_namespace"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        identity = re.search(r'identity\s*{[^}]*type\s*=\s*"([^"]+)"', block, re.DOTALL)
        if not identity:
            findings.append(
                make_candidate(
                    "AZ-SERVICEBUS-IDENTITY",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": name},
                    snippet=block[:200],
                    suggested_fix_snippet='identity {\n  type = "SystemAssigned"\n}\n',
                    unique_id=f"AZ-SERVICEBUS-IDENTITY::{name}",
                )
            )
            continue
        identity_type = identity.group(1).strip().lower()
        if identity_type == "none":
            findings.append(
                make_candidate(
                    "AZ-SERVICEBUS-IDENTITY",
                    file,
                    line=find_line_number(text, identity.group(0)),
                    context={"resource": name},
                    snippet=identity.group(0),
                    suggested_fix_snippet='identity {\n  type = "SystemAssigned"\n}\n',
                    unique_id=f"AZ-SERVICEBUS-IDENTITY::{name}",
                )
            )
    return findings


def check_servicebus_diagnostics(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    namespaces = [match.group(1) for match in re.finditer(r'resource\s+"azurerm_servicebus_namespace"\s+"([^"]+)"\s*{', text)]
    if not namespaces:
        return findings

    covered: Set[str] = set()
    for match in re.finditer(r'resource\s+"azurerm_monitor_diagnostic_setting"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 4000]
        target = re.search(r'target_resource_id\s*=\s*azurerm_servicebus_namespace\.([A-Za-z0-9_]+)\.id', block)
        has_workspace = re.search(r'log_analytics_workspace_id\s*=\s*', block)
        if target and has_workspace:
            covered.add(target.group(1))

    for name in namespaces:
        if name in covered:
            continue
        snippet_match = re.search(rf'resource\s+"azurerm_servicebus_namespace"\s+"{re.escape(name)}"\s*{{', text)
        snippet = snippet_match.group(0) if snippet_match else ""
        findings.append(
            make_candidate(
                "AZ-SERVICEBUS-DIAGNOSTICS",
                file,
                line=find_line_number(text, snippet) if snippet else 1,
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet=f'resource "azurerm_monitor_diagnostic_setting" "{name}_diag" {{\n  target_resource_id         = azurerm_servicebus_namespace.{name}.id\n  log_analytics_workspace_id = azurerm_log_analytics_workspace.example.id\n}}\n',
                unique_id=f"AZ-SERVICEBUS-DIAGNOSTICS::{name}",
            )
        )
    return findings


def check_servicebus_private_endpoint(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    namespaces = [match.group(1) for match in re.finditer(r'resource\s+"azurerm_servicebus_namespace"\s+"([^"]+)"\s*{', text)]
    if not namespaces:
        return findings

    namespaces_with_private_endpoint: Set[str] = set()
    for match in re.finditer(r'resource\s+"azurerm_private_endpoint"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 4000]
        target = re.search(r'private_connection_resource_id\s*=\s*azurerm_servicebus_namespace\.([A-Za-z0-9_]+)\.id', block)
        if target:
            namespaces_with_private_endpoint.add(target.group(1))

    for name in namespaces:
        if name in namespaces_with_private_endpoint:
            continue
        namespace_match = re.search(rf'resource\s+"azurerm_servicebus_namespace"\s+"{re.escape(name)}"\s*{{', text)
        snippet = namespace_match.group(0) if namespace_match else ""
        findings.append(
            make_candidate(
                "AZ-SERVICEBUS-PRIVATE-ENDPOINT",
                file,
                line=find_line_number(text, snippet) if snippet else 1,
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet=f'resource "azurerm_private_endpoint" "{name}_pe" {{\n  private_service_connection {{\n    private_connection_resource_id = azurerm_servicebus_namespace.{name}.id\n    subresource_names              = ["namespace"]\n  }}\n}}\n',
                unique_id=f"AZ-SERVICEBUS-PRIVATE-ENDPOINT::{name}",
            )
        )
    return findings


FUNCTION_APP_PATTERN = re.compile(r'resource\s+"azurerm_(linux_)?function_app"\s+"([^"]+)"\s*{')


def _function_app_blocks(text: str) -> List[Dict[str, Any]]:
    blocks: List[Dict[str, Any]] = []
    for match in FUNCTION_APP_PATTERN.finditer(text):
        resource_type = "azurerm_linux_function_app" if match.group(1) else "azurerm_function_app"
        name = match.group(2)
        brace_index = text.find("{", match.start())
        if brace_index == -1:
            continue
        block = extract_block(text, brace_index)
        blocks.append(
            {
                "resource_type": resource_type,
                "name": name,
                "block": block,
                "match": match,
            }
        )
    return blocks


def check_function_app_https(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for item in _function_app_blocks(text):
        block = item["block"]
        name = item["name"]
        resource_type = item["resource_type"]
        https_only = re.search(r'https_only\s*=\s*(true|false)', block)
        https_ok = https_only and https_only.group(1) == "true"

        site_config_match = re.search(r'site_config\s*{', block)
        tls_ok = False
        if site_config_match:
            site_block = extract_block(block, site_config_match.end() - 1)
            tls_match = re.search(r'minimum_tls_version\s*=\s*"([^"]+)"', site_block)
            if tls_match and tls_match.group(1) in {"1.2", "1.3"}:
                tls_ok = True

        if https_ok and tls_ok:
            continue

        snippet = block[:200]
        missing_parts = []
        if not https_ok:
            missing_parts.append("https_only")
        if not tls_ok:
            missing_parts.append("minimum_tls_version")

        findings.append(
            make_candidate(
                "AZ-FUNCTION-HTTPS",
                file,
                line=find_line_number(text, item["match"].group(0)),
                context={"resource": name, "resource_type": resource_type, "missing": ", ".join(missing_parts)},
                snippet=snippet,
                suggested_fix_snippet='https_only = true\nsite_config {\n  minimum_tls_version = "1.2"\n}\n',
                unique_id=f"AZ-FUNCTION-HTTPS::{name}",
            )
        )
    return findings


def check_function_app_ftps_disabled(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for item in _function_app_blocks(text):
        block = item["block"]
        name = item["name"]
        resource_type = item["resource_type"]

        site_config_match = re.search(r'site_config\s*{', block)
        if not site_config_match:
            findings.append(
                make_candidate(
                    "AZ-FUNCTION-FTPS-DISABLED",
                    file,
                    line=find_line_number(text, item["match"].group(0)),
                    context={"resource": name, "resource_type": resource_type, "missing": "site_config/ftps_state"},
                    snippet=block[:200],
                    suggested_fix_snippet='site_config {\n  ftps_state = "Disabled"\n}\n',
                    unique_id=f"AZ-FUNCTION-FTPS-DISABLED::{name}",
                )
            )
            continue

        site_block = extract_block(block, site_config_match.end() - 1)
        ftps_match = re.search(r'ftps_state\s*=\s*"([^"]+)"', site_block)
        if ftps_match and ftps_match.group(1).lower() == "disabled":
            continue

        snippet = site_block[:200]
        findings.append(
            make_candidate(
                "AZ-FUNCTION-FTPS-DISABLED",
                file,
                line=find_line_number(text, site_config_match.group(0)),
                context={"resource": name, "resource_type": resource_type},
                snippet=snippet,
                suggested_fix_snippet='ftps_state = "Disabled"\n',
                unique_id=f"AZ-FUNCTION-FTPS-DISABLED::{name}",
            )
        )
    return findings


def check_function_app_diagnostics(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    function_apps = {item["name"]: item for item in _function_app_blocks(text)}
    if not function_apps:
        return findings

    covered: Set[str] = set()
    for match in re.finditer(r'resource\s+"azurerm_monitor_diagnostic_setting"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 4000]
        target = re.search(r'target_resource_id\s*=\s*azurerm_(?:linux_)?function_app\.([A-Za-z0-9_]+)\.id', block)
        has_workspace = "log_analytics_workspace_id" in block
        if target and has_workspace:
            covered.add(target.group(1))

    for name, item in function_apps.items():
        if name in covered:
            continue
        resource_type = item["resource_type"]
        snippet = item["block"][:160]
        findings.append(
            make_candidate(
                "AZ-FUNCTION-DIAGNOSTICS",
                file,
                line=find_line_number(text, item["match"].group(0)),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet=f'resource "azurerm_monitor_diagnostic_setting" "{name}_diag" {{\n  target_resource_id         = {resource_type}.{name}.id\n  log_analytics_workspace_id = azurerm_log_analytics_workspace.example.id\n}}\n',
                unique_id=f"AZ-FUNCTION-DIAGNOSTICS::{name}",
            )
        )
    return findings


def check_api_management_tls(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_api_management"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        brace_index = text.find("{", match.start())
        if brace_index == -1:
            continue
        block = extract_block(text, brace_index)
        properties_match = re.search(r'custom_properties\s*=\s*{', block)
        tls10 = tls11 = False
        if properties_match:
            properties_block = extract_block(block, properties_match.end() - 1)
            tls10_match = re.search(
                r'"Microsoft\.WindowsAzure\.ApiManagement\.Gateway\.Security\.Protocols\.Tls10"\s*=\s*"([^"]+)"',
                properties_block,
            )
            tls11_match = re.search(
                r'"Microsoft\.WindowsAzure\.ApiManagement\.Gateway\.Security\.Protocols\.Tls11"\s*=\s*"([^"]+)"',
                properties_block,
            )
            tls10 = bool(tls10_match and tls10_match.group(1).lower() == "false")
            tls11 = bool(tls11_match and tls11_match.group(1).lower() == "false")
        if tls10 and tls11:
            continue
        snippet = block[:200]
        findings.append(
            make_candidate(
                "AZ-APIM-TLS12",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": name},
                snippet=snippet,
                suggested_fix_snippet='custom_properties = {\n  "Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls10" = "false"\n  "Microsoft.WindowsAzure.ApiManagement.Gateway.Security.Protocols.Tls11" = "false"\n}\n',
                unique_id=f"AZ-APIM-TLS12::{name}",
            )
        )
    return findings


def check_api_management_private_network(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"azurerm_api_management"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        brace_index = text.find("{", match.start())
        if brace_index == -1:
            continue
        block = extract_block(text, brace_index)
        vnet_type_match = re.search(r'virtual_network_type\s*=\s*"([^"]+)"', block)
        vnet_type = vnet_type_match.group(1) if vnet_type_match else None
        subnet_match = re.search(r'subnet_id\s*=\s*"([^"]+)"', block)
        private_enabled = vnet_type and vnet_type not in {"None", "none"}
        subnet_present = subnet_match and subnet_match.group(1).strip()
        if private_enabled and subnet_present:
            continue

        snippet = block[:200]
        missing = []
        if not private_enabled:
            missing.append("virtual_network_type")
        if private_enabled and not subnet_present:
            missing.append("subnet_id")

        findings.append(
            make_candidate(
                "AZ-APIM-PRIVATE-NETWORK",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": name, "missing": ", ".join(missing) if missing else "virtual network configuration"},
                snippet=snippet,
                suggested_fix_snippet='virtual_network_type = "Internal"\nvirtual_network_configuration {\n  subnet_id = "/subscriptions/.../subnets/apim-private"\n}\n',
                unique_id=f"AZ-APIM-PRIVATE-NETWORK::{name}",
            )
        )
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
    check_servicebus_identity,
    check_servicebus_diagnostics,
    check_servicebus_private_endpoint,
    check_function_app_https,
    check_function_app_ftps_disabled,
    check_function_app_diagnostics,
    check_api_management_tls,
    check_api_management_private_network,
]
