output "vpc_id" {
  description = "ID of the VPC"
  value       = aws_vpc.main.id
}

output "public_subnet_ids" {
  description = "IDs of the two public subnets (ALB lives here)"
  value       = aws_subnet.public[*].id
}

output "private_subnet_ids" {
  description = "IDs of the two private subnets (ECS tasks live here)"
  value       = aws_subnet.private[*].id
}

output "db_subnet_ids" {
  description = "IDs of the two DB subnets (RDS lives here)"
  value       = aws_subnet.db[*].id
}

output "vpc_cidr" {
  description = "CIDR block of the VPC — used by VPC endpoint SG ingress rule"
  value       = aws_vpc.main.cidr_block
}