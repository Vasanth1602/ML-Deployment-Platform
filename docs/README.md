# ML Deployment Platform

> **Note:** This document reflects the **current project state** (manual Docker container setup with AWS Secrets Manager). A login page is planned — the root `README.md` will be updated after that milestone.

---

## What Is This?

**ML Deployment Platform** is a full-stack web application that lets you deploy any ML model (packaged as a Docker container) onto AWS EC2 instances — directly from a browser dashboard. No CLI commands needed for end users.

You paste a GitHub repo URL, choose instance settings, hit **Deploy**, and watch real-time logs as your model spins up on EC2.

---

## Architecture Overview

```
Browser
  │
  ▼
┌─────────────────────────┐      Port 80
│  ml-frontend container  │  ◄─── users connect here
│  (React + Nginx)        │
└────────┬────────────────┘
         │  Nginx proxies /api/* and /socket.io/*
         ▼
┌─────────────────────────┐      Port 5000 (internal)
│  ml-backend container   │
│  (Flask + Gunicorn)     │
│  - REST API             │
│  - SocketIO (real-time) │
│  - SSH via Paramiko     │
└────────┬────────────────┘
         │
         ├──── AWS EC2  (launches your model instances)
         │
         ├──── AWS Secrets Manager  (fetches .pem SSH key at startup)
         │
         └──── PostgreSQL
┌─────────────────────────┐
│  ml-db container        │      Port 5432 (internal)
│  (PostgreSQL 15)        │
└─────────────────────────┘

All 3 containers run on: ml-network  (Docker bridge network)
```

---

## Tech Stack

| Layer         | Technology                             |
|---------------|----------------------------------------|
| Frontend      | React 18 + Vite + TailwindCSS          |
| Served by     | Nginx (inside Docker container)        |
| Backend       | Flask 3 + Flask-SocketIO + Gunicorn    |
| Database      | PostgreSQL 15                          |
| Migrations    | Alembic                                |
| AWS SDK       | boto3                                  |
| SSH           | Paramiko                               |
| PEM Storage   | AWS Secrets Manager                    |

---

## Backend Architecture (Layered)

```
backend/
├── app.py              ← App factory (create_app), Blueprint registration
├── config.py           ← All env-var config (singleton Config class)
├── api/                ← HTTP/SocketIO route handlers (Blueprints)
│   ├── health.py
│   ├── deployments.py
│   ├── applications.py
│   └── instances.py
├── services/           ← Business logic (orchestration layer)
├── providers/          ← External integrations
│   ├── aws/           ← EC2, IAM, security groups
│   ├── docker/        ← Docker commands on EC2
│   ├── github/        ← Repo cloning
│   └── nginx/         ← Nginx config on EC2
├── core/               ← Cross-cutting concerns
│   ├── utils.py       ← SSH client, PEM loader, helpers
│   ├── logging_config.py
│   └── input_validators.py
└── database/
    ├── models.py      ← SQLAlchemy models
    ├── connection.py  ← DB session management
    └── repositories.py
```

**Dependency flow:** `API → Services → Providers → Database`

---

## PEM Key — AWS Secrets Manager Integration

The `.pem` SSH private key is **never stored in the Docker image or repository**.

**How it works:**

1. Store your `.pem` content in AWS Secrets Manager (secret name configured via `PEM_SECRET_NAME` env var)
2. When the backend container starts, the `CMD` in `Dockerfile.backend` runs a Python snippet that:
   - Calls `boto3` → `secretsmanager.get_secret_value(SecretId=PEM_SECRET_NAME)`
   - Writes the key to `/app/ml-deploy-key.pem` with `chmod 600`
3. Flask's `create_app()` also calls `load_pem_from_secrets_manager()` (via `core/utils.py`) for a second-pass validation
4. Paramiko uses `/app/ml-deploy-key.pem` for all SSH connections to EC2 instances

```
AWS Secrets Manager
        │
        │  boto3 at container startup
        ▼
/app/ml-deploy-key.pem  (inside container, mode 600)
        │
        ▼
Paramiko SSH → EC2 instances
```

> **Required AWS IAM permission:** `secretsmanager:GetSecretValue` on the secret ARN.

---

## Frontend Pages

| Route          | Page           | Description                                      |
|----------------|----------------|--------------------------------------------------|
| `/dashboard`   | Dashboard      | Overview stats, recent deployments               |
| `/deploy`      | Deploy         | Launch new deployments (GitHub URL, config)      |
| `/applications`| Applications   | Manage registered applications                   |
| `/instances`   | Instances      | View and manage EC2 instances                    |

Frontend communicates with backend via:
- **REST API** calls to `/api/*` (proxied by Nginx to `ml-backend:5000`)
- **WebSocket** on `/socket.io/` (proxied by Nginx) for real-time deployment logs

---

## Docker Container Setup (Current — Manual)

Three containers are run manually on a shared Docker bridge network (`ml-network`).

> **Deprecated:** The `docker-compose.yml` in the root is the old dev setup. The **current production approach** is manual `docker run` commands as documented in [`SETUP_GUIDE.md`](./SETUP_GUIDE.md).

### Container Summary

| Container      | Image                                     | Network Port |
|----------------|-------------------------------------------|--------------|
| `ml-db`        | `postgres:15`                             | 5432 (host)  |
| `ml-backend`   | `vasanth1602/ml-platform-backend:latest`  | 5000 (host)  |
| `ml-frontend`  | `vasanthdev/ml-deploy-frontend:latest`    | 80 (host)    |

---

## Environment Variables (backend.env)

The backend container loads all config from a `backend.env` file passed via `--env-file`.

| Variable                  | Required | Description                                         |
|---------------------------|----------|-----------------------------------------------------|
| `DATABASE_URL`            | ✅        | PostgreSQL connection string (use `ml-db` hostname) |
| `SECRET_KEY`              | ✅        | Flask session secret key                            |
| `AWS_ACCESS_KEY_ID`       | ✅        | AWS IAM access key                                  |
| `AWS_SECRET_ACCESS_KEY`   | ✅        | AWS IAM secret key                                  |
| `AWS_REGION`              | ✅        | AWS region (e.g. `ap-south-1`)                      |
| `AWS_KEY_PAIR_NAME`       | ✅        | EC2 key pair name                                   |
| `PEM_SECRET_NAME`         | ✅        | AWS Secrets Manager secret name for the `.pem` file |
| `EC2_AMI_ID`              | ✅        | Ubuntu AMI ID for your region                       |
| `EC2_INSTANCE_TYPE`       | ✅        | Default EC2 instance type (e.g. `t3.micro`)         |
| `SECURITY_GROUP_NAME`     | ✅        | EC2 security group name                             |
| `FLASK_ENV`               | ✅        | `production` or `development`                       |

> See [`SETUP_GUIDE.md`](./SETUP_GUIDE.md) for a full annotated `backend.env` template.

---

## Key Files Reference

| File                    | Purpose                                               |
|-------------------------|-------------------------------------------------------|
| `Dockerfile.backend`    | Backend image — fetches PEM from Secrets Manager at start |
| `Dockerfile.frontend`   | Multi-stage: Node build → Nginx serve                 |
| `nginx/frontend.conf`   | Nginx proxy config (API + Socket.IO → ml-backend)     |
| `backend/app.py`        | Flask app factory                                     |
| `backend/config.py`     | All env-var configuration                             |
| `backend/core/utils.py` | SSH client wrapper + `load_pem_from_secrets_manager()`|
| `alembic/`              | Database migration scripts                            |
| `requirements.txt`      | Python dependencies                                   |

---

## Planned Features

- [ ] **Login / Authentication page** ← *In development*
- [ ] Root `README.md` and `SETUP_GUIDE.md` update after login page completion

---

## Docker Images

- **Backend:** `vasanth1602/ml-platform-backend:latest` (Docker Hub)
- **Frontend:** `vasanthdev/ml-deploy-frontend:latest` (Docker Hub)

To rebuild and push after code changes:

```bash
# Backend
docker build -f Dockerfile.backend -t vasanth1602/ml-platform-backend:latest .
docker push vasanth1602/ml-platform-backend:latest

# Frontend
docker build -f Dockerfile.frontend -t vasanthdev/ml-deploy-frontend:latest .
docker push vasanthdev/ml-deploy-frontend:latest
```
