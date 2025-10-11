provider "aws" { region = "us-east-1" }

resource "aws_s3_bucket" "bad_bucket" {
  bucket = "my-insecure-bucket-example-1234"
  acl    = "public-read"
}
# No versioning, no SSE, no public access block
