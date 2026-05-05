variable "region" {
  description = "AWS region"
  type        = string
  default     = "ap-south-1"
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
  default     = "ml-deploy"
}

variable "aws_account_id" {
  description = "AWS account ID — used to make the S3 bucket name globally unique"
  type        = string
}