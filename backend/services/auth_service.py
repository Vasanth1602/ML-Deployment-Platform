"""
Auth Service — backend/services/auth_service.py
================================================
Business logic for user registration and login.
Responsible for:
  - Password strength validation
  - bcrypt hashing
  - User creation
  - Credential verification

NOTE: No email verification in this version.
      Future work: add email_verified column + SendGrid/SES integration.
"""

import logging
import re
from datetime import datetime, timezone
from typing import Optional, Tuple

import bcrypt
from sqlalchemy.orm import Session

from ..database.models import User
from ..core.jwt_utils import create_access_token
from ..config import config

logger = logging.getLogger(__name__)

# ─── Constants ───────────────────────────────────────────────────────────────
_PASSWORD_MIN_LEN = 8
_GENERIC_LOGIN_ERROR = "Invalid email or password"   # Never reveal which field is wrong

# Common special characters (avoid complex escaping by listing them explicitly)
_SPECIAL_CHARS = set("!@#$%^&*(),.?;:{}<>_-+=[]\\/'`~|\"")


# ─── Password ────────────────────────────────────────────────────────────────

def validate_password_strength(password: str) -> Optional[str]:
    """
    Returns an error message string if password is too weak, else None.
    Rules: 8+ chars, 1 uppercase, 1 digit, 1 special character.
    """
    if len(password) < _PASSWORD_MIN_LEN:
        return f"Password must be at least {_PASSWORD_MIN_LEN} characters"
    if not re.search(r'[A-Z]', password):
        return "Password must contain at least one uppercase letter"
    if not re.search(r'\d', password):
        return "Password must contain at least one number"
    if not any(ch in _SPECIAL_CHARS for ch in password):
        return "Password must contain at least one special character"
    return None


def _hash_password(password: str) -> str:
    """Hash a plaintext password with bcrypt."""
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')


def _check_password(password: str, password_hash: str) -> bool:
    """Verify a plaintext password against a bcrypt hash."""
    return bcrypt.checkpw(password.encode('utf-8'), password_hash.encode('utf-8'))


# ─── Register ────────────────────────────────────────────────────────────────

def register_user(db: Session, email: str, password: str) -> Tuple[User, str]:
    """
    Create a new user account.

    Returns:
        (user, token) tuple on success.

    Raises:
        ValueError — email already taken or password too weak.
    """
    email = email.strip().lower()

    # Validate password strength before any DB work
    strength_error = validate_password_strength(password)
    if strength_error:
        raise ValueError(strength_error)

    # Check email uniqueness
    existing = db.query(User).filter_by(email=email).first()
    if existing:
        raise ValueError("An account with this email already exists")

    user = User(
        email=email,
        password_hash=_hash_password(password),
        role='user',
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user)
    logger.info('User registered: %s (id=%s)', email, str(user.id)[:8])
    return user, token


# ─── Bootstrap Admin ────────────────────────────────────────────────────────

def bootstrap_admin() -> None:
    """
    Idempotent first-admin bootstrap.

    Reads ADMIN_EMAIL and ADMIN_PASSWORD from the environment.
    If no admin user exists yet, creates one — then wipes the plaintext
    password from the process environment so it does not linger in memory.

    Safe to run on every startup:
      - If either env var is missing → silently skips.
      - If an admin already exists   → silently skips.
      - On success                   → logs at INFO, clears ADMIN_PASSWORD.

    AWS Secrets Manager note:
      Store the secret as JSON  { "ADMIN_EMAIL": "...", "ADMIN_PASSWORD": "..." }
      so the $ characters inside a bcrypt hash can never corrupt the value
      through shell variable-substitution.
    """
    import os
    from ..database.connection import SessionLocal

    admin_email    = config.ADMIN_EMAIL.strip().lower()
    admin_password = config.ADMIN_PASSWORD

    if not admin_email or not admin_password:
        logger.debug('bootstrap_admin: ADMIN_EMAIL/ADMIN_PASSWORD not set — skipping')
        return

    db = SessionLocal()
    try:
        # Already have at least one admin? Nothing to do.
        existing_admin = db.query(User).filter_by(role='admin').first()
        if existing_admin:
            logger.debug('bootstrap_admin: admin already exists (%s) — skipping', existing_admin.email)
            return

        # Also skip if this exact email already exists (any role).
        existing_user = db.query(User).filter_by(email=admin_email).first()
        if existing_user:
            logger.warning(
                'bootstrap_admin: %s already registered as role=%s — skipping',
                admin_email, existing_user.role,
            )
            return

        # Hash the plaintext password — bcrypt rounds=12 (same as register_user).
        salt          = bcrypt.gensalt(rounds=12)
        password_hash = bcrypt.hashpw(admin_password.encode('utf-8'), salt).decode('utf-8')

        admin = User(
            email=admin_email,
            password_hash=password_hash,
            role='admin',
            is_active=True,
        )
        db.add(admin)
        db.commit()

        logger.info(
            '[bootstrap] Admin account created: %s',
            admin_email,
        )
    except Exception as exc:
        db.rollback()
        logger.error('bootstrap_admin: failed to create admin — %s', exc)
        raise
    finally:
        # ── Wipe plaintext password from env immediately ───────────────────
        # It is no longer needed; keeping it in memory is unnecessary risk.
        os.environ.pop('ADMIN_PASSWORD', None)
        admin_password = None  # noqa: F841  (explicit local wipe)
        db.close()


# ─── Login ───────────────────────────────────────────────────────────────────

def login_user(db: Session, email: str, password: str) -> Tuple[User, str]:
    """
    Authenticate a user and issue a JWT.

    SECURITY: Always returns the same error message regardless of whether
    the email exists or the password is wrong (prevents user enumeration).

    Returns:
        (user, token) tuple on success.

    Raises:
        ValueError — invalid credentials (generic message).
    """
    email = email.strip().lower()

    user = db.query(User).filter_by(email=email).first()

    # Always run checkpw even if user not found — prevents timing attacks
    if user is None:
        bcrypt.checkpw(b'dummy', bcrypt.hashpw(b'dummy', bcrypt.gensalt()))
        raise ValueError(_GENERIC_LOGIN_ERROR)

    if not _check_password(password, user.password_hash):
        raise ValueError(_GENERIC_LOGIN_ERROR)

    if not user.is_active:
        raise ValueError(_GENERIC_LOGIN_ERROR)

    # Update last_login timestamp
    user.last_login = datetime.now(timezone.utc)
    db.commit()
    db.refresh(user)

    token = create_access_token(user)
    logger.info('User logged in: %s (id=%s)', email, str(user.id)[:8])
    return user, token
