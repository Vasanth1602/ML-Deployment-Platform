# Setup Guide — ML Deployment Platform

> **Scope:** This guide covers deploying the platform using **manual `docker run` commands** — the current production approach.  
> A login page is in development. Both docs will move to the root after that milestone.

---

## Prerequisites

Before you start, make sure the following are ready:

| Requirement             | Check                                                   |
|-------------------------|---------------------------------------------------------|
| Docker installed        | `docker --version`                                      |
| Docker Hub access       | `docker login`                                          |
| AWS account             | IAM user with EC2 + Secrets Manager permissions         |
| EC2 Key Pair created    | EC2 Console → Key Pairs → note the name                 |
| .pem file in AWS        | Stored in AWS Secrets Manager (see section below)       |

---

## 1. Store Your .pem Key in AWS Secrets Manager

This is required before running the backend container. The backend fetches it automatically at startup.

### Steps

1. Open [AWS Secrets Manager Console](https://console.aws.amazon.com/secretsmanager)
2. Click **Store a new secret**
3. Choose **Other type of secret** → **Plaintext**
4. Paste the full content of your `.pem` file (including `-----BEGIN RSA PRIVATE KEY-----` headers)
5. Give it a name, e.g. `ml-deploy-pem-key`
6. Click through and save

**Note the secret name** — you will use it as `PEM_SECRET_NAME` in `backend.env`.

### Required IAM Permission

Your IAM user (whose credentials go in `backend.env`) must have this policy:

```json
{
  "Effect": "Allow",
  "Action": "secretsmanager:GetSecretValue",
  "Resource": "arn:aws:secretsmanager:<REGION>:<ACCOUNT_ID>:secret:ml-deploy-pem-key*"
}
```

---

## 2. Prepare `backend.env`

Create a file named `backend.env` in any directory on your host machine. **Do not commit this file to Git.**

```env
# ── Database ────────────────────────────────────────────
# IMPORTANT: Use container name "ml-db" as hostname, NOT localhost
DATABASE_URL=postgresql://postgres:postgres@ml-db:5432/ml_platform

# ── Flask ───────────────────────────────────────────────
FLASK_ENV=production
SECRET_KEY=your-random-secret-key-here

# ── AWS Credentials (IAM user) ──────────────────────────
AWS_ACCESS_KEY_ID=AKIAxxxxxxxxxxxxxxxxxxx
AWS_SECRET_ACCESS_KEY=your-secret-access-key-here
AWS_REGION=ap-south-1

# ── AWS Secrets Manager ─────────────────────────────────
# Name of the secret that contains your .pem file content
PEM_SECRET_NAME=ml-deploy-pem-key

# ── EC2 Configuration ───────────────────────────────────
AWS_KEY_PAIR_NAME=ml-deploy-key
EC2_AMI_ID=ami-0197xxxxxxxxxxxx
EC2_INSTANCE_TYPE=t3.micro

# ── Security Group ──────────────────────────────────────
SECURITY_GROUP_NAME=ml-deployment-sg
```

> **Tip:** Generate a secure SECRET_KEY with:
> ```bash
> python -c "import secrets; print(secrets.token_hex(32))"
> ```

---

## 3. Create Docker Network

All three containers communicate by **container name** over a shared Docker bridge network. This must be created first.

```bash
docker network create ml-network
```

Verify:

```bash
docker network ls
# You should see ml-network in the list
```

---

## 4. Run PostgreSQL Container

```bash
docker run -d \
  --name ml-db \
  --network ml-network \
  -e POSTGRES_DB=ml_platform \
  -e POSTGRES_USER=postgres \
  -e POSTGRES_PASSWORD=postgres \
  -p 5432:5432 \
  postgres:15
```

**What this does:**
- Creates a PostgreSQL 15 container named `ml-db`
- Joins it to `ml-network` so the backend can reach it as `ml-db:5432`
- Exposes port 5432 on the host (optional — useful for pgAdmin / psql debugging)
- Creates database `ml_platform` with user `postgres`

Verify it's running:

```bash
docker ps
# ml-db should show Status: Up
```

---

## 5. Run Backend Container

```bash
docker run -d \
  --name ml-backend \
  --network ml-network \
  --restart unless-stopped \
  -p 5000:5000 \
  --env-file backend.env \
  vasanth1602/ml-platform-backend:latest
```

**What happens at startup (automatically):**

1. **PEM fetch** — `boto3` calls AWS Secrets Manager using `PEM_SECRET_NAME`, writes the key to `/app/ml-deploy-key.pem` with `chmod 600`
2. **DB migrations** — Alembic runs `alembic upgrade head` (creates all tables)
3. **Gunicorn starts** — Flask app served on port 5000

> ⚠️ **`--env-file` path must be relative or absolute to where you run the command.**  
> If `backend.env` is in your current directory, `--env-file backend.env` works.

Verify the backend started correctly:

```bash
docker logs ml-backend
# Look for:
# [OK] PEM key fetched from Secrets Manager → /app/ml-deploy-key.pem
# [OK] Default tenant found/created
# [INFO] Flask app created — blueprints registered
```

Check health endpoint:

```bash
curl http://localhost:5000/api/health
# Expected: {"status": "healthy", ...}
```

---

## 6. Run Frontend Container

```bash
docker run -d \
  --name ml-frontend \
  --network ml-network \
  -p 80:80 \
  vasanthdev/ml-deploy-frontend:latest
```

**What this does:**
- Serves the React SPA via Nginx on port 80
- Nginx proxies `/api/*` → `http://ml-backend:5000` (backend container by name)
- Nginx proxies `/socket.io/*` → `http://ml-backend:5000/socket.io/` (WebSocket for real-time logs)

---

## 7. Verify Everything Is Running

```bash
docker ps
```

Expected output:

```
CONTAINER ID  IMAGE                                        STATUS   NAMES
xxxxxxxxxxxx  vasanthdev/ml-deploy-frontend:latest         Up       ml-frontend
xxxxxxxxxxxx  vasanth1602/ml-platform-backend:latest       Up       ml-backend
xxxxxxxxxxxx  postgres:15                                  Up       ml-db
```

Open your browser:

```
http://localhost
```

You should see the ML Deployment Platform dashboard.

---

## 8. Container Communication Flow

```
Browser → http://localhost (port 80)
    │
    ▼
ml-frontend (Nginx, port 80)
    │
    ├── /api/*       → http://ml-backend:5000/api/*
    └── /socket.io/  → http://ml-backend:5000/socket.io/
                              │
                              ├── AWS EC2 (deploys ML models)
                              ├── AWS Secrets Manager (PEM key)
                              └── ml-db:5432 (PostgreSQL)
```

The `ml-network` Docker bridge lets containers reach each other by **container name** as hostname.

---

## Useful Commands

### View Logs

```bash
docker logs ml-backend          # Backend logs
docker logs -f ml-backend       # Follow backend logs (live)
docker logs ml-frontend         # Nginx logs
docker logs ml-db               # PostgreSQL logs
```

### Restart a Container

```bash
docker restart ml-backend
```

### Stop and Remove All Containers

```bash
docker stop ml-frontend ml-backend ml-db
docker rm ml-frontend ml-backend ml-db
```

### Remove the Network (after removing containers)

```bash
docker network rm ml-network
```

### Connect to PostgreSQL Directly

```bash
docker exec -it ml-db psql -U postgres -d ml_platform
```

---

## Updating to a New Image Version

```bash
# Pull latest image
docker pull vasanth1602/ml-platform-backend:latest

# Stop and remove old container
docker stop ml-backend && docker rm ml-backend

# Run new container (same command as Step 5)
docker run -d \
  --name ml-backend \
  --network ml-network \
  --restart unless-stopped \
  -p 5000:5000 \
  --env-file backend.env \
  vasanth1602/ml-platform-backend:latest
```

---

## Rebuilding Images from Source

```bash
# Build backend (from project root)
docker build -f Dockerfile.backend -t vasanth1602/ml-platform-backend:latest .

# Build frontend (from project root)
docker build -f Dockerfile.frontend -t vasanthdev/ml-deploy-frontend:latest .

# Push to Docker Hub
docker push vasanth1602/ml-platform-backend:latest
docker push vasanthdev/ml-deploy-frontend:latest
```

---

## Troubleshooting

### Backend fails to start — PEM fetch error

```
[PEM] Failed to fetch PEM from Secrets Manager: ...
```

**Checks:**
1. `PEM_SECRET_NAME` in `backend.env` matches the exact secret name in AWS
2. `AWS_ACCESS_KEY_ID` / `AWS_SECRET_ACCESS_KEY` are correct
3. `AWS_REGION` matches the region where the secret is stored
4. IAM user has `secretsmanager:GetSecretValue` permission

### Backend can't connect to database

```
sqlalchemy.exc.OperationalError: could not translate host name "ml-db"
```

**Cause:** Backend container is not on `ml-network`, or `ml-db` container is not running.

**Fix:**
```bash
docker network inspect ml-network
# Check that both ml-backend and ml-db are listed under "Containers"
```

### Frontend shows blank page / API errors

1. Check `docker logs ml-frontend` for Nginx errors
2. Check `docker logs ml-backend` for Flask errors
3. Make sure `ml-backend` is healthy: `curl http://localhost:5000/api/health`
4. Verify Nginx config is proxying to `ml-backend:5000` using container name

### Port already in use

```bash
# Find what's using port 80 or 5000
netstat -ano | findstr :80    # Windows
lsof -i :80                   # Linux/Mac
```

---

## Security Notes

- `backend.env` contains sensitive credentials — **never commit to Git**. It is listed in `.gitignore`.
- The `.pem` key is never stored in the Docker image. It is fetched at runtime from AWS Secrets Manager.
- In production, restrict `ALLOWED_SSH_IP` in your security group config to your known IP rather than `0.0.0.0/0`.
- Use a strong, randomly generated `SECRET_KEY` for Flask sessions.
