"""
Deployments API Blueprint
Routes: /api/deploy, /api/deployments, /api/deployments/<id>, /api/deployments/<id>/logs
"""

from flask import Blueprint, request, jsonify
from threading import Thread
from datetime import datetime
import logging

from ..database.connection import db_session
from ..database.models import Deployment, DeploymentStep, DeploymentLog
from ..database.repositories import DeploymentRepository
from ..services.deployment_orchestrator import DeploymentOrchestrator

logger = logging.getLogger(__name__)
deployments_bp = Blueprint('deployments', __name__)

# Shared orchestrator — same lifetime as the process (mirrors old app.py behaviour)
_orchestrator = DeploymentOrchestrator()


@deployments_bp.route('/api/deploy', methods=['POST'])
def deploy():
    """
    Deploy application from GitHub repository.

    Request body:
    {
        "github_url": "https://github.com/user/repo",
        "instance_name": "optional-custom-name",
        "container_port": 8000,
        "host_port": 8000
    }
    """
    try:
        data = request.get_json()
        if not data or 'github_url' not in data:
            return jsonify({'success': False, 'error': 'github_url is required'}), 400

        github_url     = data['github_url']
        instance_name  = data.get('instance_name')
        container_port = data.get('container_port')
        host_port      = data.get('host_port')

        logger.info('Received deployment request for: %s', github_url)

        def progress_callback(step, message, status, data):
            from .. import socketio
            socketio.emit('deployment_progress', {
                'step': step, 'message': message,
                'status': status, 'data': data,
            })

        def run_deployment():
            from .. import socketio
            result = _orchestrator.deploy(
                github_url, instance_name, container_port, host_port, progress_callback
            )
            socketio.emit('deployment_complete', result)

        t = Thread(target=run_deployment, daemon=True)
        t.start()

        return jsonify({'success': True, 'message': 'Deployment started', 'github_url': github_url})

    except Exception as e:
        logger.error('deploy error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@deployments_bp.route('/api/deployments', methods=['GET'])
def list_deployments():
    """
    List all deployments, newest first.
    Query params:
        limit  (int, default 50)    — max rows to return
        status (str, optional)      — filter by status (success/failed/in_progress)
        app_id (str, optional)      — filter by application ID
    """
    try:
        limit  = min(int(request.args.get('limit', 50)), 200)
        status = request.args.get('status')
        app_id = request.args.get('app_id')

        db = db_session()
        q = db.query(Deployment).order_by(Deployment.started_at.desc())
        if status:
            q = q.filter(Deployment.status == status)
        if app_id:
            q = q.filter(Deployment.application_id == app_id)
        deployments = q.limit(limit).all()

        return jsonify({
            'success': True,
            'count': len(deployments),
            'deployments': [d.to_dict() for d in deployments],
        })
    except Exception as e:
        logger.error('list_deployments error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@deployments_bp.route('/api/deployments/<deployment_id>', methods=['GET'])
def get_deployment(deployment_id):
    """
    Get one deployment's detail — includes steps and the last 200 log lines.
    Accepts either the full UUID or the 8-char short_id.
    """
    try:
        db   = db_session()
        repo = DeploymentRepository(db)

        dep = repo.get_by_short_id(deployment_id)
        if dep is None:
            dep = repo.get_by_id(deployment_id)
        if dep is None:
            return jsonify({'success': False, 'error': 'Deployment not found'}), 404

        steps = (db.query(DeploymentStep)
                 .filter_by(deployment_id=dep.id)
                 .order_by(DeploymentStep.step_number)
                 .all())

        logs = (db.query(DeploymentLog)
                .filter_by(deployment_id=dep.id)
                .order_by(DeploymentLog.timestamp.asc())
                .limit(200).all())

        return jsonify({
            'success': True,
            'deployment': dep.to_dict(),
            'steps': [
                {
                    'step_number':  s.step_number,
                    'step_name':    s.step_name,
                    'status':       s.status,
                    'message':      s.message,
                    'started_at':   s.started_at.isoformat() if s.started_at else None,
                    'completed_at': s.completed_at.isoformat() if s.completed_at else None,
                }
                for s in steps
            ],
            'logs': [
                {
                    'level':     l.log_level,
                    'message':   l.message,
                    'timestamp': l.timestamp.isoformat() if l.timestamp else None,
                }
                for l in logs
            ],
        })
    except Exception as e:
        logger.error('get_deployment error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@deployments_bp.route('/api/deployments/<deployment_id>/logs', methods=['GET'])
def get_deployment_logs(deployment_id):
    """
    Get log lines for a deployment (paginated).
    Query params:
        limit  (int, default 500) — lines per page
        after  (str, optional)    — ISO timestamp; return only lines after this time
        level  (str, optional)    — filter by log level (INFO/WARNING/ERROR)
    """
    try:
        limit = min(int(request.args.get('limit', 500)), 2000)
        after = request.args.get('after')
        level = request.args.get('level')

        db   = db_session()
        repo = DeploymentRepository(db)

        dep = repo.get_by_short_id(deployment_id) or repo.get_by_id(deployment_id)
        if dep is None:
            return jsonify({'success': False, 'error': 'Deployment not found'}), 404

        q = (db.query(DeploymentLog)
             .filter_by(deployment_id=dep.id)
             .order_by(DeploymentLog.timestamp.asc()))

        if after:
            after_dt = datetime.fromisoformat(after)
            q = q.filter(DeploymentLog.timestamp > after_dt)
        if level:
            q = q.filter(DeploymentLog.log_level == level.upper())

        logs = q.limit(limit).all()

        return jsonify({
            'success': True,
            'deployment_id': dep.short_id,
            'count': len(logs),
            'logs': [
                {
                    'level':     l.log_level,
                    'message':   l.message,
                    'timestamp': l.timestamp.isoformat() if l.timestamp else None,
                }
                for l in logs
            ],
        })
    except Exception as e:
        logger.error('get_deployment_logs error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
