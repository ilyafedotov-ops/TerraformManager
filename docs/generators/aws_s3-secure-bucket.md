# AWS S3 Secure Bucket

Provision an Amazon S3 bucket hardened with versioning, encryption defaults, public access blocking, and an optional remote state backend.

## Metadata
- **Slug:** `aws/s3-secure-bucket`
- **Provider:** `aws`
- **Service:** `s3`
- **Compliance:** `CIS AWS Foundations 2.1.1`, `NIST SP 800-53 SC-13`
- **Provider Requirements:** hashicorp/aws >= 5.0
- **Features:** `enforces_secure_transport`=True, `supports_remote_state`=True

## Terraform Docs

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | n/a |

## Resources

| Name | Type |
|------|------|
| [aws_s3_bucket.platform_logs_prod](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket) | resource |
| [aws_s3_bucket_policy.platform_logs_prod_secure_transport](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_policy) | resource |
| [aws_s3_bucket_public_access_block.platform_logs_prod](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_public_access_block) | resource |
| [aws_s3_bucket_server_side_encryption_configuration.platform_logs_prod](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_server_side_encryption_configuration) | resource |
| [aws_s3_bucket_versioning.platform_logs_prod](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/s3_bucket_versioning) | resource |

## Inputs

No inputs.

## Outputs

No outputs.
