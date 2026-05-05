variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
}

# NOTE: cloudfront_distribution_arn is intentionally NOT a variable here.
# The OAC bucket policy has been moved to the cloudfront module to avoid
# the circular dependency between s3-frontend and cloudfront.