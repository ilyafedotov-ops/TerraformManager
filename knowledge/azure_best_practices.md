# Azure Best Practices (selected)

- Storage Account: `https_traffic_only_enabled = true`, `allow_nested_items_to_be_public = false`, `min_tls_version >= TLS1_2`, and expose data through Private Endpoints mapped into trusted subnets.
- Diagnostics: route platform telemetry into Log Analytics and add SearchServiceAvailability metric alerts so operators catch ingestion issues quickly.
- NSG: avoid broad `source_address_prefix = "*" / "0.0.0.0/0"` for sensitive ports (22/3389).
- Use Private Endpoints where possible; prefer managed identities over secrets.
- AKS: enable the Azure Policy add-on to enforce pod security standards and workload guardrails; combine with runtime Azure Policy assignments.
- AKS: stream control-plane diagnostics (`kube-apiserver`, audit, controller-manager, scheduler, cluster-autoscaler, guard) into Log Analytics for incident response.
