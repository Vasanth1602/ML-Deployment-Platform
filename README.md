# 🚀 ML Deployment Platform

A production-ready, full-stack platform that automates deploying Machine Learning applications from a GitHub URL to an AWS EC2 instance — with Docker containerisation, NGINX reverse proxy, real-time progress streaming, and a modern React dashboard — all in a single click.

![Python](https://img.shields.io/badge/Python-3.11+-blue.svg)
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
- [Quick Start (Docker Compose)](#-quick-start-docker-compose)
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
| **Layered backend** | Clean API → Services → Providers → Database architecture |
| **PostgreSQL backend** | All state persisted in Postgres (managed by Alembic migrations) |

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

## ⚡ Quick Start (Docker Compose)

> **Full setup walkthrough (AWS credentials, key pairs, etc.):** see [SETUP_GUIDE.md](./SETUP_GUIDE.md)

### Prerequisites

- [Docker Desktop](https://www.docker.com/products/docker-desktop/) (v24+)
- AWS account with IAM credentials and an EC2 Key Pair
- Git

### 1 — Clone

```bash
git clone https://github.com/Vasanth1602/ML-Deployment-Platform.git
cd MML-Deployment-Platform
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
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX
AWS_SECRET_ACCESS_KEY=xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx
AWS_REGION=us-east-1
AWS_KEY_PAIR_NAME=ml-deploy-key      # Name of your EC2 key pair
EC2_AMI_ID=ami-0c7217cdde317cfec    # Ubuntu 22.04 LTS in us-east-1
SECRET_KEY=<random-string>           # python -c "import secrets; print(secrets.token_hex(32))"
```

### 3 — Add Your EC2 Key Pair File

```bash
# Place your downloaded .pem file in backend/
mv ~/Downloads/ml-deploy-key.pem backend/ml-deploy-key.pem

# Linux/macOS only
chmod 400 backend/ml-deploy-key.pem
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

---

## 🏗️ Architecture

### This Framework (how you run it locally)

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
│   health · deployments      │
│   applications · instances  │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│  Services layer (services/) │  Business logic & orchestration
│  deployment_orchestrator    │
│  health_checker             │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│  Providers (providers/)     │  External system adapters
│  aws/  docker/              │
│  github/  nginx/            │
└────────────┬────────────────┘
             │
┌────────────▼────────────────┐
│  Database (database/)       │  SQLAlchemy + Alembic
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

---

## 🏭 Production Readiness

This framework is designed with production-oriented practices in mind:

- **Dockerised full stack** — Backend, Frontend, and PostgreSQL run in isolated containers
- **Gunicorn WSGI server** — Production-grade request handling (not Flask dev server)
- **PostgreSQL persistence** — All deployments, applications, and instances stored reliably
- **Alembic migrations** — Database schema versioning and automatic upgrades on startup
- **Layered backend architecture** — Clear separation of API, orchestration, providers, and persistence
- **Runtime-mounted SSH key** — EC2 private key is injected at container runtime (not baked into the image)
- **Structured logging** — Centralised logging with configurable log levels
- **Graceful DB session management** — Scoped sessions with proper teardown handling

While designed as a lightweight deployment platform, the architecture follows patterns that can be extended for:

- Horizontal scaling
- Queue-based background workers (Celery / Redis)
- AWS SSM-based instance management (instead of SSH)
- Multi-tenant workspace isolation

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
│   │   ├── health.py               GET /api/health
│   │   ├── deployments.py          Deployment CRUD + trigger
│   │   ├── applications.py         Application registry endpoints
│   │   └── instances.py            EC2 instance management endpoints
│   │
│   ├── services/                   Business logic layer
│   │   ├── deployment_orchestrator.py  12-step deploy workflow
│   │   └── health_checker.py       Retry-based HTTP health checks
│   │
│   ├── providers/                  External system adapters
│   │   ├── aws/                    boto3 EC2 operations
│   │   ├── docker/                 Docker install & container mgmt via SSH
│   │   ├── github/                 Repo validation & cloning
│   │   └── nginx/                  NGINX install & site config
│   │
│   ├── core/                       Shared utilities
│   │   ├── utils.py                SSH client, URL parsers, helpers
│   │   ├── input_validators.py     GitHub URL & config validation
│   │   └── logging_config.py       Coloured, structured logging setup
│   │
│   ├── database/                   Persistence layer
│   │   ├── models.py               SQLAlchemy ORM models
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
│   └── frontend.conf               Nginx config for the frontend container
│
├── scripts/                        Helper shell scripts
│   ├── setup_ec2.sh                Manual EC2 bootstrap
│   ├── install_docker.sh           Standalone Docker installer
│   ├── cleanup_resources.sh        Tear down AWS resources
│   └── quick_reference.sh          Common commands cheat sheet
│
├── example_ml_app/                 Sample app you can deploy to test the flow
│
├── assets/                         Project images and documentation assets
│   └── screenshots/
│       ├── dashboard.png
│       └── deployment-progress.png
│
├── Dockerfile.backend              Python 3.11-slim + Gunicorn
├── Dockerfile.frontend             Node 20 builder → Nginx alpine
├── docker-compose.yml              postgres + backend + frontend
├── alembic.ini                     Alembic configuration
├── requirements.txt                Python dependencies
├── .env.example                    Environment variable template
├── .env                            Your secrets (git-ignored)
├── SETUP_GUIDE.md                  Step-by-step setup from scratch
└── README.md                       This file
```
> 🔐 **Security Note:**  
> The EC2 private key (`ml-deploy-key.pem`) is mounted into the backend container at runtime via Docker volumes and is **not baked into the Docker image**.  
> This prevents sensitive credentials from being stored inside image layers or shared via container registries.

---

## 🔧 Configuration Reference

All configuration is via environment variables in the root `.env` file.
Copy `.env.example` to `.env` and edit it.

### AWS (Required)

| Variable | Description | Example |
|---|---|---|
| `AWS_ACCESS_KEY_ID` | IAM access key ID | `AKIAXXXXXXXXXXXXXXXX` |
| `AWS_SECRET_ACCESS_KEY` | IAM secret access key | `wJalrXU...` |
| `AWS_REGION` | Region to deploy EC2 into | `us-east-1` |
| `AWS_KEY_PAIR_NAME` | Name of EC2 key pair (must exist in region) | `ml-deploy-key` |

### EC2 Instance

| Variable | Default | Description |
|---|---|---|
| `EC2_AMI_ID` | `ami-0c7217cdde317cfec` | Ubuntu 22.04 LTS AMI (region-specific!) |
| `EC2_INSTANCE_TYPE` | `t3.micro` | Instance type (Free Tier: t2.micro/t3.micro) |
| `EC2_VOLUME_SIZE` | `20` | Root disk size in GB |

### Application Server

| Variable | Default | Description |
|---|---|---|
| `APP_PORT` | `5000` | Flask backend port |
| `FLASK_ENV` | `development` | `development` or `production` |
| `SECRET_KEY` | — | Flask session secret (generate random) |

### Docker Ports (for apps you deploy TO EC2)

| Variable | Default | Description |
|---|---|---|
| `DOCKER_CONTAINER_PORT` | `8000` | Port your app listens on inside its container |
| `DOCKER_HOST_PORT` | `8000` | Port exposed on the EC2 host (NGINX proxies to this) |

### Security Group

| Variable | Default | Description |
|---|---|---|
| `SECURITY_GROUP_NAME` | `ml-deployment-sg` | AWS security group name (created if missing) |
| `ALLOWED_SSH_IP` | `0.0.0.0/0` | CIDR for SSH access (use `your.ip/32` for security) |

### GitHub

| Variable | Default | Description |
|---|---|---|
| `GITHUB_TOKEN` | _(empty)_ | Personal access token — only needed for private repos |

### Logging

| Variable | Default | Description |
|---|---|---|
| `LOG_LEVEL` | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `LOG_FILE` | `deployment.log` | Log file name (inside `backend/`) |

---

## 📡 API Reference

All endpoints are prefixed with `/api`.

### Health

```
GET /api/health
```
Returns service status and DB connectivity.

### Deployments

```
GET  /api/deployments              List all deployments
POST /api/deployments              Trigger a new deployment
GET  /api/deployments/<id>         Get deployment details
GET  /api/deployments/<id>/logs    Get deployment log lines
```

**POST /api/deployments — body:**
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
| `subscribe_deployment` | `{ "deployment_id": "<id>" }` | Subscribe to live logs for a deployment |

| Event (server → client) | Payload | Purpose |
|---|---|---|
| `connected` | `{ "message": "..." }` | Sent on connect |
| `deployment_update` | `{ "step": "...", "status": "...", "message": "..." }` | Real-time step update |
| `deployment_complete` | `{ "deployment_id": "...", "url": "..." }` | Deployment finished |
| `deployment_error` | `{ "error": "..." }` | Deployment failed |

---

## 🔄 Deployment Workflow

When you click **Deploy**, the orchestrator runs these 12 steps:

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
| 10 | Run Container | `docker run -d --restart=always -p host:container` |
| 11 | Configure NGINX | Generate proxy config and reload |
| 12 | Health Check | HTTP GET with retries → confirm app is live |

Typical duration: **3–5 minutes** end-to-end.

---

## 🚀 Deploying Your Own App

Your GitHub repository must have:

1. **`Dockerfile`** — builds an image that listens on `0.0.0.0:8000`
2. Application code that binds to `0.0.0.0` (not `127.0.0.1`)

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

### Application Logs

```bash
# All services
docker compose logs -f

# Backend only
docker compose logs -f backend

# Frontend (nginx) only
docker compose logs -f frontend
```

### Deployment Logs

- Each deployment's step-by-step log is stored in the database.
- Accessible via **GET /api/deployments/<id>/logs**
- Also visible in the React UI under the **Deploy** page in real-time.

### Database Inspection

```bash
# Connect to PostgreSQL
docker exec -it autodeploy_postgres psql -U dbadmin -d autodeploy

# Useful queries
SELECT id, status, created_at FROM deployments ORDER BY created_at DESC LIMIT 10;
SELECT id, name, status FROM instances;
```

---

## 🔍 Troubleshooting

| Problem | Likely Cause | Fix |
|---|---|---|
| Backend exits immediately | Missing `.env` or bad AWS credentials | Check `docker compose logs backend` |
| `InvalidClientTokenId` | Wrong `AWS_ACCESS_KEY_ID` | Verify key in IAM console |
| SSH auth failure on deployment | Wrong `.pem` file or `AWS_KEY_PAIR_NAME` mismatch | Ensure `backend/your-key.pem` matches key pair name in `.env` |
| `AMI not found` | AMI ID doesn't exist in your region | Update `EC2_AMI_ID` for your `AWS_REGION` |
| Port 80 in use | Another process using port 80 | Change frontend port in `docker-compose.yml` |
| Port 5000 in use (macOS) | AirPlay Receiver | Disable in System Settings → Sharing |
| WebSocket not connecting | Backend not up yet | Wait for `Listening at: http://0.0.0.0:5000` in logs |
| App not accessible after deploy | App listening on `127.0.0.1` | Change to `host='0.0.0.0'` in your app code |
| Deployment stuck | EC2 cloud-init slow | Increase `MAX_DEPLOYMENT_TIME` in `.env` |

---

## 🔒 Security

### Recommended Production Settings

```env
# Restrict SSH to your IP only
ALLOWED_SSH_IP=<your-ip>/32        # Get IP: curl ifconfig.me

# Use a real secret key
SECRET_KEY=<64-char-random-hex>    # python -c "import secrets; print(secrets.token_hex(32))"

# Production mode
FLASK_ENV=production
LOG_LEVEL=WARNING
```

### What to Keep Secret

- `.env` — never commit this (already in `.gitignore`)
- `backend/*.pem` — your EC2 private key (already in `.gitignore`)
- AWS credentials — rotate keys regularly in IAM

### IAM Least-Privilege

Instead of `AmazonEC2FullAccess`, you can scope down to:
- `ec2:RunInstances`, `ec2:DescribeInstances`, `ec2:TerminateInstances`
- `ec2:CreateSecurityGroup`, `ec2:AuthorizeSecurityGroupIngress`, `ec2:DescribeSecurityGroups`
- `ec2:CreateTags`, `ec2:DescribeKeyPairs`

---

## 💰 Cost Considerations

| Resource | Free Tier? | Estimated Cost |
|---|---|---|
| t2.micro EC2 instance | ✅ 750 hrs/month free | ~$0.012/hr after free tier |
| t3.micro EC2 instance | ✅ 750 hrs/month free | ~$0.013/hr after free tier |
| 20 GB EBS volume | ✅ 30 GB free | ~$0.10/GB-month after free tier |
| Data transfer | Partial | First 100 GB/month free |

> ⚠️ **Always terminate unused EC2 instances!**
> Use the **Instances** page in the dashboard or the `scripts/cleanup_resources.sh` script.

---

## ⚠️ Current Limitations

While functional and production-oriented, this framework currently has the following constraints:

- **SSH-based provisioning** — Instance configuration is performed via SSH (paramiko). In enterprise setups, AWS SSM or infrastructure-as-code tools (Terraform / CloudFormation) would be preferred.
- **Single Gunicorn worker** — Required for Flask-SocketIO state handling. Horizontal scaling would require a message broker (Redis) and multi-worker configuration.
- **Single-region deployment** — Instances are provisioned within one AWS region at a time.
- **No background job queue** — Long-running deployments are handled via threading rather than a dedicated task queue (e.g., Celery).
- **No auto-scaling or load balancing** — Each deployment provisions standalone EC2 infrastructure.

These limitations are intentional trade-offs to keep the system lightweight while demonstrating orchestration, containerisation, and infrastructure automation principles.

---

## 🛠️ Tech Stack

| Layer | Technology |
|---|---|
| **Frontend** | React 19, Vite 7, TailwindCSS v4, Socket.IO Client, React Router v7 |
| **Backend** | Python 3.11, Flask 3, Gunicorn, Flask-SocketIO, Flask-CORS |
| **Database** | PostgreSQL 16, SQLAlchemy 2, Alembic |
| **AWS SDK** | boto3 1.34 |
| **SSH** | paramiko 3.4 |
| **Container** | Docker Compose, Nginx Alpine |
| **Validation** | validators, custom input_validators |

---

## 📚 Further Reading

- [SETUP_GUIDE.md](./SETUP_GUIDE.md) — Step-by-step setup from scratch including AWS IAM, key pairs, and full `.env` walkthrough
- [scripts/README.md](./scripts/README.md) — Helper scripts reference
- [example_ml_app/](./example_ml_app/) — Sample deployable application

---

**Happy Deploying! 🚀**
