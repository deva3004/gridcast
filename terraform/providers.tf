terraform {
  required_version = ">= 1.5"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    tls = {
      source  = "hashicorp/tls"
      version = "~> 4.0"
    }
  }

  # Local state for now -- fine at portfolio scale with a single operator.
  # Move to an S3 backend (+ DynamoDB lock table) before more than one
  # person ever runs `terraform apply` against this.
}

provider "aws" {
  region = var.aws_region
}
