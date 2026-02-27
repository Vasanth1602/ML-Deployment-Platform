"""
Database Connection
====================
Handles engine creation and session management for both:
  - SQLite   (local development — zero config)
  - PostgreSQL (AWS RDS — production)

The DATABASE_URL environment variable controls which is used:
  export DATABASE_URL=sqlite:///./deployment_platform.db     # local
  export DATABASE_URL=postgresql://user:pass@host/dbname     # production

Session usage:
  db = SessionLocal()           # get a session
  try:
      ...                       # use db.query(), db.add(), db.commit()
  finally:
      db.close()                # always close

Or as a Flask dependency:
  @app.route('/...')
  def my_route():
      db = SessionLocal()
      try:
          ...
      finally:
          db.close()
"""

import os
import logging

from sqlalchemy import create_engine, event, text
from sqlalchemy.orm import sessionmaker, scoped_session

from .models import Base

logger = logging.getLogger(__name__)

# ── Database URL ──────────────────────────────────────────────────────────────
# IMPORTANT: use __file__-relative path so the same DB is opened regardless
# of which directory the process is started from.
# Flask is run from backend/ but Alembic from the project root — both
# resolve to <project_root>/deployment_platform.db this way.
_PROJECT_ROOT = os.path.abspath(
    os.path.join(os.path.dirname(__file__), '..', '..')   # backend/database/ -> project root
)
_DEFAULT_SQLITE_PATH = os.path.join(_PROJECT_ROOT, 'deployment_platform.db')

DATABASE_URL = os.getenv(
    'DATABASE_URL',
    f'sqlite:///{_DEFAULT_SQLITE_PATH}'   # absolute path — CWD-independent
)

# ── SQLite-specific: enable foreign key enforcement ───────────────────────────
# SQLite has foreign keys OFF by default. This turns them on per connection.
def _enable_sqlite_fk(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute('PRAGMA foreign_keys=ON')
    cursor.close()


# ── Engine creation ───────────────────────────────────────────────────────────
def _create_engine():
    if DATABASE_URL.startswith('sqlite'):
        engine = create_engine(
            DATABASE_URL,
            connect_args={'check_same_thread': False},  # required for Flask multi-threading
            echo=False,         # set True to log all SQL (noisy but useful for debugging)
        )
        event.listen(engine, 'connect', _enable_sqlite_fk)
        logger.info('Using SQLite database: %s', DATABASE_URL)
    else:
        engine = create_engine(
            DATABASE_URL,
            pool_size=20,           # max connections in pool
            max_overflow=40,        # extra connections above pool_size
            pool_pre_ping=True,     # verify connection health before use
            pool_recycle=3600,      # recycle connections every hour (avoid stale connections)
            echo=False,
        )
        logger.info('Using PostgreSQL database')
    return engine


engine = _create_engine()

# ── Session factory ───────────────────────────────────────────────────────────
# sessionmaker = factory that creates new Session objects
# scoped_session = thread-safe wrapper (one session per thread)
SessionLocal = sessionmaker(
    autocommit=False,   # must call db.commit() manually — important for transaction control
    autoflush=False,    # must call db.flush() manually  — gives control over when SQL is sent
    bind=engine,
)
db_session = scoped_session(SessionLocal)


# ── Public API ────────────────────────────────────────────────────────────────
def init_db():
    """
    Create all tables if they don't already exist.
    Safe to call multiple times — it's idempotent (won't drop/recreate existing tables).

    Call this once at Flask app startup:
        with app.app_context():
            init_db()
    """
    Base.metadata.create_all(bind=engine)
    logger.info('[OK] Database initialized: %s', DATABASE_URL.split('@')[-1])  # hide credentials
    print(f'[OK] Database initialized ({_db_label()})')


def _db_label():
    """Return a safe, human-readable label for the current database."""
    if DATABASE_URL.startswith('sqlite'):
        return DATABASE_URL
    host = DATABASE_URL.split('@')[-1].split('/')[0] if '@' in DATABASE_URL else 'PostgreSQL'
    return f'PostgreSQL @ {host}'


def get_db():
    """
    Generator that yields a database session and ensures it's closed after use.

    Usage:
        db = next(get_db())
        try:
            ...
        finally:
            db.close()

    Or with a context manager pattern:
        for db in get_db():
            ...
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def check_db_connection() -> bool:
    """
    Test that the database is reachable.
    Returns True if connected, False if not.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text('SELECT 1'))
        return True
    except Exception as e:
        logger.error('Database connection check failed: %s', e)
        return False
