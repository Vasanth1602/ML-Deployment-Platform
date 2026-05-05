variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
}

variable "image_retention_count" {
  description = "Number of images to keep in ECR — older images are deleted automatically"
  type        = number
  default     = 10
}