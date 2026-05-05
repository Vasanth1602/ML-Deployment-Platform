terraform {
  required_version = ">= 1.6.0"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# ── Primary provider ──────────────────────────────────────────────────────────
provider "aws" {
  region = var.region

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

# ── Alias provider — us-east-1 ────────────────────────────────────────────────
# CloudFront metric alarms (monitoring module) only exist in us-east-1
# ACM certificates also require us-east-1 if custom domain is used later
provider "aws" {
  alias  = "us_east_1"
  region = "us-east-1"

  default_tags {
    tags = {
      Project     = var.project
      Environment = var.env
      ManagedBy   = "terraform"
    }
  }
}

# ── VPC ───────────────────────────────────────────────────────────────────────
module "vpc" {
  source = "../../modules/vpc"

  env                  = var.env
  project              = var.project
  region               = var.region
  cidr_block           = var.vpc_cidr
  azs                  = var.azs
  enable_nat_gateway   = var.enable_nat_gateway
  enable_vpc_endpoints = var.enable_vpc_endpoints
}

# ── Security Groups ───────────────────────────────────────────────────────────
module "security_groups" {
  source = "../../modules/security-groups"

  env     = var.env
  project = var.project
  vpc_id  = module.vpc.vpc_id
}

# ── ECR ───────────────────────────────────────────────────────────────────────
# Backend only — no frontend repo
# React build is synced to S3 directly by GitHub Actions
module "ecr" {
  source = "../../modules/ecr"

  env                   = var.env
  project               = var.project
  image_retention_count = var.image_retention_count
}

# ── RDS ───────────────────────────────────────────────────────────────────────
# db_password passed via TF_VAR_db_password — never in tfvars
# db_endpoint output flows into secrets module below
module "rds" {
  source = "../../modules/rds"

  env            = var.env
  project        = var.project
  db_subnet_ids  = module.vpc.db_subnet_ids
  db_sg_id       = module.security_groups.db_sg_id
  db_name        = var.db_name
  db_username    = var.db_username
  db_password    = var.db_password
  instance_class = var.instance_class
}

# ── Secrets ───────────────────────────────────────────────────────────────────
# db_endpoint wired from RDS output — Terraform resolves order automatically
# All sensitive values passed via TF_VAR_ — never in tfvars
module "secrets" {
  source = "../../modules/secrets"

  env             = var.env
  project         = var.project
  db_endpoint     = module.rds.db_endpoint
  db_username     = var.db_username
  db_password     = var.db_password
  db_name         = var.db_name
  app_secret_key  = var.app_secret_key
  jwt_secret_key  = var.jwt_secret_key
  admin_password  = var.admin_password
  pem_secret_name = var.pem_secret_name
}

# ── IAM ───────────────────────────────────────────────────────────────────────
# secrets_arns — execution role uses these to inject secrets as env vars
# pem_secret_arn — task role uses this to read PEM key via boto3 at runtime
module "iam" {
  source = "../../modules/iam"

  env          = var.env
  project      = var.project
  secrets_arns = module.secrets.app_secrets_arns
  github_org   = var.github_org
  github_repo  = var.github_repo
  pem_secret_arn = module.secrets.pem_secret_arn
  aws_region   = var.region
}

# ── ALB ───────────────────────────────────────────────────────────────────────
# cloudfront_secret comes from secrets module — breaks ALB ↔ CloudFront
# circular dependency by pre-generating the secret before either exists.
module "alb" {
  source = "../../modules/alb"

  env               = var.env
  project           = var.project
  vpc_id            = module.vpc.vpc_id
  public_subnet_ids = module.vpc.public_subnet_ids
  alb_sg_id         = module.security_groups.alb_sg_id
  cloudfront_secret = module.secrets.cloudfront_secret_value
}

# ── S3 Frontend ─────────────────────────────────────────────────────────────
# Private bucket for React SPA static files.
# OAC bucket policy is applied in the cloudfront module (avoids circular dep).

module "s3_frontend" {
  source = "../../modules/s3-frontend"

  env     = var.env
  project = var.project
}

# ── CloudFront ────────────────────────────────────────────────────────────────
# Distribution with two origins: S3 (frontend) and ALB (backend API).
# Also applies the OAC S3 bucket policy — module owns both ARNs at this point.

module "cloudfront" {
  source = "../../modules/cloudfront"

  env     = var.env
  project = var.project

  s3_bucket_regional_domain_name = module.s3_frontend.bucket_regional_domain_name
  s3_bucket_arn                  = module.s3_frontend.bucket_arn
  s3_bucket_id                   = module.s3_frontend.bucket_id
  alb_dns_name                   = module.alb.alb_dns_name
  cloudfront_secret              = module.secrets.cloudfront_secret_value
}

# ── ECS ──────────────────────────────────────────────────────────────────────
# Fargate cluster + backend task definition + service.
# cors_origins auto-wired from CloudFront domain — no manual entry needed.
# ec2_subnet_id + ec2_vpc_id wired directly from VPC outputs.

module "ecs" {
  source = "../../modules/ecs"

  env     = var.env
  project = var.project

  # ── Network ──────────────────────────────────────────────────────────────
  private_subnet_ids = module.vpc.private_subnet_ids
  ecs_tasks_sg_id    = module.security_groups.ecs_tasks_sg_id

  # ── IAM ────────────────────────────────────────────────────────────────
  task_execution_role_arn = module.iam.ecs_task_execution_role_arn
  task_role_arn           = module.iam.ecs_task_role_arn

  # ── ALB ────────────────────────────────────────────────────────────────
  backend_tg_arn = module.alb.backend_tg_arn

  # ── Secrets (ARNs) ───────────────────────────────────────────────────────
  database_url_secret_arn = module.secrets.database_url_secret_arn
  app_secret_key_arn      = module.secrets.app_secret_key_arn
  jwt_secret_key_arn      = module.secrets.jwt_secret_key_arn
  admin_password_arn      = module.secrets.admin_password_arn

  # ── App config ────────────────────────────────────────────────────────
  aws_region   = var.region
  backend_image = var.backend_image

  # CORS wired from CloudFront domain — automatically correct after apply
  cors_origins  = "https://${module.cloudfront.distribution_domain_name}"

  pem_secret_name            = var.pem_secret_name
  aws_key_pair_name          = var.aws_key_pair_name
  ec2_ami_id                 = var.ec2_ami_id
  ec2_instance_type          = var.ec2_instance_type
  ec2_subnet_id              = module.vpc.public_subnet_ids[0]
  ec2_vpc_id                 = module.vpc.vpc_id
  platform_security_group_id = var.platform_security_group_id
  admin_email                = var.admin_email
  security_group_name        = var.security_group_name
}