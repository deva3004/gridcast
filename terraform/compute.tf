data "aws_ami" "al2023" {
  most_recent = true
  owners      = ["amazon"]

  filter {
    name   = "name"
    values = ["al2023-ami-*-x86_64"]
  }

  filter {
    name   = "state"
    values = ["available"]
  }
}

locals {
  user_data = templatefile("${path.module}/templates/user_data.sh.tpl", {
    aws_region       = var.aws_region
    account_id       = data.aws_caller_identity.current.account_id
    ssm_param_name   = var.ssm_snowflake_param_name
    api_image        = "${aws_ecr_repository.this["api"].repository_url}:latest"
    dashboard_image  = "${aws_ecr_repository.this["dashboard"].repository_url}:latest"
    artifacts_bucket = var.deploy_artifacts_bucket
    artifacts_prefix = var.deploy_artifacts_s3_prefix
    log_group_name   = aws_cloudwatch_log_group.app.name
  })
}

resource "aws_launch_template" "app" {
  name_prefix   = "${var.project}-app-"
  image_id      = data.aws_ami.al2023.id
  instance_type = var.instance_type
  user_data     = base64encode(local.user_data)

  iam_instance_profile {
    arn = aws_iam_instance_profile.app_instance.arn
  }

  network_interfaces {
    associate_public_ip_address = true
    security_groups             = [aws_security_group.app.id]
  }

  # IMDSv2 only.
  metadata_options {
    http_tokens = "required"
  }

  tag_specifications {
    resource_type = "instance"
    tags = {
      project = var.project
      Name    = "${var.project}-app"
    }
  }

  lifecycle {
    create_before_destroy = true
  }
}

resource "aws_autoscaling_group" "app" {
  name                = "${var.project}-app"
  vpc_zone_identifier = data.aws_subnets.default.ids
  min_size            = 1
  max_size            = 2
  desired_capacity    = 1

  # Deliberately EC2, not ELB: MLflow's registry data on this instance is
  # ephemeral (see problem_faced.txt entry 13). An ELB-type health check
  # reacting to a transient app-level hiccup would replace the instance --
  # and wipe that data -- far more often than an actual instance failure
  # would.
  health_check_type = "EC2"

  launch_template {
    id      = aws_launch_template.app.id
    version = aws_launch_template.app.latest_version
  }

  target_group_arns = [
    aws_lb_target_group.dashboard.arn,
    aws_lb_target_group.api.arn,
  ]

  tag {
    key                 = "project"
    value               = var.project
    propagate_at_launch = true
  }
}
