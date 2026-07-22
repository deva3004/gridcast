locals {
  ecr_repo_names = ["api", "dashboard"]
}

resource "aws_ecr_repository" "this" {
  for_each = toset(local.ecr_repo_names)

  name = "${var.project}-${each.key}"

  # MUTABLE so CI can keep moving the `latest` tag on every push to main.
  # The `sha-<commit>` tag pushed alongside it is unique per build and is
  # what the audit trail / rollback actually relies on.
  image_tag_mutability = "MUTABLE"

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    project = var.project
  }
}

# Keep the last 10 tagged images and anything untagged for at most 1 day,
# so the registry doesn't grow unbounded from every CI push.
resource "aws_ecr_lifecycle_policy" "this" {
  for_each   = aws_ecr_repository.this
  repository = each.value.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Expire untagged images after 1 day"
        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 1
        }
        action = { type = "expire" }
      },
      {
        rulePriority = 2
        description  = "Keep only the last 10 tagged images"
        selection = {
          tagStatus     = "tagged"
          tagPrefixList = ["sha-", "latest"]
          countType     = "imageCountMoreThan"
          countNumber   = 10
        }
        action = { type = "expire" }
      }
    ]
  })
}
