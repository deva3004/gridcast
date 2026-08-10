resource "aws_security_group" "alb" {
  name        = "${var.project}-alb"
  description = "Public HTTP entry points for the GridCast dashboard and API"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description = "Dashboard"
    from_port   = 80
    to_port     = 80
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  ingress {
    description = "API"
    from_port   = 8080
    to_port     = 8080
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { project = var.project }
}

# No inbound SSH -- the instance role carries AmazonSSMManagedInstanceCore
# (see iam_ec2.tf), so debugging goes through `aws ssm start-session`
# instead of opening port 22.
resource "aws_security_group" "app" {
  name        = "${var.project}-app"
  description = "GridCast app instance -- only reachable from the ALB"
  vpc_id      = data.aws_vpc.default.id

  ingress {
    description     = "Dashboard, from the ALB only"
    from_port       = 8501
    to_port         = 8501
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  ingress {
    description     = "API, from the ALB only"
    from_port       = 8000
    to_port         = 8000
    protocol        = "tcp"
    security_groups = [aws_security_group.alb.id]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = { project = var.project }
}
