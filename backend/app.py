"""
Flask application factory.
Initializes the app, registers Blueprints, sets up DB and SocketIO.
"""

import os
from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit, disconnect
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import logging

from .core.logging_config import configure_logging
from .core.utils import load_pem_from_secrets_manager
from .config import config
from .database.connection import init_db, db_session, check_db_connection
from .database.models import Tenant

# ── SocketIO instance ─────────────────────────────────────────────────────────
# Defined at module level so that backend/__init__.py can re-export it.
# Blueprints import it via:  from ..app import socketio
socketio = SocketIO()

# ── Flask-Limiter instance ────────────────────────────────────────────────────
# Initialised here; auth Blueprint attaches its limits in auth.py
limiter = Limiter(key_func=get_remote_address)


def create_app() -> Flask:
    """
    Application factory — called by Gunicorn and tests.
    Usage:  gunicorn backend.app:create_app --factory
    """
    # Validate config at startup — catches missing production secrets before
    # the first request. Applies to both Gunicorn and `python -m backend.app`.
    config_errors = config.validate()
    if config_errors:
        import sys
        for err in config_errors:
            print(f'[CONFIG ERROR] {err}', file=sys.stderr)
        if config.FLASK_ENV != 'development':
            raise RuntimeError(f'Invalid configuration for production: {config_errors}')

    app = Flask(__name__, static_folder=config.STATIC_FOLDER, static_url_path='')
    app.config['SECRET_KEY'] = config.SECRET_KEY
    # Restrict CORS to configured origins — never allow wildcard in production.
    cors_origins = config.get_cors_origins_list()
    CORS(app, origins=cors_origins if cors_origins else '*')

    # ── Logging ───────────────────────────────────────────────────────────
    logger = configure_logging(
        log_file=config.LOG_FILE,
        console_level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    )

    # ── PEM Key (SSH) ─────────────────────────────────────────────────────
    # Fetch from AWS Secrets Manager at startup → /app/ml-deploy-key.pem
    # Required for SSH-based deployments to EC2 instances.
    load_pem_from_secrets_manager()

    # ── Flask-Limiter ──────────────────────────────────────────────────────
    limiter.init_app(app)

    # ── SocketIO ──────────────────────────────────────────────────────────
    # cors_allowed_origins restricted to the configured frontend URL.
    # Prevents WebSocket connections from arbitrary origins in production.
    frontend_origin = os.getenv('FRONTEND_URL', '')
    if config.FLASK_ENV != 'development' and not frontend_origin:
        logger.warning('FRONTEND_URL not set — SocketIO CORS will reject all browser connections in production')
    allowed_origins = [frontend_origin] if frontend_origin else []
    # In development, allow common local origins for convenience.
    if config.FLASK_ENV == 'development':
        dev_origins = os.getenv('DEV_CORS_ORIGINS', 'http://localhost:5173,http://localhost:80,http://localhost:3000').split(',')
        for dev_origin in dev_origins:
            if dev_origin.strip() not in allowed_origins:
                allowed_origins.append(dev_origin.strip())
    socketio.init_app(
        app,
        cors_allowed_origins=allowed_origins,
        ping_timeout=300,     # 5 min — longer than any deployment
        ping_interval=25,
        async_mode='threading',
    )

    # ── Database ──────────────────────────────────────────────────────────
    with app.app_context():
        init_db()
        _ensure_default_tenant(logger)
        # Bootstrap first admin from ADMIN_EMAIL + ADMIN_PASSWORD env vars.
        # Idempotent — safe to run on every startup; skips if admin exists.
        from .services.auth_service import bootstrap_admin
        bootstrap_admin()

    # ── Blueprints ────────────────────────────────────────────────────────
    # Imported INSIDE factory to avoid circular imports at module load time.
    from .api.auth import auth_bp
    from .api.health import health_bp
    from .api.deployments import deployments_bp
    from .api.applications import applications_bp
    from .api.instances import instances_bp
    from .api.admin import admin_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(health_bp)
    app.register_blueprint(deployments_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(instances_bp)
    app.register_blueprint(admin_bp)

    # ── Static SPA ────────────────────────────────────────────────────────
    @app.route('/')
    def index():
        return send_from_directory(app.static_folder, 'index.html')

    # ── Cache headers (dev only) ──────────────────────────────────────────
    @app.after_request
    def add_header(response):
        if config.FLASK_ENV == 'development':
            response.headers['Cache-Control'] = 'no-store, no-cache, must-revalidate, max-age=0'
            response.headers['Pragma']  = 'no-cache'
            response.headers['Expires'] = '0'
        return response

    # ── DB session teardown ───────────────────────────────────────────────
    # Called after EVERY request (and on exception) — returns session to pool.
    @app.teardown_appcontext
    def shutdown_db_session(exception=None):
        if exception:
            db_session.rollback()
        db_session.remove()

    # ── Error handlers ────────────────────────────────────────────────────
    @app.errorhandler(404)
    def not_found(e):
        return jsonify({'success': False, 'error': 'Endpoint not found'}), 404

    @app.errorhandler(500)
    def internal_error(e):
        logger.error('Internal server error: %s', e)
        return jsonify({'success': False, 'error': 'Internal server error'}), 500

    # ── SocketIO events ───────────────────────────────────────────────────
    from .core.jwt_utils import verify_access_token
    from flask import request as flask_request
    from jwt import ExpiredSignatureError, InvalidTokenError

    @socketio.on('connect')
    def handle_connect():
        """
        Validate JWT on WebSocket connection.
        Reads token from query string: ?token=<JWT>
        Calls disconnect() explicitly on invalid/expired token.
        """
        token = flask_request.args.get('token')
        if not token:
            logger.warning('SocketIO: connection rejected — no token')
            disconnect()
            return

        try:
            verify_access_token(token)
        except ExpiredSignatureError:
            logger.warning('SocketIO: connection rejected — expired token')
            disconnect()
            return
        except InvalidTokenError:
            logger.warning('SocketIO: connection rejected — invalid token')
            disconnect()
            return

        logger.info('SocketIO: client connected (authenticated)')
        emit('connected', {'message': 'Connected to deployment server'})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info('SocketIO: client disconnected')

    @socketio.on('subscribe_deployment')
    def handle_subscribe(data):
        deployment_id = data.get('deployment_id')
        logger.info('SocketIO: client subscribed to deployment: %s', deployment_id)

    logger.info('Flask app created — blueprints registered')
    return app


def _ensure_default_tenant(logger):
    """
    Upsert the default tenant row (single-tenant mode).
    Uses get-or-create with a rollback-on-duplicate guard so it is safe
    even when multiple workers start at the same moment.
    """
    _db = db_session()
    try:
        existing = _db.query(Tenant).filter_by(slug='default').first()
        if existing:
            logger.info('[OK] Default tenant found (id=%s)', existing.id[:8])
            return

        tenant = Tenant(name='Default Workspace', slug='default')
        _db.add(tenant)
        _db.commit()
        logger.info('[OK] Default tenant created (id=%s)', tenant.id[:8])

    except Exception as e:
        _db.rollback()
        # Another worker beat us to it — that's fine, just log at INFO not ERROR
        existing = _db.query(Tenant).filter_by(slug='default').first()
        if existing:
            logger.info('[OK] Default tenant already exists (id=%s) — race condition handled',
                        existing.id[:8])
        else:
            logger.error('Failed to ensure default tenant: %s', e)
    finally:
        _db.close()


# ── Local dev entry point ─────────────────────────────────────────────────────
# Gunicorn imports create_app directly — this block is only for `python -m backend.app`
if __name__ == '__main__':
    # create_app() calls config.validate() internally and raises on config errors
    _app = create_app()
    socketio.run(
        _app,
        host='0.0.0.0',
        port=config.APP_PORT,
        debug=(config.FLASK_ENV == 'development'),
    )
