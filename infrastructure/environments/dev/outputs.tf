output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "public_subnet_ids" {
  description = "Public subnet IDs"
  value       = module.vpc.public_subnet_ids
}

output "private_subnet_ids" {
  description = "Private subnet IDs"
  value       = module.vpc.private_subnet_ids
}

output "db_subnet_ids" {
  description = "DB subnet IDs"
  value       = module.vpc.db_subnet_ids
}

output "ecs_task_execution_role_arn" {
  description = "ECS task execution role ARN"
  value       = module.iam.ecs_task_execution_role_arn
}

output "ecs_task_role_arn" {
  description = "ECS task role ARN"
  value       = module.iam.ecs_task_role_arn
}

output "github_actions_role_arn" {
  description = "GitHub Actions OIDC role ARN - paste this into GitHub Actions variable OIDC_ROLE_ARN"
  value       = module.iam.github_actions_role_arn
}

output "alb_arn" {
  description = "ALB ARN - used by monitoring module for CloudWatch alarms"
  value       = module.alb.alb_arn
}

output "alb_dns_name" {
  description = "ALB DNS name - internal, not the public URL (CloudFront is the public URL)"
  value       = module.alb.alb_dns_name
}

output "backend_tg_arn" {
  description = "Backend target group ARN - wired to ECS module"
  value       = module.alb.backend_tg_arn
}

# ── CloudFront ────────────────────────────────────────────────────────────────

output "cloudfront_domain_name" {
  description = "CloudFront distribution domain name - primary app URL (https://dxxx.cloudfront.net)"
  value       = module.cloudfront.distribution_domain_name
}

output "cloudfront_distribution_id" {
  description = "CloudFront distribution ID - used by GitHub Actions for cache invalidation after frontend deploy"
  value       = module.cloudfront.distribution_id
}

# ── ECR ───────────────────────────────────────────────────────────────────────

output "ecr_repo_url" {
  description = "ECR backend repository URL - used by GitHub Actions to push images and by ECS to pull them"
  value       = module.ecr.backend_repo_url
}

# ── S3 ────────────────────────────────────────────────────────────────────────

output "s3_frontend_bucket" {
  description = "S3 frontend bucket name - used by GitHub Actions for aws s3 sync during frontend deploy"
  value       = module.s3_frontend.bucket_id
}
