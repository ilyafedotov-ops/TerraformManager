Terraform Pre-commit Workflow
=============================

Overview
--------
- The TerraformManager CLI can now emit a ready-to-use `.pre-commit-config.yaml` leveraging hooks from the `pre-commit-terraform` collection and Infracost for cost checks.
- `terraform fmt` support is available directly from the `scan` command so you can enforce canonical formatting alongside policy scanning.
- These hooks mirror industry guidance gathered from the `pre-commit-terraform` repository and encourage running `terraform fmt`, `terraform validate`, `terraform_docs`, `tflint`, `checkov`, and `infracost` before merge.

Generate the Config
-------------------
- Run `python -m backend.cli precommit` to scaffold `.pre-commit-config.yaml` in the current directory.
- Use `--out <path>` to change the destination or `--force` to overwrite an existing file.
- Hook list includes:
  - `terraform_fmt` – ensures Terraform code is formatted.
  - `terraform_validate` – catches syntax and provider issues.
  - `terraform_docs` – auto-updates module docs.
  - `terraform_tflint` & `terraform_checkov` – linting and security scanning.
  - `infracost_breakdown` – surfaces cost deltas before merge.

Formatting Integration
----------------------
- The CLI `scan` command accepts `--terraform-fmt` to run `terraform fmt -check -recursive` before scanning.
- Use `--terraform-fmt-write` to rewrite files (`terraform fmt -recursive`) prior to scanning.
- Both flags are mutually exclusive with `--terraform-validate`, so you can chain formatting, validation, and policy scanning from a single command.

CI Recommendations
------------------
- Install Terraform, TFLint, Checkov, and Infracost binaries in CI environments so hooks succeed.
- Supply an `usage.yml` or equivalent Infracost usage file to unlock richer cost analysis.
- Combine the CLI formatting flags with `--terraform-validate` in pipeline scripts to enforce formatting and validation failures as gatekeepers.

Resources
---------
- `https://github.com/antonbabenko/pre-commit-terraform` – authoritative hook definitions.
- `https://github.com/infracost/infracost` – cost estimation CLI documentation.
