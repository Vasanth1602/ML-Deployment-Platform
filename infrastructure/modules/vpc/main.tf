terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

# ── VPC ───────────────────────────────────────────────────────────────────────

resource "aws_vpc" "main" {
  cidr_block           = var.cidr_block
  enable_dns_support   = true
  enable_dns_hostnames = true

  tags = {
    Name = "${var.project}-${var.env}-vpc"
  }
}

# ── Public Subnets (ALB lives here) ──────────────────────────────────────────

resource "aws_subnet" "public" {
  count = 2

  vpc_id                  = aws_vpc.main.id
  cidr_block              = cidrsubnet(var.cidr_block, 8, count.index)
  availability_zone       = var.azs[count.index]
  map_public_ip_on_launch = true

  tags = {
    Name = "${var.project}-${var.env}-public-${var.azs[count.index]}"
    Tier = "public"
  }
}

# ── Private Subnets (ECS tasks live here) ────────────────────────────────────

resource "aws_subnet" "private" {
  count = 2

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr_block, 8, count.index + 2)
  availability_zone = var.azs[count.index]

  tags = {
    Name = "${var.project}-${var.env}-private-${var.azs[count.index]}"
    Tier = "private"
  }
}

# ── DB Subnets (RDS lives here) ───────────────────────────────────────────────

resource "aws_subnet" "db" {
  count = 2

  vpc_id            = aws_vpc.main.id
  cidr_block        = cidrsubnet(var.cidr_block, 8, count.index + 4)
  availability_zone = var.azs[count.index]

  tags = {
    Name = "${var.project}-${var.env}-db-${var.azs[count.index]}"
    Tier = "db"
  }
}

# ── Internet Gateway (public subnets need this to reach internet) ─────────────

resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project}-${var.env}-igw"
  }
}

# ── EIP + NAT Gateway (only created when enable_nat_gateway = true) ───────────
# Sits in public subnet[0] only — one NAT is enough for dev/staging cost savings
# For prod HA you would create one per AZ (count = 2), but that's a later concern

resource "aws_eip" "nat" {
  count  = var.enable_nat_gateway ? 1 : 0
  domain = "vpc"

  tags = {
    Name = "${var.project}-${var.env}-nat-eip"
  }

  depends_on = [aws_internet_gateway.main]
}

resource "aws_nat_gateway" "main" {
  count = var.enable_nat_gateway ? 1 : 0

  allocation_id = aws_eip.nat[0].id
  subnet_id     = aws_subnet.public[0].id

  tags = {
    Name = "${var.project}-${var.env}-nat"
  }

  depends_on = [aws_internet_gateway.main]
}

# ── VPC Endpoints (only created when enable_vpc_endpoints = true) ─────────────
# Used in dev instead of NAT gateway — ECS tasks can pull images from ECR
# and access S3 without any internet routing, purely over AWS backbone

# ── Security Group for Interface Endpoints ────────────────────────────────────
# Interface endpoints are ENIs — they need a SG to control who can reach them

resource "aws_security_group" "vpc_endpoints" {
  count = var.enable_vpc_endpoints ? 1 : 0

  name        = "${var.project}-${var.env}-vpce-sg"
  description = "Allow HTTPS from ECS tasks to VPC interface endpoints"
  vpc_id      = aws_vpc.main.id

  ingress {
    description = "HTTPS from private subnets"
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [var.cidr_block]
  }

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = {
    Name = "${var.project}-${var.env}-vpce-sg"
  }
}

# ── ECR API endpoint (interface) ──────────────────────────────────────────────
# Handles the ECR control plane — auth, image manifest fetching

resource "aws_vpc_endpoint" "ecr_api" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ecr.api"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project}-${var.env}-vpce-ecr-api"
  }
}

# ── ECR DKR endpoint (interface) ──────────────────────────────────────────────
# Handles the actual Docker layer downloads from ECR

resource "aws_vpc_endpoint" "ecr_dkr" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ecr.dkr"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project}-${var.env}-vpce-ecr-dkr"
  }
}

# ── S3 Gateway endpoint ───────────────────────────────────────────────────────
# ECR stores image layers in S3 — this endpoint is required alongside ECR ones
# Gateway type — attaches to route tables, not subnets. No SG needed. Free.

resource "aws_vpc_endpoint" "s3" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id            = aws_vpc.main.id
  service_name      = "com.amazonaws.${var.region}.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = aws_route_table.private[*].id

  tags = {
    Name = "${var.project}-${var.env}-vpce-s3"
  }
}

# ── Secrets Manager endpoint (interface) ──────────────────────────────────────
# Required in dev — no NAT gateway means ECS tasks can't reach the internet.
# ECS execution role calls secretsmanager:GetSecretValue at task startup to inject
# DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY, ADMIN_PASSWORD as env vars.
# Without this endpoint, the call times out and ECS tasks fail to start silently.

resource "aws_vpc_endpoint" "secretsmanager" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project}-${var.env}-vpce-secretsmanager"
  }
}

# ── CloudWatch Logs endpoint (interface) ──────────────────────────────────────
# Required in dev — no NAT gateway means ECS tasks can't reach the internet.
# ECS uses awslogs driver which calls logs.ap-south-1.amazonaws.com at task
# startup to validate the log group. Without this endpoint the task is killed
# before the container even starts (ResourceInitializationError).

resource "aws_vpc_endpoint" "cloudwatch_logs" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.logs"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project}-${var.env}-vpce-cloudwatch-logs"
  }
}

# ── EC2 endpoint (interface) ──────────────────────────────────────────────────
# Required for boto3 EC2 API calls made by the Flask backend at runtime:
# RunInstances, DescribeInstances, TerminateInstances, CreateSecurityGroup, etc.
# Without this endpoint, all boto3 ec2.* calls hang from the private subnet
# until they time out — EC2 provisioning appears permanently stuck.

resource "aws_vpc_endpoint" "ec2" {
  count = var.enable_vpc_endpoints ? 1 : 0

  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.region}.ec2"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.vpc_endpoints[0].id]
  private_dns_enabled = true

  tags = {
    Name = "${var.project}-${var.env}-vpce-ec2"
  }
}

# ── Route Tables ──────────────────────────────────────────────────────────────

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = {
    Name = "${var.project}-${var.env}-public-rt"
  }
}

# Private route table exists in all envs.
# NAT route is only added when enable_nat_gateway = true (staging / prod).
# In dev, VPC endpoints handle ECR + S3 traffic — no internet route needed.

resource "aws_route_table" "private" {
  vpc_id = aws_vpc.main.id

  dynamic "route" {
    for_each = var.enable_nat_gateway ? [1] : []
    content {
      cidr_block     = "0.0.0.0/0"
      nat_gateway_id = aws_nat_gateway.main[0].id
    }
  }

  tags = {
    Name = "${var.project}-${var.env}-private-rt"
  }
}

# DB subnets are fully isolated — no internet route ever.

resource "aws_route_table" "db" {
  vpc_id = aws_vpc.main.id

  tags = {
    Name = "${var.project}-${var.env}-db-rt"
  }
}

# ── Route Table Associations ───────────────────────────────────────────────────

resource "aws_route_table_association" "public" {
  count          = 2
  subnet_id      = aws_subnet.public[count.index].id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "private" {
  count          = 2
  subnet_id      = aws_subnet.private[count.index].id
  route_table_id = aws_route_table.private.id
}

resource "aws_route_table_association" "db" {
  count          = 2
  subnet_id      = aws_subnet.db[count.index].id
  route_table_id = aws_route_table.db.id
}