variable "aws_region" {
  description = "AWS region for all GridCast infra"
  type        = string
  default     = "ap-south-1"
}

variable "github_repo" {
  description = "GitHub repo allowed to assume the CI role, as owner/name"
  type        = string
  default     = "deva3004/gridcast"
}

variable "project" {
  description = "Short name used as a prefix/tag on every resource"
  type        = string
  default     = "gridcast"
}

variable "instance_type" {
  description = "EC2 instance type for the app server (runs api+dashboard+mlflow via docker-compose)"
  type        = string
  default     = "t3.small"
}

variable "ssm_snowflake_param_name" {
  description = "Name of the SecureString SSM parameter holding SNOWFLAKE_* env vars -- created out-of-band, not by Terraform (see problem_faced.txt entry 13)"
  type        = string
  default     = "/gridcast/snowflake-env"
}
