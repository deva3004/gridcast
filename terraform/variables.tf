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
