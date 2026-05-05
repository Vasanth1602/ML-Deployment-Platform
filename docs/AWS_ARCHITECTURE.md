# AWS Architecture — ECS Fargate Deployment

Reference document for Terraform authoring and CI/CD pipeline setup.  
Stack: Flask backend · React/Nginx frontend · PostgreSQL RDS · ECS Fargate · ALB · Cloud Map

---

## Runtime Architecture

```
                         Internet
                            │
                       HTTP :80
                            │
              ┌─────────────▼──────────────┐
              │   Application Load Balancer │  (internet-facing)
              │   ml-alb-sg                 │  public subnets · 2 AZs
              │                             │
              │  Listener :80               │
              │  ├─ Rule 1: /api/*      ──► btg
              │  ├─ Rule 2: /socket.io/*──► btg
              │  └─ Default: /         ──► ftg
              └─────────────────────────────┘
                       │              │
           ┌───────────┘              └───────────┐
           ▼                                      ▼
  ┌────────────────────┐              ┌─────────────────────────┐
  │  Frontend ECS      │              │  Backend ECS             │
  │  Nginx :80         │──backend.────│  Flask/Gunicorn :5000    │
  │  Service Connect:  │  local:5000  │  Service Connect:        │
  │  client only       │◄─────────────│  client + server         │
  │  ftg target group  │              │  btg target group        │
  └────────────────────┘              └─────────┬────────────────┘
           │                                    │
           │        private subnets             │ :5432
           │        ml-ecs-tasks-sg             │
           │                                    ▼
           │                         ┌──────────────────┐
           │                         │  RDS PostgreSQL   │
           │                         │  ml-db-sg         │
           │                         │  DB subnet group  │
           │                         └──────────────────┘
           │
  ┌────────┴──────────┐   ┌──────────────────────┐
  │  ECR              │   │  AWS Cloud Map        │
  │  backend repo     │   │  namespace: local     │
  │  frontend repo    │   │  backend.local:5000   │
  └───────────────────┘   │  frontend.local:80    │
                          └──────────────────────┘
```

### VPC layout

| Subnet type | Contents | CIDR example |
|---|---|---|
| Public (2 AZs) | ALB only | 10.0.0.0/24, 10.0.1.0/24 |
| Private (2 AZs) | ECS tasks | 10.0.2.0/24, 10.0.3.0/24 |
| DB (private) | RDS | 10.0.4.0/24, 10.0.5.0/24 |

### Security group rules

| SG | Inbound | Source |
|---|---|---|
| `ml-alb-sg` | TCP 80, TCP 443 | 0.0.0.0/0 |
| `ml-ecs-tasks-sg` | TCP 80 | ml-alb-sg |
| `ml-ecs-tasks-sg` | TCP 5000 | ml-alb-sg |
| `ml-db-sg` | TCP 5432 | ml-ecs-tasks-sg |

---

## Setup Sequence (6 phases)

### Phase 1 — VPC & Security Groups

**VPC**
- Create using the *VPC & more* wizard
- CIDR: `10.0.0.0/16`
- 2 AZs · 2 public subnets · 2 private subnets · DB subnets
- 1 NAT gateway (or use VPC endpoints for ECR/S3 if skipping NAT to save cost)

**Security groups** — create all three before any other resource:
- `ml-alb-sg` — HTTP:80 + HTTPS:443 from `0.0.0.0/0`
- `ml-ecs-tasks-sg` — TCP:80 + TCP:5000 from `ml-alb-sg`
- `ml-db-sg` — PostgreSQL:5432 from `ml-ecs-tasks-sg`

> **Terraform note:** Security groups must be created before ECS services and RDS.  
> Use `depends_on` or implicit references via `security_group_id` to enforce ordering.

---

### Phase 2 — Storage & Registry

**RDS PostgreSQL**
1. Create a **DB subnet group** from the private/DB subnets
2. Create a PostgreSQL instance
3. Attach DB subnet group + `ml-db-sg`
4. Port: `5432`
5. Store credentials in AWS Secrets Manager (reference in task definition as secret env var)

**ECR**
1. Create `backend` repository
2. Create `frontend` repository
3. Build Docker images locally (or in CI/CD pipeline)
4. Authenticate and push to ECR

> **CI/CD note:** Image build + push to ECR is the first step of your deploy pipeline.  
> Tag images with the Git commit SHA for traceability (e.g. `backend:abc1234`).

---

### Phase 3 — Service Discovery (Cloud Map)

1. Create a **private DNS namespace** in Cloud Map
2. Namespace name: `local`
3. Link to the VPC
4. ECS will auto-register services; DNS entries available inside the VPC:
   - `backend.local` → resolves to backend ECS task IPs
   - `frontend.local` → resolves to frontend ECS task IPs

> **Terraform resource:** `aws_service_discovery_private_dns_namespace`

---

### Phase 4 — Task Definitions

**Backend task definition**

| Setting | Value |
|---|---|
| Launch type | FARGATE |
| Task role | IAM role with app permissions (S3, Secrets Manager, etc.) |
| Task execution role | IAM role with `ecr:*`, `logs:*`, `secretsmanager:GetSecretValue` |
| Container name | `backend` |
| Image | `<account>.dkr.ecr.<region>.amazonaws.com/backend:<tag>` |
| Port mapping | `5000/TCP` — name: `backend-api` (name is required for Service Connect) |
| Env vars | `DATABASE_URL`, `SECRET_KEY`, etc. (inject from Secrets Manager) |

**Frontend task definition**

| Setting | Value |
|---|---|
| Launch type | FARGATE |
| Container name | `frontend` |
| Image | `<account>.dkr.ecr.<region>.amazonaws.com/frontend:<tag>` |
| Port mapping | `80/TCP` |
| Env vars | `BACKEND_HOST` = `backend.local`, `BACKEND_PORT` = `5000` |

> **Important:** `BACKEND_HOST`/`BACKEND_PORT` are used by `nginx/frontend.conf` via `envsubst`  
> at container startup — they are runtime variables, not build-time args.  
> The React app itself must call relative paths (`/api/...`) so requests route through the ALB,  
> not directly to `backend.local` (which is only reachable server-side inside the VPC).

---

### Phase 5 — Load Balancing

**Target groups**

| Name | Type | Protocol | Port | Health check path |
|---|---|---|---|---|
| `ftg` (frontend) | IP | HTTP | 80 | `/` |
| `btg` (backend) | IP | HTTP | 5000 | `/api/health` |

**ALB**
- Scheme: internet-facing
- Subnets: public subnets (both AZs)
- Security group: `ml-alb-sg`

**Listener (HTTP:80) rules — in priority order**

| Priority | Condition | Action |
|---|---|---|
| 1 | Path `/api/*` | Forward → `btg` |
| 2 | Path `/socket.io/*` | Forward → `btg` |
| Default | (all other traffic) | Forward → `ftg` |

> **Terraform note:** Rules 1 and 2 must have lower priority numbers than the default.  
> `aws_lb_listener_rule` with `priority = 1` and `priority = 2`.  
> For production: add an HTTPS listener on port 443 with an ACM certificate,  
> and redirect HTTP → HTTPS on the port 80 listener.

---

### Phase 6 — ECS Services

> **Order matters:** Create the backend service first. The frontend service depends on  
> `backend.local` being registered in Cloud Map at startup.

**Backend ECS service**

| Setting | Value |
|---|---|
| Cluster | your ECS cluster |
| Task definition | backend TD (latest revision) |
| Launch type | FARGATE |
| Subnets | private subnets |
| Security group | `ml-ecs-tasks-sg` |
| Service Connect | **Client and server** mode |
| SC namespace | `local` |
| SC port alias | `backend-api` (must match port name in task definition) |
| SC DNS | `backend.local` port `5000` |
| Load balancer | existing ALB → `btg` |
| Container:port | `backend:5000` |

**Frontend ECS service**

| Setting | Value |
|---|---|
| Cluster | your ECS cluster |
| Task definition | frontend TD (latest revision) |
| Launch type | FARGATE |
| Subnets | private subnets |
| Security group | `ml-ecs-tasks-sg` |
| Service Connect | **Client only** mode |
| SC namespace | `local` |
| Load balancer | existing ALB → `ftg` |
| Container:port | `frontend:80` |

---

## Traffic Flow (runtime)

```
Browser → ALB:80 → Rule 1: /api/*       → btg → Backend ECS (:5000)
Browser → ALB:80 → Rule 2: /socket.io/* → btg → Backend ECS (:5000)
Browser → ALB:80 → Default: /           → ftg → Frontend ECS (:80)

Frontend ECS (nginx) → backend.local:5000 (Cloud Map / Service Connect) → Backend ECS
Backend ECS          → RDS PostgreSQL :5432
```

---

## Terraform Resource Order

When writing Terraform, create resources in this dependency order to avoid plan errors:

```
1. VPC, subnets, IGW, route tables, NAT
2. Security groups (ml-alb-sg, ml-ecs-tasks-sg, ml-db-sg)
3. DB subnet group → RDS instance
4. ECR repositories
5. Cloud Map namespace
6. IAM roles (task role, task execution role)
7. ECS cluster
8. Task definitions (backend, frontend)
9. ALB → target groups (ftg, btg) → listener → listener rules
10. ECS service: backend (with Service Connect server + LB)
11. ECS service: frontend (with Service Connect client + LB)
```

---

## CI/CD Pipeline Steps

```
1. Build backend Docker image
2. Build frontend Docker image  (with BACKEND_HOST/PORT as build context if needed)
3. Push both images to ECR with commit SHA tag
4. Register new task definition revision (backend) with updated image URI
5. Register new task definition revision (frontend) with updated image URI
6. Update ECS service (backend) → triggers rolling deploy
7. Update ECS service (frontend) → triggers rolling deploy
8. Wait for services to reach steady state (ecs wait services-stable)
```

> Use `aws ecs update-service --force-new-deployment` or Terraform `force_new_deployment = true`  
> to trigger a redeploy when only env vars or secrets change (not the image tag).
