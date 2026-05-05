# ── S3 Bucket ─────────────────────────────────────────────────────────────────
# Private bucket — serves React SPA via CloudFront OAC only.
# No public access allowed — bucket policy grants read to CloudFront only.
# Direct S3 URL access returns 403 — by design.

resource "aws_s3_bucket" "frontend" {
  bucket = "${var.project}-${var.env}-frontend"

  tags = {
    Name = "${var.project}-${var.env}-frontend"
  }
}

# ── Block All Public Access ───────────────────────────────────────────────────
# All 4 checkboxes ON — bucket stays fully private.
# CloudFront reads from it via OAC (SigV4 signed requests), not public URLs.

resource "aws_s3_bucket_public_access_block" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

# ── Server Side Encryption ────────────────────────────────────────────────────
# SSE-S3 — AWS managed keys, no extra cost.
# Bucket key enabled — reduces KMS API calls cost if you ever switch to SSE-KMS.

resource "aws_s3_bucket_server_side_encryption_configuration" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
    bucket_key_enabled = true
  }
}

# ── Versioning ────────────────────────────────────────────────────────────────
# Disabled — React builds use Vite content-hashed filenames.
# Old files are removed by --delete flag in aws s3 sync during CI/CD.
# Versioning would accumulate deleted versions unnecessarily.

resource "aws_s3_bucket_versioning" "frontend" {
  bucket = aws_s3_bucket.frontend.id

  versioning_configuration {
    status = "Disabled"
  }
}

# ── Bucket Policy ─────────────────────────────────────────────────────────────
# NOTE: The OAC bucket policy is intentionally NOT defined here.
# It is defined in the cloudfront module (cloudfront/main.tf) because
# the policy needs the CloudFront distribution ARN, which is only
# known after the distribution is created.
# Defining it here would create a circular dependency:
#   s3-frontend → cloudfront ARN → cloudfront → s3 bucket domain → s3-frontend
# The cloudfront module owns both ARNs and applies the policy there.