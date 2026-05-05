# ── Application Load Balancer ─────────────────────────────────────────────────
# Internet-facing — receives traffic from CloudFront only.
# ml-alb-sg restricts inbound to CloudFront managed prefix list.
# Direct access to ALB DNS bypassing CloudFront returns 404.

resource "aws_lb" "main" {
  name               = "${var.project}-${var.env}-alb"
  internal           = false
  load_balancer_type = "application"
  security_groups    = [var.alb_sg_id]
  subnets            = var.public_subnet_ids

  # Prevent accidental deletion of the ALB
  # Set to false in dev so terraform destroy works cleanly
  enable_deletion_protection = false

  tags = {
    Name = "${var.project}-${var.env}-alb"
  }
}

# ── Backend Target Group ──────────────────────────────────────────────────────
# Routes traffic to ECS backend tasks on port 5000.
# Target type = ip — required for Fargate (tasks have ENIs, not EC2 instance IDs).
# ECS service registers task IPs automatically — no manual target registration.

resource "aws_lb_target_group" "backend" {
  name        = "${var.project}-${var.env}-btg"
  port        = 5000
  protocol    = "HTTP"
  vpc_id      = var.vpc_id
  target_type = "ip"

  health_check {
    enabled             = true
    path                = var.health_check_path
    port                = "traffic-port"
    protocol            = "HTTP"
    healthy_threshold   = 2
    unhealthy_threshold = 3
    timeout             = 5
    interval            = 30
    matcher             = "200"
  }

  # ── Stickiness — REQUIRED for Socket.IO ──────────────────────────────────
  # Socket.IO polling flow:
  #   GET /socket.io/ → creates session on ECS Task A → ALB sets AWSALB cookie
  #   POST /socket.io/ → must hit same Task A → ALB reads cookie → routes correctly
  # Without stickiness ALB round-robins POST to a different task = 400 error.
  stickiness {
    type            = "lb_cookie"
    cookie_duration = 3600
    enabled         = true
  }

  tags = {
    Name = "${var.project}-${var.env}-btg"
  }
}

# ── Listener HTTP:80 ──────────────────────────────────────────────────────────
# Default action returns 404 — the ALB should never receive a bare / request.
# Real users always go through CloudFront which routes /api/* and /socket.io/*
# to the ALB via the listener rules below.
# Any request hitting the ALB at / is either misconfigured or a direct scanner.

resource "aws_lb_listener" "http" {
  load_balancer_arn = aws_lb.main.arn
  port              = 80
  protocol          = "HTTP"

  default_action {
    type = "fixed-response"

    fixed_response {
      content_type = "text/plain"
      message_body = "Not found"
      status_code  = "404"
    }
  }

  tags = {
    Name = "${var.project}-${var.env}-listener-http"
  }
}

# ── Listener Rule — /api/* ────────────────────────────────────────────────────
# Priority 1 — routes all API requests to backend target group.
# Two conditions must BOTH be true:
#   1. Path starts with /api/
#   2. X-CloudFront-Secret header matches — proves request came from CloudFront
# If header is missing or wrong → rule does not match → default 404 applies.

resource "aws_lb_listener_rule" "api" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 1

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/api/*"]
    }
  }

  condition {
    http_header {
      http_header_name = "X-CloudFront-Secret"
      values           = [var.cloudfront_secret]
    }
  }

  tags = {
    Name = "${var.project}-${var.env}-rule-api"
  }
}

# ── Listener Rule — /socket.io/* ──────────────────────────────────────────────
# Priority 2 — routes all Socket.IO requests to backend target group.
# Same X-CloudFront-Secret condition as /api/* — same security reasoning.
# AllViewerExceptHostHeader on CloudFront behavior ensures EIO=4 query param
# is forwarded unchanged — without it engineio returns 400.

resource "aws_lb_listener_rule" "socketio" {
  listener_arn = aws_lb_listener.http.arn
  priority     = 2

  action {
    type             = "forward"
    target_group_arn = aws_lb_target_group.backend.arn
  }

  condition {
    path_pattern {
      values = ["/socket.io/*"]
    }
  }

  condition {
    http_header {
      http_header_name = "X-CloudFront-Secret"
      values           = [var.cloudfront_secret]
    }
  }

  tags = {
    Name = "${var.project}-${var.env}-rule-socketio"
  }
}