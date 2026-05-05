# ── ECS Task Execution Role ───────────────────────────────────────────────────
# [DEVOPS] Used by the ECS agent itself — not your Flask code.
# Handles: pulling image from ECR, writing logs to CloudWatch,
# and fetching secrets from Secrets Manager to inject as env vars
# BEFORE the container starts.

resource "aws_iam_role" "ecs_task_execution" {
  name = "${var.project}-${var.env}-ecs-task-execution-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.env}-ecs-task-execution-role"
  }
}

# [DEVOPS] AWS managed policy — covers ECR pull + CloudWatch logs
resource "aws_iam_role_policy_attachment" "ecs_task_execution_managed" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}

# [DEVOPS] Custom policy — ECS agent reads these secrets at task startup
# and injects them as env vars (DATABASE_URL, SECRET_KEY, JWT_SECRET_KEY).
# Your Flask code reads them as os.getenv() — never calls Secrets Manager for these.
resource "aws_iam_policy" "ecs_task_execution_secrets" {
  name        = "${var.project}-${var.env}-ecs-execution-secrets-policy"
  description = "Allows ECS agent to inject app secrets as env vars at task startup"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = "secretsmanager:GetSecretValue"
        Resource = var.secrets_arns
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.env}-ecs-execution-secrets-policy"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task_execution_secrets" {
  role       = aws_iam_role.ecs_task_execution.name
  policy_arn = aws_iam_policy.ecs_task_execution_secrets.arn
}

# ── ECS Task Role ─────────────────────────────────────────────────────────────
# [DEVOPS + BACKEND] Used by YOUR Flask application code running inside
# the container — not the ECS agent.
# boto3 inside the container automatically uses this role's credentials
# via the ECS container metadata endpoint (169.254.170.2).
# No access keys are needed anywhere in the code.

resource "aws_iam_role" "ecs_task" {
  name = "${var.project}-${var.env}-ecs-task-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Service = "ecs-tasks.amazonaws.com"
        }
        Action = "sts:AssumeRole"
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.env}-ecs-task-role"
  }
}

resource "aws_iam_policy" "ecs_task" {
  name        = "${var.project}-${var.env}-ecs-task-policy"
  description = "Runtime permissions for the Flask application — PEM key + EC2 provisioning"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [

      # ── [BACKEND] core/utils.py — load_pem_from_secrets_manager() ──────────
      # Called at Flask startup (app.py create_app) via boto3 directly.
      # Reads the EC2 SSH private key and writes it to PEM_KEY_PATH.
      # Scoped to ONLY the PEM secret — not DB password or JWT key.
      # Those are injected by the ECS agent via the execution role above.
      {
        Sid    = "ReadPemKeyFromSecretsManager"
        Effect = "Allow"
        Action = [
          "secretsmanager:GetSecretValue"
        ]
        Resource = [var.pem_secret_arn]
      },

      # ── [BACKEND] aws_manager.py — create_instance() ──────────────────────
      # ec2_resource.create_instances() → ec2:RunInstances
      # instance.wait_until_running() → ec2:DescribeInstances
      # ec2_client.describe_instance_status() → ec2:DescribeInstanceStatus
      # instance.terminate() → ec2:TerminateInstances
      # instance.stop() → ec2:StopInstances
      # instance.start() → ec2:StartInstances
      # create_instances(Tags=[...]) → ec2:CreateTags
      # RunInstances needs to verify the key pair → ec2:DescribeKeyPairs
      # RunInstances needs to verify the AMI → ec2:DescribeImages
      #
      # WHY Resource = "*":
      # EC2 instance ARNs include the instance ID (i-xxxxx) which only exists
      # AFTER creation. You cannot pre-scope RunInstances to a specific ARN.
      # The region condition below restricts which region instances can be created in.
      {
        Sid    = "EC2InstanceManagement"
        Effect = "Allow"
        Action = [
          "ec2:RunInstances",
          "ec2:DescribeInstances",
          "ec2:DescribeInstanceStatus",
          "ec2:TerminateInstances",
          "ec2:StopInstances",
          "ec2:StartInstances",
          "ec2:CreateTags",
          "ec2:DescribeKeyPairs",
          "ec2:DescribeImages"
        ]
        Resource = "*"
        Condition = {
          StringEquals = {
            "aws:RequestedRegion" = var.aws_region
          }
        }
      },

      # ── [BACKEND] aws_manager.py — create_or_get_security_group() ─────────
      # ec2_client.describe_security_groups() → ec2:DescribeSecurityGroups
      # ec2_client.create_security_group() → ec2:CreateSecurityGroup
      # ec2_client.authorize_security_group_ingress() → ec2:AuthorizeSecurityGroupIngress
      #
      # WHY separate statement from EC2 instance management:
      # These are network configuration actions, not instance lifecycle actions.
      # Separating them makes the policy easier to audit and reason about.
      # If you ever need to remove EC2 creation rights but keep SG read access,
      # you can do it without touching the instance statement.
      {
        Sid    = "SecurityGroupManagement"
        Effect = "Allow"
        Action = [
          "ec2:DescribeSecurityGroups",
          "ec2:CreateSecurityGroup",
          "ec2:AuthorizeSecurityGroupIngress"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.env}-ecs-task-policy"
  }
}

resource "aws_iam_role_policy_attachment" "ecs_task" {
  role       = aws_iam_role.ecs_task.name
  policy_arn = aws_iam_policy.ecs_task.arn
}

# ── GitHub Actions OIDC ───────────────────────────────────────────────────────
# [DEVOPS] Allows GitHub Actions to assume an AWS role without storing any
# long-lived credentials in GitHub secrets.
# GitHub proves its identity using a short-lived OIDC token.
# AWS verifies the token and issues temporary credentials.
# Token expires when the job finishes.

resource "aws_iam_openid_connect_provider" "github" {
  url = "https://token.actions.githubusercontent.com"

  client_id_list = ["sts.amazonaws.com"]

  # GitHub's OIDC thumbprint — stable, does not change frequently
  thumbprint_list = ["6938fd4d98bab03faadb97b34396831e3780aea1"]

  tags = {
    Name = "${var.project}-${var.env}-github-oidc"
  }
}

resource "aws_iam_role" "github_actions" {
  name = "${var.project}-${var.env}-github-actions-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect = "Allow"
        Principal = {
          Federated = aws_iam_openid_connect_provider.github.arn
        }
        Action = "sts:AssumeRoleWithWebIdentity"
        Condition = {
          StringEquals = {
            "token.actions.githubusercontent.com:aud" = "sts.amazonaws.com"
          }
          # Scoped to your specific repo AND main branch only.
          # Without this, any branch in your repo could trigger a production deploy.
          StringLike = {
            "token.actions.githubusercontent.com:sub" = "repo:${var.github_org}/${var.github_repo}:ref:refs/heads/main"
          }
        }
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.env}-github-actions-role"
  }
}

resource "aws_iam_policy" "github_actions" {
  name        = "${var.project}-${var.env}-github-actions-policy"
  description = "CI/CD pipeline permissions — ECR push, ECS deploy, S3 sync, CF invalidation"

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [

      # [DEVOPS] GetAuthorizationToken must be * — does not accept resource ARNs
      {
        Effect = "Allow"
        Action = [
          "ecr:GetAuthorizationToken"
        ]
        Resource = "*"
      },

      # [DEVOPS] Push backend Docker image to ECR
      {
        Effect = "Allow"
        Action = [
          "ecr:BatchCheckLayerAvailability",
          "ecr:GetDownloadUrlForLayer",
          "ecr:BatchGetImage",
          "ecr:InitiateLayerUpload",
          "ecr:UploadLayerPart",
          "ecr:CompleteLayerUpload",
          "ecr:PutImage"
        ]
        Resource = "arn:aws:ecr:*:*:repository/${var.project}-*"
      },

      # [DEVOPS] Deploy to ECS and run migration tasks
      # NOTE: ecs:WaitUntilServicesStable is NOT a real IAM action.
      # It is a client-side SDK waiter that polls ecs:DescribeServices.
      # ecs:DescribeServices here is what enables that waiter to work.
      {
        Effect = "Allow"
        Action = [
          "ecs:RegisterTaskDefinition",
          "ecs:UpdateService",
          "ecs:DescribeServices",
          "ecs:DescribeTaskDefinition",
          "ecs:RunTask",
          "ecs:DescribeTasks"
        ]
        Resource = "*"
      },

      # [DEVOPS] Required when registering task definitions that reference IAM roles.
      # Without this, RegisterTaskDefinition fails with "not authorized to perform iam:PassRole".
      {
        Effect = "Allow"
        Action = [
          "iam:PassRole"
        ]
        Resource = [
          aws_iam_role.ecs_task_execution.arn,
          aws_iam_role.ecs_task.arn
        ]
      },

      # [DEVOPS] Sync React build to S3 frontend bucket
      {
        Effect = "Allow"
        Action = [
          "s3:PutObject",
          "s3:GetObject",
          "s3:DeleteObject",
          "s3:ListBucket"
        ]
        Resource = [
          "arn:aws:s3:::${var.project}-*",
          "arn:aws:s3:::${var.project}-*/*"
        ]
      },

      # [DEVOPS] Invalidate CloudFront edge cache after frontend deploy
      {
        Effect = "Allow"
        Action = [
          "cloudfront:CreateInvalidation"
        ]
        Resource = "*"
      }
    ]
  })

  tags = {
    Name = "${var.project}-${var.env}-github-actions-policy"
  }
}

resource "aws_iam_role_policy_attachment" "github_actions" {
  role       = aws_iam_role.github_actions.name
  policy_arn = aws_iam_policy.github_actions.arn
}