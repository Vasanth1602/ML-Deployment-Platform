# ── DB Subnet Group ───────────────────────────────────────────────────────────
# Tells RDS which subnets it can use for placement.
# Must span at least 2 AZs — AWS requirement for RDS even if multi_az = false.
# Uses DB subnets (private, no internet access) from VPC module.

resource "aws_db_subnet_group" "main" {
  name        = "${var.project}-${var.env}-db-subnet-group"
  subnet_ids  = var.db_subnet_ids
  description = "DB subnet group for ${var.project} ${var.env}"

  tags = {
    Name = "${var.project}-${var.env}-db-subnet-group"
  }
}

# ── Parameter Group ───────────────────────────────────────────────────────────
# Controls PostgreSQL engine settings.
# Using a custom parameter group instead of default so you can tune
# settings later without recreating the RDS instance.
# family = postgres16 must match engine_version = "16".

resource "aws_db_parameter_group" "main" {
  name        = "${var.project}-${var.env}-postgres16"
  family      = "postgres16"
  description = "Custom parameter group for ${var.project} ${var.env}"

  tags = {
    Name = "${var.project}-${var.env}-postgres16"
  }
}

# ── RDS Instance ──────────────────────────────────────────────────────────────
# PostgreSQL 16 instance — matches your docker-compose + Alembic migrations.
# Placed in DB subnets, accessible only from ml-ecs-tasks-sg on port 5432.
# Your Flask backend connects via DATABASE_URL injected by ECS agent at startup.

resource "aws_db_instance" "main" {
  identifier = "${var.project}-${var.env}-db"

  # ── Engine ────────────────────────────────────────────────────────────────
  engine         = "postgres"
  engine_version = var.engine_version

  # ── Credentials ───────────────────────────────────────────────────────────
  # db_username and db_password are used here to CREATE the RDS instance.
  # The full DATABASE_URL is then constructed in the secrets module using
  # these same values + the RDS endpoint output from this module.
  db_name  = var.db_name
  username = var.db_username
  password = var.db_password

  # ── Instance sizing ────────────────────────────────────────────────────────
  instance_class    = var.instance_class
  allocated_storage = var.allocated_storage
  storage_type      = "gp3"

  # ── Network ───────────────────────────────────────────────────────────────
  db_subnet_group_name   = aws_db_subnet_group.main.name
  vpc_security_group_ids = [var.db_sg_id]
  publicly_accessible    = false

  # ── Parameter group ───────────────────────────────────────────────────────
  parameter_group_name = aws_db_parameter_group.main.name

  # ── High availability ─────────────────────────────────────────────────────
  # false for dev/staging — saves cost
  # true for prod — survives an AZ failure
  multi_az = var.multi_az

  # ── Backup ────────────────────────────────────────────────────────────────
  # 0 = automated backups disabled (required for AWS Free Tier).
  # For paid accounts / prod, set to 7+ days via var.backup_retention_period.
  backup_retention_period = var.backup_retention_period
  backup_window           = "03:00-04:00"
  maintenance_window      = "Mon:04:00-Mon:05:00"

  # ── Protection ────────────────────────────────────────────────────────────
  # skip_final_snapshot = true for dev — destroy cleanly without orphaned snapshots
  # skip_final_snapshot = false for prod — always take a snapshot before destroy
  skip_final_snapshot       = var.skip_final_snapshot
  deletion_protection       = false
  delete_automated_backups  = true

  # ── Storage encryption ────────────────────────────────────────────────────
  # Always encrypt at rest — no cost, protects data if AWS storage is compromised
  storage_encrypted = true

  tags = {
    Name = "${var.project}-${var.env}-db"
  }
}