# Sample: VPC without flow logs to trigger AWS-VPC-FLOW-LOGS

resource "aws_vpc" "insecure" {
  cidr_block = "10.0.0.0/16"
  tags = {
    Name = "tfm-insecure-vpc"
  }
}
