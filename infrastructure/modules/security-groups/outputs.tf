output "alb_sg_id" {
  description = "Security group ID for the ALB — referenced by ECS tasks SG inbound rule"
  value       = aws_security_group.alb.id
}

output "ecs_tasks_sg_id" {
  description = "Security group ID for ECS tasks — referenced by RDS SG inbound rule"
  value       = aws_security_group.ecs_tasks.id
}

output "db_sg_id" {
  description = "Security group ID for RDS"
  value       = aws_security_group.db.id
}