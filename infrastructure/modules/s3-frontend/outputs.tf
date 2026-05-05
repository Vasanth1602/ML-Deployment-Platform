output "bucket_id" {
  description = "S3 bucket ID — used to reference the bucket in other resources"
  value       = aws_s3_bucket.frontend.id
}

output "bucket_arn" {
  description = "S3 bucket ARN — used in IAM policies"
  value       = aws_s3_bucket.frontend.arn
}

output "bucket_regional_domain_name" {
  description = "S3 bucket regional domain name — wired to CloudFront module as S3 origin domain"
  value       = aws_s3_bucket.frontend.bucket_regional_domain_name
}