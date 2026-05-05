# 🚀 ML Deployment Platform

A production-ready, full-stack platform that automates deploying Machine Learning applications from a GitHub URL to an AWS EC2 instance — with Docker containerisation, NGINX reverse proxy, real-time progress streaming, and a modern React dashboard — all in a single click.

![Python](https://img.shields.io/badge/Python-3.12+-blue.svg)
![Flask](https://img.shields.io/badge/Flask-3.0-green.svg)
![React](https://img.shields.io/badge/React-19-61DAFB.svg)
![Vite](https://img.shields.io/badge/Vite-7-646CFF.svg)
![TailwindCSS](https://img.shields.io/badge/Tailwind-v4-38B2AC.svg)
![PostgreSQL](https://img.shields.io/badge/PostgreSQL-16-336791.svg)
![Docker](https://img.shields.io/badge/Docker-Compose-2496ED.svg)
![AWS](https://img.shields.io/badge/AWS-EC2-FF9900.svg)

---

## 📑 Table of Contents

- [What it Does](#-what-it-does)
- [UI Preview](#-ui-preview)
- [Why This Exists](#-why-this-exists)
- [Quick Start — Docker Compose (Recommended)](#-quick-start--docker-compose-recommended)
- [Manual Docker Setup (Learning Path)](#-manual-docker-setup-learning-path)
- [Local Dev Without Docker](#-local-dev-without-docker)
- [Architecture](#-architecture)
- [Production Readiness](#-production-readiness)
- [Project Structure](#-project-structure)
- [Configuration Reference](#-configuration-reference)
- [API Reference](#-api-reference)
- [Deployment Workflow](#-deployment-workflow)
- [Deploying Your Own App](#-deploying-your-own-app)
- [Monitoring & Logs](#-monitoring--logs)
- [Troubleshooting](#-troubleshooting)
- [Security](#-security)
- [Cost Considerations](#-cost-considerations)
- [Current Limitations](#-current-limitations)
- [Tech Stack](#-tech-stack)
- [Further Reading](#-further-reading)

---

## ✨ What it Does

| Capability | Detail |
|---|---|
| **One-click EC2 deploy** | Enter a GitHub URL → framework provisions EC2, installs Docker, builds image, runs container |
| **Real-time progress** | WebSocket stream shows each step as it happens |
| **NGINX reverse proxy** | Deployed apps are accessible via clean `http://ip/` URLs (port 80) |
| **Instance management** | Start, stop, terminate EC2 instances from the dashboard |
| **Application registry** | Track all deployed applications and their status |
| **Health monitoring** | Automatic retry-based health checks after deployment |
| **JWT Authentication** | Secure login with JWT tokens; first admin auto-created on startup |
| **Layered backend** | Clean API → Services → Providers → Database architecture |
| **PostgreSQL backend** | All state persisted in Postgres (managed by Alembic migrations) |
| **AWS Secrets Manager** | EC2 SSH private key stored and fetched securely — never baked into the image |

---

## 🖼️ UI Preview

| Dashboard | Live Deployment |
|-----------|-----------------|
| ![Dashboard](./assets/screenshots/dashboard.png) | ![Deployment](./assets/screenshots/deployment-progress.png) |

---

## 🎯 Why This Exists

Deploying Machine Learning applications to AWS EC2 manually is repetitive, fragile, and infrastructure-heavy.

A typical deployment requires:

- Provisioning and configuring an EC2 instance
- Managing security groups and SSH access
- Installing Docker and NGINX
- Building and running containers correctly
- Setting up reverse proxy rules
- Verifying application health

Each step demands cloud, Linux, and networking knowledge — and small mistakes can break the entire workflow.

This framework eliminates that manual complexity and replaces it with:

> **A single API-driven deployment pipeline.**

By orchestrating AWS provisioning (boto3), SSH automation (paramiko), containerisation (Docker), reverse proxy configuration (NGINX), and real-time progress streaming (Socket.IO), the system transforms multi-step infrastructure setup into a controlled, observable, repeatable process.

It acts as a lightweight deployment platform on top of EC2 — allowing ML engineers and developers to focus on models, not infrastructure.

---

## ⚡ Quick Start — Docker Compose (Recommended)

> **Full setup walkthrough (AWS credentials, key pairs, etc.):** see [SETUP_GUIDE.md](./SETUP_GUIDE.md)

> **Running this locally?** Docker Compose is the only path you need. Follow the steps below.
> **Want to self-host this platform on AWS ECS?** That is an optional advanced step covered in the [ECS section of SETUP_GUIDE.md](./SETUP_GUIDE.md#optional-self-hosting-the-platform-on-aws-ecs).

This is the **fastest way** to get the entire platform running. One command starts PostgreSQL, the Flask backend, and the React frontend.

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24+)
- AWS account — IAM credentials (or IAM role for local dev via `aws configure`) and an EC2 Key Pair
- Git

### 1 — Clone

```bash
git clone https://github.com/Vasanth1602/ML-Deployment-Platform.git
cd ML-Deployment-Platform
```

### 2 — Configure

```bash
# Windows
copy .env.example .env

# macOS / Linux
cp .env.example .env
```

Open `.env` and fill in **at minimum**:

```env
# AWS — no static keys needed if you run `aws configure` on your machine
# boto3 reads ~/.aws/credentials automatically in local dev
AWS_REGION=us-east-1
AWS_KEY_PAIR_NAME=ml-deploy-key

EC2_AMI_ID=ami-0c7217cdde317cfec    # Ubuntu 22.04 LTS — update for your region
EC2_INSTANCE_TYPE=t3.micro
EC2_VOLUME_SIZE=20
EC2_VPC_ID=                         # ECS only — leave blank for local dev
EC2_SUBNET_ID=                      # ECS only — leave blank for local dev

SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
JWT_SECRET_KEY=<generate: python -c "import secrets; print(secrets.token_hex(32))">
JWT_EXPIRY_HOURS=1

# First admin account — auto-created on first startup, then ignored
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeMe123!

# Database
POSTGRES_USER=dbadmin
POSTGRES_PASSWORD=your_db_password_here
POSTGRES_DB=autodeploy

# PEM key — store in AWS Secrets Manager (see SETUP_GUIDE.md §4)
# Leave blank to skip fetch and mount the .pem file manually via Docker volume
PEM_SECRET_NAME=your-secrets-manager-secret-name
```

### 3 — Add Your EC2 Key Pair File

The `.pem` file is mounted into the backend container at runtime and is **never baked into the image**.

```bash
# Place your downloaded .pem file in backend/
# macOS / Linux
mv ~/Downloads/ml-deploy-key.pem backend/ml-deploy-key.pem
chmod 400 backend/ml-deploy-key.pem

# Windows
move %USERPROFILE%\Downloads\ml-deploy-key.pem backend\ml-deploy-key.pem
```

The `docker-compose.yml` mounts it automatically:
```yaml
volumes:
  - ./backend/ml-deploy-key.pem:/app/ml-deploy-key.pem:ro
```

### 4 — Start Everything

```bash
docker compose up --build
```

| Service | URL |
|---|---|
| **Frontend (React UI)** | http://localhost |
| **Backend API** | http://localhost:5000 |
| **PostgreSQL** | localhost:5432 |

First build: ~3–5 min. Subsequent starts: seconds.

> **First login:** Use the `ADMIN_EMAIL` / `ADMIN_PASSWORD` you set in `.env`. The account is created automatically on first startup. The plaintext password is then wiped from memory.

---

## 🐳 Manual Docker Setup (Learning Path)

> **Why use manual setup?**
> The Docker Compose path hides how the three services actually communicate. The manual path — creating the network yourself, running each container explicitly, passing environment files — teaches you exactly what Docker Compose does under the hood:
> - How Docker bridge networks work and why containers use service names instead of `localhost`
> - How environment files are injected into containers
> - How volume mounts work for secrets and persistent data
> - How to inspect, restart, and debug individual containers in isolation
>
> Use this path to build a genuine understanding of the infrastructure before automating it.

---

### Step M1 — AWS Credentials Setup

The backend uses **boto3** to call AWS APIs. Credentials are resolved automatically — no static keys in environment files.

**Option A — Local dev (recommended): `aws configure`**

```bash
# Install AWS CLI if not already installed
pip install awscli

# Configure once — stored in ~/.aws/credentials
aws configure
```

You will be prompted for:
```
AWS Access Key ID:     AKIAXXXXXXXXXXXXXXXX
AWS Secret Access Key: wJalrXU...
Default region name:   ap-south-1
Default output format: json
```

boto3 picks this up automatically. Nothing extra needed in `backend.env`.

**Option B — IAM Instance/Task Role (ECS / EC2 hosting the platform)**

If the backend itself runs on ECS Fargate or an EC2 instance with an IAM role attached, boto3 uses the container/instance metadata endpoint automatically. No credentials in any file.

**Option C — Environment variables (CI/CD pipelines only)**

```bash
export AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
export AWS_SECRET_ACCESS_KEY=wJalrXU...
export AWS_DEFAULT_REGION=ap-south-1
```

---

### Step M2 — Store PEM Key in AWS Secrets Manager

The EC2 SSH private key is stored in AWS Secrets Manager and fetched at backend container startup. It is **never** in the Docker image or repository.

1. Open **[AWS Secrets Manager Console](https://console.aws.amazon.com/secretsmanager)**
2. Click **Store a new secret** → **Other type of secret** → **Plaintext**
3. Paste the full contents of your `.pem` file (including the `-----BEGIN RSA PRIVATE KEY-----` header and footer)
4. Name it, e.g. `ml-deploy-key`
5. Click through and save

Your IAM user / role must have this permission:

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:ml-deploy-key*"
}
```

Set `PEM_SECRET_NAME=ml-deploy-key` in your `backend.env` (Step M4).

---

### Step M3 — Create Docker Network

All three containers must be on the same bridge network so they can reach each other by **container name** (e.g. `ml-postgres:5432` instead of `localhost:5432`).

```bash
docker network create ml-network
```

Verify:

```bash
docker network ls
# ml-network should appear with driver: bridge
```

---

### Step M4 — Create `backend.env`

Create a file called `backend.env` anywhere on your machine (**never commit it to Git**).

```env
# ── Database ─────────────────────────────────────────────────────────────────
# IMPORTANT: use the postgres container name as hostname, NOT localhost
DATABASE_URL=postgresql://dbadmin:your_db_password_here@ml-postgres:5432/autodeploy

# ── Flask ─────────────────────────────────────────────────────────────────────
FLASK_ENV=development
APP_PORT=5000

# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here
JWT_EXPIRY_HOURS=1

# ── First-Admin Bootstrap ─────────────────────────────────────────────────────
# Auto-creates admin on first startup (idempotent — ignored if admin exists).
# Plaintext password is wiped from memory after hashing.
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeMe123!

# ── AWS (no static keys — boto3 uses ~/.aws/credentials or IAM role) ──────────
AWS_REGION=ap-south-1
AWS_KEY_PAIR_NAME=ml-deploy-key
EC2_AMI_ID=ami-019715e0d74f695be
EC2_INSTANCE_TYPE=t3.micro
EC2_VOLUME_SIZE=20
EC2_VPC_ID=
EC2_SUBNET_ID=
SECURITY_GROUP_NAME=ml-deployment-sg
ALLOWED_SSH_IP=0.0.0.0/0

# ── PEM Key (AWS Secrets Manager) ────────────────────────────────────────────
# Name of the secret you created in Step M2
PEM_SECRET_NAME=ml-deploy-key
PEM_KEY_PATH=/app/ml-deploy-key.pem

# ── CORS / Frontend ──────────────────────────────────────────────────────────
CORS_ORIGINS=http://localhost:80,http://localhost
FRONTEND_URL=http://localhost

# ── Docker Deployment Ports (for apps deployed TO EC2) ───────────────────────
DOCKER_CONTAINER_PORT=8000
DOCKER_HOST_PORT=8000
MAX_DEPLOYMENT_TIME=600
HEALTH_CHECK_INTERVAL=10
HEALTH_CHECK_RETRIES=5
EC2_READY_TIMEOUT=300
EC2_READY_POLL_INTERVAL=10
SSH_READY_TIMEOUT=420
SSH_RETRY_INTERVAL=5

# ── Logging ──────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
LOG_FILE=deployment.log

# ── NGINX (for apps deployed ON EC2) ─────────────────────────────────────────
ENABLE_NGINX=true
NGINX_HTTP_PORT=80
```

---

### Step M5 — Run PostgreSQL Container

```bash
docker run -d \
  --name ml-postgres \
  --network ml-network \
  --restart unless-stopped \
  -e POSTGRES_USER=dbadmin \
  -e POSTGRES_PASSWORD=your_db_password_here \
  -e POSTGRES_DB=autodeploy \
  -p 5432:5432 \
  -v ml-postgres-data:/var/lib/postgresql/data \
  postgres:16-alpine
```

Verify it is healthy:

```bash
docker ps
# ml-postgres should show Status: Up (healthy) after ~10 seconds

docker exec -it ml-postgres pg_isready -U dbadmin -d autodeploy
# /var/run/postgresql:5432 - accepting connections
```

---

### Step M6 — Build the Backend Image

```bash
# From the project root (ML-Deployment-Platform/)
docker build -f Dockerfile.backend -t ml-backend .
```

---

### Step M7 — Run the Backend Container

Using `--env-file` keeps the run command short and your secrets out of shell history.

**macOS / Linux:**

```bash
docker run -d \
  --name ml-backend \
  --network ml-network \
  --restart unless-stopped \
  -p 5000:5000 \
  --env-file /path/to/backend.env \
  -v ~/.aws:/home/appuser/.aws:ro \
  ml-backend
```

**Windows (PowerShell):**

```powershell
docker run -d `
  --name ml-backend `
  --network ml-network `
  --restart unless-stopped `
  -p 5000:5000 `
  --env-file C:\path\to\backend.env `
  -v C:\Users\<YourUsername>\.aws:/home/appuser/.aws:ro `
  ml-backend
```

> **What the `-v ~/.aws` mount does:**
> The container user is `appuser` (created in `Dockerfile.backend`). Mounting `~/.aws` into its home directory lets boto3 find your `aws configure` credentials automatically — no static keys in any file.
>
> **If you use `PEM_SECRET_NAME`:** boto3 fetches the key from Secrets Manager at startup and writes it to `/app/ml-deploy-key.pem` inside the container. No volume mount for the `.pem` is needed.
>
> **If you skip Secrets Manager:** remove `PEM_SECRET_NAME` from `backend.env` and add a volume mount:
> `-v /path/to/ml-deploy-key.pem:/app/ml-deploy-key.pem:ro`

Verify startup:

```bash
docker logs ml-backend
# Look for:
# [PEM] PEM key written to /app/ml-deploy-key.pem   ← Secrets Manager fetch succeeded
# [INFO] Default tenant created
# [INFO] Admin user created: admin@example.com       ← first-run only
# [INFO] Listening at: http://0.0.0.0:5000

curl http://localhost:5000/api/health
# {"status": "healthy", ...}
```

---

### Step M8 — Build the Frontend Image

```bash
# From the project root
docker build -f Dockerfile.frontend -t ml-frontend .
```

---

### Step M9 — Run the Frontend Container

The frontend Nginx config uses `BACKEND_HOST` and `BACKEND_PORT` environment variables (injected via `envsubst` at container startup) to know where to proxy `/api/*` and `/socket.io/*` traffic.

```bash
docker run -d \
  --name ml-frontend \
  --network ml-network \
  --restart unless-stopped \
  -p 80:80 \
  -e BACKEND_HOST=ml-backend \
  -e BACKEND_PORT=5000 \
  ml-frontend
```

---

### Step M10 — Verify Everything

```bash
docker ps
```

Expected output:

```
CONTAINER ID  IMAGE         STATUS          NAMES
xxxxxxxxxxxx  ml-frontend   Up X minutes    ml-frontend
xxxxxxxxxxxx  ml-backend    Up X minutes    ml-backend
xxxxxxxxxxxx  postgres:16   Up X minutes    ml-postgres
```

Open your browser:

```
http://localhost
```

Log in with the `ADMIN_EMAIL` and `ADMIN_PASSWORD` you set in `backend.env`.

---

### Useful Manual Commands

```bash
# Follow logs for a container
docker logs -f ml-backend
docker logs -f ml-frontend
docker logs -f ml-postgres

# Restart a container
docker restart ml-backend

# Connect to PostgreSQL directly
docker exec -it ml-postgres psql -U dbadmin -d autodeploy

# Stop all three containers
docker stop ml-frontend ml-backend ml-postgres

# Remove all three containers (data volume survives)
docker rm ml-frontend ml-backend ml-postgres

# Remove the network (after removing containers)
docker network rm ml-network

# Nuclear reset — removes containers, network, AND data volume
docker stop ml-frontend ml-backend ml-postgres
docker rm ml-frontend ml-backend ml-postgres
docker volume rm ml-postgres-data
docker network rm ml-network
```

---

## 💻 Local Dev Without Docker

Use this for the fastest hot-reload cycle during active development.

### Backend

```bash
# From project root
python -m venv venv

# Activate
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows

pip install -r requirements.txt

# Needs a running PostgreSQL instance and a DATABASE_URL in .env:
# DATABASE_URL=postgresql://dbadmin:your_password@localhost:5432/autodeploy
python -m backend.app
```

Backend runs at **`http://localhost:5000`**.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server runs at **`http://localhost:5173`** with hot-reload.

> Set `VITE_API_URL=http://localhost:5000` in `frontend/.env` if the dev proxy is not picking up the backend automatically.

---

## 🏗️ Architecture

### This Platform (how you run it)

```
Browser  ──→  Nginx (port 80)  ──→  React SPA
                                    │ /api/* and /socket.io/*
                                    ▼
                             Flask + Gunicorn (port 5000)
                                    │
                             PostgreSQL (port 5432)
```

### Deployed ML App Architecture (on EC2)

```
Internet  →  EC2 port 80
               │
           NGINX (reverse proxy)
               │
           Docker container (your app, port 8000)
               │
           Built from your GitHub repo's Dockerfile
```

### Backend Layer Diagram

```
┌─────────────────────────────┐
│   API layer  (api/)         │  Flask Blueprints — HTTP & WebSocket endpoints
│   health · auth             │
│   deployments · applications│
│   instances                 │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│  Services layer (services/) │  Business logic & orchestration
│  deployment_orchestrator    │
│  health_checker             │
│  auth_service               │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│  Providers (providers/)     │  External system adapters
│  aws/  docker/              │
│  github/  nginx/            │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│  Database (database/)       │  SQLAlchemy 2 + Alembic
│  models · repositories      │
│  connection                 │
└─────────────────────────────┘
```

### Data Flow — Single Deployment

```
Frontend (Deploy page)
  └─→ POST /api/deployments
        └─→ DeploymentOrchestrator.run()
              ├─→ aws/ec2_provider    → Provision EC2 instance
              ├─→ aws/ec2_provider    → Configure security group
              ├─→ docker/provider     → Install Docker via SSH
              ├─→ nginx/provider      → Install & configure NGINX
              ├─→ github/provider     → Clone repository
              ├─→ docker/provider     → Build & run container
              ├─→ health_checker      → Verify app is up
              └─→ SocketIO emit       → Real-time step updates to frontend
```

### PEM Key Flow

```
AWS Secrets Manager (secret: PEM_SECRET_NAME)
        │
        │  boto3 at backend container startup
        │  (load_pem_from_secrets_manager in core/utils.py)
        ▼
/app/ml-deploy-key.pem  (inside container, mode 600)
        │
        ▼
Paramiko SSH  ──→  EC2 instances
```

---

## 🏭 Production Readiness

- **Dockerised full stack** — Backend, Frontend, and PostgreSQL run in isolated containers
- **Gunicorn WSGI server** — Production-grade request handling (not Flask dev server)
- **PostgreSQL persistence** — All deployments, applications, and instances stored reliably
- **Alembic migrations** — Schema versioning and automatic upgrades on startup
- **JWT Authentication** — Stateless auth with configurable expiry; bcrypt-hashed passwords
- **First-admin bootstrap** — Admin account auto-created from env vars on first startup; plaintext password wiped from memory immediately
- **AWS Secrets Manager** — EC2 SSH private key fetched at runtime; never in image layers or repository
- **IAM role / `aws configure` auth** — No static AWS keys in any file; boto3 resolves credentials automatically
- **Layered backend architecture** — Clear separation of API, orchestration, providers, and persistence
- **Runtime-mounted SSH key** — PEM file injected at container runtime via volume or Secrets Manager
- **Structured logging** — Centralised logging with configurable levels
- **Graceful DB session management** — Scoped sessions with proper teardown handling
- **Rate limiting** — Flask-Limiter applied to API endpoints
- **CORS locked in production** — `FRONTEND_URL` and `CORS_ORIGINS` restrict cross-origin access
- **SocketIO origin restriction** — WebSocket connections restricted to configured frontend URL in production

---

## 📁 Project Structure

```
ML-Deployment-Platform/
│
├── backend/                        Flask application package
│   ├── app.py                      App factory (create_app) + SocketIO init
│   ├── config.py                   Env-var config with validation
│   ├── __init__.py                 Re-exports socketio for blueprint imports
│   │
│   ├── api/                        Flask Blueprints (HTTP routes)
│   │   ├── admin.py                Admin dashboard and system endpoints
│   │   ├── health.py               GET /api/health
│   │   ├── auth.py                 POST /api/auth/login, /refresh, /logout
│   │   ├── deployments.py          Deployment CRUD + trigger
│   │   ├── applications.py         Application registry endpoints
│   │   └── instances.py            EC2 instance management endpoints
│   │
│   ├── services/                   Business logic layer
│   │   ├── deployment_orchestrator.py  12-step deploy workflow
│   │   ├── health_checker.py       Retry-based HTTP health checks
│   │   └── auth_service.py         JWT auth + bcrypt + admin bootstrap
│   │
│   ├── providers/                  External system adapters
│   │   ├── aws/                    boto3 EC2 provisioning
│   │   ├── docker/                 Docker install & container mgmt via SSH
│   │   ├── github/                 Repo validation & cloning
│   │   └── nginx/                  NGINX install & site config on EC2
│   │
│   ├── core/                       Shared utilities
│   │   ├── auth_middleware.py      JWT verification and RBAC decorators
│   │   ├── jwt_utils.py            Token generation and validation
│   │   ├── utils.py                SSH client, PEM loader (Secrets Manager)
│   │   ├── input_validators.py     GitHub URL & config validation
│   │   └── logging_config.py       Coloured, structured logging setup
│   │
│   ├── database/                   Persistence layer
│   │   ├── models.py               SQLAlchemy ORM models (incl. EnvironmentVariable)
│   │   ├── repositories.py         Data-access objects (repository pattern)
│   │   └── connection.py           Engine, session factory, init_db()
│   │
│   └── ml-deploy-key.pem          ⚠️ Your EC2 key pair (git-ignored)
│
├── frontend/                       React 19 + Vite 7 SPA
│   └── src/
│       ├── pages/                  Dashboard · Deploy · Applications · Instances
│       ├── components/             Reusable UI components
│       ├── services/               api.js (REST) · socket.js (WebSocket)
│       ├── hooks/                  Custom React hooks
│       └── utils/                  Constants, helpers
│
├── alembic/                        Database migrations
│   └── versions/                   Migration scripts (auto-applied on startup)
│
├── nginx/
│   └── frontend.conf               Nginx config template — proxies /api/* and
│                                   /socket.io/* to backend using BACKEND_HOST/PORT
│
├── scripts/                        Helper shell scripts
│   ├── setup_ec2.sh                Manual EC2 bootstrap
│   ├── install_docker.sh           Standalone Docker installer
│   ├── cleanup_resources.sh        Tear down AWS resources
│   └── quick_reference.sh          Common commands cheat sheet
│
├── example_ml_app/                 Sample ML app you can deploy to test the flow
│
├── assets/
│   └── screenshots/
│
├── Dockerfile.backend              Python 3.12-slim + Gunicorn, runs as appuser
├── Dockerfile.frontend             Node builder → Nginx alpine, envsubst for backend URL
├── docker-compose.yml              postgres + backend + frontend (full stack)
├── alembic.ini                     Alembic configuration
├── requirements.txt                Python dependencies
├── .env.example                    Environment variable template
├── .env                            Your secrets (git-ignored)
├── .dockerignore                   Files excluded from Docker builds
├── SETUP_GUIDE.md                  Step-by-step setup from scratch
└── README.md                       This file
```

> 🔐 **Security Note:**
> The EC2 private key (`ml-deploy-key.pem`) is either fetched from AWS Secrets Manager at container startup **or** mounted as a read-only volume. It is **never baked into the Docker image**.

---

## 🔧 Configuration Reference

All configuration is via environment variables. Copy `.env.example` to `.env` and edit it.

### AWS

| Variable | Description | Notes |
|---|---|---|
| `AWS_REGION` | Region where EC2 instances are created | e.g. `us-east-1` |
| `AWS_KEY_PAIR_NAME` | Name of EC2 key pair (must exist in region) | e.g. `ml-deploy-key` |

> ⚠️ `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are intentionally absent.
> - **Local dev:** run `aws configure` once — boto3 picks up `~/.aws/credentials` automatically.
> - **ECS:** attach an IAM Role to the ECS Task Definition — boto3 resolves credentials from the container metadata endpoint. No keys needed anywhere.

### EC2 Instance

| Variable | Default | Description |
|---|---|---|
| `EC2_AMI_ID` | _(none — required)_ | Ubuntu 22.04 LTS AMI — region-specific, must be set |
| `EC2_INSTANCE_TYPE` | `t2.micro` | Instance type |
| `EC2_VOLUME_SIZE` | `20` | Root disk size in GB |
| `EC2_VPC_ID` | _(empty)_ | **ECS only** — VPC ID where EC2 instances are launched. Leave blank for local dev. |
| `EC2_SUBNET_ID` | _(empty)_ | **ECS only** — public subnet ID inside the above VPC. Leave blank for local dev. |

> **VPC conflict explained:** When the platform itself runs on ECS inside a custom VPC, EC2 instances provisioned by the backend must land in the *same* VPC — otherwise they lose network connectivity to the platform. Set `EC2_VPC_ID` and `EC2_SUBNET_ID` to match the ECS VPC. For local dev these are not needed.

### Application Server

| Variable | Default | Description |
|---|---|---|
| `APP_PORT` | `5000` | Flask backend port |
| `FLASK_ENV` | `development` | `development` or `production` |
| `SECRET_KEY` | _(weak default)_ | Flask session secret — **must** be overridden in production |
| `JWT_SECRET_KEY` | _(falls back to SECRET_KEY)_ | JWT signing key — use a different value from SECRET_KEY |
| `JWT_EXPIRY_HOURS` | `1` | JWT token lifetime in hours |
| `STATIC_FOLDER` | `../frontend/dist` | Path to frontend static files in production |

### First-Admin Bootstrap

| Variable | Description |
|---|---|
| `ADMIN_EMAIL` | Email for the auto-created admin account |
| `ADMIN_PASSWORD` | Password (bcrypt-hashed on creation; plaintext wiped from memory) |

> Bootstrap is idempotent — if an admin already exists, these values are ignored.

### PEM / SSH Key

| Variable | Default | Description |
|---|---|---|
| `PEM_SECRET_NAME` | _(empty)_ | AWS Secrets Manager secret name — leave blank to skip fetch |
| `PEM_KEY_PATH` | `/app/ml-deploy-key.pem` | Single source of truth — where the key is written and read |

> - **Local dev:** place the `.pem` file in `backend/` and mount it as a read-only volume (the compose file does this automatically). Leave `PEM_SECRET_NAME` blank.
> - **ECS:** store the key in AWS Secrets Manager and set `PEM_SECRET_NAME`. The backend fetches it at container startup and writes it to `PEM_KEY_PATH`.

### CORS / Frontend

| Variable | Default | Description |
|---|---|---|
| `FRONTEND_URL` | _(empty)_ | Production frontend origin — restricts SocketIO CORS |
| `CORS_ORIGINS` | _(empty)_ | Comma-separated allowed origins for Flask-CORS |

### Docker Ports (for apps deployed TO EC2)

| Variable | Default | Description |
|---|---|---|
| `DOCKER_CONTAINER_PORT` | `8000` | Port app listens on inside container (`EXPOSE` in Dockerfile) |
| `DOCKER_HOST_PORT` | `8000` | Port exposed on EC2 host (NGINX proxies port 80 → this) |

### Deployment Settings

| Variable | Default | Description |
|---|---|---|
| `MAX_DEPLOYMENT_TIME` | `600` | Maximum time to wait for a deployment (seconds) |
| `HEALTH_CHECK_INTERVAL` | `10` | Time between app health checks (seconds) |
| `HEALTH_CHECK_RETRIES` | `5` | Number of health check failures before aborting |
| `EC2_READY_TIMEOUT` | `300` | Max wait time for EC2 to be healthy (seconds) |
| `EC2_READY_POLL_INTERVAL` | `10` | Poll interval for EC2 status (seconds) |
| `SSH_READY_TIMEOUT` | `420` | Max wait for SSH connection (seconds) |
| `SSH_RETRY_INTERVAL` | `5` | Time between SSH retries (seconds) |

### Security Group

| Variable | Default | Description |
|---|---|---|
| `SECURITY_GROUP_NAME` | `ml-deployment-sg` | Created automatically if missing |
| `ALLOWED_SSH_IP` | `0.0.0.0/0` | CIDR for SSH access — use `your.ip/32` in production |

### GitHub

| Variable | Default | Description |
|---|---|---|
| `GITHUB_TOKEN` | _(empty)_ | Personal access token — only needed for private repos |

### Logging

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FILE` | `deployment.log` | Log file name (written inside `backend/`) |

### Database

| Variable | Description |
|---|---|
| `DATABASE_URL` | Full SQLAlchemy connection string |
| `POSTGRES_USER`     | PostgreSQL username |
| `POSTGRES_PASSWORD` | PostgreSQL password |
| `POSTGRES_DB`       | Database name |

---

## 📡 API Reference

All endpoints are prefixed with `/api`.

### Health

```
GET /api/health
```

### Authentication

```
POST /api/auth/login      { "email": "...", "password": "..." }
POST /api/auth/refresh    Refresh JWT token
POST /api/auth/logout
```

### Deployments

```
GET  /api/deployments              List all deployments
POST /api/deployments              Trigger a new deployment
GET  /api/deployments/<id>         Get deployment details
GET  /api/deployments/<id>/logs    Get deployment log lines
```

**POST /api/deployments body:**
```json
{
  "github_url": "https://github.com/user/repo",
  "instance_name": "my-ml-model",
  "container_port": 8000,
  "host_port": 8000
}
```

### Applications

```
GET    /api/applications           List all registered applications
GET    /api/applications/<id>      Get application details
DELETE /api/applications/<id>      Delete an application record
```

### Instances

```
GET  /api/instances                  List all EC2 instances
GET  /api/instances/<id>             Get instance details
POST /api/instances/<id>/start       Start a stopped instance
POST /api/instances/<id>/stop        Stop a running instance
POST /api/instances/<id>/terminate   Terminate an instance
```

### WebSocket Events (Socket.IO)

| Event (client → server) | Payload | Purpose |
|---|---|---|
| `subscribe_deployment` | `{ "deployment_id": "<id>" }` | Subscribe to live logs |

| Event (server → client) | Payload | Purpose |
|---|---|---|
| `connected` | `{ "message": "..." }` | Sent on connect |
| `deployment_update` | `{ "step": "...", "status": "...", "message": "..." }` | Real-time step update |
| `deployment_complete` | `{ "deployment_id": "...", "url": "..." }` | Deployment finished |
| `deployment_error` | `{ "error": "..." }` | Deployment failed |

---

## 🔄 Deployment Workflow

When you click **Deploy**, the orchestrator runs these steps:

| # | Step | What Happens |
|---|---|---|
| 1 | Validate GitHub URL | Format check + repo accessibility |
| 2 | Check Dockerfile | Verifies `Dockerfile` exists in repo |
| 3 | Provision EC2 | Creates instance, waits for running state |
| 4 | Configure Security Group | Opens ports 22, 80, 443 (+ 8000 if no NGINX) |
| 5 | Wait for SSH | Polls until SSH is available (up to 5 min) |
| 6 | Install Docker | apt-get + Docker CE via SSH |
| 7 | Install NGINX | nginx package + enable service |
| 8 | Clone Repository | `git clone` on the EC2 instance |
| 9 | Build Docker Image | `docker build` from repo Dockerfile |
| 10 | Run Container | `docker run -d --restart=unless-stopped -p host:container` |
| 11 | Configure NGINX | Generate proxy config and reload |
| 12 | Health Check | HTTP GET with retries → confirm app is live |

Typical duration: **3–5 minutes** end-to-end.

---

## 🚀 Deploying Your Own App

Your GitHub repository must contain:

1. **`Dockerfile`** at the root — the platform runs `docker build` automatically
2. Application code that binds to **`0.0.0.0`** (not `127.0.0.1`)

### Trained Model File (`.pkl`, `.pt`, `.h5`, etc.)

If your ML app loads a trained model file, that file must be **present inside the Docker container** when it starts. The platform only clones your GitHub repo — it has no other way to supply files. You have three options:

| Option | How it works | Best for |
|--------|-------------|----------|
| **1. Commit to repo** | Add the `.pkl` to your GitHub repo → `COPY model.pkl .` in Dockerfile | Small models (< 100 MB) — simplest |
| **2. Download in Dockerfile** | `RUN wget https://your-storage.com/model.pkl` during `docker build` | Models hosted on S3, GCS, or any public URL |
| **3. Fetch at app startup** | App downloads the model on first request or startup (e.g. from HuggingFace Hub, S3) | Large models; keeps repo size small |

> **⚠️ Important:** If the model file is missing when the container starts, your app will crash. Deployment will be marked as failed at the health-check step.

### Minimal Python example

```python
# app.py
from flask import Flask
app = Flask(__name__)

@app.route('/')
def hello():
    return "Hello from my ML app!"

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)  # ← must be 0.0.0.0
```

```dockerfile
# Dockerfile
FROM python:3.11-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install -r requirements.txt
COPY . .
EXPOSE 8000
CMD ["python", "app.py"]
```

A complete example is in `example_ml_app/`.

---

## 📊 Monitoring & Logs

### Docker Compose

```bash
docker compose logs -f           # all services
docker compose logs -f backend   # backend only
docker compose logs -f frontend  # nginx only
```

### Manual Docker Setup

```bash
docker logs -f ml-backend
docker logs -f ml-frontend
docker logs -f ml-postgres
```

### Deployment Logs

- Each deployment's step-by-step log is stored in PostgreSQL.
- Accessible via **GET /api/deployments/\<id\>/logs**
- Visible in the React UI under the **Deploy** page in real-time via WebSocket.

### Database Inspection

```bash
# Docker Compose
docker exec -it autodeploy_postgres psql -U dbadmin -d autodeploy

# Manual setup
docker exec -it ml-postgres psql -U dbadmin -d autodeploy

# Useful queries
SELECT id, status, created_at FROM deployments ORDER BY created_at DESC LIMIT 10;
SELECT id, name, status FROM instances;
SELECT id, email FROM users;
```

---

## 🔍 Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| Backend exits immediately | Missing `.env` / `backend.env` value | Check `docker logs ml-backend` or `docker compose logs backend` |
| `EC2_AMI_ID is required` | Not set in env | Add `EC2_AMI_ID` for your region to `.env` |
| `AWS_KEY_PAIR_NAME is required` | Not set in env | Add `AWS_KEY_PAIR_NAME` to `.env` |
| `InvalidClientTokenId` | Wrong AWS credentials | Run `aws configure` again and verify |
| SSH auth failure on deployment | Wrong `.pem` file or name mismatch | Ensure key name in env matches the AWS key pair name |
| `AMI not found` | AMI ID wrong for region | Update `EC2_AMI_ID` for your `AWS_REGION` |
| PEM fetch error at startup | Secrets Manager config wrong | Check `PEM_SECRET_NAME`, region, and IAM permissions |
| `could not translate host name "postgres"` | Wrong `DATABASE_URL` hostname | Use container name (`ml-postgres` or `postgres`) not `localhost` |
| Port 80 in use | Another process | Change `NGINX_HTTP_PORT` or stop conflicting service |
| Port 5000 in use (macOS) | AirPlay Receiver | Disable in System Settings → Sharing |
| WebSocket not connecting | Backend not up | Wait for `Listening at: http://0.0.0.0:5000` in logs |
| App not accessible after deploy | App bound to `127.0.0.1` | Change to `host='0.0.0.0'` in your app |
| Deployment stuck | EC2 slow to boot | Increase `MAX_DEPLOYMENT_TIME` in env |
| Login fails | Wrong credentials or no admin created | Check `ADMIN_EMAIL`/`ADMIN_PASSWORD` were set before first startup |

---

## 🔒 Security

### Recommended Production Settings

```env
ALLOWED_SSH_IP=<your-ip>/32        # curl ifconfig.me
SECRET_KEY=<64-char-hex>           # python -c "import secrets; print(secrets.token_hex(32))"
JWT_SECRET_KEY=<different-64-char-hex>
FLASK_ENV=production
LOG_LEVEL=WARNING
FRONTEND_URL=https://yourdomain.com
CORS_ORIGINS=https://yourdomain.com
```

### What to Keep Secret

- `.env` / `backend.env` — never commit (already in `.gitignore`)
- `backend/*.pem` — EC2 private key (already in `.gitignore`)
- AWS credentials — use IAM roles where possible; rotate access keys regularly
- `ADMIN_PASSWORD` — change before first run; the plaintext is wiped after hashing

### IAM Least-Privilege

Instead of `AmazonEC2FullAccess`, scope down to:
- `ec2:RunInstances`, `ec2:DescribeInstances`, `ec2:TerminateInstances`
- `ec2:CreateSecurityGroup`, `ec2:AuthorizeSecurityGroupIngress`, `ec2:DescribeSecurityGroups`
- `ec2:CreateTags`, `ec2:DescribeKeyPairs`
- `secretsmanager:GetSecretValue` on the specific secret ARN

---

## 💰 Cost Considerations

| Resource | Free Tier? | Estimated Cost |
|---|---|---|
| t2.micro / t3.micro EC2 | ✅ 750 hrs/month | ~$0.012–0.013/hr after free tier |
| 20 GB EBS volume | ✅ 30 GB free | ~$0.10/GB-month after free tier |
| Data transfer | Partial | First 100 GB/month free |

> ⚠️ **Always terminate unused EC2 instances!** Use the Instances page or `scripts/cleanup_resources.sh`.

---

## ⚠️ Current Limitations

- **SSH-based provisioning** — paramiko SSH rather than AWS SSM or Terraform
- **Single Gunicorn worker** — required for Flask-SocketIO; horizontal scaling needs Redis broker
- **Single-region deployment** — one AWS region at a time
- **No background job queue** — deployments use threading rather than Celery
- **No auto-scaling or load balancing** — each deploy is a standalone EC2 instance
- **Model file must be self-supplied** — the platform clones your GitHub repo and builds the Docker image; it does not manage or upload model files (`.pkl`, `.pt`, `.h5`, etc.) separately. If your app requires a trained model, it must be included in the repo, downloaded via the `Dockerfile`, or fetched at container startup. Missing model files cause the app to crash after deployment.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, Vite 7, TailwindCSS v4, Socket.IO Client, React Router v7 |
| **Backend** | Python 3.12, Flask 3, Gunicorn, Flask-SocketIO, Flask-CORS, Flask-Limiter |
| **Auth** | JWT (PyJWT), bcrypt |
| **Database** | PostgreSQL 16, SQLAlchemy 2, Alembic |
| **AWS SDK** | boto3 |
| **SSH** | paramiko |
| **Secrets** | AWS Secrets Manager |
| **Container** | Docker Compose, Nginx Alpine |
| **Validation** | validators, custom input_validators |

---

## 📚 Further Reading

- [SETUP_GUIDE.md](./SETUP_GUIDE.md) — Step-by-step setup including AWS IAM, key pairs, Secrets Manager, and full env walkthrough
- [scripts/README.md](./scripts/README.md) — Helper scripts reference
- [example_ml_app/](./example_ml_app/) — Sample deployable ML application
- [docs/](./docs/) — Additional architecture and phase-by-phase Docker docs

---

**Happy Deploying! 🚀**
