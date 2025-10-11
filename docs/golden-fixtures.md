# Golden Fixtures

TerraformManager captures canonical renders for each generator under `tests/golden/`. These snapshots ensure template regressions are caught automatically.

| Generator | Golden file |
| --- | --- |
| `aws_s3_bucket.tf.j2` | `tests/golden/aws_s3_expected.tf` |
| `aws_observability_baseline.tf.j2` | `tests/golden/aws_observability_expected.tf` |
| `aws_rds_baseline.tf.j2` | `tests/golden/aws_rds_baseline_expected.tf` |
| `aws_rds_multi_region.tf.j2` | `tests/golden/aws_rds_multi_region_expected.tf` |
| `aws_alb_waf.tf.j2` | `tests/golden/aws_alb_expected.tf` |
| `azure_storage_account.tf.j2` | `tests/golden/azure_storage_expected.tf` |
| `azure_vnet_baseline.tf.j2` | `tests/golden/azure_vnet_expected.tf` |
| `azure_key_vault.tf.j2` | `tests/golden/azure_key_vault_expected.tf` |
| `azure_diagnostics_baseline.tf.j2` | `tests/golden/azure_diagnostics_expected.tf` |
| `azure_aks_cluster.tf.j2` | `tests/golden/azure_aks_expected.tf` |
| `k8s_deployment.tf.j2` | `tests/golden/k8s_deployment_expected.tf` |
| `k8s_pod_security_baseline.tf.j2` | `tests/golden/k8s_pod_security_expected.tf` |
| `k8s_psa_namespaces.tf.j2` | `tests/golden/k8s_psa_expected.tf` |
| `k8s_hpa_pdb.tf.j2` | `tests/golden/k8s_hpa_pdb_expected.tf` |

## Refreshing goldens

Regenerate snapshots when template defaults change:

```bash
python3 - <<'PY'
from pathlib import Path
from jinja2 import Template
ctx = dict(name="bucket", bucket_name="example-bucket", region="us-east-1", environment="prod", versioning=True, force_destroy=False, kms_key_id="", owner_tag="platform", cost_center_tag="ENG", enforce_secure_transport=True, backend=None)
rendered = Template(Path('backend/generators/aws_s3_bucket.tf.j2').read_text()).render(**ctx)
Path('tests/golden/aws_s3_expected.tf').write_text(rendered)
PY
```

Run `pytest tests/test_generators_golden.py` afterwards to verify snapshots.
