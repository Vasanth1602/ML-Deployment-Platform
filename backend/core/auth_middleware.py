"""
Auth Middleware — backend/core/auth_middleware.py
==================================================
Flask decorators for protecting API endpoints.

Usage:
    from ..core.auth_middleware import require_auth, require_admin

    @app.route('/api/something')
    @require_auth
    def protected_route():
        user = g.current_user   # injected by @require_auth
        ...

    @app.route('/api/admin/something')
    @require_auth
    @require_admin
    def admin_route():
        ...

g.current_user fields:
    g.current_user.id
    g.current_user.email
    g.current_user.role
    g.current_user.is_active
"""

import logging
from functools import wraps

from flask import g, jsonify, request
from jwt import ExpiredSignatureError, InvalidTokenError

from ..core.jwt_utils import verify_access_token
from ..database.connection import db_session
from ..database.models import User

logger = logging.getLogger(__name__)


def require_auth(f):
    """
    Decorator: ensures the request carries a valid JWT Bearer token.
    Injects g.current_user (User ORM object) for use in the route.

    Error responses:
        401 — missing, expired, or invalid token
        401 — user not found or inactive
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        auth_header = request.headers.get('Authorization', '')

        if not auth_header or not auth_header.startswith('Bearer '):
            return jsonify({'success': False, 'error': 'Authorization token required'}), 401

        token = auth_header.split(' ', 1)[1].strip()
        if not token:
            return jsonify({'success': False, 'error': 'Authorization token required'}), 401

        try:
            payload = verify_access_token(token)
        except ExpiredSignatureError:
            logger.debug('Rejected expired JWT')
            return jsonify({'success': False, 'error': 'Token has expired'}), 401
        except InvalidTokenError as e:
            logger.debug('Rejected invalid JWT: %s', e)
            return jsonify({'success': False, 'error': 'Invalid token'}), 401

        # Load user from DB to catch deactivated accounts
        user_id = payload.get('sub')
        db = db_session()
        user = db.query(User).filter_by(id=user_id, is_active=True).first()

        if not user:
            return jsonify({'success': False, 'error': 'User not found or inactive'}), 401

        g.current_user = user
        return f(*args, **kwargs)

    return decorated


def require_admin(f):
    """
    Decorator: ensures g.current_user has role == 'admin'.
    Must be applied AFTER @require_auth.

    Error responses:
        403 — user is authenticated but not an admin
    """
    @wraps(f)
    def decorated(*args, **kwargs):
        user = getattr(g, 'current_user', None)
        if user is None or user.role != 'admin':
            return jsonify({'success': False, 'error': 'Admin access required'}), 403
        return f(*args, **kwargs)

    return decorated
