data "aws_iam_policy_document" "ec2_trust" {
  statement {
    effect  = "Allow"
    actions = ["sts:AssumeRole"]

    principals {
      type        = "Service"
      identifiers = ["ec2.amazonaws.com"]
    }
  }
}

resource "aws_iam_role" "app_instance" {
  name               = "${var.project}-app-instance"
  assume_role_policy = data.aws_iam_policy_document.ec2_trust.json
}

resource "aws_iam_instance_profile" "app_instance" {
  name = "${var.project}-app-instance"
  role = aws_iam_role.app_instance.name
}

# Session Manager access instead of an SSH key + open port 22.
resource "aws_iam_role_policy_attachment" "ssm_core" {
  role       = aws_iam_role.app_instance.name
  policy_arn = "arn:aws:iam::aws:policy/AmazonSSMManagedInstanceCore"
}

data "aws_iam_policy_document" "app_instance_ecr_pull" {
  statement {
    sid       = "EcrAuth"
    effect    = "Allow"
    actions   = ["ecr:GetAuthorizationToken"]
    resources = ["*"]
  }

  statement {
    sid    = "EcrPull"
    effect = "Allow"
    actions = [
      "ecr:BatchCheckLayerAvailability",
      "ecr:GetDownloadUrlForLayer",
      "ecr:BatchGetImage",
    ]
    resources = [for repo in aws_ecr_repository.this : repo.arn]
  }
}

resource "aws_iam_role_policy" "app_instance_ecr_pull" {
  name   = "ecr-pull"
  role   = aws_iam_role.app_instance.id
  policy = data.aws_iam_policy_document.app_instance_ecr_pull.json
}

# The SNOWFLAKE_* values behind this parameter are created OUT-OF-BAND, not
# by Terraform -- an aws_ssm_parameter resource's value round-trips through
# Terraform state in plaintext even for SecureString, and this project's
# state is local (see providers.tf). Terraform only grants read access to
# whatever already exists at this name. See problem_faced.txt entry 13.
#
# Create it once (before applying this file) with:
#
#   aws ssm put-parameter \
#     --region ap-south-1 \
#     --name "/gridcast/snowflake-env" \
#     --type SecureString \
#     --value "$(cat <<'EOF'
#   SNOWFLAKE_ACCOUNT=...
#   SNOWFLAKE_USER=...
#   SNOWFLAKE_PASSWORD=...
#   SNOWFLAKE_ROLE=...
#   SNOWFLAKE_WAREHOUSE=...
#   SNOWFLAKE_DATABASE=...
#   SNOWFLAKE_SCHEMA=...
#   EOF
#   )"
#
# and re-run with --overwrite if it already exists and the values change.
data "aws_iam_policy_document" "app_instance_ssm_read" {
  statement {
    sid       = "ReadSnowflakeEnv"
    effect    = "Allow"
    actions   = ["ssm:GetParameter"]
    resources = ["arn:aws:ssm:${var.aws_region}:${data.aws_caller_identity.current.account_id}:parameter${var.ssm_snowflake_param_name}"]
  }
}

resource "aws_iam_role_policy" "app_instance_ssm_read" {
  name   = "ssm-read-snowflake-env"
  role   = aws_iam_role.app_instance.id
  policy = data.aws_iam_policy_document.app_instance_ssm_read.json
}

# Read-only access to the pretrained model + feature-cache snapshot, uploaded
# out-of-band to S3 (same reasoning as the SSM parameter above -- Snowflake
# is unreachable right now, so these are pulled in pre-computed rather than
# regenerated at boot). Scoped to one prefix, not the whole bucket.
data "aws_iam_policy_document" "app_instance_s3_read" {
  statement {
    sid       = "ReadDeployArtifacts"
    effect    = "Allow"
    actions   = ["s3:GetObject"]
    resources = ["arn:aws:s3:::${var.deploy_artifacts_bucket}/${var.deploy_artifacts_s3_prefix}/*"]
  }
}

resource "aws_iam_role_policy" "app_instance_s3_read" {
  name   = "s3-read-deploy-artifacts"
  role   = aws_iam_role.app_instance.id
  policy = data.aws_iam_policy_document.app_instance_s3_read.json
}

# Container-stdout-to-CloudWatch-Logs (an instance-role policy for the
# awslogs docker driver) was dropped along with the log group in
# cloudwatch.tf -- see that file's comment.
