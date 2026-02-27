"""
Alembic Migration Environment
================================
Configured to work with both SQLite (local) and PostgreSQL (production).
The DATABASE_URL env var controls which database is used — same as connection.py.

To generate a new migration:
    alembic revision --autogenerate -m "describe your change"

To apply all pending migrations:
    alembic upgrade head

To roll back one migration:
    alembic downgrade -1
"""

import os
import sys
from logging.config import fileConfig

from sqlalchemy import engine_from_config, pool
from alembic import context

# ── Add project root to Python path so `backend` package is importable ──────
# Point to project root (one level up from alembic/), NOT to backend/.
# PYTHONPATH=/app is also set in Dockerfile.backend as a belt-and-suspenders guard.
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# ── Import all models so Alembic can see the full schema ───────────────────
from backend.database.models import Base   # noqa: E402  (import after sys.path change)

# ── Alembic config object ──────────────────────────────────────────────────
config = context.config

# Interpret the config file for Python logging.
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# ── Tell Alembic which tables to manage (autogenerate reads this) ──────────
target_metadata = Base.metadata

# ── Load .env so DATABASE_URL is always available ──────────────────────────
# Without this, Alembic reads only OS env vars and falls back to SQLite
try:
    from dotenv import load_dotenv
    load_dotenv(os.path.join(os.path.dirname(__file__), '..', '.env'))
except ImportError:
    pass  # dotenv not installed — rely on OS env vars (fine in CI/CD)

# ── Override sqlalchemy.url from environment variable if set ───────────────
# This means you can run `alembic upgrade head` without touching alembic.ini
database_url = os.getenv('DATABASE_URL')
if database_url:
    config.set_main_option('sqlalchemy.url', database_url)


def run_migrations_offline() -> None:
    """
    Run migrations in 'offline' mode (generates SQL without connecting to DB).
    Useful for generating migration scripts to review before applying.
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        # render_as_batch is required for SQLite to support ALTER TABLE
        render_as_batch=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """
    Run migrations in 'online' mode (connects to DB and applies migrations directly).
    This is the normal mode used when you run 'alembic upgrade head'.
    """
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection,
            target_metadata=target_metadata,
            # render_as_batch is required for SQLite to support ALTER TABLE
            render_as_batch=True,
        )

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
