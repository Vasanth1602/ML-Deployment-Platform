# ── ECR Repository — Backend Only ─────────────────────────────────────────────
# Stores Docker images for the Flask backend.
# ❌ No frontend repository — React is built and synced to S3 directly.
# GitHub Actions pushes images here using commit SHA as the tag.

resource "aws_ecr_repository" "backend" {
  name                 = "${var.project}-${var.env}-backend"
  image_tag_mutability = "IMMUTABLE"

  # Scan on push — detects known CVEs in your Docker image layers automatically.
  # Results visible in ECR console. Does not block push — only reports.
  image_scanning_configuration {
    scan_on_push = true
  }

  tags = {
    Name = "${var.project}-${var.env}-backend"
  }
}

# ── Lifecycle Policy ───────────────────────────────────────────────────────────
# Keeps only the last N images tagged with any tag.
# Every GitHub Actions push creates a new image with a commit SHA tag.
# Without this policy, images accumulate indefinitely and storage costs grow.
# Oldest images beyond the retention count are deleted automatically.

resource "aws_ecr_lifecycle_policy" "backend" {
  repository = aws_ecr_repository.backend.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Keep last ${var.image_retention_count} images"
        selection = {
          tagStatus   = "any"
          countType   = "imageCountMoreThan"
          countNumber = var.image_retention_count
        }
        action = {
          type = "expire"
        }
      }
    ]
  })
}