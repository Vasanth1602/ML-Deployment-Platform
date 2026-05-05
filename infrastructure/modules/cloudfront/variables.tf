variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
}

# ── S3 Origin ─────────────────────────────────────────────────────────────────
# Regional domain name used as the S3 origin in the CloudFront distribution.
# Must be the regional domain — not the global one — for OAC to work correctly.

variable "s3_bucket_regional_domain_name" {
  description = "S3 bucket regional domain name — from module.s3_frontend.bucket_regional_domain_name"
  type        = string
}

variable "s3_bucket_arn" {
  description = "S3 bucket ARN — used in OAC bucket policy to scope access to this specific bucket"
  type        = string
}

variable "s3_bucket_id" {
  description = "S3 bucket ID (name) — used to attach the OAC bucket policy to the correct bucket"
  type        = string
}

# ── ALB Origin ────────────────────────────────────────────────────────────────
# ALB DNS name used as the second origin for /api/* and /socket.io/* behaviors.

variable "alb_dns_name" {
  description = "ALB DNS name — from module.alb.alb_dns_name"
  type        = string
}

# ── CloudFront Secret ─────────────────────────────────────────────────────────
# Added as a custom header on every request CloudFront sends to the ALB.
# ALB listener rules check for this header — direct ALB access without it returns 404.

variable "cloudfront_secret" {
  description = "CloudFront origin verification header value — from module.secrets.cloudfront_secret_value"
  type        = string
  sensitive   = true
}