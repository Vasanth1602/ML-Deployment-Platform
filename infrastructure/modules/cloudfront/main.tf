# ── Origin Access Control ─────────────────────────────────────────────────────
# OAC signs every request CloudFront sends to S3 using SigV4.
# S3 bucket policy only allows requests signed by this specific distribution.
# Replaces the older OAI (Origin Access Identity) approach.

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "${var.project}-${var.env}-oac"
  description                       = "OAC for ${var.project} ${var.env} S3 frontend bucket"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

# ── Data Sources — Managed Policies ───────────────────────────────────────────
# AWS provides managed cache and origin request policies.
# Using data sources ensures we always get the correct policy ID
# without hardcoding IDs that differ between AWS accounts/regions.

data "aws_cloudfront_cache_policy" "caching_optimized" {
  name = "Managed-CachingOptimized"
}

data "aws_cloudfront_cache_policy" "caching_disabled" {
  name = "Managed-CachingDisabled"
}

data "aws_cloudfront_origin_request_policy" "all_viewer_except_host_header" {
  name = "Managed-AllViewerExceptHostHeader"
}

# ── CloudFront Distribution ───────────────────────────────────────────────────

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  price_class         = "PriceClass_All"
  comment             = "${var.project}-${var.env} frontend distribution"

  # ── Origin 1 — S3 ───────────────────────────────────────────────────────────
  # Serves React SPA static files.
  # OAC handles authentication — no public access needed on the bucket.

  origin {
    origin_id                = "s3-origin"
    domain_name              = var.s3_bucket_regional_domain_name
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # ── Origin 2 — ALB ──────────────────────────────────────────────────────────
  # Routes /api/* and /socket.io/* to the Flask backend via ALB.
  # HTTP only — ALB listener is on port 80, TLS is terminated at CloudFront.
  # X-CloudFront-Secret header proves the request came from this distribution.

  origin {
    origin_id   = "alb-origin"
    domain_name = var.alb_dns_name

    custom_origin_config {
      http_port              = 80
      https_port             = 443
      origin_protocol_policy = "http-only"
      origin_ssl_protocols   = ["TLSv1.2"]
    }

    custom_header {
      name  = "X-CloudFront-Secret"
      value = var.cloudfront_secret
    }
  }

  # ── Default Behavior — /* → S3 ───────────────────────────────────────────────
  # Serves React SPA for all paths not matched by ordered behaviors below.
  # GET + HEAD only — static files never need POST/PUT/DELETE.
  # CachingOptimized — caches files at edge, respects Cache-Control headers.

  default_cache_behavior {
    target_origin_id       = "s3-origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_optimized.id
    compress               = true
  }

  # ── Ordered Behavior 0 — /api/* → ALB ────────────────────────────────────────
  # Routes all API requests to the Flask backend.
  # All HTTP methods — API needs POST, PUT, DELETE etc.
  # CachingDisabled — API responses are dynamic, must never be cached.
  # AllViewerExceptHostHeader — forwards all query strings and headers to ALB
  # unchanged. Using AllViewer would send CloudFront Host header causing rejection.

  ordered_cache_behavior {
    path_pattern           = "/api/*"
    target_origin_id       = "alb-origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer_except_host_header.id
    compress               = true
  }

  # ── Ordered Behavior 1 — /socket.io/* → ALB ──────────────────────────────────
  # Routes all Socket.IO requests to the Flask backend.
  # AllViewerExceptHostHeader — forwards EIO=4, transport=polling, sid= query
  # params unchanged. Without this engineio strips EIO param and returns 400.
  # All HTTP methods — Socket.IO polling uses GET + POST, WebSocket uses GET.

  ordered_cache_behavior {
    path_pattern           = "/socket.io/*"
    target_origin_id       = "alb-origin"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["DELETE", "GET", "HEAD", "OPTIONS", "PATCH", "POST", "PUT"]
    cached_methods         = ["GET", "HEAD"]
    cache_policy_id        = data.aws_cloudfront_cache_policy.caching_disabled.id
    origin_request_policy_id = data.aws_cloudfront_origin_request_policy.all_viewer_except_host_header.id
    compress               = true
  }

  # ── Custom Error Pages — React Router fix ────────────────────────────────────
  # S3 returns 403 for any path it doesn't have a file for (e.g. /deployments/123).
  # Without this, direct URL navigation returns an S3 XML error page.
  # Remapping to /index.html with 200 lets React Router handle the path client-side.

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  # ── Geo Restrictions ──────────────────────────────────────────────────────────
  # None — accessible from all countries.

  restrictions {
    geo_restriction {
      restriction_type = "none"
    }
  }

  # ── TLS Certificate ───────────────────────────────────────────────────────────
  # Using default CloudFront certificate — free TLS for *.cloudfront.net.
  # If custom domain is added later, replace with acm_certificate_arn.

  viewer_certificate {
    cloudfront_default_certificate = true
  }

  tags = {
    Name = "${var.project}-${var.env}-cloudfront"
  }
}

# ── S3 Bucket Policy — OAC ───────────────────────────────────────────────────────
# Defined here (not in s3-frontend module) because this policy needs the
# CloudFront distribution ARN to scope the condition, and the distribution
# ARN is only known after aws_cloudfront_distribution is created.
# At this point we have both:
#   - aws_cloudfront_distribution.frontend.arn (this module)
#   - var.s3_bucket_arn                        (from s3-frontend module output)
# No circular dependency exists here.

data "aws_iam_policy_document" "frontend_bucket_policy" {
  statement {
    sid    = "AllowCloudFrontOACAccess"
    effect = "Allow"

    principals {
      type        = "Service"
      identifiers = ["cloudfront.amazonaws.com"]
    }

    actions = ["s3:GetObject"]

    resources = ["${var.s3_bucket_arn}/*"]

    condition {
      test     = "StringEquals"
      variable = "aws:SourceArn"
      values   = [aws_cloudfront_distribution.frontend.arn]
    }
  }
}

resource "aws_s3_bucket_policy" "frontend" {
  bucket = var.s3_bucket_id
  policy = data.aws_iam_policy_document.frontend_bucket_policy.json

  depends_on = [aws_cloudfront_distribution.frontend]
}