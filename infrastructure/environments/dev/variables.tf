# ── Environment ───────────────────────────────────────────────────────────────

variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name - used as a prefix for all resource names"
  type        = string
}

variable "region" {
  description = "AWS region where all resources are deployed"
  type        = string
}

# ── VPC ───────────────────────────────────────────────────────────────────────

variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "azs" {
  description = "List of availability zones to deploy into (must be exactly 2)"
  type        = list(string)

  validation {
    condition     = length(var.azs) == 2
    error_message = "Exactly 2 availability zones are required."
  }
}

variable "enable_nat_gateway" {
  description = "Set true for staging/prod - ECS tasks reach internet via NAT gateway"
  type        = bool
}

variable "enable_vpc_endpoints" {
  description = "Set true for dev - ECS tasks reach ECR and S3 without NAT gateway"
  type        = bool
}

# ── ECR ───────────────────────────────────────────────────────────────────────

variable "image_retention_count" {
  description = "Number of images to keep in ECR - older images deleted automatically"
  type        = number
  default     = 10
}

# ── RDS ───────────────────────────────────────────────────────────────────────

variable "db_name" {
  description = "PostgreSQL database name"
  type        = string
}

variable "db_username" {
  description = "RDS master username"
  type        = string
}

variable "db_password" {
  description = "RDS master password - pass via TF_VAR_db_password, never in tfvars"
  type        = string
  sensitive   = true
}

variable "instance_class" {
  description = "RDS instance class - db.t3.micro for dev, db.t3.medium for prod"
  type        = string
  default     = "db.t3.micro"
}

# ── Secrets ───────────────────────────────────────────────────────────────────

variable "app_secret_key" {
  description = "Flask SECRET_KEY - pass via TF_VAR_app_secret_key, never in tfvars"
  type        = string
  sensitive   = true
}

variable "jwt_secret_key" {
  description = "JWT_SECRET_KEY - pass via TF_VAR_jwt_secret_key, never in tfvars"
  type        = string
  sensitive   = true
}

variable "admin_password" {
  description = "Initial admin password - pass via TF_VAR_admin_password, never in tfvars"
  type        = string
  sensitive   = true
}

variable "pem_secret_name" {
  description = "Name of the Secrets Manager secret holding the EC2 SSH private key - read by backend at startup via PEM_SECRET_NAME env var"
  type        = string
}

# ── IAM / GitHub Actions OIDC ─────────────────────────────────────────────────

variable "github_org" {
  description = "GitHub organisation name - used in OIDC trust policy condition"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name - used in OIDC trust policy condition"
  type        = string
}

# ── ECS / EC2 ─────────────────────────────────────────────────────────────────

variable "backend_image" {
  description = "Full ECR image URI including tag - e.g. 123456789.dkr.ecr.ap-south-1.amazonaws.com/ml-deploy-dev-backend:latest"
  type        = string
}

variable "aws_key_pair_name" {
  description = "EC2 key pair name - used by the backend when launching EC2 instances for ML workloads"
  type        = string
}

variable "ec2_ami_id" {
  description = "AMI ID for EC2 instances launched by the backend - use Ubuntu 22.04 LTS for ap-south-1"
  type        = string
}

variable "ec2_instance_type" {
  description = "EC2 instance type for ML workload instances"
  type        = string
  default     = "t3.micro"
}

variable "platform_security_group_id" {
  description = "Security group ID attached to backend-launched EC2 instances - leave empty string on first apply, backend creates it"
  type        = string
  default     = ""
}

variable "admin_email" {
  description = "Initial admin account email address — used to seed the admin user in the database"
  type        = string
}

variable "security_group_name" {
  description = "Name of the security group the backend creates for user-facing EC2 instances"
  type        = string
  default     = "ml-deployment-sg"
}
