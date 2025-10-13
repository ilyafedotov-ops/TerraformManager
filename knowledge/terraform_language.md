# Terraform Language Quick Reference

- **Blocks**: `provider`, `resource`, `data`, `module`, `variable`, `output`.
- **Expressions**: references `resource.type.name.attr`, `${}` not needed in HCL2.
- **Variables**: define in `variables.tf`, values via `*.tfvars` or environment (`TF_VAR_*`).
- **Modules**: `module "x" { source = "./mod" }`, pass inputs, export outputs.
- **Depends**: implicit via references; explicit `depends_on = [...]` for edge cases.
- **Formatting**: `terraform fmt` to normalize style.
- **Validation**: `terraform validate` after `init`.

## Remote State Basics

- S3 backend: enable `encrypt = true` and configure `dynamodb_table` for state locking alongside unique bucket/key per workspace.
- Azure backend: set `resource_group_name`, `storage_account_name`, `container_name`, and `key` explicitly to control where state is written.
