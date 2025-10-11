# Insecure S3 configuration lacking encryption, logging, and account protections

resource "aws_s3_bucket" "insecure" {
  bucket = "tfm-insecure-app"
  acl    = "public-read"
}

# Missing SSE configuration, secure transport policy, and access logging

# No aws_s3_account_public_access_block present to exercise AWS-S3-ACCOUNT-BLOCK rule.
