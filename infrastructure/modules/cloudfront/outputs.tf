output "distribution_id" {
  description = "CloudFront distribution ID — used by CI/CD for cache invalidation after frontend deploy"
  value       = aws_cloudfront_distribution.frontend.id
}

output "distribution_domain_name" {
  description = "CloudFront distribution domain name — primary app URL (e.g. dxxxx.cloudfront.net)"
  value       = aws_cloudfront_distribution.frontend.domain_name
}

output "distribution_arn" {
  description = "CloudFront distribution ARN — passed to S3 frontend module for bucket policy OAC condition"
  value       = aws_cloudfront_distribution.frontend.arn
}

output "oac_id" {
  description = "Origin Access Control ID — attached to S3 origin in the distribution"
  value       = aws_cloudfront_origin_access_control.frontend.id
}