# Reuse the account's default VPC/subnets rather than standing up a new
# one -- fine at portfolio scale, and the default VPC's 3 subnets already
# span 3 AZs, satisfying the ALB's 2-AZ minimum with room to spare.
data "aws_vpc" "default" {
  default = true
}

data "aws_subnets" "default" {
  filter {
    name   = "vpc-id"
    values = [data.aws_vpc.default.id]
  }
}

data "aws_caller_identity" "current" {}
