output "github_actions_role_arn" {
  description = "Set this as the AWS_ROLE_ARN repo variable in GitHub"
  value       = aws_iam_role.github_actions.arn
}

output "ecr_repository_urls" {
  description = "Registry URLs for the api/dashboard images"
  value       = { for k, repo in aws_ecr_repository.this : k => repo.repository_url }
}

output "aws_region" {
  value = var.aws_region
}

output "alb_dns_name" {
  description = "Dashboard: http://<this>/  |  API: http://<this>:8080/health"
  value       = aws_lb.app.dns_name
}
