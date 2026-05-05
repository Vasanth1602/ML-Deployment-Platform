# Deployment Architecture Plan
### ML Deployment Platform — AWS ECS Fargate Production Design

**Date:** March 2026  
**Status:** Architecture Plan (Pre-Terraform)  
**Author:** DevOps Engineering

---

## Table of Contents

1. [Application Overview](#1-application-overview)
2. [Service Architecture](#2-service-architecture)
3. [Containerization Strategy](#3-containerization-strategy)
4. [Infrastructure Design](#4-infrastructure-design)
5. [Networking Architecture](#5-networking-architecture)
6. [Security Architecture](#6-security-architecture)
7. [Deployment Flow](#7-deployment-flow)
8. [CI/CD Flow](#8-cicd-flow)
9. [Monitoring Strategy](#9-monitoring-strategy)
10. [Infrastructure Phasing Plan](#10-infrastructure-phasing-plan)

---

## 1. Application Overview

### What This Platform Does

The **ML Deployment Platform** is a SaaS-style DevOps automation platform. It allows operators to deploy ML applications (and any Dockerized apps) from GitHub repositories to AWS EC2 instances by:

1. Provisioning new EC2 instances on demand via the AWS API
2. SSH-ing into those instances to install Docker, Git, and Nginx
3. Cloning the target GitHub repository onto the instance
4. Building and running the application's Docker container
5. Configuring an Nginx reverse proxy for HTTP access
6. Reporting real-time deployment progress to the browser via WebSocket

The platform itself is a three-tier web application: a React SPA frontend, a Flask REST API + WebSocket backend, and a PostgreSQL database.

### Domain Model Summary

The platform manages 10 database entities:

| Table | Purpose |
|---|---|
| `tenants` | Multi-tenant organisation scoping |
| `ec2_instances` | Platform-provisioned AWS EC2 instances |
| `applications` | Registered GitHub repositories |
| `application_instances` | Maps which app runs on which instance and port |
| `deployments` | Full deployment history (every attempt) |
| `deployment_steps` | Granular step tracking per deployment |
| `deployment_logs` | Real-time log lines streamed to browser |
| `secrets` | AWS Secrets Manager ARN references |
| `environment_variables` | Per-app config: plaintext or secret reference |
| `instance_metrics` | CPU / memory / disk time-series data |

### Technology Stack

| Layer | Technology | Version |
|---|---|---|
| Frontend runtime | React + React Router | 19.x / 7.x |
| Frontend build | Vite | 7.x |
| Frontend UI | Tailwind CSS | 4.x |
| Frontend server | Nginx | alpine |
| Backend framework | Flask + Flask-SocketIO | 3.0 / 5.3 |
| Backend WSGI | Gunicorn + gthread workers | 21.x |
| Backend runtime | Python | 3.11 |
| ORM | SQLAlchemy | 2.0 |
| Migrations | Alembic | 1.13 |
| Database | PostgreSQL | 16 |
| AWS SDK | boto3 / botocore | 1.34 |
| SSH / Remote exec | paramiko | 3.4 |
| Real-time comms | Socket.IO (server + client) | 5.x / 4.x |

---

## 2. Service Architecture

### Current Local Architecture (Docker Compose)

```
Browser
  │
  ▼
┌─────────────────────┐
│  frontend:80        │  Nginx — serves React SPA
│  (autodeploy_      │         proxies /api/* → backend:5000
│   frontend)         │         proxies /socket.io/* → backend:5000
└──────────┬──────────┘
           │ Docker network: app_network
           ▼
┌─────────────────────┐        ┌─────────────────────┐
│  backend:5000        │ ──────► │  postgres:5432       │
│  (autodeploy_       │        │  (autodeploy_        │
│   backend)          │        │   postgres)          │
│  Flask / Gunicorn   │        │  PostgreSQL 16        │
└──────────┬──────────┘        └─────────────────────┘
           │ boto3 / paramiko
           ▼
┌──────────────────────────────────────┐
│  AWS (external)                      │
│  ┌────────────┐  ┌────────────────┐  │
│  │ EC2        │  │ EC2            │  │
│  │ instances  │  │ instances      │  │
│  │ (managed)  │  │ (managed)      │  │
│  └────────────┘  └────────────────┘  │
└──────────────────────────────────────┘
```

### Target Production Architecture (AWS ECS Fargate)

```
Internet
  │
  ▼
┌──────────────────────────────┐
│  Route 53 (DNS)              │
└──────────────┬───────────────┘
               ▼
┌──────────────────────────────┐
│  Application Load Balancer   │  HTTPS :443 / HTTP :80 → redirect
│  (public subnets)            │
│  Listener rules:             │
│   /api/*      → backend TG   │
│   /socket.io/*→ backend TG   │
│   /*          → frontend TG  │
└──────┬───────────────┬───────┘
       │               │
       ▼               ▼
┌─────────────┐  ┌─────────────────────┐
│  ECS Service│  │  ECS Service        │
│  frontend   │  │  backend            │
│  (Fargate)  │  │  (Fargate)          │
│  Nginx:80   │  │  Gunicorn:5000      │
│  private    │  │  private subnets    │
│  subnets    │  │                     │
└─────────────┘  └──────────┬──────────┘
                             │ SQLAlchemy (DATABASE_URL)
                             ▼
                 ┌─────────────────────┐
                 │  Amazon RDS         │
                 │  PostgreSQL 16      │
                 │  private subnets    │
                 │  Multi-AZ           │
                 └─────────────────────┘
                             │
                 + ECS backend → boto3/paramiko → managed EC2 instances
```

### Application API Surface

| Method | Route | Description |
|--------|-------|-------------|
| GET | `/api/health` | Health check — returns DB connectivity status |
| GET | `/api/config/validate` | Validates AWS configuration |
| POST | `/api/deploy` | Trigger a new deployment from GitHub URL |
| GET | `/api/deployments` | List deployments (filterable by status/app) |
| GET | `/api/deployments/<id>` | Get a single deployment + step details |
| GET | `/api/deployments/<id>/logs` | Stream deployment log lines |
| GET | `/api/applications` | List all registered applications |
| GET | `/api/applications/<id>` | Get one application + recent deployments |
| DELETE | `/api/applications/<id>` | Remove an application record |
| GET | `/api/instances` | List EC2 instances (merged DB + live AWS state) |
| POST | `/api/instances/sync` | Sync EC2 state from AWS into the DB |
| POST | `/api/instances/<id>/stop` | Stop a managed EC2 instance |
| POST | `/api/instances/<id>/start` | Start a stopped EC2 instance |
| POST | `/api/instances/<id>/terminate` | Terminate and remove an instance |
| GET | `/api/stats` | Platform-wide counts and metrics |
| WS | `/socket.io/` | Real-time deployment progress events |

---

## 3. Containerization Strategy

### Container Images

Two container images will be built, tagged, and published to Amazon ECR.

#### Image 1: `ml-deploy-backend`

| Property | Value |
|---|---|
| Base image | `python:3.11-slim` |
| Build context | Repository root |
| Dockerfile | `Dockerfile.backend` |
| Exposed port | `5000` |
| Entry point | `alembic upgrade head && gunicorn -k gthread -w 1 --threads 4 --bind 0.0.0.0:5000 --timeout 300 "backend.app:create_app()"` |

**Key characteristics:**
- Runs Alembic database migrations on each container start (safe — Alembic is idempotent)
- Uses gthread worker class to support Flask-SocketIO threading mode
- Single worker process with 4 threads (appropriate for I/O-bound async workloads)
- Gunicorn timeout 300s accommodates long-running EC2 provisioning operations
- Requires `PYTHONPATH=/app` to resolve the `backend` package

**Production changes required:**
- Remove `COPY .env .` from Dockerfile — secrets will be injected via ECS task definition environment / AWS Secrets Manager
- SSH key (`ml-deploy-key.pem`) must be injected at runtime via AWS Secrets Manager (not volume mount)
- `FLASK_ENV` must be set to `production`

#### Image 2: `ml-deploy-frontend`

| Property | Value |
|---|---|
| Build stage 1 | `node:20-alpine` — builds Vite/React bundle |
| Build stage 2 | `nginx:alpine` — serves static assets |
| Exposed port | `80` |
| Nginx config | `nginx/frontend.conf` |

**Key characteristics:**
- Multi-stage build: Node.js is build-time only; final image is pure Nginx (~50 MB)
- React SPA with client-side routing — Nginx handles fallback to `index.html`
- Nginx proxies `/api/*` and `/socket.io/*` to the backend service

**Production changes required:**
- The `frontend.conf` `proxy_pass` target (`http://backend:5000`) must be updated to reference the backend ECS service via its ALB DNS or internal service discovery hostname
- `VITE_API_URL` should match the ALB hostname at build time (or the proxy handles it transparently)

### ECR Repository Plan

| Repository Name | Image | Tag Strategy |
|---|---|---|
| `ml-deploy/backend` | Flask API | `latest`, `git-sha` (short) |
| `ml-deploy/frontend` | Nginx + React | `latest`, `git-sha` (short) |

Tags: images will be tagged with both `latest` and the full 7-character Git commit SHA (e.g., `a3f892c`). Production deployments reference the SHA tag for immutability; `latest` is used for convenience.

### Image Size Targets

| Image | Estimated Size |
|---|---|
| `ml-deploy-backend` | ~250–350 MB (Python slim + compiled C extensions for psycopg2/paramiko) |
| `ml-deploy-frontend` | ~30–50 MB (nginx:alpine + static assets) |

---

## 4. Infrastructure Design

### AWS Region Strategy

- **Primary region:** `us-east-1` (configurable via Terraform variable)
- **Availability zones:** 2 AZs minimum (`us-east-1a`, `us-east-1b`) for high availability
- No multi-region deployment in initial rollout

### Resource Inventory

| Resource | Service | Notes |
|---|---|---|
| VPC | Networking | `/16` CIDR, dedicated to this platform |
| Public subnets (×2) | Networking | 1 per AZ — ALB, NAT gateway |
| Private subnets (×2) | Networking | 1 per AZ — ECS tasks, RDS |
| Internet Gateway | Networking | Public subnet internet access |
| NAT Gateway | Networking | Private subnet outbound (ECS → DockerHub, GitHub, AWS APIs) |
| Route tables | Networking | Public (IGW) + Private (NAT) |
| Application Load Balancer | Compute | Public-facing, HTTPS termination |
| ALB Target Groups | Compute | `frontend-tg` (port 80), `backend-tg` (port 5000) |
| ECS Cluster | Compute | Fargate launch type |
| ECS Service: backend | Compute | 1–4 tasks, Fargate, private subnet |
| ECS Service: frontend | Compute | 1–2 tasks, Fargate, private subnet |
| ECS Task Definition: backend | Compute | 512 CPU / 1024 MB RAM (initial) |
| ECS Task Definition: frontend | Compute | 256 CPU / 512 MB RAM (initial) |
| Auto Scaling Policies | Compute | CPU ≥ 70% → scale out; CPU ≤ 30% → scale in |
| RDS Instance | Database | `db.t3.medium`, PostgreSQL 16, Multi-AZ |
| RDS Subnet Group | Database | Private subnets only |
| RDS Parameter Group | Database | Custom params: `log_min_duration_statement=1000` |
| ECR Repository (×2) | Registry | backend + frontend |
| ACM Certificate | Security | Wildcard or domain-specific TLS cert |
| Secrets Manager Secret | Security | DATABASE_URL, SECRET_KEY, AWS creds, SSH key |
| IAM Role: ECS Task Execution | Security | Pull from ECR, write CloudWatch Logs |
| IAM Role: ECS Task | Security | EC2 + SSM permissions (for the platform's own operations) |
| S3 Bucket: Terraform state | Bootstrap | Versioned, encrypted, private |
| DynamoDB Table: TF lock | Bootstrap | State locking |
| CloudWatch Log Groups | Monitoring | `/ecs/ml-deploy/backend`, `/ecs/ml-deploy/frontend` |
| CloudWatch Alarms | Monitoring | CPU, memory, ALB 5xx rate, RDS connections |
| SNS Topic | Monitoring | Alert routing to email / PagerDuty |

### Compute Sizing (Initial)

| Service | vCPU | Memory | Min Tasks | Max Tasks |
|---|---|---|---|---|
| Backend | 0.5 | 1024 MB | 1 | 4 |
| Frontend | 0.25 | 512 MB | 1 | 2 |
| RDS | db.t3.medium | 4 GB | — | — (Multi-AZ standby) |

These are starting values. Right-sizing should follow two weeks of production metrics.

---

## 5. Networking Architecture

### VPC Layout

```
VPC: 10.0.0.0/16
│
├── Public Subnet AZ-a: 10.0.1.0/24  ──┐
│   (ALB, NAT Gateway)                  │
│                                        │─── Internet Gateway
├── Public Subnet AZ-b: 10.0.2.0/24  ──┘
│   (ALB, NAT Gateway)
│
├── Private Subnet AZ-a: 10.0.11.0/24
│   (ECS tasks — backend, frontend)
│   (RDS Primary)
│   Route: 0.0.0.0/0 → NAT Gateway AZ-a
│
└── Private Subnet AZ-b: 10.0.12.0/24
    (ECS tasks — backend, frontend)
    (RDS Standby / Multi-AZ)
    Route: 0.0.0.0/0 → NAT Gateway AZ-b
```

### Traffic Flows

**Inbound (user → application):**
```
Internet → IGW → ALB (public subnet :443)
  → ALB path rule:  /api/* or /socket.io/*  → Backend TG → ECS backend task :5000
  → ALB path rule:  /* (default)             → Frontend TG → ECS frontend task :80
```

**Outbound (ECS tasks → external):**
```
ECS tasks (private subnet) → NAT Gateway → IGW → Internet
  (used for: ECR image pulls, GitHub cloning on managed EC2s via paramiko,
   PyPI/npm during builds, DockerHub pulls on managed EC2s, AWS API calls)
```

**Database:**
```
ECS backend task (private subnet) → RDS Security Group → RDS :5432 (private subnet)
```

**Managed EC2 instances (platform workload):**
```
ECS backend task → boto3 → AWS EC2 API (create/stop/terminate instances)
ECS backend task → paramiko (SSH) → managed EC2 public IP :22
  (SSH key injected from Secrets Manager at task startup)
```

### ALB Listener Rules

| Priority | Condition | Target Group | Protocol |
|---|---|---|---|
| 1 | Path: `/api/*` | `backend-tg` | HTTP/1.1 |
| 2 | Path: `/socket.io/*` | `backend-tg` | HTTP/1.1, WebSocket upgrade |
| 3 (default) | `/*` | `frontend-tg` | HTTP/1.1 |

**WebSocket note:** ALB natively supports WebSocket upgrades. The `Connection: Upgrade` and `Upgrade: websocket` headers are forwarded. Sticky sessions (duration-based cookies) should be enabled on `backend-tg` to ensure Socket.IO connections remain on the same ECS task.

### DNS

- Primary domain registered in Route 53 (e.g., `mlplatform.example.com`)
- ALB alias record in Route 53 pointing to the ALB DNS name
- ACM certificate covers the domain for HTTPS termination at the ALB

---

## 6. Security Architecture

### Principle of Least Privilege

All IAM principals are granted only the minimum permissions required. No wildcard resource ARNs on destructive actions.

### IAM Roles

#### ECS Task Execution Role (`ecs-task-execution-role`)

Assumed by the ECS agent (not the application). Required to:
- Pull container images from ECR
- Write logs to CloudWatch Logs
- Fetch secrets from Secrets Manager (for injecting into the container environment)

Managed policies:
- `AmazonECSTaskExecutionRolePolicy` (AWS managed)

Inline additions:
- `secretsmanager:GetSecretValue` on specific secret ARNs
- `kms:Decrypt` if secrets are encrypted with a custom KMS key

#### ECS Task Role (`ml-deploy-task-role`)

Assumed by the application code running inside the container. Required for:
- Creating / describing / stopping / terminating EC2 instances (the platform's core function)
- Describing security groups, key pairs, and AMIs
- Writing deployment logs to CloudWatch Logs (structured logging)
- Fetching its own secrets from Secrets Manager at runtime

Minimum permissions:
```
ec2:RunInstances
ec2:DescribeInstances
ec2:StopInstances
ec2:StartInstances
ec2:TerminateInstances
ec2:DescribeSecurityGroups
ec2:CreateSecurityGroup
ec2:AuthorizeSecurityGroupIngress
ec2:DescribeKeyPairs
ec2:DescribeImages
ec2:CreateTags
logs:CreateLogGroup
logs:CreateLogStream
logs:PutLogEvents
secretsmanager:GetSecretValue
```

> **Important:** The ECS task role replaces the need for `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` environment variables in production. boto3 automatically uses the task role credentials via the ECS credentials endpoint. The `config.py` AWS credential loading should be updated to omit explicit key injection and rely on the IAM role.

### Security Groups

| Security Group | Inbound | Outbound |
|---|---|---|
| `sg-alb` | 443 from `0.0.0.0/0`, 80 from `0.0.0.0/0` | All to `sg-ecs-backend`, `sg-ecs-frontend` |
| `sg-ecs-backend` | 5000 from `sg-alb` | 5432 to `sg-rds`, 443 to internet (HTTPS), 22 to EC2 instances (paramiko) |
| `sg-ecs-frontend` | 80 from `sg-alb` | HTTPS to internet (none required at runtime) |
| `sg-rds` | 5432 from `sg-ecs-backend` | None |
| `sg-managed-ec2` | 22 from `sg-ecs-backend` (SSH), 80/443 from `0.0.0.0/0` (apps) | All |

### Secrets Management

All sensitive values are stored in **AWS Secrets Manager**, not in environment variables passed via the task definition in plaintext. ECS supports native Secrets Manager injection via the `secrets` block in the task definition.

| Secret Name | Contents |
|---|---|
| `ml-deploy/prod/database-url` | Full PostgreSQL connection string |
| `ml-deploy/prod/secret-key` | Flask `SECRET_KEY` |
| `ml-deploy/prod/github-token` | GitHub API token (private repo access) |
| `ml-deploy/prod/ssh-private-key` | EC2 SSH private key (PEM) — replaces volume mount |
| `ml-deploy/prod/aws-credentials` | (Only needed if not using task role — prefer task role) |

### TLS / Encryption

- ALB terminates TLS using an ACM-managed certificate (auto-renewed)
- Backend-to-ALB communication is plaintext on the internal VPC network (standard practice with VPC security groups as the perimeter)
- RDS storage encryption at rest using AWS-managed KMS key
- RDS in-transit encryption enforced via `ssl_mode=require` in `DATABASE_URL`
- Secrets Manager values encrypted at rest using AWS-managed KMS key
- S3 Terraform state bucket: SSE-S3 encryption, versioning enabled, public access blocked

### Credential Removal from Codebase

Before production deployment, the following must be addressed:
1. Remove `COPY .env .` from `Dockerfile.backend` — no secrets in container images
2. Update `backend/config.py` to not require explicit `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` — use task role instead
3. Remove hardcoded `POSTGRES_PASSWORD: AutoDeploy123` from docker-compose (already separate from prod, but document it)
4. `SECRET_KEY` default `'dev-secret-key-change-in-production'` must always be overridden in production via Secrets Manager

---

## 7. Deployment Flow

### Application Deployment (Platform's Own Services)

This describes how the platform itself (the Flask + React app) is deployed to ECS Fargate — distinct from how the platform deploys user ML apps onto EC2.

```
Step 1 — Build
  GitHub Actions builds Docker images:
    docker build -f Dockerfile.backend -t ml-deploy/backend:$SHA .
    docker build -f Dockerfile.frontend -t ml-deploy/frontend:$SHA .

Step 2 — Push
  Images tagged and pushed to ECR:
    $ECR_REGISTRY/ml-deploy/backend:$SHA
    $ECR_REGISTRY/ml-deploy/backend:latest
    $ECR_REGISTRY/ml-deploy/frontend:$SHA
    $ECR_REGISTRY/ml-deploy/frontend:latest

Step 3 — Database Migrations (automatic)
  On every ECS backend task start, the CMD runs:
    alembic upgrade head
  This is safe because Alembic migration is idempotent (checks current revision).
  In ECS rolling deployments, new task starts first, runs migrations, then old task
  is drained. Migration backward compatibility must be maintained during rollover.

Step 4 — ECS Service Update
  GitHub Actions forces a new deployment on the ECS service:
    aws ecs update-service --cluster ml-deploy --service backend --force-new-deployment
    aws ecs update-service --cluster ml-deploy --service frontend --force-new-deployment

Step 5 — Rolling Deployment
  ECS performs a rolling update:
  - Minimum healthy percent: 100% (no downtime)
  - Maximum percent: 200% (new tasks start before old tasks stop)
  - ALB deregisters old tasks only after new tasks pass health checks

Step 6 — Health Check Verification
  ALB health check: GET /api/health → expects HTTP 200 with {"status": "healthy"}
  ECS considers a task healthy after N consecutive passing health checks.
  If the new task fails health checks, ECS rolls back automatically.
```

### Managed EC2 Deployment Flow (Platform's Core Functionality)

This is what the platform does when a user clicks "Deploy" in the UI:

```
Browser → POST /api/deploy { github_url: "...", ... }
  │
  ▼
Flask API (ECS backend task)
  │  spawns background thread
  ▼
DeploymentOrchestrator.deploy()
  │
  ├── boto3: Create EC2 instance (or reuse existing)
  │         → Wait for instance running state
  │         → Wait for status checks pass
  │
  ├── paramiko SSH: Wait for SSH to be available
  │                 → Upload SSH key (from Secrets Manager)
  │
  ├── GitHubManager: Install Git on EC2
  │                  → git clone <github_url>
  │
  ├── DockerManager: Install Docker CE on EC2
  │                  → docker build
  │                  → docker run -p <host_port>:<container_port>
  │
  ├── NginxManager: Install Nginx on EC2
  │                 → Configure reverse proxy
  │                 → Reload Nginx
  │
  ├── HealthChecker: Poll HTTP endpoint until healthy
  │
  └── DeploymentRepository: Persist all steps + logs to RDS

Each step emits Socket.IO events → ALB (WebSocket) → browser (real-time progress)
```

### Migration Deployment Safety

Because `alembic upgrade head` runs on task startup in a rolling deployment:
- Migrations must be **additive only** (add columns/tables, never drop or rename)
- Column renames require a three-step migration cycle: add → migrate data → drop old column
- No migration should remove columns that the currently running old tasks still reference

---

## 8. CI/CD Flow

### GitHub Actions Pipelines

Two pipelines will be defined in `.github/workflows/`:

#### Pipeline 1: `ci.yml` — Continuous Integration

Triggers: every push to any branch, every pull request to `main`

```
Jobs:
  test:
    runs-on: ubuntu-latest
    services:
      postgres:
        image: postgres:16-alpine
        env: { POSTGRES_DB: test_db, POSTGRES_USER: test, POSTGRES_PASSWORD: test }
    steps:
      - checkout
      - setup Python 3.11
      - pip install -r requirements.txt
      - run: pytest tests/ -v --tb=short --cov=backend
      - upload coverage report

  lint:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup Python 3.11
      - pip install ruff (or flake8)
      - run: ruff check backend/ tests/

  frontend-build:
    runs-on: ubuntu-latest
    steps:
      - checkout
      - setup Node 20
      - npm ci (in frontend/)
      - npm run build
      - npm run lint
```

#### Pipeline 2: `deploy.yml` — Continuous Deployment

Triggers: push to `main` branch only (after CI passes)

```
Jobs:
  build-and-deploy:
    runs-on: ubuntu-latest
    permissions:
      id-token: write   # OIDC — no long-lived AWS keys in GitHub
      contents: read

    steps:
      1. Checkout code  (git SHA → IMAGE_TAG)

      2. Configure AWS credentials
         - Use OIDC (aws-actions/configure-aws-credentials@v4)
         - IAM role: arn:aws:iam::<account>:role/github-actions-deploy-role
         - No AWS_ACCESS_KEY_ID stored in GitHub Secrets

      3. Login to ECR
         - aws-actions/amazon-ecr-login@v2

      4. Build and push backend image
         - docker build -f Dockerfile.backend -t $ECR_REGISTRY/ml-deploy/backend:$SHA .
         - docker tag ... :latest
         - docker push (both tags)

      5. Build and push frontend image
         - docker build -f Dockerfile.frontend -t $ECR_REGISTRY/ml-deploy/frontend:$SHA .
         - docker tag ... :latest
         - docker push (both tags)

      6. Render new ECS task definition
         - Download current task def JSON
         - Update image URI to new SHA tag (aws-actions/amazon-ecs-render-task-definition)
         - Repeat for both backend and frontend task defs

      7. Deploy to ECS
         - aws-actions/amazon-ecs-deploy-task-definition (backend service)
         - aws-actions/amazon-ecs-deploy-task-definition (frontend service)
         - wait-for-service-stability: true
         - Rolls back automatically if health checks fail

      8. Post-deploy smoke test
         - curl https://mlplatform.example.com/api/health
         - Assert: {"status": "healthy"}
```

### Required GitHub Secrets / Variables

| Name | Type | Purpose |
|---|---|---|
| `AWS_ACCOUNT_ID` | Variable | ECR registry prefix |
| `AWS_REGION` | Variable | Target region |
| `ECR_BACKEND_REPO` | Variable | ECR repo name for backend |
| `ECR_FRONTEND_REPO` | Variable | ECR repo name for frontend |
| `ECS_CLUSTER` | Variable | ECS cluster name |
| `ECS_SERVICE_BACKEND` | Variable | ECS service name for backend |
| `ECS_SERVICE_FRONTEND` | Variable | ECS service name for frontend |

No long-lived AWS credentials are stored. OIDC federation grants GitHub Actions a temporary role via `id-token: write`.

### Branch Strategy

| Branch | Pipeline | Environment |
|---|---|---|
| `main` | CI + CD | Production |
| `develop` | CI only | — |
| Feature branches | CI only | — |
| Pull requests to `main` | CI only | — |

---

## 9. Monitoring Strategy

### CloudWatch Log Groups

| Log Group | Retention | Source |
|---|---|---|
| `/ecs/ml-deploy/backend` | 30 days | Backend ECS task `awslogs` driver |
| `/ecs/ml-deploy/frontend` | 14 days | Frontend ECS task `awslogs` driver |
| `/rds/ml-deploy/postgresql` | 7 days | RDS enhanced monitoring |

All application logs are already structured (uses `colorlog` + Python logging). In production, the log format should emit JSON to enable CloudWatch Insights queries.

### CloudWatch Alarms

| Alarm | Metric | Threshold | Action |
|---|---|---|---|
| Backend CPU High | `ECS/CPUUtilization` (backend service) | > 70% for 5 min | Scale out + SNS alert |
| Backend Memory High | `ECS/MemoryUtilization` (backend service) | > 80% for 5 min | SNS alert |
| ALB 5xx Rate | `ApplicationELB/HTTPCode_Target_5XX_Count` | > 10 in 5 min | SNS alert |
| ALB Target Unhealthy | `ApplicationELB/UnHealthyHostCount` | > 0 for 2 min | SNS alert (paging priority) |
| RDS CPU High | `RDS/CPUUtilization` | > 80% for 10 min | SNS alert |
| RDS Free Storage Low | `RDS/FreeStorageSpace` | < 5 GB | SNS alert |
| RDS Connection Count High | `RDS/DatabaseConnections` | > 80 | SNS alert |
| ECS Task Stopped | CloudWatch Events rule | Any `STOPPED` event | SNS alert |

### Auto Scaling

Auto scaling for ECS services is based on CloudWatch metrics:

**Backend service:**
- Scale out: Average CPU > 70% for 3 minutes → add 1 task
- Scale in: Average CPU < 30% for 10 minutes → remove 1 task
- Min tasks: 1, Max tasks: 4
- Scale-in cooldown: 300 seconds (avoids flapping)

**Frontend service:**
- Scale out: Average CPU > 60% for 3 minutes → add 1 task
- Scale in: Average CPU < 20% for 10 minutes → remove 1 task
- Min tasks: 1, Max tasks: 2

### Health Check Endpoints

The existing `/api/health` endpoint already checks DB connectivity and is suitable as the ALB target group health check:

```
GET /api/health
200 → {"status": "healthy", "database": "connected"}
503 → {"status": "degraded", "database": "unreachable"}
```

ALB configuration:
- Path: `/api/health`
- Protocol: HTTP
- Port: 5000 (backend TG)
- Healthy threshold: 2 consecutive 200s
- Unhealthy threshold: 3 consecutive non-200s
- Interval: 30 seconds
- Timeout: 10 seconds

### SNS Topics

| Topic | Subscribers |
|---|---|
| `ml-deploy-critical-alerts` | On-call email, PagerDuty (future) |
| `ml-deploy-info-alerts` | Team email distribution list |

---

## 10. Infrastructure Phasing Plan

Each phase is independently deployable and verifiable before proceeding to the next. Phases build on prior phases.

---

### Phase 1 — Bootstrap (Terraform Remote State)

**Goal:** Establish the Terraform state backend so all subsequent phases use remote state with locking.

**Resources:**
- S3 bucket for Terraform state (versioned, SSE-S3 encrypted, public access fully blocked)
- DynamoDB table for state locking (`LockID` partition key, PAY_PER_REQUEST billing)

**Implementation note:** Phase 1 is bootstrapped manually (or with a local `terraform apply`) once. The S3 bucket and DynamoDB table cannot themselves be stored in the remote state they are creating.

**Verification:** Run `terraform init -reconfigure` from Phase 2 onward with the backend config pointing to the S3 bucket. Confirm lock is acquired/released on `terraform plan`.

---

### Phase 2 — Networking

**Goal:** Establish the full network foundation that all other resources will live in.

**Resources:**
- VPC (`10.0.0.0/16`)
- 2 public subnets (`10.0.1.0/24`, `10.0.2.0/24`) across 2 AZs
- 2 private subnets (`10.0.11.0/24`, `10.0.12.0/24`) across 2 AZs
- Internet Gateway (attached to VPC)
- 2 NAT Gateways (one per AZ, in public subnets) with Elastic IPs
- Public route table: `0.0.0.0/0 → IGW`, associated with public subnets
- Private route tables: `0.0.0.0/0 → NAT GW`, one per AZ, associated with private subnets
- VPC Flow Logs → CloudWatch Logs (for network security investigation)

**Verification:** Confirm VPC and subnets visible in AWS Console. Launch a test EC2 in a private subnet and verify it can reach `8.8.8.8` via NAT.

---

### Phase 3 — Security

**Goal:** Define all security groups and IAM roles that will be referenced by later phases.

**Resources:**
- Security group: `sg-alb` (inbound 80/443 from internet)
- Security group: `sg-ecs-backend` (inbound 5000 from `sg-alb`)
- Security group: `sg-ecs-frontend` (inbound 80 from `sg-alb`)
- Security group: `sg-rds` (inbound 5432 from `sg-ecs-backend`)
- IAM role: `ecs-task-execution-role` + trust policy for `ecs-tasks.amazonaws.com`
- IAM role: `ml-deploy-task-role` + EC2/SSM/Secrets Manager inline policies
- IAM role: `github-actions-deploy-role` + OIDC trust policy for GitHub Actions
- Secrets Manager secrets (empty values, correct ARNs to reference in Phase 6)
- ACM certificate request (DNS-validated via Route 53)

**Verification:** Confirm IAM roles can be assumed. Confirm security groups have correct rules. Certificate status reaches `ISSUED`.

---

### Phase 4 — ECR

**Goal:** Create container registries and test that images can be pushed.

**Resources:**
- ECR repository: `ml-deploy/backend` (image scanning on push enabled, lifecycle policy: keep last 10 images)
- ECR repository: `ml-deploy/frontend` (same lifecycle policy)

**Verification:** Manually build and push a test image to both repositories. Confirm images appear in ECR console with vulnerability scan results.

---

### Phase 5 — RDS

**Goal:** Deploy the PostgreSQL database in private subnets.

**Resources:**
- RDS DB subnet group (covers both private subnets)
- RDS parameter group (PostgreSQL 16 family, custom params)
- RDS instance: `db.t3.medium`, PostgreSQL 16, Multi-AZ, 20 GB gp3 storage, auto-scaling to 100 GB
- RDS security group association: `sg-rds`
- Automated backups: 7-day retention
- Enhanced monitoring: 60-second granularity
- Performance Insights: enabled

**Secrets to populate after RDS creation:**
- `ml-deploy/prod/database-url` → `postgresql://dbadmin:<password>@<rds-endpoint>:5432/autodeploy`

**Verification:** From a bastion host or ECS task (after Phase 6), `psql` into the RDS endpoint. Confirm connection succeeds and database is empty.

---

### Phase 6 — Compute

**Goal:** Deploy both ECS services with the ALB in front.

**Resources:**
- ALB (internet-facing, in public subnets, `sg-alb`)
- ALB listener: HTTPS :443, ACM cert attached, redirect HTTP :80 → HTTPS
- ALB target group: `backend-tg` (port 5000, health check `/api/health`)
- ALB target group: `frontend-tg` (port 80, health check `/`)
- ALB listener rules (as defined in Section 5, Networking)
- ECS cluster: `ml-deploy` (Fargate)
- ECS task definition: `ml-deploy-backend` (backend image from ECR, secrets injected, logging to CloudWatch)
- ECS task definition: `ml-deploy-frontend` (frontend image from ECR, logging to CloudWatch)
- ECS service: `backend` (desired count: 1, rolling update, assigns to `backend-tg`)
- ECS service: `frontend` (desired count: 1, rolling update, assigns to `frontend-tg`)
- Application Auto Scaling targets and policies for both services

**Key task definition environment (backend):**

| Key | Source |
|---|---|
| `DATABASE_URL` | Secrets Manager: `ml-deploy/prod/database-url` |
| `SECRET_KEY` | Secrets Manager: `ml-deploy/prod/secret-key` |
| `GITHUB_TOKEN` | Secrets Manager: `ml-deploy/prod/github-token` |
| `SSH_PRIVATE_KEY_PEM` | Secrets Manager: `ml-deploy/prod/ssh-private-key` |
| `FLASK_ENV` | Plain env: `production` |
| `AWS_REGION` | Plain env: `us-east-1` |
| `LOG_LEVEL` | Plain env: `INFO` |
| `LOG_FILE` | Plain env: `/dev/stdout` (CloudWatch via awslogs driver) |

**Verification:** Access `https://mlplatform.example.com/api/health` — must return `{"status": "healthy"}`. Navigate to the React UI — must load. Trigger a test deployment from the UI.

---

### Phase 7 — Monitoring

**Goal:** Establish observability for all production services.

**Resources:**
- CloudWatch Log Groups (backend, frontend, RDS — as defined in Section 9)
- CloudWatch Metric Alarms (as defined in Section 9)
- SNS topic: `ml-deploy-critical-alerts` with email subscriptions
- SNS topic: `ml-deploy-info-alerts` with email subscriptions
- CloudWatch Dashboard: `ml-deploy-production` (ECS CPU/memory, ALB request count, RDS metrics)
- CloudWatch Logs Insights saved queries (5xx error analysis, slow deployment detection)
- EventBridge rule: ECS task state change → SNS notification

**Verification:** Manually trigger an ALB 5xx (e.g., stop backend tasks temporarily) and confirm alarm fires and email is received within 5 minutes.

---

### Phase 8 — CI/CD

**Goal:** Automate build, test, and deployment via GitHub Actions.

**Resources:**
- GitHub OIDC provider in IAM (one-time setup per AWS account)
- IAM role: `github-actions-deploy-role` (created in Phase 3, populated here with policies)
- `.github/workflows/ci.yml` — test, lint, frontend build on every push
- `.github/workflows/deploy.yml` — build images, push to ECR, update ECS on merge to `main`

**Verification:** Merge a trivial change to `main` and confirm the GitHub Actions pipeline completes successfully. Check that the new image SHA appears in ECS and `docker images` on the running task. Confirm smoke test step passes.

---

## Appendix A — Configuration Checklist (Pre-Production)

Before running `terraform apply` for Phase 6, the following items must be resolved in the application code:

- [ ] Remove `COPY .env .` from `Dockerfile.backend`
- [ ] Update `backend/config.py`: remove explicit `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` fields; rely on IAM role via boto3's default credential chain
- [ ] Update `nginx/frontend.conf`: change `proxy_pass http://backend:5000` to reference the backend via ALB internal hostname (or keep as-is if using sidecar pattern within same task)
- [ ] Ensure `LOG_FILE` defaults to `deployment.log` is overridden to `/dev/stdout` in ECS (or update the logging config to detect ECS environment)
- [ ] SSH key for managed EC2 instances must be read from `SSH_PRIVATE_KEY_PEM` environment variable (injected from Secrets Manager) rather than from the `ml-deploy-key.pem` file path
- [ ] `FLASK_ENV=production` disables the no-cache headers response middleware
- [ ] Review `ALLOWED_SSH_IP` config — in production, restrict to the ECS task subnet CIDRs, not `0.0.0.0/0`
- [ ] Set `SECRET_KEY` from Secrets Manager — never use the default value

---

## Appendix B — Deployment Topology Diagram (ECS)

```
                           ┌──────────────────────────┐
                           │       AWS Account         │
                           │                           │
  Internet ──── IGW ────► ALB (public subnets)        │
                           │  /api/* /socket.io/*      │
                           │       ↓          ↓        │
                           │  ┌──────────┐ ┌────────┐  │
                           │  │ backend  │ │frontend│  │
                           │  │ ECS Task │ │ECS Task│  │
                           │  │ :5000    │ │ :80    │  │
                           │  │ (private)│ │(priv.) │  │
                           │  └────┬─────┘ └────────┘  │
                           │       │                    │
                           │       ▼                    │
                           │  ┌──────────┐              │
                           │  │   RDS    │              │
                           │  │ Postgres │              │
                           │  │ :5432    │              │
                           │  │ (private)│              │
                           │  └──────────┘              │
                           │                           │
                           │  ECR  Secrets Mgr  CW     │
                           │  (supporting services)    │
                           └──────────────────────────┘
                                        │
                                        │ boto3 / paramiko
                                        ▼
                           ┌──────────────────────────┐
                           │  Managed EC2 instances   │
                           │  (customer ML app hosts) │
                           │  Docker + Nginx + apps   │
                           └──────────────────────────┘
```

---

# Repository Analysis

> This section documents facts **extracted directly from repository files**. Nothing here is assumed or inferred beyond what the code confirms. Where a property cannot be determined from repository files, it is marked as **"Not explicitly defined in repository"**.

---

### Application Components

The repository contains **three distinct runnable components** and **one example workload**:

#### Component 1 — React SPA Frontend (`frontend/`)

A single-page application served by Nginx.

| Property | Value | Source |
|---|---|---|
| Entry point | `frontend/src/main.jsx` | `package.json` → `vite build` |
| Router | React Router v7, client-side | `App.jsx` |
| Pages | 4 (`Dashboard`, `Deploy`, `Applications`, `Instances`) | `frontend/src/pages/` |
| UI Components | 9 (`ApplicationsTable`, `ConfirmDialog`, `DeploymentForm`, `InstancesGrid`, `Navbar`, `ProgressTracker`, `Sidebar`, `StatCard`, `Toast`) | `frontend/src/components/` |
| Services | `api.js` (HTTP), `socket.js` (WebSocket) | `frontend/src/services/` |
| Hooks | `useToast.js` | `frontend/src/hooks/` |
| Constants | `API_BASE_URL`, deployment step names, status codes, instance states | `frontend/src/utils/constants.js` |
| API base URL | `import.meta.env.VITE_API_URL` or `http://localhost:5000` | `constants.js` |
| Build output | `frontend/dist/` → copied to Nginx image | `Dockerfile.frontend` |
| Dark mode | Hardcoded `className="dark"` in `App.jsx` | `App.jsx` |

**Deployment step sequence** (from `constants.js`, directly drives the progress tracker UI):
```
Validation → EC2 Creation → SSH Connection → Docker Installation →
NGINX Installation → Repository Clone → Project Validation →
Docker Build → Container Deployment → NGINX Configuration →
Health Check → Deployment Complete
```

#### Component 2 — Flask REST + WebSocket Backend (`backend/`)

A Python application exposing both a REST API and a WebSocket server.

| Property | Value | Source |
|---|---|---|
| Application factory | `backend.app:create_app()` | `app.py`, `Dockerfile.backend` CMD |
| WSGI server | Gunicorn 21, gthread worker, 1 worker × 4 threads | `Dockerfile.backend` CMD |
| Listening port | `5000` | `config.py` → `APP_PORT` |
| Blueprints | `health_bp`, `deployments_bp`, `applications_bp`, `instances_bp` | `app.py` |
| WebSocket library | Flask-SocketIO 5.3, `async_mode='threading'` | `app.py` |
| Background jobs | Python `threading.Thread` (daemon=True) per deployment | `api/deployments.py` |
| Static files | `../frontend` (serves SPA `index.html` at `/`) | `app.py` `static_folder` |
| DB session lifecycle | `@app.teardown_appcontext` — closed after every request | `app.py` |
| Log filtering | Suppresses `/socket.io/` poll lines and `/api/health` calls from logs | `core/logging_config.py` |
| JSON log formatter | `JSONFormatter` class present, disabled by default | `core/logging_config.py` |
| Deployment context tracking | `contextvars.ContextVar` injects `deployment_id` into every log record | `core/logging_config.py` |

**Provider modules** (all communicate with remote EC2 instances via paramiko SSH):

| Module | Location | Responsibility |
|---|---|---|
| `AWSManager` | `providers/aws/aws_manager.py` | Create EC2 instances, security groups, describe/stop/terminate via boto3 |
| `DockerManager` | `providers/docker/docker_manager.py` | Install Docker CE on EC2, build images, run/stop containers via SSH |
| `GitHubManager` | `providers/github/github_manager.py` | Install Git on EC2, `git clone` target repositories via SSH |
| `NginxManager` | `providers/nginx/nginx_manager.py` | Install Nginx on EC2, write reverse-proxy config, reload via SSH |

**Service classes:**

| Class | Location | Responsibility |
|---|---|---|
| `DeploymentOrchestrator` | `services/deployment_orchestrator.py` | Coordinates all provider calls in sequence; persists every step and log line to DB; emits Socket.IO progress events |
| `HealthChecker` | `services/health_checker.py` | Polls HTTP endpoint and Docker container status on managed EC2 instances |

**Repository (data access) layer** (`database/repositories.py`):

| Class | Tables Managed |
|---|---|
| `TenantRepository` | `tenants` |
| `ApplicationRepository` | `applications` |
| `EC2InstanceRepository` | `ec2_instances` |
| `DeploymentRepository` | `deployments`, `deployment_steps`, `deployment_logs` |

#### Component 3 — PostgreSQL Database

Managed by Alembic migrations; not a custom application but a first-class runtime dependency.

| Property | Value | Source |
|---|---|---|
| Engine | PostgreSQL 16-alpine (Docker Compose) | `docker-compose.yml` |
| Database name | `autodeploy` | `docker-compose.yml` |
| Default user | `dbadmin` | `docker-compose.yml` |
| Connection | `DATABASE_URL` environment variable | `database/connection.py` |
| Fallback (dev) | SQLite at `<project_root>/deployment_platform.db` | `database/connection.py` |
| Schema manager | Alembic 1.13, 2 migrations present | `alembic/versions/` |
| ORM | SQLAlchemy 2.0, `DeclarativeBase` | `database/models.py` |

#### Component 4 — Example ML Application (`example_ml_app/`)

A minimal Python app used to validate the platform's own deployment pipeline.

| Property | Value | Source |
|---|---|---|
| Runtime | Python 3.9-slim | `example_ml_app/Dockerfile` |
| Exposed port | `8000` | `example_ml_app/Dockerfile` |
| Purpose | Platform dogfooding / smoke-test target | `example_ml_app/README.md` |

---

### Runtime Technologies

#### Backend Runtime

| Technology | Version | Declared In |
|---|---|---|
| Python | 3.11 | `Dockerfile.backend` (`FROM python:3.11-slim`) |
| Flask | 3.0.0 | `requirements.txt` |
| Flask-CORS | 4.0.0 | `requirements.txt` |
| Flask-SocketIO | 5.3.5 | `requirements.txt` |
| python-socketio | 5.11.0 | `requirements.txt` |
| eventlet | 0.35.1 | `requirements.txt` |
| Gunicorn | 21.2.0 | `requirements.txt` |
| SQLAlchemy | 2.0.25 | `requirements.txt` |
| Flask-SQLAlchemy | 3.1.1 | `requirements.txt` |
| Alembic | 1.13.1 | `requirements.txt` |
| psycopg2-binary | 2.9.9 | `requirements.txt` |
| boto3 | 1.34.19 | `requirements.txt` |
| botocore | 1.34.19 | `requirements.txt` |
| paramiko | 3.4.0 | `requirements.txt` |
| python-dotenv | 1.0.0 | `requirements.txt` |
| requests | 2.31.0 | `requirements.txt` |
| validators | 0.22.0 | `requirements.txt` |
| colorlog | 6.8.0 | `requirements.txt` |
| python-dateutil | 2.8.2 | `requirements.txt` |

**System packages installed in the backend image** (from `Dockerfile.backend`):
- `gcc` — required by some Python C extension builds
- `libpq-dev` — required by `psycopg2-binary`
- `openssh-client` — required by paramiko for SSH key operations

#### Frontend Runtime

| Technology | Version | Declared In |
|---|---|---|
| Node.js | 20-alpine (build stage only) | `Dockerfile.frontend` |
| React | 19.2.0 | `frontend/package.json` |
| React DOM | 19.2.0 | `frontend/package.json` |
| React Router DOM | 7.13.0 | `frontend/package.json` |
| socket.io-client | 4.8.3 | `frontend/package.json` |
| Vite | 7.2.4 | `frontend/package.json` |
| Tailwind CSS | 4.1.18 | `frontend/package.json` |
| lucide-react | 0.563.0 | `frontend/package.json` |
| clsx | 2.1.1 | `frontend/package.json` |
| tailwind-merge | 3.4.0 | `frontend/package.json` |

**Final frontend image** (from `Dockerfile.frontend`): `nginx:alpine` — Node.js is build-time only and is **not present** in the deployed container image.

#### Test Runtime

| Technology | Version / Note | Source |
|---|---|---|
| pytest | 7.4.3 | `requirements.txt` |
| pytest-cov | 4.1.0 | `requirements.txt` |
| bcrypt | imported in `tests/conftest.py` | **not listed in `requirements.txt`** |
| PyJWT | imported as `jwt` in `tests/conftest.py` | **not listed in `requirements.txt`** |

> **Gap identified:** `bcrypt` and `PyJWT` are used by the test suite (`tests/conftest.py`) but are absent from `requirements.txt`. They must be added before the test suite can fully run.

---

### Containerization Overview

#### Docker Compose Services (local development)

Three services are defined in `docker-compose.yml`:

| Service | Image / Build | Internal Port | Host Port | Restart Policy | Health Check |
|---|---|---|---|---|---|
| `postgres` | `postgres:16-alpine` | 5432 | 5432 | `unless-stopped` | `pg_isready -U dbadmin -d autodeploy` |
| `backend` | `Dockerfile.backend` | 5000 | 5000 | `unless-stopped` | None defined |
| `frontend` | `Dockerfile.frontend` | 80 | 80 | `unless-stopped` | None defined |

**Startup order:** `backend` waits on `postgres` (`depends_on: condition: service_healthy`). `frontend` has no explicit dependency — it relies on Nginx proxying to the backend service name.

**Shared Docker network:** `app_network` (bridge mode) — all three services communicate by service name (e.g., `postgres`, `backend`).

**Persistent volume:** `postgres_data` is mounted to `/var/lib/postgresql/data` in the `postgres` service.

**SSH key volume mount:** `./backend/ml-deploy-key.pem:/app/backend/ml-deploy-key.pem:ro` — the EC2 SSH private key is bind-mounted read-only into the backend container. **This pattern cannot be used in ECS Fargate** (no bind mounts to host filesystem); the key must be injected via AWS Secrets Manager.

#### Backend Image Build (`Dockerfile.backend`)

```
Base:     python:3.11-slim
Packages: gcc, libpq-dev, openssh-client
Work dir: /app
Steps:    pip install requirements.txt
          COPY backend/ → ./backend/
          COPY alembic/ → ./alembic/
          COPY alembic.ini
          COPY .env          ← MUST be removed for production
ENV:      PYTHONPATH=/app
Port:     5000
CMD:      alembic upgrade head && gunicorn -k gthread -w 1 --threads 4
          --bind 0.0.0.0:5000 --timeout 300 "backend.app:create_app()"
```

**Production blocker:** `COPY .env .` embeds all secrets into the container image layer. This line must be removed before building production images.

#### Frontend Image Build (`Dockerfile.frontend`)

```
Stage 1 (builder):
  Base:     node:20-alpine
  Work dir: /app
  Steps:    npm ci (from package.json + package-lock.json)
            COPY frontend/ → ./
            npm run build   (outputs to /app/dist/)

Stage 2 (serve):
  Base:     nginx:alpine
  Config:   COPY nginx/frontend.conf → /etc/nginx/conf.d/default.conf
  Content:  COPY --from=builder /app/dist → /usr/share/nginx/html
  Port:     80
  CMD:      nginx -g "daemon off;"
```

No environment variables are baked into the frontend image at build time. The `VITE_API_URL` is resolved at build time if set; otherwise defaults to `http://localhost:5000` at runtime via `constants.js`.

#### Nginx Reverse-Proxy Configuration (`nginx/frontend.conf`)

```nginx
location /          → try_files (SPA fallback to index.html)
location /api/      → proxy_pass http://backend:5000
location /socket.io/ → proxy_pass http://backend:5000
                       (includes Upgrade + Connection headers for WebSocket)
```

**Service discovery note:** `http://backend:5000` works in Docker Compose (shared bridge network). In ECS, this must resolve to the backend service's ALB listeners or an internal DNS name.

---

### Service Dependencies

#### Internal Dependencies (runtime)

```
frontend (Nginx)
  └── backend:5000          HTTP proxy for /api/* and /socket.io/*

backend (Flask/Gunicorn)
  ├── postgres:5432          SQLAlchemy DATABASE_URL (required — app exits on failure)
  └── [managed EC2 instances] boto3 (EC2 API) + paramiko (SSH) — runtime only, on deployments
```

#### External Dependencies (network egress required)

| Dependency | Protocol | Purpose | Required At |
|---|---|---|---|
| `github.com` | HTTPS 443 | `git clone` target repos onto managed EC2 instances (via SSH from EC2, not from backend container directly) | Deployment time |
| `github.com API` | HTTPS 443 | Validate repo existence (`validate_github_repo_exists`) from backend | Request time |
| `AWS EC2 API` | HTTPS 443 | Create/describe/stop/terminate EC2 instances | Deployment time |
| `AWS Secrets Manager` | HTTPS 443 | Fetch SSH PEM key ARN at runtime (PEM_SECRET_NAME) | Deployment time |
| `DockerHub` / container registries | HTTPS 443 | `docker pull` base images on managed EC2 instances (from EC2, not backend) | Deployment time |
| `apt.ubuntu.com` (Ubuntu repos) | HTTP/HTTPS | `apt-get install` Docker, Git, Nginx on managed EC2 instances (from EC2, not backend) | Deployment time |

#### No Message Queue, No Cache Layer

The repository contains **no Redis, RabbitMQ, Celery, or any message queue dependency**. All background processing is via Python `threading.Thread` spawned within the Gunicorn process. This is confirmed by:
- `requirements.txt` — no Redis, Celery, or similar packages
- `api/deployments.py` — `Thread(target=run_deployment, daemon=True).start()`
- `docker-compose.yml` — no cache or queue service defined

#### Database Relationship Map

```
tenants (1)
  ├── applications (N)        tenant_id FK
  │     ├── application_instances (N)   application_id FK
  │     ├── deployments (N)             application_id FK
  │     │     ├── deployment_steps (N)  deployment_id FK
  │     │     └── deployment_logs (N)   deployment_id FK  [BIGSERIAL PK]
  │     └── environment_variables (N)   application_id FK
  │           └── secrets (1 opt.)      secret_id FK
  └── secrets (N)             tenant_id FK

ec2_instances (1)
  ├── application_instances (N)  instance_id FK  [joins to applications]
  └── instance_metrics (N)       instance_id FK  [BIGSERIAL PK]
```

---

### Configuration and Environment Variables

All configuration is loaded by `backend/config.py` via `python-dotenv` reading a `.env` file. A `.env.example` template is present at the repository root.

#### Complete Variable Inventory

**AWS Configuration**

| Variable | Default | Required | Source |
|---|---|---|---|
| `AWS_ACCESS_KEY_ID` | None | Yes (unless IAM role used) | `.env.example`, `config.py` |
| `AWS_SECRET_ACCESS_KEY` | None | Yes (unless IAM role used) | `.env.example`, `config.py` |
| `AWS_REGION` | `us-east-1` | No | `.env.example`, `config.py` |
| `AWS_DEFAULT_INSTANCE_TYPE` | `t2.micro` | No | `.env.example`, `config.py` |
| `AWS_KEY_PAIR_NAME` | None | Yes | `.env.example`, `config.py` |

**EC2 Instance Configuration**

| Variable | Default | Required | Source |
|---|---|---|---|
| `EC2_AMI_ID` | `ami-0c55b159cbfafe1f0` | No | `.env.example`, `config.py` |
| `EC2_INSTANCE_TYPE` | `t2.micro` | No | `.env.example`, `config.py` |
| `EC2_VOLUME_SIZE` | `20` (GB) | No | `.env.example`, `config.py` |

**Security Group Configuration**

| Variable | Default | Required | Source |
|---|---|---|---|
| `SECURITY_GROUP_NAME` | `ml-deployment-sg` | No | `.env.example`, `config.py` |
| `ALLOWED_SSH_IP` | `0.0.0.0/0` | No | `.env.example`, `config.py` |

**Application Configuration**

| Variable | Default | Required | Source |
|---|---|---|---|
| `APP_PORT` | `5000` | No | `.env.example`, `config.py` |
| `FLASK_ENV` | `development` | No | `.env.example`, `config.py` |
| `SECRET_KEY` | `dev-secret-key-change-in-production` | **Yes (production)** | `.env.example`, `config.py` |

**Docker Port Configuration (per-app deployment)**

| Variable | Default | Required | Source |
|---|---|---|---|
| `DOCKER_CONTAINER_PORT` | `8000` | No | `.env.example`, `config.py` |
| `DOCKER_HOST_PORT` | `8000` | No | `.env.example`, `config.py` |

**Deployment Behavior**

| Variable | Default | Required | Source |
|---|---|---|---|
| `MAX_DEPLOYMENT_TIME` | `600` (seconds) | No | `.env.example`, `config.py` |
| `HEALTH_CHECK_INTERVAL` | `10` (seconds) | No | `.env.example`, `config.py` |
| `HEALTH_CHECK_RETRIES` | `5` | No | `.env.example`, `config.py` |

**GitHub**

| Variable | Default | Required | Source |
|---|---|---|---|
| `GITHUB_TOKEN` | None | Optional (private repos only) | `.env.example`, `config.py` |

**Nginx / SSL** (for managed EC2s — not the platform's own Nginx)

| Variable | Default | Source |
|---|---|---|
| `ENABLE_NGINX` | `true` | `config.py` |
| `NGINX_HTTP_PORT` | `80` | `config.py` |
| `NGINX_HTTPS_PORT` | `443` | `config.py` |
| `ENABLE_SSL` | `false` | `config.py` |
| `SSL_EMAIL` | `""` | `config.py` |

**Logging**

| Variable | Default | Source |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `config.py` |
| `LOG_FILE` | `deployment.log` | `config.py` |

**Database**

| Variable | Default | Source |
|---|---|---|
| `DATABASE_URL` | `sqlite:///<project_root>/deployment_platform.db` | `database/connection.py` |

**Additional variables referenced in tests (not yet in `config.py` or `.env.example`)**

| Variable | Purpose | Source |
|---|---|---|
| `JWT_SECRET_KEY` | JWT token signing key | `tests/conftest.py` |
| `JWT_EXPIRY_HOURS` | Token lifetime | `tests/conftest.py` |
| `PEM_SECRET_NAME` | AWS Secrets Manager secret name for SSH PEM key | `tests/conftest.py` |
| `ADMIN_EMAIL` | Seed admin account email | `tests/conftest.py` |
| `ADMIN_PASSWORD` | Seed admin account password | `tests/conftest.py` |
| `CORS_ORIGINS` | Allowed CORS origins for production | `tests/conftest.py` |
| `FRONTEND_URL` | Frontend URL (CORS or redirect use) | `tests/conftest.py` |
| `TESTING` | Disables AWS/SSH calls in test mode | `tests/conftest.py` |

> These variables are set in `tests/conftest.py` but have no corresponding entries in `config.py` or `.env.example`, indicating they belong to **in-progress authentication and security features** that are tested but not yet merged into the main application code.

#### Configuration Loading Sequence

```
1. python-dotenv loads .env from project root (backend/config.py calls load_dotenv())
2. os.getenv() reads values with defaults
3. alembic/env.py separately loads .env (for DATABASE_URL) and overrides alembic.ini
4. Tests: os.environ.setdefault() in tests/conftest.py sets values before backend imports
```

---

### Networking Requirements

#### Public-Facing Services (internet-accessible)

| Service | Port | Protocol | Rationale |
|---|---|---|---|
| `frontend` | 80 | HTTP | Browser access to React SPA |
| `backend` | 5000 | HTTP + WebSocket | Direct API access (also proxied through frontend Nginx) |

> In the Docker Compose setup both ports are `host`-published. In production (ECS), only the ALB should be internet-accessible; ECS tasks should be in private subnets with no public IPs.

#### Internal-Only Services

| Service | Port | Protocol | Rationale |
|---|---|---|---|
| `postgres` | 5432 | TCP (PostgreSQL protocol) | Database — no public access ever needed |
| Backend → EC2 SSH | 22 | TCP (SSH/paramiko) | Platform-to-managed-EC2 only; ECS backend task must egress to managed EC2 public IPs |

#### WebSocket Transport Mode

The Socket.IO client (`frontend/src/services/socket.js`) is explicitly configured with `transports: ['polling']` only — **WebSocket upgrade is disabled on the client side**. This means:
- No `Upgrade: websocket` HTTP header is sent
- The connection uses HTTP long-polling exclusively
- ALB does **not** need sticky sessions for WebSocket protocol (but does need them for Socket.IO session affinity across multiple backend tasks)
- ALB idle timeout must be ≥ `pingTimeout` (300,000 ms = 5 minutes) to avoid mid-deployment disconnects

#### API URL Resolution

The frontend resolves the API server via `VITE_API_URL` at build time. If not set, it defaults to `http://localhost:5000`. In production:
- When served through the Nginx proxy (same origin), the default `http://localhost:5000` will **not** work from a browser connecting to the ALB
- `VITE_API_URL` must be set to an empty string (to use same-origin relative paths, relying on the Nginx proxy) or to the ALB HTTPS URL at build time

---

### Data Storage Requirements

#### Primary Relational Database

| Property | Value | Source |
|---|---|---|
| Engine | PostgreSQL 16 | `docker-compose.yml`, `requirements.txt` (`psycopg2-binary`) |
| Development fallback | SQLite (file-based) | `database/connection.py` |
| Test | SQLite in-memory (`sqlite:///:memory:`) | `tests/conftest.py` |
| ORM | SQLAlchemy 2.0 | `requirements.txt` |
| Schema migrations | Alembic 1.13 (2 revisions: `465a230b0d66`, `b1c2d3e4f5a6`) | `alembic/versions/` |
| SQLite compatibility | `render_as_batch=True` in `alembic/env.py` | `alembic/env.py` |
| Foreign keys (SQLite) | Enforced via `PRAGMA foreign_keys=ON` | `database/connection.py` |

#### High-Volume Tables

Two tables use `Integer` (BIGSERIAL on PostgreSQL) auto-increment PKs instead of UUID, for write performance:

| Table | PK Type | Reason |
|---|---|---|
| `deployment_logs` | `Integer` (BIGSERIAL on PG) | One row per log line — can be thousands per deployment |
| `instance_metrics` | `Integer` (BIGSERIAL on PG) | Time-series metrics — periodic snapshots per instance |

Both tables include comments noting "plan for data retention: archive rows older than 30 days" (`instance_metrics` docstring).

#### File-Based Storage

| Path | Contents | Note |
|---|---|---|
| `backend/deployment_logs/` | Local log files (dev only) | Not used when `LOG_FILE=/dev/stdout` |
| `deployment_logs/` (root) | Duplicate log directory | Appears to be a leftover artefact |
| `backend/ml-deploy-key.pem` | EC2 SSH private key (PEM) | Bind-mounted into container; must move to Secrets Manager for production |

No object storage (S3) is used by the application at present. The `SSHClient` in `core/utils.py` resolves relative key file paths to `/app/backend/<key_file>`, which is the container's working directory layout.

#### Persistent Volume (Docker Compose)

| Volume | Mount Target | Purpose |
|---|---|---|
| `postgres_data` (named) | `/var/lib/postgresql/data` | PostgreSQL data directory persistence across container restarts |

No equivalent ECS volume configuration is defined in the repository. In ECS Fargate, the database is expected to run on Amazon RDS (not a container), so no EFS volume is required for the database.

---

### Secrets and Sensitive Configuration

#### Secrets Identified in Repository

| Secret | Current Location | Risk | Production Replacement |
|---|---|---|---|
| `AWS_ACCESS_KEY_ID` | `.env` file (not committed), docker-compose env | Medium — long-lived key | ECS task IAM role (boto3 default chain) |
| `AWS_SECRET_ACCESS_KEY` | `.env` file (not committed), docker-compose env | **High** — long-lived secret | ECS task IAM role (boto3 default chain) |
| `SECRET_KEY` | `.env` file; default `dev-secret-key-change-in-production` in `config.py` | **Critical** — Flask session signing | AWS Secrets Manager |
| `POSTGRES_PASSWORD` | Hardcoded `AutoDeploy123` in `docker-compose.yml` | High (dev only, not production) | RDS-generated password in AWS Secrets Manager |
| `GITHUB_TOKEN` | `.env` file (not committed) | Medium — GitHub API token | AWS Secrets Manager |
| `ml-deploy-key.pem` | File at `backend/ml-deploy-key.pem`; volume-mounted into container | **Critical** — SSH private key for managed EC2 access | AWS Secrets Manager (`PEM_SECRET_NAME`) |
| `DATABASE_URL` | Constructed from `docker-compose.yml` env vars | High — contains DB password | AWS Secrets Manager → ECS task `secrets` injection |
| `JWT_SECRET_KEY` | `tests/conftest.py` only; not in main app yet | N/A currently | AWS Secrets Manager (when auth is implemented) |

#### Secrets Architecture in the Data Model

The `secrets` table in the database intentionally stores **only AWS Secrets Manager ARNs** — never actual secret values. The `EnvironmentVariable` model has a `value_source` field (`'plaintext'` or `'secret'`); when `'secret'`, the application is expected to call `boto3` at runtime to fetch the value using the stored ARN.

This design is already aligned with ECS secret injection patterns and AWS Secrets Manager best practices.

#### Production Secrets Remediation Checklist

| Item | File to Change | Action |
|---|---|---|
| Remove `.env` bake-in | `Dockerfile.backend` | Delete `COPY .env .` line |
| Replace static AWS creds | `backend/config.py` | Remove `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` from `Config` class; rely on boto3 credential chain |
| SSH PEM key | `docker-compose.yml`, `core/utils.py` | Inject via `PEM_SECRET_NAME` env var pointing to Secrets Manager; load at runtime, not from file path |
| Flask `SECRET_KEY` | `backend/config.py` | Remove default value; require env var, injected from Secrets Manager |
| DB password | `docker-compose.yml` | Dev-only; production uses RDS endpoint in `DATABASE_URL` from Secrets Manager |
| `ALLOWED_SSH_IP` | `backend/config.py` | Change default from `0.0.0.0/0` to the ECS task subnet CIDRs |

#### Missing Dependencies for Auth (In-Progress Feature)

The test suite references the following that do not yet exist in the main application code:

| Missing Artifact | Referenced In | Status |
|---|---|---|
| `User` model (`backend/database/models.py`) | `tests/conftest.py` | Not implemented in models.py |
| `backend/api/auth.py` (routes: `/api/auth/register`, `/api/auth/login`, `/api/auth/logout`, `/api/auth/me`) | `tests/integration/test_auth_api.py` | Not present in `backend/api/` |
| `backend/core/jwt_utils.py` (`create_access_token()`) | `tests/conftest.py` docstring | File does not exist |
| `bcrypt` package | `tests/conftest.py` | Not in `requirements.txt` |
| `PyJWT` package | `tests/conftest.py` | Not in `requirements.txt` |
| `DeploymentCancelled` exception | `tests/unit/test_deployment_orchestrator.py` | Referenced in import but likely not in current `deployment_orchestrator.py` |

These items indicate an authentication phase is actively under development but not yet merged. The infrastructure plan should account for the `JWT_SECRET_KEY` secret and auth-related variables when finalizing the Secrets Manager configuration in Phase 3.

---

# Infrastructure as Code Architecture

> This section defines the Terraform project layout, module responsibilities, environment structure, and phase execution order. No Terraform code is written here — this is a design specification to be implemented in Phase 1 through Phase 8.

---

### Terraform Directory Structure

The full `infrastructure/` tree follows a **modules + environments** pattern. Modules define reusable, phase-aligned resource groups. Environments (`dev`, `staging`, `prod`) are the concrete deployments that call those modules with environment-specific variable values.

```
infrastructure/
│
├── bootstrap/                    # Phase 1 — one-time manual run
│   ├── main.tf                   # S3 bucket + DynamoDB lock table
│   └── outputs.tf                # bucket name, table name, region for reuse
│
├── modules/
│   ├── vpc/                      # Phase 2
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   │
│   ├── security-groups/          # Phase 3
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   │
│   ├── iam/                      # Phase 3
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   │
│   ├── ecr/                      # Phase 4
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   │
│   ├── rds/                      # Phase 5
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   │
│   ├── alb/                      # Phase 6
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   │
│   ├── ecs/                      # Phase 6
│   │   ├── main.tf
│   │   ├── outputs.tf
│   │   └── variables.tf
│   │
│   └── monitoring/               # Phase 7
│       ├── main.tf
│       ├── outputs.tf
│       └── variables.tf
│
└── environments/
    ├── dev/
    │   ├── main.tf               # calls modules with dev-specific values
    │   ├── variables.tf          # variable declarations
    │   ├── outputs.tf            # exposes ALB URL, ECS cluster name, RDS endpoint
    │   ├── backend.tf            # remote state config → S3 key: env/dev/terraform.tfstate
    │   └── terraform.tfvars      # concrete dev values (instance sizes, min tasks, etc.)
    │
    ├── staging/
    │   ├── main.tf
    │   ├── variables.tf
    │   ├── outputs.tf
    │   ├── backend.tf            # remote state → S3 key: env/staging/terraform.tfstate
    │   └── terraform.tfvars
    │
    └── prod/
        ├── main.tf
        ├── variables.tf
        ├── outputs.tf
        ├── backend.tf            # remote state → S3 key: env/prod/terraform.tfstate
        └── terraform.tfvars
```

---

### Module Responsibilities

#### `bootstrap/`

**Phase:** 1 — executed once, manually, before all other Terraform work.

This is not a module — it is a root configuration with no remote state backend. It creates the remote state infrastructure that all other phases depend on, so it must bootstrap itself with a local state file first, then the state file can optionally be committed or stored manually.

| Resource | Purpose |
|---|---|
| `aws_s3_bucket` | Stores all Terraform state files, one key per environment |
| `aws_s3_bucket_versioning` | Preserves every state version — allows rollback to any prior apply |
| `aws_s3_bucket_server_side_encryption_configuration` | SSE-S3 encryption at rest for all state files |
| `aws_s3_bucket_public_access_block` | Blocks all public access (4 block settings set to `true`) |
| `aws_dynamodb_table` | State lock table — `LockID` (String) partition key, `PAY_PER_REQUEST` billing; prevents concurrent `terraform apply` runs |

**Outputs:** S3 bucket name, DynamoDB table name — referenced in all `environments/*/backend.tf` files.

---

#### `modules/vpc/`

**Phase:** 2 — foundational networking; all subsequent modules depend on its outputs.

Justified by: ECS Fargate tasks require VPC placement; RDS requires a DB subnet group; ALB requires public subnets; NAT Gateway required for ECS tasks to reach ECR, GitHub API, and AWS APIs from private subnets (confirmed by `providers/aws/aws_manager.py`, `providers/github/github_manager.py`, `core/utils.py`).

| Resource | Purpose |
|---|---|
| `aws_vpc` | Primary VPC — `/16` CIDR, DNS hostnames enabled (required for RDS endpoint resolution) |
| `aws_subnet` (×4) | 2 public (one per AZ) for ALB + NAT GW; 2 private (one per AZ) for ECS tasks + RDS |
| `aws_internet_gateway` | Attached to VPC; enables inbound/outbound internet for public subnets |
| `aws_eip` (×2) | Elastic IPs for NAT Gateways (one per AZ) |
| `aws_nat_gateway` (×2) | One per AZ in public subnets; provides outbound internet to private subnets |
| `aws_route_table` (public) | Default route `0.0.0.0/0 → IGW`; associated with public subnets |
| `aws_route_table` (×2 private) | Default route `0.0.0.0/0 → NAT GW` per AZ; associated with private subnets |
| `aws_route_table_association` (×4) | Binds each subnet to its route table |
| `aws_flow_log` | VPC Flow Logs → CloudWatch Logs for network security investigation |
| `aws_cloudwatch_log_group` | Log group for VPC Flow Logs |

**Key variables:** `vpc_cidr`, `availability_zones`, `public_subnet_cidrs`, `private_subnet_cidrs`, `environment`, `project`.

**Key outputs:** `vpc_id`, `public_subnet_ids`, `private_subnet_ids` — consumed by every downstream module.

---

#### `modules/security-groups/`

**Phase:** 3 — must exist before RDS, ECS, or ALB are created.

Justified by: Four distinct trust boundaries identified in the repository analysis: internet→ALB, ALB→ECS-frontend, ALB→ECS-backend, ECS-backend→RDS. The `ALLOWED_SSH_IP` config variable (`config.py`) and paramiko SSH egress (`core/utils.py`) require an explicit outbound SSH rule from the backend security group.

| Resource | Purpose | Inbound | Outbound |
|---|---|---|---|
| `aws_security_group` `sg_alb` | ALB — internet-facing | 443 from `0.0.0.0/0`; 80 from `0.0.0.0/0` | All to `sg_ecs_frontend` and `sg_ecs_backend` |
| `aws_security_group` `sg_ecs_frontend` | ECS frontend tasks | 80 from `sg_alb` | HTTPS 443 to ECR/internet |
| `aws_security_group` `sg_ecs_backend` | ECS backend tasks | 5000 from `sg_alb` | 5432 to `sg_rds`; 443 to internet; 22 to `0.0.0.0/0` (paramiko → managed EC2 public IPs) |
| `aws_security_group` `sg_rds` | RDS PostgreSQL | 5432 from `sg_ecs_backend` | None |

**Security group rules** are defined as separate `aws_security_group_rule` resources (not inline blocks) to avoid cycles between interdependent security groups.

**Key variables:** `vpc_id`, `environment`, `project`.

**Key outputs:** `sg_alb_id`, `sg_ecs_frontend_id`, `sg_ecs_backend_id`, `sg_rds_id` — consumed by `alb`, `ecs`, and `rds` modules.

---

#### `modules/iam/`

**Phase:** 3 — required before ECS task definitions can be created; OIDC provider required before CI/CD can authenticate.

Justified by: ECS requires a task execution role to pull ECR images and write CloudWatch logs. The backend application uses boto3 to call EC2 APIs (`providers/aws/aws_manager.py`) and Secrets Manager (`PEM_SECRET_NAME` + `aws_secret_arn` fields in the `secrets` table); these permissions must be attached to the ECS task role. GitHub Actions CI/CD requires OIDC federation to avoid long-lived credentials.

| Resource | Purpose |
|---|---|
| `aws_iam_role` `ecs_task_execution_role` | Assumed by ECS agent — ECR pull, CloudWatch Logs write, Secrets Manager read for task secrets injection |
| `aws_iam_role_policy_attachment` | Attaches `AmazonECSTaskExecutionRolePolicy` AWS managed policy |
| `aws_iam_policy` `ecs_execution_secrets` | Inline: `secretsmanager:GetSecretValue` scoped to project secret ARNs only |
| `aws_iam_role` `ecs_task_role` | Assumed by the Flask application inside the container |
| `aws_iam_policy` `ecs_task_ec2_policy` | EC2 actions required by `AWSManager`: `RunInstances`, `DescribeInstances`, `StopInstances`, `StartInstances`, `TerminateInstances`, `DescribeSecurityGroups`, `CreateSecurityGroup`, `AuthorizeSecurityGroupIngress`, `DescribeKeyPairs`, `DescribeImages`, `CreateTags` |
| `aws_iam_policy` `ecs_task_secrets_policy` | `secretsmanager:GetSecretValue` — runtime secret retrieval (SSH PEM key, GitHub token) |
| `aws_iam_policy` `ecs_task_logs_policy` | `logs:CreateLogGroup`, `logs:CreateLogStream`, `logs:PutLogEvents` — structured log output from the Flask app |
| `aws_iam_openid_connect_provider` | GitHub Actions OIDC provider (`token.actions.githubusercontent.com`) — one per AWS account |
| `aws_iam_role` `github_actions_deploy_role` | Assumed by GitHub Actions via OIDC; scoped to specific GitHub org/repo via condition |
| `aws_iam_policy` `github_actions_deploy_policy` | ECR push permissions + ECS `UpdateService` + `DescribeServices` + ECS task definition registration + `iam:PassRole` for task execution role |

**Key variables:** `environment`, `project`, `aws_account_id`, `github_org`, `github_repo`, `secret_arns`.

**Key outputs:** `ecs_task_execution_role_arn`, `ecs_task_role_arn`, `github_actions_deploy_role_arn` — consumed by `ecs` module and referenced in GitHub Actions workflows.

---

#### `modules/ecr/`

**Phase:** 4 — must exist before the first CI/CD pipeline run that pushes images.

Justified by: Two container images are built in the repository — `Dockerfile.backend` and `Dockerfile.frontend`. Both must be stored in a registry accessible to ECS at task launch time.

| Resource | Purpose |
|---|---|
| `aws_ecr_repository` `backend` | Stores `ml-deploy/backend` images |
| `aws_ecr_repository` `frontend` | Stores `ml-deploy/frontend` images |
| `aws_ecr_lifecycle_policy` (×2) | Retains the last 10 tagged images and expires untagged images after 1 day — prevents unbounded storage growth |
| `aws_ecr_repository_policy` (×2) | Allows the `ecs_task_execution_role` and `github_actions_deploy_role` to pull/push |

**Repository settings** (both repos):
- `image_tag_mutability = "MUTABLE"` — allows `latest` tag to be overwritten by CI/CD
- `image_scanning_configuration { scan_on_push = true }` — vulnerability scanning on every push
- `force_delete = false` — prevents accidental deletion of repos containing images via `terraform destroy`

**Key variables:** `environment`, `project`, `aws_account_id`.

**Key outputs:** `backend_repository_url`, `frontend_repository_url`, `backend_repository_arn`, `frontend_repository_arn` — consumed by the `ecs` module (task definitions) and used in GitHub Actions workflows.

---

#### `modules/rds/`

**Phase:** 5 — database must exist before the backend ECS task can start (the `CMD` in `Dockerfile.backend` runs `alembic upgrade head` on startup, which requires a live database).

Justified by: `database/connection.py` confirms PostgreSQL as the production database. `docker-compose.yml` uses `postgres:16-alpine`. `requirements.txt` pins `psycopg2-binary==2.9.9`. Two Alembic migration revisions exist in `alembic/versions/`.

| Resource | Purpose |
|---|---|
| `aws_db_subnet_group` | Groups the two private subnets; ensures RDS is never placed in a public subnet |
| `aws_db_parameter_group` | PostgreSQL 16 family; sets `log_min_duration_statement = 1000` (log slow queries ≥ 1 s) and `log_connections = on` |
| `aws_db_instance` | PostgreSQL 16, `db.t3.medium` (prod) / `db.t3.micro` (dev), Multi-AZ (prod only), encrypted at rest, automated 7-day backup |
| `aws_secretsmanager_secret` `db_url` | Creates the Secrets Manager secret that will hold the full `DATABASE_URL` connection string |
| `aws_secretsmanager_secret_version` `db_url` | Stores `postgresql://<username>:<password>@<endpoint>:5432/<db_name>` after the RDS instance is created |

**Storage configuration:**
- Initial: 20 GB gp3 (matches `EC2_VOLUME_SIZE` default in `.env.example`)
- Max: 100 GB (`max_allocated_storage`) — auto-scaling enabled
- `delete_automated_backups = false`, `skip_final_snapshot = false` (prod) / `true` (dev)

**Key variables:** `environment`, `project`, `vpc_id`, `private_subnet_ids`, `sg_rds_id`, `db_instance_class`, `db_name`, `db_username`, `multi_az`, `backup_retention_period`.

**Key outputs:** `db_endpoint`, `db_port`, `db_name`, `db_secret_arn` — `db_secret_arn` consumed by `ecs` module for secret injection into the backend task definition.

---

#### `modules/alb/`

**Phase:** 6 — ALB must be provisioned before ECS services are created, as services register their tasks as ALB targets.

Justified by: Nginx reverse-proxy config (`nginx/frontend.conf`) separates frontend and backend routing by path prefix. Socket.IO uses HTTP long-polling (`transports: ['polling']` in `socket.js`), requiring sticky sessions on the backend target group. The `/api/health` route (`api/health.py`) returns `HTTP 200` with `{"status": "healthy"}` — directly usable as the ALB health check.

| Resource | Purpose |
|---|---|
| `aws_lb` | Internet-facing ALB in public subnets; `sg_alb` security group |
| `aws_lb_target_group` `frontend` | Port 80, protocol HTTP; health check `GET /` expecting 200 |
| `aws_lb_target_group` `backend` | Port 5000, protocol HTTP; health check `GET /api/health` expecting 200; **stickiness enabled** (LB-generated cookie, 86400 s duration) to maintain Socket.IO session affinity |
| `aws_lb_listener` `http` | Port 80 → redirect to HTTPS 443 (HTTP 301) |
| `aws_lb_listener` `https` | Port 443, SSL policy `ELBSecurityPolicy-TLS13-1-2-2021-06`; default action → frontend target group |
| `aws_lb_listener_rule` `api` | Priority 1: path pattern `/api/*` → backend target group |
| `aws_lb_listener_rule` `socketio` | Priority 2: path pattern `/socket.io/*` → backend target group |
| `aws_acm_certificate` | TLS certificate for the ALB domain; DNS-validated |
| `aws_acm_certificate_validation` | Waits for DNS validation to complete before proceeding |

**ALB idle timeout:** Must be set to ≥ 300 seconds to match the Socket.IO `pingTimeout` value set in `app.py` (`ping_timeout=300`) and `socket.js` (`pingTimeout: 300000`). Default AWS idle timeout (60 s) would cause premature disconnects during long deployments.

**Key variables:** `environment`, `project`, `vpc_id`, `public_subnet_ids`, `sg_alb_id`, `certificate_arn`, `domain_name`, `alb_idle_timeout`.

**Key outputs:** `alb_arn`, `alb_dns_name`, `alb_zone_id`, `frontend_target_group_arn`, `backend_target_group_arn`, `https_listener_arn` — consumed by `ecs` module.

---

#### `modules/ecs/`

**Phase:** 6 — depends on VPC, security groups, IAM, ECR, RDS, and ALB all being available.

Justified by: Two Docker images exist in the repository. The deployment model requires independent scaling of frontend and backend. The backend runs Alembic migrations on startup (`Dockerfile.backend` CMD). The backend uses threading for background deployments (confirmed in `api/deployments.py`) requiring a gthread Gunicorn worker that must survive for up to 300 seconds per container lifecycle.

**ECS Cluster:**

| Resource | Purpose |
|---|---|
| `aws_ecs_cluster` | Fargate cluster; `containerInsights = enabled` for CloudWatch Container Insights |
| `aws_ecs_cluster_capacity_providers` | `FARGATE` and `FARGATE_SPOT` capacity providers; prod: 100% FARGATE; dev: FARGATE_SPOT preferred |

**Backend Service:**

| Resource | Purpose |
|---|---|
| `aws_cloudwatch_log_group` `/ecs/<project>/backend` | Log group for backend container stdout/stderr; 30-day retention |
| `aws_ecs_task_definition` `backend` | Fargate launch type; 512 CPU / 1024 MB RAM; `awslogs` log driver; `ecs_task_execution_role`; `ecs_task_role` |
| `aws_ecs_service` `backend` | Desired count configurable per environment; `FARGATE` launch type; private subnets; `sg_ecs_backend`; registers to `backend_target_group_arn` |
| `aws_appautoscaling_target` | ECS service as scalable target; min 1, max 4 tasks (prod) |
| `aws_appautoscaling_policy` `scale_out` | CPU ≥ 70% for 3 minutes → add 1 task |
| `aws_appautoscaling_policy` `scale_in` | CPU ≤ 30% for 10 minutes → remove 1 task; 300 s cooldown |

**Backend task definition — secret injection** (replaces the `.env` file pattern from local development):

| Container env key | Source type | Justification |
|---|---|---|
| `DATABASE_URL` | `secrets` → Secrets Manager ARN | `database/connection.py` reads `DATABASE_URL` env var |
| `SECRET_KEY` | `secrets` → Secrets Manager ARN | `config.py` reads `SECRET_KEY`; default is insecure |
| `GITHUB_TOKEN` | `secrets` → Secrets Manager ARN | `config.py` reads `GITHUB_TOKEN` for private repo access |
| `PEM_SECRET_NAME` | `environment` (plaintext) | The secret name/ARN string itself; app reads PEM at runtime via boto3 |
| `FLASK_ENV` | `environment` (plaintext) | Set to `production` |
| `AWS_REGION` | `environment` (plaintext) | `config.py` `AWS_REGION`; no credentials needed — task role provides them |
| `LOG_LEVEL` | `environment` (plaintext) | Set to `INFO` |
| `LOG_FILE` | `environment` (plaintext) | Set to `/dev/stdout` so logs reach CloudWatch via awslogs driver |
| `EC2_INSTANCE_TYPE` | `environment` (plaintext) | Default instance type for managed EC2 deployments |
| `EC2_AMI_ID` | `environment` (plaintext) | Ubuntu AMI ID for managed EC2 deployments |
| `EC2_VOLUME_SIZE` | `environment` (plaintext) | Root disk size for managed EC2 instances |
| `SECURITY_GROUP_NAME` | `environment` (plaintext) | Name of the SG applied to managed EC2 instances |
| `AWS_KEY_PAIR_NAME` | `environment` (plaintext) | EC2 key pair name for SSH access to managed instances |

> `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` are intentionally **absent** from the task definition. boto3 resolves credentials from the ECS task role via the instance metadata endpoint automatically.

**Frontend Service:**

| Resource | Purpose |
|---|---|
| `aws_cloudwatch_log_group` `/ecs/<project>/frontend` | Log group for frontend Nginx; 14-day retention |
| `aws_ecs_task_definition` `frontend` | Fargate launch type; 256 CPU / 512 MB RAM; `awslogs` log driver |
| `aws_ecs_service` `frontend` | Desired count 1 (prod: 2); `FARGATE`; private subnets; `sg_ecs_frontend`; registers to `frontend_target_group_arn` |
| `aws_appautoscaling_target` | Min 1, max 2 tasks |
| `aws_appautoscaling_policy` `scale_out` | CPU ≥ 60% for 3 minutes → add 1 task |
| `aws_appautoscaling_policy` `scale_in` | CPU ≤ 20% for 10 minutes → remove 1 task |

**Key variables:** `environment`, `project`, `vpc_id`, `private_subnet_ids`, `sg_ecs_backend_id`, `sg_ecs_frontend_id`, `ecs_task_execution_role_arn`, `ecs_task_role_arn`, `backend_image`, `frontend_image`, `backend_target_group_arn`, `frontend_target_group_arn`, `db_secret_arn`, `secret_key_arn`, `github_token_arn`, `pem_secret_name`, `backend_cpu`, `backend_memory`, `frontend_cpu`, `frontend_memory`, `backend_desired_count`, `frontend_desired_count`.

**Key outputs:** `ecs_cluster_name`, `ecs_cluster_arn`, `backend_service_name`, `frontend_service_name`, `backend_task_definition_arn`, `frontend_task_definition_arn` — used by GitHub Actions `deploy.yml` to force new ECS deployments.

---

#### `modules/monitoring/`

**Phase:** 7 — requires ECS cluster, RDS, and ALB to already exist so alarms can reference their metrics.

Justified by: `backend/core/logging_config.py` already includes a `JSONFormatter` class that outputs JSON suitable for CloudWatch Logs Insights. The `/api/health` endpoint already exposes DB connectivity; if that endpoint returns 503, an alarm on unhealthy ALB targets catches it. The `instance_metrics` table stores time-series CPU/memory/disk per managed EC2 — these data points feed into custom CloudWatch metrics.

| Resource | Purpose |
|---|---|
| `aws_cloudwatch_log_group` (backend, frontend) | Already declared in `ecs` module; referenced here for metric filters |
| `aws_cloudwatch_log_metric_filter` (5xx errors) | Scans backend log group for HTTP 5xx patterns; emits `BackendErrorCount` custom metric |
| `aws_cloudwatch_metric_alarm` `backend_cpu_high` | `AWS/ECS` CPUUtilization (backend service) > 70% for 5 min → SNS |
| `aws_cloudwatch_metric_alarm` `backend_memory_high` | `AWS/ECS` MemoryUtilization (backend service) > 80% for 5 min → SNS |
| `aws_cloudwatch_metric_alarm` `alb_5xx_high` | `AWS/ApplicationELB` HTTPCode_Target_5XX_Count > 10 per 5 min → SNS |
| `aws_cloudwatch_metric_alarm` `alb_unhealthy_hosts` | `AWS/ApplicationELB` UnHealthyHostCount > 0 for 2 min → SNS |
| `aws_cloudwatch_metric_alarm` `rds_cpu_high` | `AWS/RDS` CPUUtilization > 80% for 10 min → SNS |
| `aws_cloudwatch_metric_alarm` `rds_storage_low` | `AWS/RDS` FreeStorageSpace < 5 GB → SNS |
| `aws_cloudwatch_metric_alarm` `rds_connections_high` | `AWS/RDS` DatabaseConnections > 80 → SNS |
| `aws_sns_topic` `critical_alerts` | Endpoint for high-priority alarms; email subscription |
| `aws_sns_topic` `info_alerts` | Endpoint for informational alarms; email subscription |
| `aws_sns_topic_subscription` | Email subscriptions (addresses provided via variable) |
| `aws_cloudwatch_dashboard` | Single dashboard: ECS CPU/memory, ALB request count + 5xx rate, RDS CPU + connections |
| `aws_cloudwatch_event_rule` (ECS task stopped) | EventBridge rule: any ECS task `STOPPED` event → SNS `critical_alerts` |
| `aws_cloudwatch_event_target` | Routes ECS task stopped events to SNS |

**Key variables:** `environment`, `project`, `ecs_cluster_name`, `backend_service_name`, `alb_arn_suffix`, `rds_identifier`, `alert_email_critical`, `alert_email_info`.

**Key outputs:** `critical_sns_topic_arn`, `info_sns_topic_arn`, `dashboard_name`.

---

### Environment Structure

Each environment in `environments/*/` is a self-contained Terraform root that calls all required modules. Environments are isolated by separate state files in S3.

#### `backend.tf` (per environment)

Each environment declares its remote state backend pointing to the shared S3 bucket created in Phase 1:

```
# environments/prod/backend.tf  (design — not code)
terraform {
  backend "s3" {
    bucket         = "<project>-terraform-state"
    key            = "env/prod/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "<project>-terraform-locks"
  }
}
```

State file keys per environment:

| Environment | S3 Key |
|---|---|
| dev | `env/dev/terraform.tfstate` |
| staging | `env/staging/terraform.tfstate` |
| prod | `env/prod/terraform.tfstate` |

#### `terraform.tfvars` Differences Per Environment

The same modules are called by all three environments; only the variable values differ:

| Variable | dev | staging | prod |
|---|---|---|---|
| `backend_desired_count` | 1 | 1 | 2 |
| `frontend_desired_count` | 1 | 1 | 2 |
| `backend_cpu` | 256 | 512 | 512 |
| `backend_memory` | 512 | 1024 | 1024 |
| `db_instance_class` | `db.t3.micro` | `db.t3.small` | `db.t3.medium` |
| `multi_az` | `false` | `false` | `true` |
| `db_backup_retention_period` | 1 | 3 | 7 |
| `db_skip_final_snapshot` | `true` | `true` | `false` |
| `nat_gateway_count` | 1 (shared) | 1 (shared) | 2 (per AZ) |
| `enable_container_insights` | `false` | `true` | `true` |
| `ecs_capacity_provider` | `FARGATE_SPOT` | `FARGATE` | `FARGATE` |
| `alb_idle_timeout` | 300 | 300 | 300 |
| `log_retention_days` (backend) | 7 | 14 | 30 |

#### Environment Promotion Flow

```
Feature branch → dev environment (manual Terraform apply, tested ad-hoc)
                        │
                        ▼ (merge to main, CI triggers)
               staging environment (automated plan + manual apply gate)
                        │
                        ▼ (manual approval in GitHub Actions)
               prod environment (apply after approval)
```

---

### Phase Execution Order

Phases must be executed strictly in dependency order. Each phase's `terraform apply` must complete successfully before the next begins.

```
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 1 — Bootstrap                                                 │
│ Location: infrastructure/bootstrap/                                 │
│ Run: terraform init && terraform apply (local state, run once)      │
│ Creates: S3 state bucket, DynamoDB lock table                       │
│ Dependency: None                                                    │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼  all subsequent phases use remote state
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 2 — Networking  [module: vpc]                                 │
│ Run: cd environments/<env> && terraform apply -target=module.vpc    │
│ Creates: VPC, subnets, IGW, NAT GW, route tables, flow logs         │
│ Provides: vpc_id, public_subnet_ids, private_subnet_ids             │
│ Dependency: Phase 1                                                 │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 3 — Security  [modules: security-groups, iam]                 │
│ Run: terraform apply -target=module.security_groups                 │
│             terraform apply -target=module.iam                      │
│ Creates: 4 security groups, 3 IAM roles, 5 policies, OIDC provider  │
│ Provides: sg_*_id outputs, role ARNs                                │
│ Dependency: Phase 2 (vpc_id required for security groups)           │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 4 — ECR  [module: ecr]                                        │
│ Run: terraform apply -target=module.ecr                             │
│ Creates: 2 ECR repositories with lifecycle policies                 │
│ Provides: repository URLs for CI/CD push and ECS pull               │
│ Dependency: Phase 3 (IAM role ARNs for repository policies)         │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼  (run CI/CD pipeline at this point to push
                          │   initial images before ECS services start)
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 5 — RDS  [module: rds]                                        │
│ Run: terraform apply -target=module.rds                             │
│ Creates: RDS PostgreSQL 16, subnet group, parameter group,          │
│          Secrets Manager secret with DATABASE_URL                   │
│ Provides: db_endpoint, db_secret_arn                                │
│ Dependency: Phase 2 (private_subnet_ids), Phase 3 (sg_rds_id)      │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 6 — Compute  [modules: alb, ecs]                              │
│ Run: terraform apply -target=module.alb                             │
│             terraform apply -target=module.ecs                      │
│ Creates: ACM cert, ALB, listeners, target groups, ECS cluster,      │
│          task definitions, services, auto scaling                   │
│ Provides: service names/ARNs for CI/CD, ALB DNS name for Route 53  │
│ Dependency: Phases 2, 3, 4 (images must exist), 5 (db_secret_arn)  │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 7 — Monitoring  [module: monitoring]                          │
│ Run: terraform apply -target=module.monitoring                      │
│ Creates: CloudWatch alarms, SNS topics, EventBridge rule, dashboard │
│ Dependency: Phase 6 (ECS cluster/service names, ALB ARN, RDS ID)   │
└─────────────────────────┬───────────────────────────────────────────┘
                          │
                          ▼
┌─────────────────────────────────────────────────────────────────────┐
│ PHASE 8 — CI/CD  [no Terraform resources]                           │
│ Location: .github/workflows/                                        │
│ Creates: ci.yml, deploy.yml GitHub Actions workflows                │
│ Consumes: Terraform outputs (ECR URLs, ECS cluster/service names,   │
│           IAM role ARN for OIDC)                                    │
│ Dependency: All phases complete; images in ECR; services healthy    │
└─────────────────────────────────────────────────────────────────────┘
```

**Important ordering note:** Phase 6 (`ecs`) registers an image URI in the ECS task definition. A placeholder image (e.g., `public.ecr.aws/amazonlinux/amazonlinux:latest`) should be used in Terraform for the first apply; the real application image is injected by CI/CD on the first pipeline run after ECR images are pushed (end of Phase 4).

---

### CI/CD Interaction with Infrastructure

The GitHub Actions pipelines interact with Terraform-provisioned infrastructure at runtime, consuming Terraform outputs as pipeline inputs. No pipeline writes infrastructure — deployments only update ECS task definitions and force service redeployments.

#### Values Consumed by CI/CD from Terraform Outputs

| Terraform Output | Module | GitHub Actions Usage |
|---|---|---|
| `backend_repository_url` | `ecr` | `docker build` tag and `docker push` destination |
| `frontend_repository_url` | `ecr` | `docker build` tag and `docker push` destination |
| `ecs_cluster_name` | `ecs` | `aws ecs update-service --cluster` |
| `backend_service_name` | `ecs` | `aws ecs update-service --service` (backend) |
| `frontend_service_name` | `ecs` | `aws ecs update-service --service` (frontend) |
| `backend_task_definition_arn` | `ecs` | Base for rendering updated task definition with new image |
| `frontend_task_definition_arn` | `ecs` | Base for rendering updated task definition with new image |
| `github_actions_deploy_role_arn` | `iam` | `role-to-assume` in `aws-actions/configure-aws-credentials@v4` |

These values are stored as **GitHub Actions Variables** (not secrets) after each Terraform apply. They can be set manually or via a Terraform post-apply script using the GitHub REST API.

#### GitHub Actions → AWS Authentication

Authentication uses **OIDC federation** — no long-lived `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are stored in GitHub Secrets. The `aws_iam_openid_connect_provider` and `github_actions_deploy_role` resources in `modules/iam/` enable this.

The trust policy on `github_actions_deploy_role` must be scoped to the specific repository using the `sub` condition:
```
token.actions.githubusercontent.com:sub = repo:<github_org>/<github_repo>:ref:refs/heads/main
```
This ensures only pushes to the `main` branch of the designated repository can assume the deploy role.

#### Alembic Migration in CI/CD

Alembic migrations (`alembic upgrade head`) run automatically as part of the backend container's `CMD` in `Dockerfile.backend`. They execute when ECS starts a new task revision during a rolling deployment. This means:
- Migrations are not a separate CI/CD step
- The `ecs_task_execution_role` does not need additional permissions for migrations
- Migration backward compatibility must be maintained during the rolling update window

---

### Additional Required Infrastructure Components

The following components are strictly required for a production deployment but were not explicitly listed in the phasing plan. They are placed within existing phases:

#### Route 53 DNS Record (Phase 6 — `alb` module)

| Resource | Purpose |
|---|---|
| `aws_route_53_record` | `A` record (alias) pointing the application domain to the ALB DNS name |

Justification: The frontend's `VITE_API_URL` and browser access both require a stable hostname. Without a Route 53 record, users must access the ALB via its auto-generated AWS DNS name, which changes if the ALB is recreated.

Required variable: `hosted_zone_id` (the Route 53 hosted zone for the domain).

#### Secrets Manager Secrets (Phase 3 — `iam` module or standalone)

The following Secrets Manager secrets must be created by Terraform before the ECS task definition can reference their ARNs. Secret values are populated outside Terraform (manually or via CI/CD), but the secret resources themselves — and their ARNs — must exist at plan time:

| Secret Name Pattern | Contents | Phase |
|---|---|---|
| `/<project>/<env>/database-url` | Full PostgreSQL `DATABASE_URL` | Phase 5 (populated after RDS creation) |
| `/<project>/<env>/secret-key` | Flask `SECRET_KEY` (random 32-char hex) | Phase 3 (placeholder; updated before Phase 6) |
| `/<project>/<env>/github-token` | GitHub PAT for private repo access | Phase 3 (placeholder) |
| `/<project>/<env>/ssh-private-key` | EC2 SSH PEM key content (replaces volume mount) | Phase 3 (placeholder) |
| `/<project>/<env>/jwt-secret-key` | JWT signing key (auth phase) | Phase 3 (placeholder; activates with auth) |

These are referenced in the ECS task definition `secrets` block using their ARNs, which Terraform outputs after `aws_secretsmanager_secret` is created. Secret values are never stored in Terraform state.

#### ACM Certificate (Phase 6 — `alb` module)

The `aws_acm_certificate` resource requires DNS validation. The `aws_route53_record` for the CNAME validation record must be created as part of the same `alb` module apply, followed by `aws_acm_certificate_validation` which blocks until the certificate reaches `ISSUED` status. This is the primary reason Phase 6 can take 5–10 minutes rather than the usual 1–2 minutes.

#### ECS Task Definition Image Bootstrap (Phase 4–6 transition)

Before ECS services can be created in Phase 6, at least one image must exist in each ECR repository. A bootstrap step is needed between Phase 4 and Phase 6:

```
Phase 4 completes (ECR repos created)
        ↓
Manual or CI trigger: build + push initial images to ECR
        ↓
Phase 6 begins (ECS task definitions reference real image URIs)
```

Without this step, ECS will attempt to pull from ECR and fail, causing the service to enter a crash loop and Terraform to time out waiting for service stability.

---

### Terraform Provider and Version Requirements

| Component | Required Version | Justification |
|---|---|---|
| Terraform CLI | `>= 1.6.0` | `backend "s3"` with DynamoDB locking and `moved` block support |
| AWS Provider (`hashicorp/aws`) | `~> 5.0` | ECS Fargate Spot, RDS gp3 storage, OIDC provider resources |
| AWS Region | Configurable via `aws_region` variable | Default: `us-east-1` (matches `config.py` default) |
| Terraform state encryption | S3 SSE-S3 | Configured via `aws_s3_bucket_server_side_encryption_configuration` |

All three environment directories will declare the same provider version constraint to prevent provider drift between environments.

---

### Module Dependency Graph

```
bootstrap (Phase 1)
    │
    └── [provides S3 + DynamoDB for all remote backends]
            │
            ▼
    vpc (Phase 2)
     │         │
     ▼         ▼
security-groups  iam  (Phase 3 — both need vpc_id)
     │    │      │
     │    │      └── [provides role ARNs]
     │    │                 │
     │    └── [provides sg_ids]
     │                      │
     ▼                      │
    ecr (Phase 4) ◄─────────┘
     │
     │ [images pushed to ECR here — CI/CD trigger]
     │
     ▼
    rds (Phase 5)  ◄── vpc (private_subnet_ids)
     │                  security-groups (sg_rds_id)
     └── [db_secret_arn]
             │
             ▼
    alb (Phase 6)  ◄── vpc (public_subnet_ids)
     │                  security-groups (sg_alb_id)
     │
     ▼
    ecs (Phase 6)  ◄── vpc, security-groups, iam, ecr, rds, alb
     │
     ▼
monitoring (Phase 7) ◄── ecs, alb, rds
     │
     ▼
CI/CD pipelines (Phase 8) ◄── iam (OIDC role), ecr (repo URLs), ecs (service names)
```
