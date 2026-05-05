terraform {
  required_providers {
    random = {
      source  = "hashicorp/random"
      version = "~> 3.0"
    }
  }
}

# ── CloudFront Secret ─────────────────────────────────────────────────────────
# Generated once here — breaks the ALB ↔ CloudFront circular dependency.
# Passed to CloudFront as custom origin header (X-CloudFront-Secret).
# Passed to ALB listener rules as a condition — requests without this header
# are rejected with 404, locking the ALB to CloudFront traffic only.

resource "random_password" "cloudfront_secret" {
  length  = 32
  special = false
}

resource "aws_secretsmanager_secret" "cloudfront_secret" {
  name                    = "${var.project}/${var.env}/cloudfront-secret"
  description             = "CloudFront origin verification header value"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project}-${var.env}-cloudfront-secret"
  }
}

resource "aws_secretsmanager_secret_version" "cloudfront_secret" {
  secret_id     = aws_secretsmanager_secret.cloudfront_secret.id
  secret_string = random_password.cloudfront_secret.result
}

# ── Database URL ──────────────────────────────────────────────────────────────
# Full PostgreSQL connection string constructed from RDS module outputs.
# Stored as one secret — endpoint, username, password never exposed separately.
# ECS agent reads this ARN at task startup and injects as DATABASE_URL env var.
# Your Flask code reads: os.getenv('DATABASE_URL') — never calls Secrets Manager.
# db_endpoint comes from module.rds.db_endpoint wired in environments/dev/main.tf.

resource "aws_secretsmanager_secret" "database_url" {
  name                    = "${var.project}/${var.env}/database-url"
  description             = "Full PostgreSQL DATABASE_URL connection string"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project}-${var.env}-database-url"
  }
}

resource "aws_secretsmanager_secret_version" "database_url" {
  secret_id     = aws_secretsmanager_secret.database_url.id
  secret_string = "postgresql://${var.db_username}:${var.db_password}@${var.db_endpoint}:5432/${var.db_name}"
}

# ── Flask Secret Key ──────────────────────────────────────────────────────────
# Flask SECRET_KEY — used for session signing and CSRF protection.
# ECS agent injects as SECRET_KEY env var at task startup.
# Your Flask code reads: os.getenv('SECRET_KEY')

resource "aws_secretsmanager_secret" "app_secret_key" {
  name                    = "${var.project}/${var.env}/app-secret-key"
  description             = "Flask application secret key"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project}-${var.env}-app-secret-key"
  }
}

resource "aws_secretsmanager_secret_version" "app_secret_key" {
  secret_id     = aws_secretsmanager_secret.app_secret_key.id
  secret_string = var.app_secret_key
}

# ── JWT Secret Key ────────────────────────────────────────────────────────────
# Separate from Flask SECRET_KEY — used only for signing JWT tokens.
# ECS agent injects as JWT_SECRET_KEY env var at task startup.
# Your Flask code reads: os.getenv('JWT_SECRET_KEY')

resource "aws_secretsmanager_secret" "jwt_secret_key" {
  name                    = "${var.project}/${var.env}/jwt-secret-key"
  description             = "JWT token signing secret key"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project}-${var.env}-jwt-secret-key"
  }
}

resource "aws_secretsmanager_secret_version" "jwt_secret_key" {
  secret_id     = aws_secretsmanager_secret.jwt_secret_key.id
  secret_string = var.jwt_secret_key
}

# ── Admin Password ────────────────────────────────────────────────────────────
# Initial admin account password for bootstrap_admin() in auth_service.py.
# ECS agent injects as ADMIN_PASSWORD env var at task startup.
# Plaintext is wiped from memory immediately after bcrypt hashing at startup.

resource "aws_secretsmanager_secret" "admin_password" {
  name                    = "${var.project}/${var.env}/admin-password"
  description             = "Initial admin account password"
  recovery_window_in_days = 0

  tags = {
    Name = "${var.project}-${var.env}-admin-password"
  }
}

resource "aws_secretsmanager_secret_version" "admin_password" {
  secret_id     = aws_secretsmanager_secret.admin_password.id
  secret_string = var.admin_password
}

# ── PEM Key data source ───────────────────────────────────────────────────────
# PEM key is stored manually in Secrets Manager — not managed by Terraform.
# Data source looks up the existing secret by name to get its ARN.
# ARN is then passed to IAM module for task role policy scoping.

data "aws_secretsmanager_secret" "pem_key" {
  name = var.pem_secret_name
}