# Observability for the app instance -- deliberately minimal: no Evidently,
# no Airflow, no new agents. A dashboard over the ALB/target-group metrics
# CloudWatch already emits for free, which nothing currently visualizes.
#
# Container-stdout-to-CloudWatch-Logs (awslogs driver) was dropped for now --
# devTripathi's IAM permissions for the Logs API kept surfacing new
# action/ARN gaps one at a time (problem_faced.txt entry 15), and it wasn't
# worth the remaining iteration time against a hard deadline. Revisit later:
# needs a log group + logs:CreateLogGroup/PutRetentionPolicy/TagResource/
# ListTagsForResource (unsuffixed ARN) plus logs:CreateLogStream/PutLogEvents
# (suffixed ARN) on the instance role.

resource "aws_cloudwatch_dashboard" "app" {
  dashboard_name = "${var.project}-app"

  dashboard_body = jsonencode({
    widgets = [
      {
        type   = "metric"
        x      = 0
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "ALB requests"
          region = var.aws_region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "RequestCount", "LoadBalancer", aws_lb.app.arn_suffix],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 0
        width  = 12
        height = 6
        properties = {
          title  = "Target response time"
          region = var.aws_region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "TargetResponseTime", "LoadBalancer", aws_lb.app.arn_suffix],
          ]
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "5XX errors"
          region = var.aws_region
          stat   = "Sum"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "HTTPCode_ELB_5XX_Count", "LoadBalancer", aws_lb.app.arn_suffix],
            ["AWS/ApplicationELB", "HTTPCode_Target_5XX_Count", "LoadBalancer", aws_lb.app.arn_suffix],
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 6
        width  = 12
        height = 6
        properties = {
          title  = "Target health (api / dashboard)"
          region = var.aws_region
          stat   = "Average"
          period = 60
          metrics = [
            ["AWS/ApplicationELB", "HealthyHostCount", "TargetGroup", aws_lb_target_group.api.arn_suffix, "LoadBalancer", aws_lb.app.arn_suffix],
            ["AWS/ApplicationELB", "UnHealthyHostCount", "TargetGroup", aws_lb_target_group.api.arn_suffix, "LoadBalancer", aws_lb.app.arn_suffix],
            ["AWS/ApplicationELB", "HealthyHostCount", "TargetGroup", aws_lb_target_group.dashboard.arn_suffix, "LoadBalancer", aws_lb.app.arn_suffix],
            ["AWS/ApplicationELB", "UnHealthyHostCount", "TargetGroup", aws_lb_target_group.dashboard.arn_suffix, "LoadBalancer", aws_lb.app.arn_suffix],
          ]
        }
      },
    ]
  })
}
