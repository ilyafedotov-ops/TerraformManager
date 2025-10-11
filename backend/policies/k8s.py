from __future__ import annotations

import re
from pathlib import Path
from typing import List, Dict, Any, Iterable, Tuple

from backend.policies.helpers import make_candidate, find_line_number


WORKLOAD_PATTERN = re.compile(r'resource\s+"kubernetes_(deployment|daemonset|stateful_set|pod)"\s+"([^"]+)"\s*{', re.MULTILINE)


def _iter_workloads(text: str, window: int = 5000) -> Iterable[Tuple[str, str, str, re.Match[str]]]:
    for match in WORKLOAD_PATTERN.finditer(text):
        resource_type = match.group(1)
        name = match.group(2)
        block = text[match.start(): match.start() + window]
        yield resource_type, name, block, match


def check_image_not_latest(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"kubernetes_deployment"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 2500]
        img = re.search(r'image\s*=\s*"([^"]+)"', block)
        if img and img.group(1).endswith(":latest"):
            snippet = img.group(0)
            findings.append(
                make_candidate(
                    "K8S-IMAGE-NO-LATEST",
                    file,
                    line=find_line_number(text, snippet),
                    context={"resource": name, "image": img.group(1)},
                    snippet=snippet,
                    suggested_fix_snippet=snippet.replace(":latest", ":1.0.0"),
                    unique_id=f"K8S-IMAGE-NO-LATEST::{name}",
                )
            )
    return findings


def check_run_as_non_root(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for resource_type, name, block, match in _iter_workloads(text, window=4000):
        run_non_root = re.search(r'run_as_non_root\s*=\s*true', block)
        read_only = re.search(r'read_only_root_filesystem\s*=\s*true', block)
        if run_non_root and read_only:
            continue
        findings.append(
            make_candidate(
                "K8S-POD-RUN-AS-NON-ROOT",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": f"{resource_type}.{name}"},
                snippet=block[:200],
                suggested_fix_snippet='security_context { run_as_non_root = true\n  read_only_root_filesystem = true\n}\n',
                unique_id=f"K8S-POD-RUN-AS-NON-ROOT::{resource_type}.{name}",
            )
        )
    return findings


def check_resources_limits(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for resource_type, name, block, match in _iter_workloads(text, window=4000):
        resources_block = re.search(r'resources\s*{[^}]+}', block, re.DOTALL)
        has_limits = bool(re.search(r'limits\s*=\s*{', block))
        has_requests = bool(re.search(r'requests\s*=\s*{', block))
        if resources_block and has_limits and has_requests:
            continue
        findings.append(
            make_candidate(
                "K8S-POD-RESOURCES-LIMITS",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": f"{resource_type}.{name}"},
                snippet=block[:200],
                suggested_fix_snippet='resources {\n  limits   = { cpu = "500m", memory = "256Mi" }\n  requests = { cpu = "250m", memory = "128Mi" }\n}\n',
                unique_id=f"K8S-POD-RESOURCES-LIMITS::{resource_type}.{name}",
            )
        )
    return findings


def check_namespace_network_policy(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    namespace_refs = []
    for match in re.finditer(r'resource\s+"kubernetes_namespace"\s+"([^"]+)"\s*{', text):
        namespace_refs.append((match.group(1), match.group(0)))

    if not namespace_refs:
        return findings

    policy_refs = set()
    for match in re.finditer(r'resource\s+"kubernetes_network_policy"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 2500]
        ns_ref = re.search(r'namespace\s*=\s*kubernetes_namespace\.([A-Za-z0-9_]+)', block)
        if ns_ref:
            policy_refs.add(ns_ref.group(1))

    for name, snippet in namespace_refs:
        if name not in policy_refs:
            findings.append(
                make_candidate(
                    "K8S-NAMESPACE-NETPOL",
                    file,
                    line=find_line_number(text, snippet),
                    context={"resource": name},
                    snippet=snippet,
                    suggested_fix_snippet=f'''resource "kubernetes_network_policy" "{name}_default_deny" {{
  metadata {{
    name      = "{name}-default-deny"
    namespace = kubernetes_namespace.{name}.metadata[0].name
  }}
  spec {{
    pod_selector {{}}
    policy_types = ["Ingress", "Egress"]
  }}
}}
''',
                    unique_id=f"K8S-NAMESPACE-NETPOL::{name}",
                )
            )
    return findings


def check_seccomp_profile(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for resource_type, name, block, match in _iter_workloads(text, window=5000):
        seccomp_block = re.search(r'seccomp_profile\s*{[^}]*type\s*=\s*"RuntimeDefault"', block, re.DOTALL)
        alpha_annotation = re.search(
            r'container\.seccomp\.security\.alpha\.kubernetes\.io/[A-Za-z0-9_-]+"\s*=\s*"runtime/default"',
            block,
        )
        if seccomp_block or alpha_annotation:
            continue
        findings.append(
            make_candidate(
                "K8S-POD-SECCOMP",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": f"{resource_type}.{name}"},
                snippet=block[:200],
                suggested_fix_snippet='security_context {\n  seccomp_profile {\n    type = "RuntimeDefault"\n  }\n}\n',
                unique_id=f"K8S-POD-SECCOMP::{resource_type}.{name}",
            )
        )
    return findings


def check_apparmor_profile(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    for resource_type, name, block, match in _iter_workloads(text, window=5000):
        apparmor_annotation = re.search(
            r'container\.apparmor\.security\.beta\.kubernetes\.io/[A-Za-z0-9_-]+"\s*=\s*"runtime/default"',
            block,
        )
        if apparmor_annotation:
            continue
        findings.append(
            make_candidate(
                "K8S-POD-APPARMOR",
                file,
                line=find_line_number(text, match.group(0)),
                context={"resource": f"{resource_type}.{name}"},
                snippet=block[:200],
                suggested_fix_snippet='metadata {\n  annotations = {\n    "container.apparmor.security.beta.kubernetes.io/<container>" = "runtime/default"\n  }\n}\n',
                unique_id=f"K8S-POD-APPARMOR::{resource_type}.{name}",
            )
        )
    return findings


def check_pdb_for_deployments(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    deployments: List[Dict[str, Any]] = []
    for match in re.finditer(r'resource\s+"kubernetes_deployment"\s+"([^"]+)"\s*{', text):
        name = match.group(1)
        block = text[match.start(): match.start() + 4000]
        replicas_match = re.search(r'replicas\s*=\s*(\d+)', block)
        replicas = int(replicas_match.group(1)) if replicas_match else 1
        if replicas < 2:
            continue
        label_match = re.search(r'app\s*=\s*"([^"]+)"', block)
        app_label = label_match.group(1) if label_match else None
        if app_label:
            deployments.append({"name": name, "label": app_label, "snippet": block[:200]})

    if not deployments:
        return findings

    pdb_labels = set()
    for match in re.finditer(r'resource\s+"kubernetes_pod_disruption_budget"\s+"([^"]+)"\s*{', text):
        block = text[match.start(): match.start() + 2000]
        label_match = re.search(r'app\s*=\s*"([^"]+)"', block)
        if label_match:
            pdb_labels.add(label_match.group(1))

    for dep in deployments:
        if dep["label"] not in pdb_labels:
            findings.append(
                make_candidate(
                    "K8S-PDB-REQUIRED",
                    file,
                    line=find_line_number(text, dep["snippet"]),
                    context={"resource": dep["name"]},
                    snippet=dep["snippet"],
                    suggested_fix_snippet=f'## Define a PodDisruptionBudget for app "{dep["label"]}"\n',
                    unique_id=f"K8S-PDB-REQUIRED::{dep['name']}",
                )
            )
    return findings


def check_privileged_containers(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    pattern = re.compile(r'resource\s+"kubernetes_(deployment|daemonset|stateful_set|pod)"\s+"([^"]+)"\s*{', re.MULTILINE)
    for match in pattern.finditer(text):
        resource_type = match.group(1)
        name = match.group(2)
        block = text[match.start(): match.start() + 5000]
        if re.search(r'privileged\s*=\s*true', block):
            findings.append(
                make_candidate(
                    "K8S-POD-PRIVILEGED",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": f"{resource_type}.{name}"},
                    snippet=block[:200],
                    suggested_fix_snippet='security_context { privileged = false }\n',
                    unique_id=f"K8S-POD-PRIVILEGED::{resource_type}.{name}",
                )
            )
    return findings


def check_hostpath_volumes(file: Path, text: str) -> List[Dict[str, Any]]:
    findings: List[Dict[str, Any]] = []
    pattern = re.compile(r'resource\s+"kubernetes_(deployment|daemonset|stateful_set|pod)"\s+"([^"]+)"\s*{', re.MULTILINE)
    for match in pattern.finditer(text):
        resource_type = match.group(1)
        name = match.group(2)
        block = text[match.start(): match.start() + 5000]
        if re.search(r'host_path\s*{', block):
            findings.append(
                make_candidate(
                    "K8S-POD-HOSTPATH",
                    file,
                    line=find_line_number(text, match.group(0)),
                    context={"resource": f"{resource_type}.{name}"},
                    snippet=block[:200],
                    suggested_fix_snippet="# Replace host_path volume with managed storage (PVC, emptyDir, etc.)\n",
                    unique_id=f"K8S-POD-HOSTPATH::{resource_type}.{name}",
                )
            )
    return findings


CHECKS = [
    check_image_not_latest,
    check_run_as_non_root,
    check_resources_limits,
    check_seccomp_profile,
    check_apparmor_profile,
    check_namespace_network_policy,
    check_pdb_for_deployments,
    check_privileged_containers,
    check_hostpath_volumes,
]
