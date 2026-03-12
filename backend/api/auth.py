"""
Auth API — backend/api/auth.py
==============================
Authentication endpoints.

Routes:
    POST /api/auth/register  — create account, return token
    POST /api/auth/login     — validate credentials, return token
    POST /api/auth/logout    — stateless JWT logout (client clears token)
    GET  /api/auth/me        — return current user info

Rate limits (Flask-Limiter):
    login    — 5 per minute
    register — 3 per minute
"""

import logging
import re

from flask import Blueprint, jsonify, request, g
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

from ..database.connection import db_session
from ..services.auth_service import register_user, login_user
from ..core.auth_middleware import require_auth

logger = logging.getLogger(__name__)

auth_bp = Blueprint('auth', __name__, url_prefix='/api/auth')

# Limiter — rate-limit auth endpoints to prevent brute force
limiter = Limiter(key_func=get_remote_address)


# ─── Validators ──────────────────────────────────────────────────────────────

_EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')


def _validate_register_input(data: dict):
    """Returns (email, password) or raises ValueError with a human-readable message."""
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not email:
        raise ValueError("Email is required")
    if not _EMAIL_RE.match(email):
        raise ValueError("Invalid email format")
    if not password:
        raise ValueError("Password is required")
    if len(password) < 8:
        raise ValueError("Password must be at least 8 characters")

    return email, password


def _validate_login_input(data: dict):
    """Returns (email, password) or raises ValueError."""
    email = (data.get('email') or '').strip()
    password = data.get('password') or ''

    if not email or not password:
        raise ValueError("Email and password are required")

    return email, password


# ─── Endpoints ───────────────────────────────────────────────────────────────

@auth_bp.route('/register', methods=['POST'])
@limiter.limit("3 per minute")
def register():
    """
    POST /api/auth/register
    Body: { "email": "...", "password": "..." }
    Returns: { "token": "...", "user": { id, email, role } }
    """
    data = request.get_json(silent=True) or {}

    try:
        email, password = _validate_register_input(data)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    db = db_session()
    try:
        user, token = register_user(db, email, password)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400
    except Exception as e:
        logger.error('Register error: %s', e)
        return jsonify({'success': False, 'error': 'Registration failed'}), 500

    return jsonify({
        'success': True,
        'token': token,
        'user': user.to_dict(),
    }), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    """
    POST /api/auth/login
    Body: { "email": "...", "password": "..." }
    Returns: { "token": "...", "user": { id, email, role } }
    """
    data = request.get_json(silent=True) or {}

    try:
        email, password = _validate_login_input(data)
    except ValueError as e:
        return jsonify({'success': False, 'error': str(e)}), 400

    db = db_session()
    try:
        user, token = login_user(db, email, password)
    except ValueError as e:
        # Always returns generic "Invalid email or password" (no enumeration)
        return jsonify({'success': False, 'error': str(e)}), 401
    except Exception as e:
        logger.error('Login error: %s', e)
        return jsonify({'success': False, 'error': 'Login failed'}), 500

    return jsonify({
        'success': True,
        'token': token,
        'user': user.to_dict(),
    })


@auth_bp.route('/logout', methods=['POST'])
@require_auth
def logout():
    """
    POST /api/auth/logout
    JWT is stateless — server doesn't store tokens.
    The client is responsible for deleting the token from localStorage.
    This endpoint exists so the frontend can call a clear logout action
    and to allow future blocklist implementation.
    """
    return jsonify({'success': True, 'message': 'Logged out successfully'})


@auth_bp.route('/me', methods=['GET'])
@require_auth
def me():
    """
    GET /api/auth/me
    Returns current authenticated user's info.
    Used by frontend AuthContext on page reload (token rehydration).
    """
    return jsonify({'success': True, 'user': g.current_user.to_dict()})
