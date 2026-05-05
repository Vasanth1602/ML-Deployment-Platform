variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
}

# ── Network ───────────────────────────────────────────────────────────────────

variable "private_subnet_ids" {
  description = "Private subnet IDs — ECS tasks run here, not in public subnets"
  type        = list(string)
}

variable "ecs_tasks_sg_id" {
  description = "Security group ID for ECS tasks — from module.security_groups.ecs_tasks_sg_id"
  type        = string
}

# ── IAM ───────────────────────────────────────────────────────────────────────

variable "task_execution_role_arn" {
  description = "ECS task execution role ARN — used by ECS agent to pull image and inject secrets"
  type        = string
}

variable "task_role_arn" {
  description = "ECS task role ARN — used by Flask app at runtime for boto3 calls"
  type        = string
}

# ── Container ─────────────────────────────────────────────────────────────────

variable "backend_image" {
  description = "Full ECR image URI including tag — e.g. account.dkr.ecr.region.amazonaws.com/backend:sha"
  type        = string
}

variable "backend_cpu" {
  description = "CPU units for backend task — 1024 = 1 vCPU"
  type        = number
  default     = 1024
}

variable "backend_memory" {
  description = "Memory in MB for backend task"
  type        = number
  default     = 2048
}

variable "app_port" {
  description = "Port the Flask app listens on inside the container"
  type        = number
  default     = 5000
}

variable "desired_count" {
  description = "Number of ECS tasks to run — 1 for dev, 2 for prod"
  type        = number
  default     = 1
}

# ── Load Balancer ─────────────────────────────────────────────────────────────

variable "backend_tg_arn" {
  description = "Backend target group ARN — ECS service registers task IPs here automatically"
  type        = string
}

# ── Region & Naming ───────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region — used in container env vars and log configuration"
  type        = string
}

# ── Secrets ───────────────────────────────────────────────────────────────────

variable "database_url_secret_arn" {
  description = "ARN of DATABASE_URL secret — ECS agent injects as DATABASE_URL env var"
  type        = string
}

variable "app_secret_key_arn" {
  description = "ARN of SECRET_KEY secret — ECS agent injects as SECRET_KEY env var"
  type        = string
}

variable "jwt_secret_key_arn" {
  description = "ARN of JWT_SECRET_KEY secret — ECS agent injects as JWT_SECRET_KEY env var"
  type        = string
}

variable "admin_password_arn" {
  description = "ARN of ADMIN_PASSWORD secret — ECS agent injects as ADMIN_PASSWORD env var"
  type        = string
}

# ── Application Environment ───────────────────────────────────────────────────

variable "cors_origins" {
  description = "CloudFront domain URL — Flask-CORS and Flask-SocketIO both read this. Must be https://xxxx.cloudfront.net"
  type        = string
}

variable "pem_secret_name" {
  description = "Name of the PEM key secret in Secrets Manager — backend reads at startup via boto3"
  type        = string
}

variable "aws_key_pair_name" {
  description = "EC2 key pair name — used by backend when launching EC2 instances"
  type        = string
}

variable "ec2_ami_id" {
  description = "AMI ID for EC2 instances launched by the backend"
  type        = string
}

variable "ec2_instance_type" {
  description = "EC2 instance type for ML workload instances"
  type        = string
  default     = "t3.micro"
}

variable "ec2_subnet_id" {
  description = "Subnet ID where backend-launched EC2 instances will be placed"
  type        = string
}

variable "ec2_vpc_id" {
  description = "VPC ID where backend-launched EC2 instances will be placed"
  type        = string
}

variable "platform_security_group_id" {
  description = "Security group ID attached to backend-launched EC2 instances"
  type        = string
}

variable "admin_email" {
  description = "Initial admin account email address"
  type        = string
}

variable "security_group_name" {
  description = "Name of the security group created by backend for user EC2 instances"
  type        = string
  default     = "ml-deployment-sg"
}