variable "env" {
  description = "Environment name (dev / staging / prod)"
  type        = string
}

variable "project" {
  description = "Project name — used as a prefix for all resource names"
  type        = string
}

# ── Network ───────────────────────────────────────────────────────────────────

variable "db_subnet_ids" {
  description = "List of DB subnet IDs — from VPC module output db_subnet_ids"
  type        = list(string)
}

variable "db_sg_id" {
  description = "Security group ID for RDS — from security-groups module output db_sg_id"
  type        = string
}

# ── Database Configuration ────────────────────────────────────────────────────

variable "db_name" {
  description = "PostgreSQL database name — matches POSTGRES_DB in your docker-compose"
  type        = string
}

variable "db_username" {
  description = "RDS master username — used to construct DATABASE_URL in secrets module"
  type        = string
}

variable "db_password" {
  description = "RDS master password — sensitive, passed via TF_VAR_db_password, never in tfvars"
  type        = string
  sensitive   = true
}

# ── Instance Configuration ────────────────────────────────────────────────────

variable "instance_class" {
  description = "RDS instance class — db.t3.micro for dev, db.t3.small for staging, db.t3.medium for prod"
  type        = string
  default     = "db.t3.micro"
}

variable "allocated_storage" {
  description = "Initial storage in GB allocated to RDS instance"
  type        = number
  default     = 20
}

variable "engine_version" {
  description = "PostgreSQL engine version — must match what your Alembic migrations expect"
  type        = string
  default     = "16"
}

variable "multi_az" {
  description = "Enable Multi-AZ for high availability — false for dev/staging, true for prod"
  type        = bool
  default     = false
}

variable "skip_final_snapshot" {
  description = "Skip final snapshot on deletion — true for dev, false for prod to prevent data loss"
  type        = bool
  default     = true
}

variable "backup_retention_period" {
  description = "Number of days to retain automated backups. Must be 0 on AWS Free Tier. Set to 7+ for prod."
  type        = number
  default     = 0
}