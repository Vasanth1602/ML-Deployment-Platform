# AWS Architecture — S3 + CloudFront + ECS Fargate Deployment

Reference document for Terraform authoring and CI/CD pipeline setup.  
Stack: Flask backend · React S3/CloudFront frontend · PostgreSQL RDS · ECS Fargate · ALB

---

## Runtime Architecture

```
                              Internet
                                 │
                        HTTPS (CloudFront)
                                 │
              ┌──────────────────▼─────────────────┐
              │        CloudFront Distribution       │
              │        xxxx.cloudfront.net           │
              │                                      │
              │  Behavior 0: /api/*      ──► ALB     │
              │  Behavior 1: /socket.io/*──► ALB     │
              │  Default:    /*          ──► S3      │
              └──────────────────────────────────────┘
                          │              │
           ┌──────────────┘              └──────────────┐
           ▼                                            ▼
  ┌─────────────────┐              ┌────────────────────────────┐
  │   S3 Bucket     │              │  Application Load Balancer  │
  │  (private)      │              │  ml-alb-sg                  │
  │  React SPA      │              │  public subnets · 2 AZs     │
  │  static files   │              │                             │
  │  OAC policy     │              │  Listener :80               │
  │  index.html     │              │  ├─ Rule 1: /api/*  ──► btg │
  │  assets/        │              │  ├─ Rule 2: /socket.io/*    │
  └─────────────────┘              │  │            ──► btg       │
                                   │  └─ Default: Fixed 404      │
                                   └─────────────────────────────┘
                                                  │
                                                  ▼
                                   ┌──────────────────────────┐
                                   │      Backend ECS          │
                                   │  Flask/Gunicorn :5000     │
                                   │  Service Connect:         │
                                   │  client + server          │
                                   │  btg target group         │
                                   │  Stickiness: ON (1hr)     │
                                   └────────────┬─────────────┘
                                                │
                                           :5432│  private subnets
                                                │  ml-ecs-tasks-sg
                                                ▼
                                   ┌──────────────────┐
                                   │  RDS PostgreSQL   │
                                   │  ml-db-sg         │
                                   │  DB subnet group  │
                                   └──────────────────┘

  ┌───────────────────┐   
  │  ECR              │   
  │  backend repo     │   
  │  (backend only)   │   
  └───────────────────┘   
```

---

## VPC Layout

| Subnet type | Contents | CIDR example |
|---|---|---|
| Public (2 AZs) | ALB only | 10.0.0.0/24, 10.0.1.0/24 |
| Private (2 AZs) | ECS tasks | 10.0.2.0/24, 10.0.3.0/24 |
| DB (private) | RDS | 10.0.4.0/24, 10.0.5.0/24 |

---

## Security Group Rules

| SG | Inbound | Source |
|---|---|---|
| `ml-alb-sg` | TCP 80 | `com.amazonaws.global.cloudfront.origin-facing` (AWS managed prefix list) |
| `ml-ecs-tasks-sg` | TCP 80 | ml-alb-sg |
| `ml-ecs-tasks-sg` | TCP 5000 | ml-alb-sg |
| `ml-db-sg` | TCP 5432 | ml-ecs-tasks-sg |

> **Critical:** `ml-alb-sg` source must be the CloudFront managed prefix list — NOT `0.0.0.0/0`.  
> This ensures the ALB only accepts traffic from CloudFront edge nodes.  
> Direct access to the ALB DNS name will return connection refused.

---

## Traffic Flow (runtime)

```
Browser → CloudFront → Default /*          → S3 bucket → index.html + JS + CSS
Browser → CloudFront → /api/*              → ALB → btg → Backend ECS (:5000)
Browser → CloudFront → /socket.io/* (GET)  → ALB → btg → Backend ECS (:5000) → 200 (session created, AWSALB cookie set)
Browser → CloudFront → /socket.io/* (POST) → ALB → btg → same ECS task (stickiness cookie) → 200
Browser → CloudFront → /socket.io/* (WSS)  → ALB → btg → Backend ECS (:5000) → 101 WebSocket upgrade

Backend ECS → RDS PostgreSQL :5432

Direct → ALB DNS → connection refused  (ml-alb-sg blocks all non-CloudFront IPs)
```

---

## CloudFront Behavior Order

| Precedence | Path pattern | Origin | Cache policy | Origin request policy |
|---|---|---|---|---|
| 0 | `/api/*` | `alb-origin` | CachingDisabled | AllViewerExceptHostHeader |
| 1 | `/socket.io/*` | `alb-origin` | CachingDisabled | AllViewerExceptHostHeader |
| Default | `*` | `s3-origin` | CachingOptimized | — |

> **Why `AllViewerExceptHostHeader` for ALB behaviors:**  
> Forwards all query strings (`EIO=4`, `transport=polling`, `sid=...`, `token=...`) and all headers  
> to the ALB unchanged. Without this, `EIO` query param is stripped → engineio returns 400.  
> `AllViewer` sends the CloudFront Host header to the ALB which causes request rejection.

---

## What is NOT in this setup

| Resource | Status | Reason |
|---|---|---|
| Frontend ECS service | ❌ Not created | React app served from S3 |
| Frontend task definition | ❌ Not created | No container needed |
| ECR frontend repository | ❌ Not created | No Docker image for frontend |
| `ftg` (frontend target group) | ❌ Not created | No frontend ECS service |
| Cloud Map `frontend.local` | ❌ Not created | No frontend container to register |
| ALB default → forward to ECS | ❌ Not used | Default returns fixed 404 |
| `nginx/frontend.conf` (in prod) | ❌ Not used | Replaced by CloudFront behaviors |
| `Dockerfile.frontend` (in prod) | ❌ Not used | Used for local Docker Compose only |

---

## Setup Sequence (7 phases)

### Phase 1 — VPC & Security Groups

> **Order matters:** Create all three security groups before any other resource.

**VPC**
- Create using the *VPC & more* wizard
- CIDR: `10.0.0.0/16`
- 2 AZs · 2 public subnets · 2 private subnets · DB subnets
- 1 NAT gateway (or use VPC endpoints for ECR/S3 to save cost)

**Security groups — create all three first:**

`ml-alb-sg`
- Inbound: TCP 80 from `com.amazonaws.global.cloudfront.origin-facing` (AWS managed prefix list)
- Search for `cloudfront` in the source dropdown to find the prefix list

`ml-ecs-tasks-sg`
- Inbound: TCP 80 from `ml-alb-sg`
- Inbound: TCP 5000 from `ml-alb-sg`

`ml-db-sg`
- Inbound: TCP 5432 from `ml-ecs-tasks-sg`

> **Terraform note:** Security groups must be created before ECS services and RDS.  
> Use `depends_on` or implicit references via `security_group_id` to enforce ordering.

---

### Phase 2 — Storage & Registry

**RDS PostgreSQL**
1. Create a **DB subnet group** from the private/DB subnets
2. Create a PostgreSQL 16 instance
3. Attach DB subnet group + `ml-db-sg`
4. Port: `5432`
5. Store credentials in AWS Secrets Manager (reference in task definition as secret env var)

**ECR — backend only**
1. Create `backend` repository only
2. ~~frontend repository — not needed~~
3. Build backend Docker image locally or in CI/CD
4. Authenticate and push to ECR with commit SHA tag (e.g. `backend:abc1234`)

**S3 Bucket — frontend hosting**
1. Go to S3 → Create bucket
2. Bucket name: `ml-deploy-frontend-prod`
3. Region: same as your VPC (e.g. `ap-south-1`)
4. Namespace: Account Regional namespace (recommended)
5. Block ALL public access: **ON** (all 4 checkboxes)
6. ACLs: disabled (recommended)
7. Versioning: disable
8. Encryption: SSE-S3 + Bucket Key enabled
9. Tags: `Project=ml-deploy-platform`, `Environment=prod`
10. Click **Create bucket**

> **Do NOT upload files yet** — bucket policy must be applied after CloudFront OAC is created in Phase 3.

---

### Phase 3 — Frontend Hosting (CloudFront Distribution)

#### Step 1 — Create distribution (wizard)

**Get started (Step 1)**
- Distribution name: `ml-deploy-frontend-prod`
- Description: `ML Deploy Platform frontend - S3 + CloudFront`
- Distribution type: Single website or app
- Domain: leave blank (no custom domain — CloudFront provides free `xxxx.cloudfront.net` URL with HTTPS)
- Tags: `Project=ml-deploy-platform`, `Environment=prod`
- Click **Next**

**Specify origin (Step 2)**
- Origin type: Amazon S3
- S3 origin: Browse → select `ml-deploy-frontend-prod`
- Origin path: leave blank
- Allow private S3 bucket access to CloudFront: **Yes — Recommended**
  - This auto-creates the OAC (Origin Access Control) and applies bucket policy
  - Bucket stays private — only this CloudFront distribution can read from it
- Origin settings: Use recommended origin settings
- Cache settings: Customize → select `CachingOptimized`
- Click **Next**

**Enable security (Step 3)**
- WAF: **Do not enable security protections**
  - Reason: $14/month minimum cost — enable later when app goes public
- Click **Next**

**Get TLS certificate (Step 4)**
- No custom domain → skip entirely
- CloudFront automatically provides free TLS for `*.cloudfront.net`
- Click **Next**

**Review and create (Step 5)**
- Confirm settings and click **Create distribution**
- Wait 5–10 minutes for status to show **Enabled**
- Copy the **Distribution domain name** (e.g. `dphxf22kvwtvk.cloudfront.net`)

---

#### Step 2 — Post-creation fixes (REQUIRED immediately after creation)

**Fix 1 — Default root object**
- General tab → Edit
- Default root object: `index.html`
- Click Save changes

> Without this, hitting `https://xxxx.cloudfront.net/` returns an S3 XML error instead of your React app.

**Fix 2 — Custom error pages (React Router fix)**
- Error pages tab → Create custom error response

  | HTTP error code | Customize | Response page path | HTTP response code |
  |---|---|---|---|
  | `403` | Yes | `/index.html` | `200` |
  | `404` | Yes | `/index.html` | `200` |

> Without this, direct URL navigation (e.g. `/deployments/123`) returns an S3 error page instead of your React app. S3 has no file at that path → returns 403 → must be remapped to index.html for React Router to handle it client-side.

---

#### Step 3 — Add ALB as second origin (do AFTER ALB is created in Phase 5)

**Origins tab → Create origin**

| Setting | Value |
|---|---|
| Origin domain | your ALB DNS name (e.g. `ml-alb-xxxx.ap-south-1.elb.amazonaws.com`) |
| Protocol | HTTP only |
| HTTP port | 80 |
| Name | `alb-origin` |
| Custom header name | `X-CloudFront-Secret` |
| Custom header value | `<generate a random string — save this value>` |
| Enable Origin Shield | No |
| Connection attempts | 3 |
| Connection timeout | 10 |
| Response timeout | 30 |

- Click **Save changes**
- Wait for distribution status → **Enabled**

> **Why the custom header:** CloudFront adds this header to every request sent to the ALB.  
> The ALB listener rules check for this header — direct access without it is rejected.  
> This locks the ALB so only CloudFront can reach it.

---

#### Step 4 — Add cache behaviors for API and WebSocket (do AFTER ALB origin is added)

**Behaviors tab → Create behavior**

**Behavior 1 — API**

| Setting | Value |
|---|---|
| Path pattern | `/api/*` |
| Origin | `alb-origin` |
| Viewer protocol policy | Redirect HTTP to HTTPS |
| Allowed HTTP methods | GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE |
| Cache policy | `CachingDisabled` |
| Origin request policy | `AllViewerExceptHostHeader` |

**Behavior 2 — WebSocket / Socket.IO**

| Setting | Value |
|---|---|
| Path pattern | `/socket.io/*` |
| Origin | `alb-origin` |
| Viewer protocol policy | Redirect HTTP to HTTPS |
| Allowed HTTP methods | GET, HEAD, OPTIONS, PUT, POST, PATCH, DELETE |
| Cache policy | `CachingDisabled` |
| Origin request policy | `AllViewerExceptHostHeader` |

> **Why CachingDisabled:** API responses are dynamic. WebSocket connections cannot be cached.  
> **Why AllViewerExceptHostHeader:** Forwards all query strings including `EIO=4`, `transport=polling`,  
> `sid=`, `token=` to the ALB unchanged. Using `AllViewer` sends the CloudFront Host header  
> to the ALB causing rejection. Using default policies strips the `EIO` param causing engineio 400 errors.

**Verify behavior order after creation:**

| Precedence | Path | Origin |
|---|---|---|
| 0 | `/api/*` | `alb-origin` |
| 1 | `/socket.io/*` | `alb-origin` |
| Default | `*` | `s3-origin` |

---

### Phase 4 — Task Definitions

**Backend task definition**

| Setting | Value |
|---|---|
| Launch type | FARGATE |
| Task role | IAM role with app permissions (S3, Secrets Manager, EC2, etc.) |
| Task execution role | IAM role with `ecr:*`, `logs:*`, `secretsmanager:GetSecretValue` |
| Container name | `backend` |
| Image | `<account>.dkr.ecr.<region>.amazonaws.com/backend:<tag>` |
| Port mapping | `5000/TCP` — name: `backend-api` (required for Service Connect) |
| Env vars | `DATABASE_URL`, `SECRET_KEY`, `JWT_SECRET_KEY`, `CORS_ORIGINS`, `FLASK_ENV=production` |

> **Critical env var:** `CORS_ORIGINS` must be set to your CloudFront domain:  
> `CORS_ORIGINS=https://xxxx.cloudfront.net`  
> Both Flask-CORS (HTTP routes) and Flask-SocketIO (WebSocket) read this value.  
> If missing or wrong, all API and Socket.IO requests from the browser will be rejected with 400.

**Frontend task definition — NOT CREATED**
> React app is served from S3 via CloudFront. No Docker image, no container, no task definition required.  
> Frontend deploy = `npm run build` → `aws s3 sync` → CloudFront invalidation.

---

### Phase 5 — Load Balancing

**Backend target group (btg)**

| Setting | Value |
|---|---|
| Target type | IP addresses |
| Name | `btg` |
| Protocol | HTTP |
| Port | `5000` |
| VPC | your existing VPC |
| Health check protocol | HTTP |
| Health check path | `/api/health` |
| Healthy threshold | 2 |
| Unhealthy threshold | 3 |
| Timeout | 5 seconds |
| Interval | 30 seconds |
| **Stickiness** | **ON** |
| Stickiness type | Load balancer generated cookie |
| Stickiness duration | 1 hour |

> **Why stickiness is required:** Socket.IO polling uses two HTTP methods:  
> `GET /socket.io/` → creates session on ECS Task A → ALB sets `AWSALB` cookie  
> `POST /socket.io/` → must hit the same task → ALB reads cookie → routes to Task A  
> Without stickiness, ALB round-robins POST to a different task which has no session → 400 error.  
> Do not register any targets manually — ECS registers its own task IPs automatically.

**ALB**
- Name: `ml-alb`
- Scheme: internet-facing
- IP type: IPv4
- Subnets: both **public subnets** (2 AZs)
- Security group: `ml-alb-sg` only (CloudFront prefix list source)
- Default action during creation: select `btg` (will be changed to 404 below)
- Tags: `Project=ml-deploy-platform`, `Environment=prod`

**Listener HTTP:80 rules — in priority order**

| Priority | Condition | Action |
|---|---|---|
| 1 | Path `/api/*` | Forward → `btg` |
| 2 | Path `/socket.io/*` | Forward → `btg` |
| Default | all other traffic | Fixed response: 404 |

**Default rule settings:**
- Action: Return fixed response
- Response code: `404`
- Content type: `text/plain`
- Response body: `Not found`

> **Why default returns 404:** The ALB will never receive a `/` request from real users — CloudFront  
> serves the frontend from S3 directly. Any request hitting the ALB at `/` is either misconfigured  
> or a direct scanner bypassing CloudFront — return 404.

> **Terraform note:** Rules 1 and 2 must have lower priority numbers than the default.  
> Use `aws_lb_listener_rule` with `priority = 1` and `priority = 2`.

---

### Phase 6 — ECS Services

> **Backend service only.** No frontend ECS service is created.  
> Cloud Map only needs `backend.local` — `frontend.local` is not registered.

**Backend ECS service**

| Setting | Value |
|---|---|
| Cluster | your ECS cluster |
| Task definition | backend TD (latest revision) |
| Launch type | FARGATE |
| Subnets | private subnets (both AZs) |
| Security group | `ml-ecs-tasks-sg` |
| Desired count | 1 |
| Service Connect | **Client and server** mode |
| SC namespace | `local` |
| SC port alias | `backend-api` (must match port name in task definition) |
| SC DNS | `backend.local` port `5000` |
| Load balancer | existing ALB → `btg` |
| Container:port | `backend:5000` |

> ECS registers backend task IP into `btg` automatically at startup — no manual target registration.  
> Wait for service to reach steady state (1/1 running) before testing.

**Frontend ECS service — NOT CREATED**

---

### Phase 7 — Deploy Frontend & Verify

**Build and upload**

```bash
# 1. Ensure no VITE_API_URL is set in frontend/.env or frontend/.env.local
#    API_BASE_URL must resolve to '' so all calls use relative paths

# 2. Build
cd frontend
npm run build

# 3. Verify no localhost URLs baked in (must return nothing)
grep -r "localhost" dist/

# 4. Upload to S3
aws s3 sync dist/ s3://ml-deploy-frontend-prod/ --delete

# 5. Invalidate CloudFront edge cache
aws cloudfront create-invalidation \
  --distribution-id <your-distribution-id> \
  --paths "/*"
```

> **Why `--delete` flag:** Removes old files from S3 that no longer exist in dist/.  
> Vite generates new hashed filenames on every build — without `--delete` old files accumulate.  
> **Why invalidation:** CloudFront caches files at edge locations. Without invalidation, users  
> get the old bundle for up to 24 hours. Invalidation takes ~60 seconds and is free for the  
> first 1,000 paths per month.

**Verification checklist**

```bash
# React app loads at CloudFront URL
open https://xxxx.cloudfront.net

# API routing works
curl https://xxxx.cloudfront.net/api/health
# Expected: {"status":"healthy","database":"connected"}

# ALB is locked down (must fail)
curl http://ml-alb-xxxx.ap-south-1.elb.amazonaws.com/api/health
# Expected: connection refused or timeout

# Socket.IO polling works
curl "https://xxxx.cloudfront.net/socket.io/?EIO=4&transport=polling"
# Expected: {"sid":"...","upgrades":["websocket"],"pingInterval":25000}

# React Router paths work (must return 200, not S3 error)
curl -I https://xxxx.cloudfront.net/deployments/123
# Expected: 200
```

Browser DevTools → Network tab → filter `socket.io`:
```
GET  /socket.io/?EIO=4&transport=polling   → 200  ✅ (session created)
POST /socket.io/?EIO=4&transport=polling   → 200  ✅ (stickiness working)
GET  /socket.io/?EIO=4&transport=websocket → 101  ✅ (WebSocket upgraded)
```

---

## Terraform Resource Order

When writing Terraform, create resources in this dependency order to avoid plan errors:

```
1.  VPC, subnets, IGW, route tables, NAT
2.  Security groups (ml-alb-sg with CF prefix list, ml-ecs-tasks-sg, ml-db-sg)
3.  DB subnet group → RDS instance
4.  ECR repository (backend only)
5.  S3 bucket (block all public access)
6.  CloudFront OAC → CloudFront distribution (S3 origin only first)
7.  S3 bucket policy (output from CloudFront OAC)
8.  Cloud Map namespace (backend.local only)
9.  IAM roles (task role, task execution role)
10. ECS cluster
11. Backend task definition
12. ALB → btg (with stickiness) → listener → listener rules
13. ECS service: backend (Service Connect server + LB)
14. CloudFront: add ALB as second origin
15. CloudFront: add /api/* and /socket.io/* behaviors
```

---

## CI/CD Pipeline Steps

```
── Frontend deploy ──────────────────────────────────────────────────────────
1. npm run build                      (compile React → dist/)
2. aws s3 sync dist/ s3://bucket/ --delete   (upload to S3)
3. aws cloudfront create-invalidation --paths "/*"  (clear edge cache)

── Backend deploy ────────────────────────────────────────────────────────────
4. Build backend Docker image         (docker build -f Dockerfile.backend)
5. Push to ECR with commit SHA tag    (docker push ecr-uri/backend:abc1234)
6. Register new task definition revision (with updated image URI)
7. Update ECS service (backend)       (triggers rolling deploy)
8. Wait for service to reach steady state (ecs wait services-stable)
```

> Use `aws ecs update-service --force-new-deployment` or Terraform `force_new_deployment = true`  
> to trigger a redeploy when only env vars or secrets change (not the image tag).

> **Frontend vs backend deploy are independent.** A CSS change only needs steps 1–3 (~60 seconds).  
> A Python change only needs steps 4–8 (~5 minutes). No more rebuilding a Docker image for a typo fix.

---

## Known Production Issues & Fixes

| Issue | Root cause | Fix |
|---|---|---|
| `VITE_API_URL=localhost:5000` baked into bundle | `.env.local` had localhost URL at build time | Remove VITE_API_URL from all `.env` files before building |
| Socket.IO 400 on POST | ALB stickiness off — POST routed to different ECS task than GET | Enable stickiness on btg (load balancer cookie, 1 hour) |
| `EIO unsupported version` | CloudFront behavior stripping `EIO=4` query param | Set Origin request policy to `AllViewerExceptHostHeader` |
| CORS 400 on Socket.IO | Flask-SocketIO has separate CORS from Flask-CORS | Set `CORS_ORIGINS` env var in ECS task definition |
| React Router 403 on direct URL | S3 returns 403 for unknown paths | Add CloudFront custom error: 403 → /index.html → 200 |
| WebSocket wss:// fails | CloudFront behavior had only GET/HEAD methods | Set Allowed HTTP methods to include all (DELETE, GET, HEAD, OPTIONS, PATCH, POST, PUT) |