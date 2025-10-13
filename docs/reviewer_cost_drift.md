Reviewer Cost & Drift Analysis
==============================

Overview
--------
- Reviewer scans can now surface estimated cloud cost deltas and Terraform plan drift alongside policy findings.
- Cost estimates are powered by [Infracost](https://github.com/infracost/infracost); provide a usage file for usage-based resources.
- Drift insights parse `terraform show -json` output, summarising resource additions/updates/deletes and listing affected addresses.

Running From The CLI
--------------------
- Include `--cost` to run Infracost for each scanned directory. Optionally pass `--cost-usage-file usage.yml`.
- Attach a Terraform plan with `--plan-json plan.json` (use `terraform plan -out` + `terraform show -json`).
- Example:

```bash
terraform plan -out tf.plan
terraform show -json tf.plan > plan.json
python -m backend.cli scan --path environments/prod --out report.json \
  --cost --cost-usage-file infracost-usage.yml \
  --plan-json plan.json \
  --terraform-fmt --terraform-validate
```

Upload Flow In The UI
---------------------
- Navigate to **Generate → Reviewer**, enable **Include cost estimates**, and optionally upload an Infracost usage file.
- Upload a plan JSON to populate the drift section (generate via `terraform show -json`).
- The resulting summary includes:
  - Cost cards (total & delta monthly/hourly) with per-project breakdowns.
  - Drift status (total changes, action counts) with expandable resource/output listings.

Report Structure
----------------
- `report.summary.cost` / `report.cost` expose currency, totals, and per-project data.
- `report.summary.drift` / `report.drift` include action counts, `resource_changes`, `output_changes`, and error messaging.
- HTML reports render cost/d drift sections; CSV/JSON remain unchanged for compatibility.

Tips
----
- Ensure the Infracost CLI is installed where the API/CLI runs (`infracost breakdown --format json` must succeed).
- Set `INFRACOST_API_KEY` (or use open-source pricing files) before running cost analysis.
- Plans should represent the target environment (e.g., run Terraform in a clean workspace to avoid stale state comparisons).
