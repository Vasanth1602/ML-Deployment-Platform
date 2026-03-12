"""
JWT Utilities — backend/core/jwt_utils.py
==========================================
Standalone JWT helpers reused by:
  - auth_middleware.py  (@require_auth decorator)
  - auth.py             (login/register endpoints)
  - app.py              (SocketIO connect handler)

Token Payload (standard JWT claims):
  {
    "sub":   "<user_uuid>",   # subject — user id
    "email": "user@...",
    "role":  "user|admin",
    "iat":   <unix_timestamp>,
    "exp":   <unix_timestamp>
  }
"""

import logging
from datetime import datetime, timezone, timedelta

import jwt
from jwt import ExpiredSignatureError, InvalidTokenError

from ..config import config

logger = logging.getLogger(__name__)


def create_access_token(user) -> str:
    """
    Generate a signed JWT for the given User ORM object.
    Returns the encoded token string.
    """
    now = datetime.now(timezone.utc)
    payload = {
        'sub':   str(user.id),
        'email': user.email,
        'role':  user.role,
        'iat':   now,
        'exp':   now + timedelta(hours=config.JWT_EXPIRY_HOURS),
    }
    token = jwt.encode(payload, config.JWT_SECRET_KEY, algorithm='HS256')
    logger.debug('JWT created for user %s (role=%s)', user.email, user.role)
    return token


def verify_access_token(token: str) -> dict:
    """
    Decode and verify a JWT token string.

    Returns:
        dict — the decoded payload (sub, email, role, iat, exp)

    Raises:
        jwt.ExpiredSignatureError  — token is past its exp
        jwt.InvalidTokenError      — signature bad, malformed, etc.
    """
    return jwt.decode(token, config.JWT_SECRET_KEY, algorithms=['HS256'])


def decode_token_unverified(token: str) -> dict:
    """
    Decode token WITHOUT verifying signature or expiry.
    For debugging/logging only — NEVER use for auth decisions.
    """
    return jwt.decode(
        token,
        options={'verify_signature': False},
        algorithms=['HS256'],
    )
