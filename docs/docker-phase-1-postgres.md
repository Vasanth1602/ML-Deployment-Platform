# 🐳 Docker Phase 1 — PostgreSQL Only

> **Revision doc** — covers architecture, docker-compose breakdown, connection flow, all commands used, 3 persistence experiments, and key DevOps concepts learned.

---

## 📌 Objective

Replace SQLite with PostgreSQL running inside a Docker container, while:

- Backend runs **locally** (`python backend/app.py`)
- Frontend runs **locally** (`npm run dev`)
- Only **PostgreSQL is containerized**

**Focus areas:** Docker basics · Port mapping · Volumes & persistence · DB lifecycle

---

## 🏗 Architecture

```
┌─────────────────────────────────┐
│         Your Machine            │
│                                 │
│  Frontend (Vite/React)          │
│  http://localhost:5173          │
│              │                  │
│              ▼                  │
│  Backend (Flask)                │
│  http://localhost:5000          │
│              │ DATABASE_URL     │
│              ▼                  │
│  localhost:5432  ◄──────────────┼── Docker exposes this port
│              │                  │
└──────────────┼──────────────────┘
               │
    ┌──────────▼──────────┐
    │  Docker Container   │
    │  autodeploy_postgres│
    │                     │
    │  PostgreSQL 16      │
    │  port: 5432         │
    │       │             │
    │       ▼             │
    │  Docker Volume      │
    │  postgres_data      │
    │  (persistent disk)  │
    └─────────────────────┘
```

**Key insight:** `localhost` works in Phase 1 because Docker exposes port 5432 directly to your machine. The backend has no idea it's talking to Docker — it just sees a Postgres server at localhost:5432.

---

## 📦 docker-compose.yml

```yaml
services:
  postgres:
    image: postgres:16-alpine          # Official image, Alpine = lightweight
    container_name: autodeploy_postgres
    restart: unless-stopped            # Auto-restarts if Docker restarts

    environment:
      POSTGRES_USER: dbadmin           # DB username (you choose)
      POSTGRES_PASSWORD: AutoDeploy123 # DB password (you choose)
      POSTGRES_DB: autodeploy          # Database name created on startup

    ports:
      - "5432:5432"                    # HOST:CONTAINER port mapping

    volumes:
      - postgres_data:/var/lib/postgresql/data  # Named volume for persistence

    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U dbadmin -d autodeploy"]
      interval: 10s
      timeout: 5s
      retries: 5

volumes:
  postgres_data:
    driver: local
```

---

## 🔎 docker-compose.yml Explained Line by Line

### `image: postgres:16-alpine`
- Pulls the official PostgreSQL 16 image from Docker Hub
- `alpine` variant = ~50MB instead of ~300MB (no Ubuntu overhead)
- On first `docker compose up`, Docker downloads this image once and caches it

### `container_name: autodeploy_postgres`
- Names the container so you can refer to it by name instead of container ID
- Used in: `docker exec -it autodeploy_postgres sh`

### `restart: unless-stopped`
| Value | Behaviour |
|-------|-----------|
| `no` | Never restarts |
| `always` | Restarts always, even after `docker stop` |
| `unless-stopped` | Restarts automatically **unless** you explicitly `docker stop` it |
| `on-failure` | Only restarts on crash |

`unless-stopped` is the right choice for a database — it recovers from crashes but respects your intentional stops.

### `environment` block
These variables are **only used on first initialization** (when the volume is empty):
- `POSTGRES_USER` → creates the DB superuser
- `POSTGRES_PASSWORD` → sets the password for that user
- `POSTGRES_DB` → creates an initial database

If the volume already has data, these are **ignored** — PostgreSQL reuses the existing cluster.

### `ports: "5432:5432"`
```
"HOST_PORT:CONTAINER_PORT"
  5432    :    5432
```
- Container-internal port 5432 → exposed on your machine as localhost:5432
- This is why `DATABASE_URL=postgresql://...@localhost:5432/...` works

### `volumes: postgres_data:/var/lib/postgresql/data`
```
/var/lib/postgresql/data   ← inside the container
        │                    this is where PostgreSQL stores EVERYTHING:
        │                    tables, indexes, WAL logs, configs
        ▼
postgres_data              ← Docker-managed volume on your disk
                             survives: container restarts, container removal
                             lost only: docker volume rm
```

### `healthcheck`
- Runs `pg_isready` every 10 seconds to confirm PostgreSQL is accepting connections
- Container shows `Up (healthy)` vs `Up (health: starting)` in `docker ps`
- Useful in Phase 2+ so the backend waits for the DB to be truly ready

---

## 🔌 .env Connection String

```bash
# Phase 1: PostgreSQL in Docker, backend local
DATABASE_URL=postgresql://dbadmin:AutoDeploy123@localhost:5432/autodeploy
#                         USERNAME  PASSWORD     HOST      PORT  DB_NAME

# Fallback: switch back to SQLite anytime by swapping this line
# DATABASE_URL=sqlite:///./deployment_platform.db
```

---

## 🚀 Commands Used in Phase 1

### Starting & checking

```bash
# Start PostgreSQL container in background
docker compose up -d

# Check it's running + healthy
docker ps

# View container logs (useful if it fails to start)
docker logs autodeploy_postgres

# Stop container (data kept)
docker compose stop

# Stop + remove container (data kept in volume)
docker compose down
```

### Install Python driver + migrate

```bash
# Install PostgreSQL driver for Python
pip install psycopg2-binary==2.9.9

# Create all tables on PostgreSQL (Alembic reads DATABASE_URL from .env)
alembic upgrade head

# Verify connection + tables
python tests/db/phase1_docker_verify.py
```

### Entering the container (direct DB access)

```bash
# Open a shell inside the running container
docker exec -it autodeploy_postgres sh

# Inside container: open PostgreSQL CLI
psql -U dbadmin -d autodeploy

# Useful psql commands:
\dt                              -- list all tables
\d deployments                   -- describe a table (columns, types)
SELECT * FROM tenants;
SELECT COUNT(*) FROM deployment_logs;
SELECT status, COUNT(*) FROM deployments GROUP BY status;

# Exit psql, then container
\q
exit
```

---

## 🧪 Experiment 1 — Restart Container (Data Survives)

**Question:** Does data survive a container restart?

```bash
# Check current data
docker exec -it autodeploy_postgres psql -U dbadmin -d autodeploy \
  -c "SELECT COUNT(*) FROM deployments;"

# Stop container
docker stop autodeploy_postgres

# Start it again
docker start autodeploy_postgres

# Check data again
docker exec -it autodeploy_postgres psql -U dbadmin -d autodeploy \
  -c "SELECT COUNT(*) FROM deployments;"
```

**Result: ✅ Data survived** — volume kept the data intact.

---

## 🧪 Experiment 2 — Remove Container, Keep Volume (Data Survives)

**Question:** Does data survive deleting the container itself?

```bash
# Stop and REMOVE the container entirely
docker stop autodeploy_postgres
docker rm autodeploy_postgres

# Confirm container is gone
docker ps -a   # should not show autodeploy_postgres

# Confirm the volume still exists
docker volume ls   # should show: automated_framework_postgres_data

# Recreate container from compose (reads same volume)
docker compose up -d

# Data still there?
docker exec -it autodeploy_postgres psql -U dbadmin -d autodeploy \
  -c "SELECT COUNT(*) FROM deployments;"
```

**Result: ✅ Data survived** — the container was gone but the volume persisted.

**Why:** The container is just a process. The volume is disk storage. They are separate things.

---

## 🧨 Experiment 3 — Remove Volume (Intentional Data Loss)

**Question:** What actually causes data loss?

```bash
# Stop and remove container
docker stop autodeploy_postgres
docker rm autodeploy_postgres

# Remove the volume itself
docker volume rm automated_framework_postgres_data

# Recreate container (gets a fresh empty volume)
docker compose up -d

# Check tables
docker exec -it autodeploy_postgres psql -U dbadmin -d autodeploy -c "\dt"
```

**Result:**
```
Did not find any relations.
```

**Data is gone.** The volume was the disk. Removing the volume = formatting the disk.

```bash
# Recover: re-run migrations to restore schema (data cannot be recovered)
alembic upgrade head
```

---

## 📊 Persistence Summary

| Action | Data Survives? | Why |
|--------|---------------|-----|
| `docker compose stop` | ✅ Yes | Container paused, volume untouched |
| `docker compose restart` | ✅ Yes | Container restarted, volume untouched |
| `docker stop` + `docker start` | ✅ Yes | Same as above |
| `docker rm` (remove container) | ✅ Yes | Container deleted, volume is separate |
| `docker pull` new image version | ✅ Yes | Image ≠ volume |
| `docker volume rm` | ❌ **No** | Volume deleted = data deleted |
| `docker compose down -v` | ❌ **No** | `-v` flag removes volumes too |

> ⚠️ **The dangerous command is `docker compose down -v`** — the `-v` flag silently removes volumes. Never use `-v` unless you intentionally want to wipe the database.

---

## 🧠 Core DevOps Concepts Learned

### 1. Containers Are Stateless
A container is just a **running process**. When you delete it, you delete the process — not the data. This is intentional: containers should be replaceable, upgradeable, and disposable.

### 2. Volumes Are Stateful
A volume is **persistent disk storage** managed by Docker. It exists independently of any container. This is why databases need volumes — they are stateful by nature.

### 3. Port Mapping = The Bridge
```
Your machine (localhost:5432)  ←─── docker -p 5432:5432 ───→  Container (port 5432)
```
Without the `ports` entry, the container is completely isolated — nothing outside can connect to it.

### 4. Why `localhost` Works in Phase 1
Because Docker maps the container port directly to your machine's localhost. In **Phase 2**, when backend also moves into Docker, `localhost` stops working — you use the **service name** (`postgres`) instead. This is the most important concept to understand before Phase 2.

### 5. DB Initialized Only Once
PostgreSQL reads `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB` **only when the volume is empty**. After that, it uses whatever is stored in the volume. This means:
- Changing the env vars has **no effect** on an existing volume
- To change credentials, you must remove the volume and recreate

### 6. Separation of Compute and Storage
This phase demonstrates a production principle:
- **Compute** (the database process) = disposable, replaceable
- **Storage** (the volume / RDS) = permanent, backed up, independent

This is why in Phase 4, the database moves to RDS — where AWS manages the storage separately from any EC2 instance.

---

## ✅ Phase 1 Completion Checklist

- [x] PostgreSQL running in Docker (`docker compose up -d`)
- [x] Backend connected successfully (`DATABASE_URL` in `.env`)
- [x] PostgreSQL driver installed (`psycopg2-binary`)
- [x] Alembic running against PostgreSQL (not SQLite)
- [x] Migrations executed (`alembic upgrade head` → `PostgresqlImpl`)
- [x] All tables verified on PostgreSQL
- [x] Write/read test passed
- [x] Restart experiment completed
- [x] Container removal experiment completed
- [x] Volume deletion experiment completed
- [x] Data behavior fully understood

---

## 🔜 What Changes in Phase 2

In **Docker Phase 2**, the Flask backend also moves into Docker:

```
# Phase 1 (current)          # Phase 2 (next)
Backend = local Python        Backend = Docker container
DB = Docker                   DB = Docker
                              ↓
localhost:5432 works          localhost STOPS working
                              Use service name "postgres" instead
```

The `DATABASE_URL` will change from:
```bash
postgresql://dbadmin:...@localhost:5432/autodeploy      # Phase 1
postgresql://dbadmin:...@postgres:5432/autodeploy       # Phase 2 (service name)
```
