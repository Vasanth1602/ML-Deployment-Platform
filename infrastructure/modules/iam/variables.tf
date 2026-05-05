variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
}

variable "secrets_arns" {
  description = "List of Secrets Manager ARNs the ECS task execution role needs to read at runtime"
  type        = list(string)
}

variable "github_org" {
  description = "GitHub organisation name — used in OIDC trust policy condition"
  type        = string
}

variable "github_repo" {
  description = "GitHub repository name — used in OIDC trust policy condition"
  type        = string
}

# need for backend
variable "pem_secret_arn" {
  description = "ARN of the Secrets Manager secret holding the EC2 SSH private key — read by core/utils.py at runtime via boto3"
  type        = string
}

variable "aws_region" {
  description = "AWS region — used to scope EC2 permissions in the task role policy to a specific region only"
  type        = string
}