# ── ECS Cluster ───────────────────────────────────────────────────────────────

resource "aws_ecs_cluster" "main" {
  name = "${var.project}-${var.env}-cluster"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = {
    Name = "${var.project}-${var.env}-cluster"
  }
}

# ── Capacity Providers ────────────────────────────────────────────────────────
# Sets FARGATE as capacity provider.

resource "aws_ecs_cluster_capacity_providers" "main" {
  cluster_name = aws_ecs_cluster.main.name

  capacity_providers = ["FARGATE"]

  default_capacity_provider_strategy {
    capacity_provider = "FARGATE"
    weight            = 1
  }
}

# ── CloudWatch Log Group ──────────────────────────────────────────────────────
# Backend container logs stream here.
# Retention set to 30 days — adjust for prod if compliance requires longer.

resource "aws_cloudwatch_log_group" "backend" {
  name              = "/ecs/${var.project}-${var.env}-backend"
  retention_in_days = 30

  tags = {
    Name = "${var.project}-${var.env}-backend-logs"
  }
}

# ── Backend Task Definition ───────────────────────────────────────────────────
# Defines the container spec for the Flask backend.
# Execution role — used by ECS agent to pull image + inject secrets.
# Task role — used by Flask app at runtime for boto3 EC2 + Secrets Manager calls.

resource "aws_ecs_task_definition" "backend" {
  family                   = "${var.project}-${var.env}-backend"
  requires_compatibilities = ["FARGATE"]
  network_mode             = "awsvpc"
  cpu                      = var.backend_cpu
  memory                   = var.backend_memory
  execution_role_arn       = var.task_execution_role_arn
  task_role_arn            = var.task_role_arn

  container_definitions = jsonencode([
    {
      name      = "backend"
      image     = var.backend_image
      essential = true

      portMappings = [
        {
          # name is required for Service Connect
          name          = "backend-api"
          containerPort = var.app_port
          hostPort      = var.app_port
          protocol      = "tcp"
          appProtocol   = "http"
        }
      ]

      # ── Secrets — injected by ECS agent at task startup ───────────────────
      # Flask reads these as os.getenv() — no boto3 calls needed for these.
      # ECS agent fetches from Secrets Manager and injects before container starts.
      secrets = [
        {
          name      = "DATABASE_URL"
          valueFrom = var.database_url_secret_arn
        },
        {
          name      = "SECRET_KEY"
          valueFrom = var.app_secret_key_arn
        },
        {
          name      = "JWT_SECRET_KEY"
          valueFrom = var.jwt_secret_key_arn
        },
        {
          name      = "ADMIN_PASSWORD"
          valueFrom = var.admin_password_arn
        }
      ]

      # ── Environment — non-sensitive config values ─────────────────────────
      # CORS_ORIGINS — critical: Flask-CORS + Flask-SocketIO both read this.
      # Must be the CloudFront domain — wrong value = all API requests rejected.
      environment = [
        {
          name  = "FLASK_ENV"
          value = "production"
        },
        {
          name  = "CORS_ORIGINS"
          value = var.cors_origins
        },
        {
          name  = "AWS_REGION"
          value = var.aws_region
        },
        {
          name  = "PEM_SECRET_NAME"
          value = var.pem_secret_name
        },
        {
          name  = "PEM_KEY_PATH"
          value = "/app/ml-deploy-key.pem"
        },
        {
          name  = "AWS_KEY_PAIR_NAME"
          value = var.aws_key_pair_name
        },
        {
          name  = "EC2_AMI_ID"
          value = var.ec2_ami_id
        },
        {
          name  = "EC2_INSTANCE_TYPE"
          value = var.ec2_instance_type
        },
        {
          name  = "AWS_DEFAULT_INSTANCE_TYPE"
          value = var.ec2_instance_type
        },
        {
          name  = "EC2_SUBNET_ID"
          value = var.ec2_subnet_id
        },
        {
          name  = "EC2_VPC_ID"
          value = var.ec2_vpc_id
        },
        {
          name  = "PLATFORM_SECURITY_GROUP_ID"
          value = var.platform_security_group_id
        },
        {
          name  = "ADMIN_EMAIL"
          value = var.admin_email
        },
        {
          name  = "RUNNING_IN_AWS"
          value = "true"
        },
        {
          name  = "SECURITY_GROUP_NAME"
          value = var.security_group_name
        }
      ]

      logConfiguration = {
        logDriver = "awslogs"
        options = {
          "awslogs-group"         = aws_cloudwatch_log_group.backend.name
          "awslogs-region"        = var.aws_region
          "awslogs-stream-prefix" = "ecs"
        }
      }
    }
  ])

  tags = {
    Name = "${var.project}-${var.env}-backend-td"
  }
}

# ── Backend ECS Service ───────────────────────────────────────────────────────
# Runs the Flask backend as a Fargate service.
# Service Connect server mode — registers backend.local:5000 in Cloud Map.
# Load balancer — ALB routes /api/* and /socket.io/* to this service via btg.

resource "aws_ecs_service" "backend" {
  name            = "${var.project}-${var.env}-backend"
  cluster         = aws_ecs_cluster.main.id
  task_definition = aws_ecs_task_definition.backend.arn
  desired_count   = var.desired_count
  launch_type     = "FARGATE"

  # Allow Terraform to update the service without forcing a new deployment
  # when only the task definition revision changes.
  force_new_deployment = true

  network_configuration {
    subnets          = var.private_subnet_ids
    security_groups  = [var.ecs_tasks_sg_id]
    assign_public_ip = false
  }


  # ── Load Balancer ─────────────────────────────────────────────────────────
  # ECS registers task IP into btg automatically when task starts.
  # No manual target registration needed.

  load_balancer {
    target_group_arn = var.backend_tg_arn
    container_name   = "backend"
    container_port   = var.app_port
  }

  lifecycle {
    ignore_changes = [task_definition]
  }

  # Ensure task definition and target group exist before service is created.
  depends_on = [aws_ecs_task_definition.backend]

  tags = {
    Name = "${var.project}-${var.env}-backend-service"
  }
}