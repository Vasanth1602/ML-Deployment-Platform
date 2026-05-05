output "db_endpoint" {
  description = "RDS endpoint — wired to secrets module as var.db_endpoint to construct DATABASE_URL"
  value       = aws_db_instance.main.address
}

output "db_port" {
  description = "RDS port — always 5432 for PostgreSQL"
  value       = aws_db_instance.main.port
}

output "db_name" {
  description = "Database name — passed through for reference"
  value       = aws_db_instance.main.db_name
}

output "db_instance_id" {
  description = "RDS instance identifier — used by monitoring module for CloudWatch alarms"
  value       = aws_db_instance.main.identifier
}