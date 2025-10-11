# Sample: IAM policy with wildcard permissions

resource "aws_iam_policy" "wildcard" {
  name   = "tfm-insecure-wildcard"
  policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": "*",
      "Resource": "*"
    }
  ]
}
POLICY
}
