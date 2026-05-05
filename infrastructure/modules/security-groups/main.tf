# ── Data Source: CloudFront Managed Prefix List ───────────────────────────────
# Fetches the AWS-managed prefix list that contains all CloudFront edge node IPs.
# This is the correct source for ml-alb-sg — NOT 0.0.0.0/0.
# Direct access to the ALB bypassing CloudFront will be blocked automatically.

data "aws_ec2_managed_prefix_list" "cloudfront" {
  name = "com.amazonaws.global.cloudfront.origin-facing"
}

# ── ALB Security Group ────────────────────────────────────────────────────────
# Only CloudFront edge nodes can reach the ALB on port 80.
# No other inbound traffic is allowed.

resource "aws_security_group" "alb" {
  name        = "${var.project}-${var.env}-alb-sg"
  description = "ALB - inbound from CloudFront edge nodes only"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.project}-${var.env}-alb-sg"
  }
}

resource "aws_security_group_rule" "alb_inbound_cloudfront" {
  security_group_id = aws_security_group.alb.id
  type              = "ingress"
  description       = "HTTP from CloudFront managed prefix list"
  from_port         = 80
  to_port           = 80
  protocol          = "tcp"
  prefix_list_ids   = [data.aws_ec2_managed_prefix_list.cloudfront.id]
}

resource "aws_security_group_rule" "alb_outbound_all" {
  security_group_id = aws_security_group.alb.id
  type              = "egress"
  description       = "Allow all outbound"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

# ── ECS Tasks Security Group ──────────────────────────────────────────────────
# ECS tasks only accept traffic from the ALB.
# Port 80 — for any HTTP health checks ALB may send.
# Port 5000 — Flask/Gunicorn backend.

resource "aws_security_group" "ecs_tasks" {
  name        = "${var.project}-${var.env}-ecs-tasks-sg"
  description = "ECS tasks - inbound from ALB only"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.project}-${var.env}-ecs-tasks-sg"
  }
}

resource "aws_security_group_rule" "ecs_inbound_alb_http" {
  security_group_id        = aws_security_group.ecs_tasks.id
  type                     = "ingress"
  description              = "HTTP from ALB"
  from_port                = 80
  to_port                  = 80
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
}

resource "aws_security_group_rule" "ecs_inbound_alb_app" {
  security_group_id        = aws_security_group.ecs_tasks.id
  type                     = "ingress"
  description              = "App port 5000 from ALB"
  from_port                = 5000
  to_port                  = 5000
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.alb.id
}

resource "aws_security_group_rule" "ecs_outbound_all" {
  security_group_id = aws_security_group.ecs_tasks.id
  type              = "egress"
  description       = "Allow all outbound - ECR pull, RDS, Secrets Manager"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}

# ── RDS Security Group ────────────────────────────────────────────────────────
# RDS only accepts Postgres connections from ECS tasks.
# No direct access from anywhere else.

resource "aws_security_group" "db" {
  name        = "${var.project}-${var.env}-db-sg"
  description = "RDS - inbound from ECS tasks only"
  vpc_id      = var.vpc_id

  tags = {
    Name = "${var.project}-${var.env}-db-sg"
  }
}

resource "aws_security_group_rule" "db_inbound_ecs" {
  security_group_id        = aws_security_group.db.id
  type                     = "ingress"
  description              = "PostgreSQL from ECS tasks"
  from_port                = 5432
  to_port                  = 5432
  protocol                 = "tcp"
  source_security_group_id = aws_security_group.ecs_tasks.id
}

resource "aws_security_group_rule" "db_outbound_all" {
  security_group_id = aws_security_group.db.id
  type              = "egress"
  description       = "Allow all outbound"
  from_port         = 0
  to_port           = 0
  protocol          = "-1"
  cidr_blocks       = ["0.0.0.0/0"]
}