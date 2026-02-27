# 🚀 Complete Setup Guide — ML Deployment Platform

This guide walks you through setting up the framework **from absolute scratch**.
The **recommended (and easiest) path is Docker Compose** — it starts everything
(PostgreSQL, Flask backend, React frontend) with a single command.

---

## 📋 Table of Contents

1. [Prerequisites](#1-prerequisites)
2. [Clone the Repository](#2-clone-the-repository)
3. [AWS Credentials — Detailed Setup](#3-aws-credentials--detailed-setup)
4. [EC2 Key Pair — Detailed Setup](#4-ec2-key-pair--detailed-setup)
5. [Configure Environment Variables](#5-configure-environment-variables)
6. [Run with Docker Compose (Recommended)](#6-run-with-docker-compose-recommended)
7. [Run Locally Without Docker (Alternative)](#7-run-locally-without-docker-alternative)
8. [Using the Application](#8-using-the-application)
9. [Troubleshooting](#9-troubleshooting)

---

## 1. Prerequisites

Install all of the following before you begin.

| Tool | Minimum Version | Download |
|------|----------------|----------|
| **Docker Desktop** | 24+ | <https://www.docker.com/products/docker-desktop/> |
| **Git** | Any | <https://git-scm.com/downloads> |
| **AWS Account** | — | <https://aws.amazon.com/free/> |

> **Note — Local dev only (no Docker):** You also need Python 3.11+ and Node.js 20+.

### Verify Installations

```bash
docker --version          # Docker version 24.x or later
docker compose version    # Docker Compose v2.x or later
git --version
```

---

## 2. Clone the Repository

```bash
git clone https://github.com/Vasanth1602/ML-Deployment-Platform.git
cd ML-Deployment-Platform
```

---

## 3. AWS Credentials — Detailed Setup

The framework uses **boto3 (AWS SDK)** to provision EC2 instances on your behalf.
You must supply credentials for an IAM user that has the right permissions.

### Step 3.1 — Create (or use an existing) IAM User

1. Open the **[AWS Console](https://console.aws.amazon.com/)** → Search for **IAM** → Open it.
2. Click **Users** in the left sidebar → **Create user**.
3. Give the user a name, e.g. `ml-deploy-bot`.
4. On the **Permissions** page chose **Attach policies directly**.
5. Attach the following managed policy (broad but sufficient for this tool):
   - `AmazonEC2FullAccess`
   - *(Optional)* `AmazonVPCFullAccess` — only if your account has a custom VPC.
6. Finish the wizard and click **Create user**.

### Step 3.2 — Generate an Access Key

1. Click the newly created user → **Security credentials** tab.
2. Scroll to **Access keys** → **Create access key**.
3. Choose **"Application running outside AWS"** as the use case.
4. Copy **both** values:

   | Variable | What it looks like |
   |---|---|
   | **Access Key ID** | `AKIA...` (20-character string starting with `AKIA`) |
   | **Secret Access Key** | `wJalrXU...` (40-character base-64 string) |

   > ⚠️ **Important:** The Secret Access Key is shown **only once**.
   > Copy it now or download the CSV. If you lose it, you must create a new key.

5. Paste these into your `.env` file (see [Section 5](#5-configure-environment-variables)).

### Step 3.3 — Choose Your AWS Region

This determines where EC2 instances are created.
Common options:

| Region Code | Location |
|---|---|
| `us-east-1` | N. Virginia (default, cheapest) |
| `us-west-2` | Oregon |
| `eu-west-1` | Ireland |
| `ap-south-1` | Mumbai |

Use the same region for **everything** (credentials, key pair, AMI).

---

## 4. EC2 Key Pair — Detailed Setup

The framework SSH-connects to EC2 instances using a `.pem` private key file.

### Step 4.1 — Create a Key Pair in AWS

1. AWS Console → **EC2** → **Key Pairs** (left sidebar, under **Network & Security**).
2. Click **Create key pair**.
3. Fill in:
   - **Name:** e.g. `ml-deploy-key` ← you'll use this name in `.env`
   - **Key pair type:** RSA
   - **Private key file format:** `.pem`
4. Click **Create key pair** — the browser will automatically **download** `ml-deploy-key.pem`.

### Step 4.2 — Place the `.pem` File in the Project

```bash
# Move the downloaded file into the backend/ directory
mv ~/Downloads/ml-deploy-key.pem  backend/ml-deploy-key.pem

# On Linux/macOS — restrict permissions (REQUIRED for SSH to work)
chmod 400 backend/ml-deploy-key.pem
```

> **Windows users:** Docker mounts the file as read-only, so permissions are
> handled automatically. No `chmod` needed.

### Step 4.3 — Find the Right AMI ID for Your Region

The AMI (Amazon Machine Image) is the OS template for new EC2 instances.
The framework defaults to **Ubuntu 22.04 LTS**.

Look up the correct AMI ID for your region at:
<https://cloud-images.ubuntu.com/locator/ec2/>

Common Ubuntu 22.04 LTS AMI IDs:

| Region | AMI ID |
|---|---|
| `us-east-1` | `ami-0c7217cdde317cfec` |
| `us-west-2` | `ami-0735c191cf914754d` |
| `eu-west-1` | `ami-0965bd5ba4d59211c` |
| `ap-south-1` | `ami-007020fd9ab68be57` |

> ⚠️ AMI IDs change with new Ubuntu releases. Always verify the latest at the link above.

---

## 5. Configure Environment Variables

```bash
# Copy the template
copy .env.example .env        # Windows
cp .env.example .env          # macOS / Linux
```

Now open `.env` in any text editor and fill in the values below.
**Mandatory fields are marked with ⚠️.**

```env
# ============================================================
# ⚠️ AWS CREDENTIALS — required to provision EC2 instances
# ============================================================
AWS_ACCESS_KEY_ID=AKIAXXXXXXXXXXXXXXXX        # ← from Step 3.2
AWS_SECRET_ACCESS_KEY=wJalrXUxxxxxxxxxxxxxxxxx  # ← from Step 3.2

# ⚠️ Region where instances will be created (must match your key pair region)
AWS_REGION=us-east-1

# ⚠️ Name of your EC2 key pair (just the name, NOT the .pem file path)
AWS_KEY_PAIR_NAME=ml-deploy-key              # ← from Step 4.1

# ============================================================
# EC2 INSTANCE SETTINGS
# ============================================================
# ⚠️ AMI ID for Ubuntu 22.04 LTS — must match AWS_REGION (see Step 4.3)
EC2_AMI_ID=ami-0c7217cdde317cfec

# Instance type (t3.micro = Free Tier eligible)
EC2_INSTANCE_TYPE=t3.micro

# Root disk size in GB (minimum 8, recommended 20)
EC2_VOLUME_SIZE=20

# ============================================================
# SECURITY GROUP
# ============================================================
SECURITY_GROUP_NAME=ml-deployment-sg

# SSH access — replace with your public IP for better security
# Find your IP: curl ifconfig.me
ALLOWED_SSH_IP=0.0.0.0/0

# ============================================================
# APPLICATION SERVER
# ============================================================
APP_PORT=5000
FLASK_ENV=development

# Generate a random secret: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=change-this-to-a-random-string

# ============================================================
# DOCKER PORT MAPPING (for apps you deploy TO EC2)
# ============================================================
# Port your deployed Docker app listens on INSIDE the container
DOCKER_CONTAINER_PORT=8000

# Port exposed on the EC2 host that NGINX proxies to
DOCKER_HOST_PORT=8000

# ============================================================
# DEPLOYMENT BEHAVIOUR
# ============================================================
MAX_DEPLOYMENT_TIME=600
HEALTH_CHECK_INTERVAL=10
HEALTH_CHECK_RETRIES=5

# ============================================================
# GITHUB (optional — only needed for PRIVATE repositories)
# ============================================================
# Generate at https://github.com/settings/tokens (scope: repo)
GITHUB_TOKEN=

# ============================================================
# NGINX (applies to apps deployed ON EC2, not this framework)
# ============================================================
ENABLE_NGINX=true
NGINX_HTTP_PORT=80
NGINX_HTTPS_PORT=443
ENABLE_SSL=false
SSL_EMAIL=

# ============================================================
# LOGGING
# ============================================================
# DEBUG = verbose, INFO = standard, WARNING/ERROR = quiet
LOG_LEVEL=INFO
LOG_FILE=deployment.log
```

---

## 6. Run with Docker Compose (Recommended)

This starts three containers:
- **`autodeploy_postgres`** — PostgreSQL 16 (persistent data volume)
- **`autodeploy_backend`** — Flask + Gunicorn + SocketIO (port 5000)
- **`autodeploy_frontend`** — React/Vite built app served by Nginx (port 80)

### Step 6.1 — Make Sure Docker Desktop is Running

Open Docker Desktop and wait until it shows **"Engine running"**.

### Step 6.2 — Start Everything

```bash
# From the project root directory (ML-Deployment-Platform/)
docker compose up --build
```

First build takes **3–5 minutes** (downloads base images, installs packages).
Subsequent starts take seconds.

**Expected output tail:**
```
autodeploy_postgres   | LOG:  database system is ready to accept connections
autodeploy_backend    | [INFO] Starting gunicorn 21.2.0
autodeploy_backend    | [INFO] Listening at: http://0.0.0.0:5000
autodeploy_frontend   | /docker-entrypoint.sh: Configuration complete; ready for start up
```

### Step 6.3 — Database Migrations

Alembic migrations run **automatically** when the backend container starts.
You do not need to run them manually.

### Step 6.4 — Open the Application

| Service | URL | Description |
|---|---|---|
| **Frontend UI** | <http://localhost> | Main dashboard (port 80) |
| **Backend API** | <http://localhost:5000> | Flask REST API |
| **PostgreSQL** | `localhost:5432` | DB (user: `dbadmin`, pass: `AutoDeploy123`, db: `autodeploy`) |

### Useful Docker Commands

```bash
# Run in background (detached)
docker compose up --build -d

# View live logs
docker compose logs -f

# View logs for one service
docker compose logs -f backend

# Stop all services
docker compose down

# Stop and delete database volume (full reset)
docker compose down -v

# Rebuild only the backend after code changes
docker compose up --build backend
```

---

## 7. Run Locally Without Docker (Alternative)

Use this when you want faster hot-reload during development.

### 7.1 — Backend

```bash
# From project root
python -m venv venv

# Activate
venv\Scripts\activate        # Windows
source venv/bin/activate     # macOS / Linux

# Install Python packages
pip install -r requirements.txt

# Start the backend
python -m backend.app
```

Backend runs at **`http://localhost:5000`**.

> You still need a PostgreSQL instance running and a `DATABASE_URL` in your `.env`:
> ```env
> DATABASE_URL=postgresql://dbadmin:AutoDeploy123@localhost:5432/autodeploy
> ```

### 7.2 — Frontend

```bash
cd frontend
npm install
npm run dev
```

Frontend dev server runs at **`http://localhost:5173`**.

---

## 8. Using the Application

Once the app is running at `http://localhost`:

### First Deployment

1. Click **Deploy** in the sidebar.
2. Enter a **GitHub repository URL** (e.g. `https://github.com/you/your-ml-app`).
3. The repository must contain a `Dockerfile` that builds an image listening
   on `0.0.0.0:8000`.
4. Click **Deploy Application**.
5. Watch real-time logs stream in via WebSocket.
6. When complete, you'll get the **EC2 public IP** to access your deployed app.

### Example Repository

The `example_ml_app/` folder in this repo contains a sample Flask ML app
with a ready-to-use `Dockerfile`. Push it to your GitHub account and deploy it
to test the full pipeline.

---

## 9. Troubleshooting

### Docker Issues

| Problem | Solution |
|---|---|
| `docker compose` command not found | Use `docker-compose` (v1 CLI) or update Docker Desktop |
| `port 80 already in use` | Stop any local web server (nginx, xampp) or change frontend port in `docker-compose.yml` |
| `port 5000 already in use` | On macOS, AirPlay uses 5000. Disable AirPlay Receiver in System Settings → Sharing |
| `port 5432 already in use` | Stop a local PostgreSQL service |
| Backend exits immediately | Check `docker compose logs backend` — likely a missing `.env` value |

### AWS / Deployment Issues

| Problem | Solution |
|---|---|
| `AWS_ACCESS_KEY_ID is required` | `.env` file is missing or not loaded — verify it is in the project root |
| `InvalidClientTokenId` | Access Key ID is wrong or the IAM user was deleted |
| `AuthFailure` (SSH) | `.pem` file is missing from `backend/` or its name doesn't match `AWS_KEY_PAIR_NAME` |
| `AMI not found` | `EC2_AMI_ID` in `.env` does not exist in your `AWS_REGION` — update it per Step 4.3 |
| Instance stuck provisioning | Increase `MAX_DEPLOYMENT_TIME` in `.env` |

### Frontend / API Issues

| Problem | Solution |
|---|---|
| Dashboard shows no data | Check backend is healthy: `curl http://localhost:5000/api/health` |
| WebSocket not connecting | Ensure backend is running; check browser console for errors |
| `npm install` fails | Delete `frontend/node_modules/` and `frontend/package-lock.json`, then retry |

---

## ✅ You're All Set!

| Component | Status |
|---|---|
| PostgreSQL 16 | Running in Docker on port 5432 |
| Flask + Gunicorn backend | Running in Docker on port 5000 |
| React frontend (Nginx) | Running in Docker on port 80 |
| AWS credentials | Configured in `.env` |
| EC2 key pair | `.pem` file in `backend/` |

**Open the app → <http://localhost> — Happy Deploying! 🚀**
