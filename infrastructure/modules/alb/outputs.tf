output "alb_arn" {
  description = "ALB ARN — used by monitoring module for CloudWatch alarms"
  value       = aws_lb.main.arn
}

output "alb_dns_name" {
  description = "ALB DNS name — wired to CloudFront module as alb_dns_name for ALB origin"
  value       = aws_lb.main.dns_name
}

output "alb_zone_id" {
  description = "ALB hosted zone ID — needed if using Route53 alias record pointing to ALB"
  value       = aws_lb.main.zone_id
}

output "backend_tg_arn" {
  description = "Backend target group ARN — wired to ECS module for service load balancer config"
  value       = aws_lb_target_group.backend.arn
}

output "listener_arn" {
  description = "HTTP listener ARN — referenced by listener rules, available for future rules"
  value       = aws_lb_listener.http.arn
}