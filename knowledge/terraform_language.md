# Terraform Language Quick Reference

- **Blocks**: `provider`, `resource`, `data`, `module`, `variable`, `output`.
- **Expressions**: references `resource.type.name.attr`, `${}` not needed in HCL2.
- **Variables**: define in `variables.tf`, values via `*.tfvars` or environment (`TF_VAR_*`).
- **Modules**: `module "x" { source = "./mod" }`, pass inputs, export outputs.
- **Depends**: implicit via references; explicit `depends_on = [...]` for edge cases.
- **Formatting**: `terraform fmt` to normalize style.
- **Validation**: `terraform validate` after `init`.
