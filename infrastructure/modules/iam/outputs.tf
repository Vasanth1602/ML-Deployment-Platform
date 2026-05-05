output "ecs_task_execution_role_arn" {
  description = "ARN of the ECS task execution role — passed to ECS task definition"
  value       = aws_iam_role.ecs_task_execution.arn
}

output "ecs_task_role_arn" {
  description = "ARN of the ECS task role — passed to ECS task definition"
  value       = aws_iam_role.ecs_task.arn
}

output "github_actions_role_arn" {
  description = "ARN of the GitHub Actions role — configure this in GitHub Actions variable OIDC_ROLE_ARN"
  value       = aws_iam_role.github_actions.arn
}