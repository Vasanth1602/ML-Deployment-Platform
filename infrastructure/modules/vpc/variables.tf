variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
}

variable "region" {
  description = "AWS region"
  type        = string
}

variable "cidr_block" {
  description = "CIDR block for the VPC"
  type        = string
}

variable "azs" {
  description = "List of availability zones to deploy into (must be exactly 2)"
  type        = list(string)

  validation {
    condition     = length(var.azs) == 2
    error_message = "Exactly 2 availability zones are required."
  }
}

variable "enable_nat_gateway" {
  description = "Set true for staging/prod. ECS tasks reach internet via NAT."
  type        = bool
}

variable "enable_vpc_endpoints" {
  description = "Set true for dev. Allows ECS to pull from ECR without NAT gateway."
  type        = bool
}