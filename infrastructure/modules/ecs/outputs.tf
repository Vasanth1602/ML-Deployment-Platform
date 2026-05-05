output "cluster_id" {
  description = "ECS cluster ID — referenced by autoscaling module"
  value       = aws_ecs_cluster.main.id
}

output "cluster_arn" {
  description = "ECS cluster ARN"
  value       = aws_ecs_cluster.main.arn
}

output "cluster_name" {
  description = "ECS cluster name — used by autoscaling and monitoring modules"
  value       = aws_ecs_cluster.main.name
}

output "backend_service_name" {
  description = "Backend ECS service name — used by autoscaling and monitoring modules"
  value       = aws_ecs_service.backend.name
}

output "backend_task_definition_arn" {
  description = "Backend task definition ARN — referenced by CI/CD pipeline for rolling deploys"
  value       = aws_ecs_task_definition.backend.arn
}