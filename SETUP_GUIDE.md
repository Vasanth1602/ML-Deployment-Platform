# 🚀 Complete Setup Guide — ML Deployment Platform

This guide covers **local development setup using Docker Compose**.
That is the recommended starting point for everyone.

If you later want to self-host this platform on AWS ECS, there is an optional
section at the bottom: [Optional: Self-Hosting the Platform on AWS ECS](#optional-self-hosting-the-platform-on-aws-ecs).
You do not need to read that section to get started locally.

Two local setup paths are documented:

| Path | Best For |
|---|---|
| **[Docker Compose](#6-run-with-docker-compose-recommended)** | Fastest way to get running — one command starts everything |
| **[Manual Docker](#7-manual-docker-setup-learning-path)** | Learn exactly how the containers communicate — recommended if you want to understand the infrastructure |

---

## 📋 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [AWS Credentials Setup](#3-aws-credentials-setup)
4. [Store PEM Key in AWS Secrets Manager](#4-store-pem-key-in-aws-secrets-manager)
5. [EC2 Key Pair Setup](#5-ec2-key-pair-setup)
6. [Run with Docker Compose (Recommended)](#6-run-with-docker-compose-recommended)
7. [Manual Docker Setup (Learning Path)](#7-manual-docker-setup-learning-path)
8. [Run Locally Without Docker (Dev)](#8-run-locally-without-docker-dev)
9. [Using the Application](#9-using-the-application)
10. [Troubleshooting](#10-troubleshooting)

---

## 1. Prerequisites

### Required for all paths

| Tool | Minimum Version | Download |
|---|---|---|
| **Docker Desktop** | 24+ | https://www.docker.com/products/docker-desktop/ |
| **Git** | Any | https://git-scm.com/downloads |
| **AWS Account** | — | https://aws.amazon.com/free/ |
| **AWS CLI** | 2.x | https://aws.amazon.com/cli/ |

### Required for local dev only (no Docker)

| Tool | Minimum Version |
|---|---|
| Python | 3.11+ |
| Node.js | 20+ |

### Verify Installations

```bash
docker --version          # Docker version 24.x or later
docker compose version    # Docker Compose v2.x or later
git --version
aws --version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/Vasanth1602/ML-Deployment-Platform.git
cd ML-Deployment-Platform
```

---

## 3. AWS Credentials Setup [Local + ECS]

The platform uses **boto3** to provision EC2 instances. boto3 resolves credentials automatically — you **never put `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` in `.env` or any env file**.

### Step 3.1 — Create an IAM User

1. Open **[AWS Console](https://console.aws.amazon.com/)** → **IAM** → **Users** → **Create user**
2. Name it, e.g. `ml-deploy-bot`
3. On the Permissions page, choose **Attach policies directly** and attach:
   - `AmazonEC2FullAccess`
   - *(Optional)* `AmazonVPCFullAccess` — only if your account uses a custom VPC
   - A custom policy granting `secretsmanager:GetSecretValue` on your PEM secret (see Step 4)
4. Finish and click **Create user**

**For least-privilege EC2 permissions**, use this custom policy instead of `AmazonEC2FullAccess`:

```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Effect": "Allow",
      "Action": [
        "ec2:RunInstances",
        "ec2:DescribeInstances",
        "ec2:TerminateInstances",
        "ec2:StartInstances",
        "ec2:StopInstances",
        "ec2:CreateSecurityGroup",
        "ec2:AuthorizeSecurityGroupIngress",
        "ec2:DescribeSecurityGroups",
        "ec2:CreateTags",
        "ec2:DescribeKeyPairs",
        "ec2:DescribeImages",
        "ec2:DescribeInstanceStatus"
      ],
      "Resource": "*"
    }
  ]
}
```

### Step 3.2 — Generate an Access Key

1. Click your new user → **Security credentials** tab
2. Scroll to **Access keys** → **Create access key**
3. Choose **"Application running outside AWS"**
4. Copy both values — the **Secret Access Key is shown only once**

### Step 3.3 — Configure the AWS CLI

```bash
aws configure
```

Enter the values when prompted:

```
AWS Access Key ID:     AKIAXXXXXXXXXXXXXXXX
AWS Secret Access Key: wJalrXU...
Default region name:   ap-south-1
Default output format: json
```

Credentials are stored in `~/.aws/credentials`. boto3 in the backend container picks these up automatically when you mount `~/.aws` as a volume (see the manual Docker setup).

### Step 3.4 — Verify

```bash
aws sts get-caller-identity
# Returns your account ID and user ARN — confirms credentials work
```

### Step 3.5 — Choose Your AWS Region

| Region Code | Location |
|---|---|
| `us-east-1` | N. Virginia (cheapest) |
| `us-west-2` | Oregon |
| `eu-west-1` | Ireland |
| `ap-south-1` | Mumbai |

Use the **same region** for your credentials, key pair, AMI ID, and Secrets Manager secret.

---

## 4. Store PEM Key in AWS Secrets Manager [Optional for Local Dev]

> **Local dev only?** This step is optional. Skip to Step 5 and use Option A (manual `.pem` file copy) instead.

The EC2 SSH private key is stored in AWS Secrets Manager and fetched automatically at backend startup. It is **never** in the Docker image, repository, or any committed file.

### Step 4.1 — Upload the Secret

1. Open **[AWS Secrets Manager Console](https://console.aws.amazon.com/secretsmanager)**
2. Click **Store a new secret**
3. Choose **Other type of secret** → **Plaintext**
4. Paste the **full contents** of your `.pem` file, including headers:
   ```
   -----BEGIN RSA PRIVATE KEY-----
   MIIEowIBAAK...
   -----END RSA PRIVATE KEY-----
   ```
5. Name the secret, e.g. `ml-deploy-key`
6. Click through and save

Note the exact secret name — you will use it as `PEM_SECRET_NAME`.

### Step 4.2 — Grant IAM Permission

Add this statement to the IAM policy for your `ml-deploy-bot` user:

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:ml-deploy-key*"
}
```

Replace `<REGION>` and `<ACCOUNT_ID>` with your values.

### How It Works at Runtime

When the backend container starts, `load_pem_from_secrets_manager()` in `backend/core/utils.py`:

1. Calls `boto3 → secretsmanager.get_secret_value(SecretId=PEM_SECRET_NAME)`
2. Writes the key content to `PEM_KEY_PATH` (default: `/app/ml-deploy-key.pem`) with `chmod 600`
3. Paramiko uses this file for all SSH connections to deployed EC2 instances

If `PEM_SECRET_NAME` is not set, the fetch is skipped and a warning is logged. SSH deployments will fail unless the file exists at `PEM_KEY_PATH` via another means (e.g. a Docker volume mount).

---

## 5. EC2 Key Pair Setup

### Step 5.1 — Create a Key Pair in AWS

1. AWS Console → **EC2** → **Key Pairs** (under Network & Security)
2. Click **Create key pair**
3. Fill in:
   - **Name:** e.g. `ml-deploy-key` ← this is `AWS_KEY_PAIR_NAME` in your env
   - **Key pair type:** RSA
   - **Private key file format:** `.pem`
4. Click **Create key pair** — the browser downloads `ml-deploy-key.pem`

### Step 5.2 — PEM Key: Choose Your Approach
  Local dev  → Place in backend/ folder (Step 5.3) — Secrets Manager not needed
  ECS        → Upload to Secrets Manager (Step 4)

### Step 5.3 — Place in Project (for Docker volume mount / Docker Compose)

```bash
# macOS / Linux
mv ~/Downloads/ml-deploy-key.pem backend/ml-deploy-key.pem
chmod 400 backend/ml-deploy-key.pem

# Windows
move %USERPROFILE%\Downloads\ml-deploy-key.pem backend\ml-deploy-key.pem
```

> **Windows Docker users:** permissions are handled by Docker's read-only mount. No `chmod` needed.

`docker-compose.yml` mounts this automatically:
```yaml
volumes:
  - ./backend/ml-deploy-key.pem:/app/ml-deploy-key.pem:ro
```

For the manual setup you can either rely on Secrets Manager (recommended) or add a volume mount to the `docker run` command.

### Step 5.4 — Find the Right AMI ID for Your Region

The platform provisions **Ubuntu 22.04 LTS** instances by default.

Look up the correct AMI ID for your region at:
https://cloud-images.ubuntu.com/locator/ec2/

Common Ubuntu 22.04 LTS AMI IDs:

| Region | AMI ID |
|---|---|
| `us-east-1` | `ami-0c7217cdde317cfec` |
| `us-west-2` | `ami-0735c191cf914754d` |
| `eu-west-1` | `ami-0965bd5ba4d59211c` |
| `ap-south-1` | `ami-007020fd9ab68be57` |

> ⚠️ AMI IDs change with new Ubuntu releases. Always verify at the link above.

---

## 6. Run with Docker Compose (Recommended)

Starts three containers in one command: **PostgreSQL 16**, **Flask + Gunicorn backend**, and **React/Nginx frontend**.

### Step 6.1 — Configure Environment Variables

```bash
# macOS / Linux
cp .env.example .env

# Windows
copy .env.example .env
```

Open `.env` and fill in the mandatory values:

> **VPC Configuration Note (ECS/Custom VPCs):**
> Default VPC is fine for local dev. When self-hosting the platform in a custom VPC (ECS),
> set `EC2_VPC_ID` and `EC2_SUBNET_ID` to match the platform's VPC/subnet to prevent connectivity loss.
> Find these values in: AWS Console → VPC → Your VPCs / Subnets.

```env
# ── AWS (no static keys — use aws configure instead) ─────────────────────────
AWS_REGION=us-east-1
AWS_KEY_PAIR_NAME=ml-deploy-key

# ── EC2 ───────────────────────────────────────────────────────────────────────
EC2_AMI_ID=ami-0c7217cdde317cfec    # Ubuntu 22.04 LTS — update for your region
EC2_INSTANCE_TYPE=t3.micro
EC2_VOLUME_SIZE=20
EC2_VPC_ID=                         # Optional VPC override
EC2_SUBNET_ID=                      # Optional Subnet override

# ── Security Group ────────────────────────────────────────────────────────────
SECURITY_GROUP_NAME=ml-deployment-sg
ALLOWED_SSH_IP=0.0.0.0/0            # Replace with your IP/32 for production

# ── Flask ─────────────────────────────────────────────────────────────────────
APP_PORT=5000
FLASK_ENV=development

# Generate: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here
JWT_EXPIRY_HOURS=1

# ── First-Admin Bootstrap ─────────────────────────────────────────────────────
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeMe123!

# ── PEM Key ───────────────────────────────────────────────────────────────────
PEM_SECRET_NAME=ml-deploy-key       # Your Secrets Manager secret name (Step 4)
PEM_KEY_PATH=/app/ml-deploy-key.pem

# ── Database ──────────────────────────────────────────────────────────────────
POSTGRES_USER=dbadmin
POSTGRES_PASSWORD=your_db_password_here
POSTGRES_DB=autodeploy

# ── CORS / Frontend ───────────────────────────────────────────────────────────
FRONTEND_URL=http://localhost
CORS_ORIGINS=http://localhost,http://localhost:80

# ── Docker deployment ports (for apps deployed TO EC2) ────────────────────────
DOCKER_CONTAINER_PORT=8000
DOCKER_HOST_PORT=8000
MAX_DEPLOYMENT_TIME=600
HEALTH_CHECK_INTERVAL=10
HEALTH_CHECK_RETRIES=5
EC2_READY_TIMEOUT=300
EC2_READY_POLL_INTERVAL=10
SSH_READY_TIMEOUT=420
SSH_RETRY_INTERVAL=5

# ── Nginx ─────────────────────────────────────────────────────────────────────
NGINX_HTTP_PORT=80
ENABLE_NGINX=true

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
LOG_FILE=deployment.log
```

### Step 6.2 — Make Sure Docker Desktop is Running

Open Docker Desktop and wait until it shows **"Engine running"**.

### Step 6.3 — Start Everything

```bash
docker compose up --build
```

First build: **3–5 minutes**. Subsequent starts: seconds.

**Expected output:**

```
autodeploy_postgres   | database system is ready to accept connections
autodeploy_backend    | [INFO] Starting gunicorn 21.2.0
autodeploy_backend    | [INFO] Listening at: http://0.0.0.0:5000
autodeploy_frontend   | Configuration complete; ready for start up
```

### Step 6.4 — Alembic Migrations

Migrations run **automatically** at backend container startup. No manual step needed.

### Step 6.5 — Open the Application

| Service | URL |
|---|---|
| **Frontend UI** | http://localhost |
| **Backend API** | http://localhost:5000 |
| **PostgreSQL** | localhost:5432 (user: dbadmin) |

Log in with the `ADMIN_EMAIL` and `ADMIN_PASSWORD` you set in `.env`.

### Useful Docker Compose Commands

```bash
# Run in background
docker compose up --build -d

# View live logs (all services)
docker compose logs -f

# View logs for one service
docker compose logs -f backend

# Stop all services (data preserved)
docker compose down

# Stop and delete the database volume (full reset)
docker compose down -v

# Rebuild only the backend
docker compose up --build backend
```

---

## 7. Manual Docker Setup (Learning Path)

> **Why do this?**
> Docker Compose abstracts away the individual steps. Doing it manually teaches you:
> - How Docker bridge networks work and why you use service names (`ml-postgres`) instead of `localhost`
> - How `--env-file` injects environment variables into a container
> - How volume mounts work for secrets, credentials, and persistent data
> - How to inspect, debug, and restart individual containers independently
> - The exact startup sequence the backend requires (database must be ready first)
>
> This knowledge makes it far easier to debug issues and adapt the platform to different environments.

---

### M1 — AWS Credentials (Already Done in Step 3)

The backend container must be able to call AWS APIs. The AWS CLI configuration from Step 3 (`aws configure`) stores credentials in `~/.aws/credentials` on your host machine. You mount this directory into the container in Step M7.

---

### M2 — Create Docker Network

```bash
docker network create ml-network
```

Verify:

```bash
docker network ls
# NAME         DRIVER    SCOPE
# ml-network   bridge    local
```

All three containers join this network. They can then reach each other by container name — `ml-postgres`, `ml-backend`, `ml-frontend` — instead of `localhost`.

---

### M3 — Run PostgreSQL

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

Wait ~10 seconds then verify:

```bash
docker exec -it ml-postgres pg_isready -U dbadmin -d autodeploy
# /var/run/postgresql:5432 - accepting connections
```

---

### M4 — Create `backend.env`

Create `backend.env` in any directory on your machine. **Do not commit this file.**

> **VPC Configuration Note (ECS/Custom VPCs):**
> Default VPC is fine for local dev. When self-hosting the platform in a custom VPC (ECS),
> set `EC2_VPC_ID` and `EC2_SUBNET_ID` to match the platform's VPC/subnet to prevent connectivity loss.
> Find these values in: AWS Console → VPC → Your VPCs / Subnets.

```env
# ── Database ──────────────────────────────────────────────────────────────────
# Use the postgres CONTAINER NAME as hostname, not localhost
DATABASE_URL=postgresql://dbadmin:your_db_password_here@ml-postgres:5432/autodeploy

# ── Flask ─────────────────────────────────────────────────────────────────────
FLASK_ENV=development
APP_PORT=5000

# Generate: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=your_secret_key_here
JWT_SECRET_KEY=your_jwt_secret_key_here
JWT_EXPIRY_HOURS=1

# ── First-Admin Bootstrap ─────────────────────────────────────────────────────
ADMIN_EMAIL=admin@example.com
ADMIN_PASSWORD=ChangeMe123!

# ── AWS (credentials come from ~/.aws volume mount — no keys here) ────────────
AWS_REGION=ap-south-1
AWS_KEY_PAIR_NAME=ml-deploy-key
EC2_AMI_ID=ami-019715e0d74f695be
EC2_INSTANCE_TYPE=t3.micro
EC2_VOLUME_SIZE=20
EC2_VPC_ID=
EC2_SUBNET_ID=
SECURITY_GROUP_NAME=ml-deployment-sg
ALLOWED_SSH_IP=0.0.0.0/0

# ── PEM Key (Secrets Manager) ─────────────────────────────────────────────────
PEM_SECRET_NAME=ml-deploy-key
PEM_KEY_PATH=/app/ml-deploy-key.pem

# ── CORS / Frontend ───────────────────────────────────────────────────────────
FRONTEND_URL=http://localhost
CORS_ORIGINS=http://localhost,http://localhost:80

# ── Nginx backend routing (used by frontend Nginx config template) ────────────
BACKEND_HOST=ml-backend
BACKEND_PORT=5000

# ── Docker deployment ports (for apps deployed TO EC2) ────────────────────────
DOCKER_CONTAINER_PORT=8000
DOCKER_HOST_PORT=8000
MAX_DEPLOYMENT_TIME=600
HEALTH_CHECK_INTERVAL=10
HEALTH_CHECK_RETRIES=5
EC2_READY_TIMEOUT=300
EC2_READY_POLL_INTERVAL=10
SSH_READY_TIMEOUT=420
SSH_RETRY_INTERVAL=5

# ── Logging ───────────────────────────────────────────────────────────────────
LOG_LEVEL=INFO
LOG_FILE=deployment.log

# ── NGINX on EC2 ──────────────────────────────────────────────────────────────
ENABLE_NGINX=true
NGINX_HTTP_PORT=80
```

---

### M5 — Build the Backend Image

```bash
# Run from the project root (ML-Deployment-Platform/)
docker build -f Dockerfile.backend -t ml-backend .
```

---

### M6 — Run the Backend Container

`--env-file` keeps the run command short and keeps secrets out of your shell history.

The `-v ~/.aws` mount gives boto3 inside the container access to your `aws configure` credentials. The container runs as `appuser`, so the mount destination is `/home/appuser/.aws`.

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
> boto3 uses the standard AWS credentials lookup chain. Mounting `~/.aws` into the container's `appuser` home directory means boto3 finds your `aws configure` credentials without any static keys in `backend.env`.
>
> **PEM key:** If `PEM_SECRET_NAME` is set, the key is fetched from Secrets Manager at startup and written to `/app/ml-deploy-key.pem` automatically.
>
> **Alternative — mount the .pem directly** (if you prefer not to use Secrets Manager):
> Remove `PEM_SECRET_NAME` from `backend.env` and add:
> ```
> -v /absolute/path/to/ml-deploy-key.pem:/app/ml-deploy-key.pem:ro
> ```

Verify startup:

```bash
docker logs ml-backend
# Expected lines:
# [PEM] PEM key written to /app/ml-deploy-key.pem
# [INFO] Default tenant created
# [INFO] Admin user created: admin@example.com    ← first run only
# [INFO] Listening at: http://0.0.0.0:5000

curl http://localhost:5000/api/health
# {"status": "healthy", ...}
```

---

### M7 — Build the Frontend Image

```bash
docker build -f Dockerfile.frontend -t ml-frontend .
```

---

### M8 — Run the Frontend Container

The frontend Nginx config template uses `BACKEND_HOST` and `BACKEND_PORT` (injected via `envsubst` at startup) to proxy `/api/*` and `/socket.io/*` to the backend container.

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

### M9 — Verify Everything

```bash
docker ps
```

Expected:

```
CONTAINER ID  IMAGE         STATUS           NAMES
xxxxxxxxxxxx  ml-frontend   Up X minutes     ml-frontend
xxxxxxxxxxxx  ml-backend    Up X minutes     ml-backend
xxxxxxxxxxxx  postgres:16   Up X minutes     ml-postgres
```

Open:

```
http://localhost
```

Log in with the `ADMIN_EMAIL` and `ADMIN_PASSWORD` from `backend.env`.

---

### Manual Management Commands

```bash
# Follow logs
docker logs -f ml-backend
docker logs -f ml-frontend
docker logs -f ml-postgres

# Restart a container
docker restart ml-backend

# Open a shell inside a container
docker exec -it ml-backend bash
docker exec -it ml-postgres psql -U dbadmin -d autodeploy

# Stop all containers
docker stop ml-frontend ml-backend ml-postgres

# Remove containers (volume survives)
docker rm ml-frontend ml-backend ml-postgres

# Remove network
docker network rm ml-network

# Full reset — remove containers, network, and data volume
docker stop ml-frontend ml-backend ml-postgres
docker rm ml-frontend ml-backend ml-postgres
docker volume rm ml-postgres-data
docker network rm ml-network
```

---

## 8. Run Locally Without Docker (Dev)

Use this for the fastest hot-reload cycle during development. You still need a running PostgreSQL instance.

### Backend

```bash
# From project root
python -m venv venv

# Activate
source venv/bin/activate      # macOS / Linux
venv\Scripts\activate         # Windows

pip install -r requirements.txt

# Start
python -m backend.app
```

Ensure your `.env` has:

```env
DATABASE_URL=postgresql://dbadmin:your_password@localhost:5432/autodeploy
FLASK_ENV=development
```

Backend runs at **http://localhost:5000**.

### Frontend

```bash
cd frontend
npm install
npm run dev
```

Create `frontend/.env`:

```env
VITE_API_URL=http://localhost:5000
```

Frontend dev server runs at **http://localhost:5173** with hot-reload.

---

## 9. Using the Application

Once running at `http://localhost`:

### First Login

Use `ADMIN_EMAIL` and `ADMIN_PASSWORD` from your `.env` or `backend.env`. The account is created automatically on first startup. If the admin already exists, the env vars are ignored on subsequent startups.

### First Deployment

1. Click **Deploy** in the sidebar
2. Enter a GitHub repository URL (e.g. `https://github.com/you/your-ml-app`)
3. The repository must contain a `Dockerfile` that builds an image listening on `0.0.0.0:8000`
4. Click **Deploy Application**
5. Watch real-time logs stream via WebSocket
6. On completion you receive the EC2 public IP to access your deployed app

### Example Repository

`example_ml_app/` contains a ready-to-use Flask ML app with a `Dockerfile`. Push it to your GitHub account and deploy it to test the full pipeline.

---

## 10. Troubleshooting

### Docker Issues

| Problem | Solution |
|---|---|
| `docker compose` not found | Use `docker-compose` (v1) or update Docker Desktop |
| Port 80 in use | Stop the conflicting service or change `NGINX_HTTP_PORT` |
| Port 5000 in use (macOS) | AirPlay uses 5000 — disable AirPlay Receiver in System Settings → Sharing |
| Port 5432 in use | Stop a local PostgreSQL instance |
| Backend exits immediately | Run `docker logs ml-backend` — likely a missing env value |
| `could not translate host name "postgres"` | `DATABASE_URL` uses wrong hostname — must be container name (`ml-postgres` or `postgres`) not `localhost` |

### AWS / Deployment Issues

| Problem | Solution |
|---|---|
| `AWS_KEY_PAIR_NAME is required` | Add it to `.env` or `backend.env` |
| `EC2_AMI_ID is required` | Add an AMI ID for your region (Step 5.4) |
| `InvalidClientTokenId` | Run `aws configure` again with correct credentials |
| `AuthFailure` (SSH) | Key pair name in env doesn't match the name in AWS, or PEM content is wrong |
| `AMI not found` | `EC2_AMI_ID` doesn't exist in your `AWS_REGION` — update it |
| PEM fetch error | Check `PEM_SECRET_NAME` matches the exact Secrets Manager secret name; verify IAM permission and region |
| Instance stuck provisioning | Increase `MAX_DEPLOYMENT_TIME` in env |

### Auth Issues

| Problem | Solution |
|---|---|
| Login fails on first run | Check `ADMIN_EMAIL`/`ADMIN_PASSWORD` were set in env **before** first startup |
| Admin already exists message | Bootstrap is idempotent — this is expected behaviour on subsequent starts |
| JWT expired | Increase `JWT_EXPIRY_HOURS` or re-login |

### Frontend / API Issues

| Problem | Solution |
|---|---|
| Dashboard shows no data | Check backend health: `curl http://localhost:5000/api/health` |
| WebSocket not connecting | Ensure backend is up; check browser console for CORS errors |
| CORS errors in browser | Verify `CORS_ORIGINS` / `FRONTEND_URL` match the origin you are connecting from |
| `npm install` fails | Delete `frontend/node_modules/` and `frontend/package-lock.json`, then retry |

---

## ✅ You're All Set!

| Component | Status |
|---|---|
| PostgreSQL 16 | Running in Docker |
| Flask + Gunicorn backend | Running in Docker on port 5000 |
| React frontend (Nginx) | Running in Docker on port 80 |
| AWS credentials | Configured via `aws configure` |
EC2 key pair | Placed in backend/ folder (or Secrets Manager for ECS)
| Admin account | Auto-created on first startup |

**Open the app → http://localhost — Happy Deploying! 🚀**

---

## Optional: Self-Hosting the Platform on AWS ECS

If you want to deploy the platform itself on AWS ECS rather than running it locally,
the following additional steps are required.
These are separate from the local dev setup above.

---

### ECS Step 1 — Create an IAM Role for the ECS Task

1. AWS Console → **IAM** → **Roles** → **Create role**
2. **Trusted entity type:** AWS service — **Use case:** Elastic Container Service Task
3. Attach these permissions:
   - Scoped EC2 permissions (see **IAM Least-Privilege** in `README.md`)
   - `secretsmanager:GetSecretValue` on your PEM secret ARN
4. Name it, e.g. `ml-platform-task-role`

This role gives the backend container AWS access at runtime. No access keys are used anywhere.

---

### ECS Step 2 — Attach the IAM Role to Your ECS Task Definition

1. ECS Console → **Task Definitions** → your task → create a new revision
2. Under **Task role** → select `ml-platform-task-role`
3. Under **Task execution role** → select `ecsTaskExecutionRole` (standard AWS-managed role)

boto3 inside the container will now resolve credentials automatically via the container metadata endpoint.

---

### ECS Step 3 — Store PEM Key in AWS Secrets Manager

Already documented in [Step 4](#4-store-pem-key-in-aws-secrets-manager-ecs) of this guide.
Confirm that `PEM_SECRET_NAME` is set in your ECS Task Definition under **Environment variables**.

---

### ECS Step 4 — Set VPC and Subnet in ECS Task Environment Variables

The backend provisions EC2 instances for users. Without these, EC2 launches in the
default VPC instead of your platform’s custom VPC, breaking connectivity between them.

Find the values:
- AWS Console → **VPC** → **Your VPCs** → copy the VPC ID of your ECS VPC
- AWS Console → **Subnets** → pick a **public** subnet in that VPC → copy its ID

Add to your ECS Task Definition under **Environment variables**:

```
EC2_VPC_ID=vpc-xxxxxxxxxxxxxxxxx
EC2_SUBNET_ID=subnet-xxxxxxxxxxxxxxxxx
```
### ECS Step X — Set DATABASE_URL in ECS Task Definition

The platform uses RDS (or any external PostgreSQL) in ECS — not a
local container. Set DATABASE_URL directly in your ECS Task Definition
under Environment variables:

  DATABASE_URL=postgresql://<user>:<password>@<your-rds-endpoint>:5432/<dbname>

Find your RDS endpoint:
  AWS Console → RDS → Databases → your instance → Connectivity → Endpoint
