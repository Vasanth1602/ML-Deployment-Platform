"""
backend package
Exposes socketio so Blueprints can import it cleanly:
    from .. import socketio
"""
from .app import socketio  # noqa: F401
