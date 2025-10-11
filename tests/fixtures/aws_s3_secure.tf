# Secure S3 baseline with logging and account public access block

resource "aws_s3_bucket" "secure" {
  bucket = "tfm-secure-app"
  force_destroy = false
}

resource "aws_s3_bucket_server_side_encryption_configuration" "secure" {
  bucket = aws_s3_bucket.secure.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_policy" "secure_transport" {
  bucket = aws_s3_bucket.secure.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Sid       = "DenyInsecureTransport"
      Effect    = "Deny"
      Principal = "*"
      Action    = ["s3:*"]
      Resource = [
        aws_s3_bucket.secure.arn,
        "${aws_s3_bucket.secure.arn}/*"
      ]
      Condition = {
        Bool = { "aws:SecureTransport" = "false" }
      }
    }]
  })
}

resource "aws_s3_bucket_logging" "secure" {
  bucket        = aws_s3_bucket.secure.id
  target_bucket = "tfm-central-logs"
  target_prefix = "secure/"
}

data "aws_caller_identity" "current" {}

resource "aws_s3_account_public_access_block" "org" {
  account_id              = data.aws_caller_identity.current.account_id
  block_public_acls       = true
  ignore_public_acls      = true
  block_public_policy     = true
  restrict_public_buckets = true
}
