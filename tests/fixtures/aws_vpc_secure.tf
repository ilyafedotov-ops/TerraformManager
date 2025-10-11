resource "aws_vpc" "secure" {
  cidr_block = "10.10.0.0/16"
  tags = { Name = "tfm-secure-vpc" }
}

resource "aws_cloudwatch_log_group" "vpc" {
  name = "/aws/vpc/tfm-secure"
}

resource "aws_iam_role" "flow_logs" {
  name = "tfm-secure-vpc-flow-logs"
  assume_role_policy = <<POLICY
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Principal": {"Service": "vpc-flow-logs.amazonaws.com"},
      "Action": "sts:AssumeRole"
    }
  ]
}
POLICY
}

resource "aws_flow_log" "vpc" {
  log_destination      = aws_cloudwatch_log_group.vpc.arn
  iam_role_arn         = aws_iam_role.flow_logs.arn
  traffic_type         = "ALL"
  vpc_id               = aws_vpc.secure.id
  log_destination_type = "cloud-watch-logs"
}
