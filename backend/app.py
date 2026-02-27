"""
Flask application factory.
Initializes the app, registers Blueprints, sets up DB and SocketIO.
"""

from flask import Flask, send_from_directory, jsonify
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import logging

from .core.logging_config import configure_logging
from .config import config
from .database.connection import init_db, db_session, check_db_connection
from .database.models import Tenant

# ── SocketIO instance ─────────────────────────────────────────────────────────
# Defined at module level so that backend/__init__.py can re-export it.
# Blueprints import it via:  from .. import socketio
socketio = SocketIO()


def create_app() -> Flask:
    """
    Application factory — called by Gunicorn and tests.
    Usage:  gunicorn backend.app:create_app --factory
    """
    app = Flask(__name__, static_folder='../frontend', static_url_path='')
    app.config['SECRET_KEY'] = config.SECRET_KEY
    CORS(app)

    # ── Logging ───────────────────────────────────────────────────────────
    logger = configure_logging(
        log_file=config.LOG_FILE,
        console_level=getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    )

    # ── SocketIO ──────────────────────────────────────────────────────────
    socketio.init_app(
        app,
        cors_allowed_origins="*",
        ping_timeout=300,     # 5 min — longer than any deployment
        ping_interval=25,
        async_mode='threading',
    )

    # ── Database ──────────────────────────────────────────────────────────
    with app.app_context():
        init_db()
        _ensure_default_tenant(logger)

    # ── Blueprints ────────────────────────────────────────────────────────
    # Imported INSIDE factory to avoid circular imports at module load time.
    from .api.health import health_bp
    from .api.deployments import deployments_bp
    from .api.applications import applications_bp
    from .api.instances import instances_bp

    app.register_blueprint(health_bp)
    app.register_blueprint(deployments_bp)
    app.register_blueprint(applications_bp)
    app.register_blueprint(instances_bp)

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
    @socketio.on('connect')
    def handle_connect():
        logger.info('Client connected')
        emit('connected', {'message': 'Connected to deployment server'})

    @socketio.on('disconnect')
    def handle_disconnect():
        logger.info('Client disconnected')

    @socketio.on('subscribe_deployment')
    def handle_subscribe(data):
        deployment_id = data.get('deployment_id')
        logger.info('Client subscribed to deployment: %s', deployment_id)

    logger.info('Flask app created — blueprints registered')
    return app


def _ensure_default_tenant(logger):
    """Create the default tenant row if it doesn't exist (single-tenant mode)."""
    _db = db_session()
    try:
        existing = _db.query(Tenant).filter_by(slug='default').first()
        if not existing:
            tenant = Tenant(name='Default Workspace', slug='default')
            _db.add(tenant)
            _db.commit()
            logger.info('[OK] Default tenant created (id=%s)', tenant.id[:8])
        else:
            logger.info('[OK] Default tenant found (id=%s)', existing.id[:8])
    except Exception as e:
        _db.rollback()
        logger.error('Failed to ensure default tenant: %s', e)
    finally:
        _db.close()


# ── Local dev entry point ─────────────────────────────────────────────────────
# Gunicorn imports create_app directly — this block is only for `python -m backend.app`
if __name__ == '__main__':
    config_errors = config.validate()
    if config_errors:
        import sys
        for err in config_errors:
            print(f'[CONFIG ERROR] {err}')
        print('Please configure your .env file. See .env.example for reference.')
        sys.exit(1)

    _app = create_app()
    socketio.run(
        _app,
        host='0.0.0.0',
        port=config.APP_PORT,
        debug=(config.FLASK_ENV == 'development'),
    )
