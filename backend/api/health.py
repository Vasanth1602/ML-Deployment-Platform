"""
Health & Config API Blueprint
Routes: /api/health, /api/config/validate
"""

from flask import Blueprint, jsonify
import logging

from ..database.connection import check_db_connection
from ..config import config

logger = logging.getLogger(__name__)
health_bp = Blueprint('health', __name__)


@health_bp.route('/api/health', methods=['GET'])
def health_check():
    """Health check endpoint — also reports DB connectivity."""
    db_ok = check_db_connection()
    status = 'healthy' if db_ok else 'degraded'
    code = 200 if db_ok else 503
    return jsonify({
        'status': status,
        'service': 'Automated Deployment Framework',
        'version': '1.0.0',
        'database': 'connected' if db_ok else 'unreachable',
    }), code


@health_bp.route('/api/config/validate', methods=['GET'])
def validate_config():
    """Validate AWS configuration."""
    errors = config.validate()
    if errors:
        return jsonify({'valid': False, 'errors': errors}), 400
    return jsonify({'valid': True, 'message': 'Configuration is valid'})
