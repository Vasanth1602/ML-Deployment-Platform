output "backend_repo_url" {
  description = "Full ECR repository URL — used in GitHub Actions to push images and in ECS task definition as the image URI"
  value       = aws_ecr_repository.backend.repository_url
}

output "backend_repo_name" {
  description = "ECR repository name — used in GitHub Actions IAM policy and lifecycle policy"
  value       = aws_ecr_repository.backend.name
}