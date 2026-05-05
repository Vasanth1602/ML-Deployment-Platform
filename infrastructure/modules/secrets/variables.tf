variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
}

# ── RDS connection ────────────────────────────────────────────────────────────
# These four are combined in main.tf to construct the full DATABASE_URL string.
# Stored as one secret in Secrets Manager — never exposed individually.

variable "db_endpoint" {
  description = "RDS endpoint — wired from module.rds.db_endpoint in environments/dev/main.tf"
  type        = string
}

variable "db_username" {
  description = "RDS master username — used to construct DATABASE_URL"
  type        = string
}

variable "db_password" {
  description = "RDS master password — used to construct DATABASE_URL, passed via TF_VAR_db_password"
  type        = string
  sensitive   = true
}

variable "db_name" {
  description = "RDS database name — used to construct DATABASE_URL"
  type        = string
}

# ── Application secrets ───────────────────────────────────────────────────────

variable "app_secret_key" {
  description = "Flask SECRET_KEY — session signing, passed via TF_VAR_app_secret_key"
  type        = string
  sensitive   = true
}

variable "jwt_secret_key" {
  description = "JWT_SECRET_KEY — token signing, separate from SECRET_KEY, passed via TF_VAR_jwt_secret_key"
  type        = string
  sensitive   = true
}

variable "admin_password" {
  description = "Initial admin password — wiped from memory after bcrypt hashing, passed via TF_VAR_admin_password"
  type        = string
  sensitive   = true
}

# ── PEM key ───────────────────────────────────────────────────────────────────
# The PEM key itself is stored manually in Secrets Manager — not managed by Terraform.
# This variable holds the secret name so it can be passed through to:
# 1. ECS task as PEM_SECRET_NAME env var — backend reads it at startup
# 2. IAM module as pem_secret_arn — task role needs GetSecretValue permission

variable "pem_secret_name" {
  description = "Name of the manually created Secrets Manager secret holding the EC2 SSH private key"
  type        = string
}