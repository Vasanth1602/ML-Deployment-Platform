# ── Secret ARNs for ECS execution role ───────────────────────────────────────
# ECS agent uses these ARNs to fetch secrets and inject as env vars at startup.
# These flow into IAM module as secrets_arns for execution role policy.

output "database_url_secret_arn" {
  description = "ARN of DATABASE_URL secret — ECS agent injects as DATABASE_URL env var"
  value       = aws_secretsmanager_secret.database_url.arn
}

output "app_secret_key_arn" {
  description = "ARN of SECRET_KEY secret — ECS agent injects as SECRET_KEY env var"
  value       = aws_secretsmanager_secret.app_secret_key.arn
}

output "jwt_secret_key_arn" {
  description = "ARN of JWT_SECRET_KEY secret — ECS agent injects as JWT_SECRET_KEY env var"
  value       = aws_secretsmanager_secret.jwt_secret_key.arn
}

output "admin_password_arn" {
  description = "ARN of ADMIN_PASSWORD secret — ECS agent injects as ADMIN_PASSWORD env var"
  value       = aws_secretsmanager_secret.admin_password.arn
}

# ── Combined list for IAM module ──────────────────────────────────────────────
# Passed to IAM module as secrets_arns — execution role policy scoped to these only.
# Wired in environments/dev/main.tf:
#   module "iam" { secrets_arns = module.secrets.app_secrets_arns }

output "app_secrets_arns" {
  description = "All secret ARNs the ECS execution role needs to read at task startup"
  value = [
    aws_secretsmanager_secret.database_url.arn,
    aws_secretsmanager_secret.app_secret_key.arn,
    aws_secretsmanager_secret.jwt_secret_key.arn,
    aws_secretsmanager_secret.admin_password.arn,
  ]
}

# ── PEM key ───────────────────────────────────────────────────────────────────
# Secret name passed through to ECS task as PEM_SECRET_NAME env var.
# Your backend reads this name and calls boto3 to fetch the key at startup.

output "pem_secret_name" {
  description = "Name of the PEM key secret — passed to ECS task as PEM_SECRET_NAME env var"
  value       = var.pem_secret_name
}

output "pem_secret_arn" {
  description = "ARN of the PEM key secret — passed to IAM module task role policy so boto3 can read it at runtime"
  value       = data.aws_secretsmanager_secret.pem_key.arn
}

# ── CloudFront secret ─────────────────────────────────────────────────────────
# Raw value passed to ALB listener rules and CloudFront origin header.
# ALB rejects any request that does not include this header value.

output "cloudfront_secret_value" {
  description = "CloudFront origin verification header value — passed to ALB and CloudFront modules"
  value       = random_password.cloudfront_secret.result
  sensitive   = true
}
