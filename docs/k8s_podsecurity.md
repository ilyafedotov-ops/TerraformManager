# Kubernetes PodSecurity Namespace Set

TerraformManager provides a generator (`k8s_psa_namespaces.tf.j2`) that labels multiple namespaces with PodSecurity Standards in one go.

## Wizard usage
1. Open the On-Prem (Kubernetes) tab and select **PodSecurity Namespace Set**.
2. Paste namespace lines (`namespace` or `namespace,team`). Blanks and duplicates are ignored; optional team overrides slot a different team label per namespace.
3. Choose enforcement levels:
   - **Enforce**: `baseline` or `restricted` (default `restricted`).
   - **Warn / Audit**: typically `baseline` to provide softer feedback while tightening workloads.
4. Optional: configure an S3/MinIO backend if you store state centrally.
5. Click **Generate** to review and download the Terraform module.

## Generated outputs
The module creates `kubernetes_namespace` resources with labels:
- `pod-security.kubernetes.io/enforce`
- `pod-security.kubernetes.io/enforce-version`
- `pod-security.kubernetes.io/warn`
- `pod-security.kubernetes.io/audit`

All namespaces inherit the common tags (`managed_by`, `environment`, `team`). Resource names are derived from the namespace string (sanitised and deduplicated when necessary).

## Sample snippet
```hcl
module "psa" {
  source = "../generated/k8s_psa_namespaces.tf"
}
```

Combine this module with workload templates (`k8s_deployment.tf.j2`, `k8s_hpa_pdb.tf.j2`) to ensure applications run in namespaces that align with PodSecurity Baseline/Restricted.
