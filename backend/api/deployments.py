"""
Deployments API Blueprint
Routes: /api/deploy, /api/deployments, /api/deployments/<id>, /api/deployments/<id>/logs
"""

from flask import Blueprint, request, jsonify, g
from threading import Thread
from datetime import datetime
import logging

from ..database.connection import db_session
from ..database.models import Deployment, DeploymentStep, DeploymentLog
from ..database.repositories import DeploymentRepository
from ..services.deployment_orchestrator import DeploymentOrchestrator
from ..core.auth_middleware import require_auth

logger = logging.getLogger(__name__)
deployments_bp = Blueprint('deployments', __name__)

# Shared orchestrator — same lifetime as the process (mirrors old app.py behaviour)
_orchestrator = DeploymentOrchestrator()


@deployments_bp.route('/api/deploy', methods=['POST'])
@require_auth
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
        user_id        = g.current_user.id   # captured before background thread

        logger.info('Received deployment request for: %s (user=%s)', github_url, user_id[:8])

        # Mutable holder so the background thread can write the deployment_id
        # and we can return it to the frontend immediately in the response.
        id_holder = {'deployment_id': None}

        import threading
        id_ready = threading.Event()

        def progress_callback(step, message, status, data):
            from ..app import socketio
            payload = {'step': step, 'message': message,
                       'status': status, 'data': data}
            if id_holder['deployment_id']:
                payload['deployment_id'] = id_holder['deployment_id']
            socketio.emit('deployment_progress', payload)

        def run_deployment():
            from ..app import socketio
            result = _orchestrator.deploy(
                github_url, instance_name, container_port, host_port,
                progress_callback,
                on_id_assigned=lambda dep_id: (
                    id_holder.update({'deployment_id': dep_id}),
                    id_ready.set(),
                ),
                user_id=user_id,   # store triggered_by_user_id
            )
            socketio.emit('deployment_complete', result)

        t = Thread(target=run_deployment, daemon=True)
        t.start()

        # Wait up to 5 s for the orchestrator to create the DB record and assign short_id.
        id_ready.wait(timeout=5)

        return jsonify({
            'success': True,
            'message': 'Deployment started',
            'github_url': github_url,
            'deployment_id': id_holder['deployment_id'],
        })

    except Exception as e:
        logger.error('deploy error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@deployments_bp.route('/api/deployments/<deployment_id>/cancel', methods=['POST'])
@require_auth
def cancel_deployment(deployment_id):
    """
    Cancel a running deployment.
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

        # Ownership check: only the owner or an admin can cancel
        user = g.current_user
        if user.role != 'admin' and dep.triggered_by_user_id != user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        if dep.status not in ('in_progress', 'pending'):
            return jsonify({
                'success': False,
                'error': f'Deployment is already {dep.status} — cannot cancel',
            }), 409

        cancelled = _orchestrator.cancel(dep.short_id)
        return jsonify({
            'success': True,
            'cancelled': cancelled,
            'message': 'Cancel signal sent' if cancelled else 'Deployment not active in memory (may have just finished)',
        })

    except Exception as e:
        logger.error('cancel_deployment error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@deployments_bp.route('/api/deployments', methods=['GET'])
@require_auth
def list_deployments():
    """
    List deployments — filtered by ownership unless user is admin.
    Query params:
        limit  (int, default 50)
        status (str, optional)
        app_id (str, optional)
    """
    try:
        limit  = min(int(request.args.get('limit', 50)), 200)
        status = request.args.get('status')
        app_id = request.args.get('app_id')
        user   = g.current_user

        db   = db_session()
        repo = DeploymentRepository(db)

        # Service-layer role dispatch: admin sees all, user sees own
        if user.role == 'admin':
            deployments = repo.list_all_admin(limit=limit)
        else:
            deployments = repo.list_by_user(user.id, limit=limit)

        # Optional in-memory filters after ownership-aware query
        if status:
            deployments = [d for d in deployments if d.status == status]
        if app_id:
            deployments = [d for d in deployments if d.application_id == app_id]

        return jsonify({
            'success': True,
            'count': len(deployments),
            'deployments': [d.to_dict() for d in deployments],
        })
    except Exception as e:
        logger.error('list_deployments error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@deployments_bp.route('/api/deployments/<deployment_id>', methods=['GET'])
@require_auth
def get_deployment(deployment_id):
    """
    Get one deployment's detail — includes steps and the last 200 log lines.
    Accepts either the full UUID or the 8-char short_id.
    """
    try:
        db   = db_session()
        repo = DeploymentRepository(db)
        user = g.current_user

        dep = repo.get_by_short_id(deployment_id)
        if dep is None:
            dep = repo.get_by_id(deployment_id)
        if dep is None:
            return jsonify({'success': False, 'error': 'Deployment not found'}), 404

        # Ownership check: only owner or admin can view
        if user.role != 'admin' and dep.triggered_by_user_id != user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

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
@require_auth
def get_deployment_logs(deployment_id):
    """
    Get log lines for a deployment (paginated).
    Query params:
        limit  (int, default 500)
        after  (str, optional) — ISO timestamp
        level  (str, optional) — INFO/WARNING/ERROR
    """
    try:
        limit = min(int(request.args.get('limit', 500)), 2000)
        after = request.args.get('after')
        level = request.args.get('level')
        user  = g.current_user

        db   = db_session()
        repo = DeploymentRepository(db)

        dep = repo.get_by_short_id(deployment_id) or repo.get_by_id(deployment_id)
        if dep is None:
            return jsonify({'success': False, 'error': 'Deployment not found'}), 404

        # Ownership check
        if user.role != 'admin' and dep.triggered_by_user_id != user.id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

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
