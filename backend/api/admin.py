"""
Admin API Blueprint — backend/api/admin.py
============================================
Platform-wide admin endpoints.
Every route requires both @require_auth AND @require_admin.

Routes:
    GET /api/admin/users        — list all registered users
    GET /api/admin/deployments  — list all deployments (across all users)
    GET /api/admin/platform-stats — aggregated platform statistics
"""

import logging

from flask import Blueprint, jsonify, request

from ..database.connection import db_session
from ..database.models import User, Deployment, Application, EC2Instance, ApplicationInstance
from ..database.repositories import (
    UserRepository, DeploymentRepository, ApplicationRepository,
)
from ..core.auth_middleware import require_auth, require_admin

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__, url_prefix='/api/admin')


@admin_bp.route('/users', methods=['GET'])
@require_auth
@require_admin
def list_users():
    """
    GET /api/admin/users
    Returns all registered platform users.
    """
    try:
        db = db_session()
        repo = UserRepository(db)
        users = repo.list_all()

        return jsonify({
            'success': True,
            'count': len(users),
            'users': [u.to_dict() for u in users],
        })
    except Exception as e:
        logger.error('admin list_users error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/deployments', methods=['GET'])
@require_auth
@require_admin
def list_all_deployments():
    """
    GET /api/admin/deployments
    Returns all deployments across all users.
    Query params:
        limit  (int, default 100)
        status (str, optional)
    """
    try:
        limit  = min(int(request.args.get('limit', 100)), 500)
        status = request.args.get('status')

        db   = db_session()
        repo = DeploymentRepository(db)
        deployments = repo.list_all_admin(limit=limit)

        if status:
            deployments = [d for d in deployments if d.status == status]

        # Build a user-id → email lookup to avoid N+1 queries
        user_ids = {d.triggered_by_user_id for d in deployments if d.triggered_by_user_id}
        user_map = {}
        if user_ids:
            users = db.query(User).filter(User.id.in_(user_ids)).all()
            user_map = {str(u.id): u.email for u in users}

        enriched = []
        for dep in deployments:
            d = dep.to_dict()
            # Pull github_url from the related Application
            app = dep.application
            d['github_url']          = app.github_url if app else None
            d['application_name']    = app.name       if app else None
            # Attach owner email
            d['triggered_by_email']  = user_map.get(str(dep.triggered_by_user_id)) if dep.triggered_by_user_id else None
            enriched.append(d)

        return jsonify({
            'success': True,
            'count': len(enriched),
            'deployments': enriched,
        })
    except Exception as e:
        logger.error('admin list_all_deployments error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/applications', methods=['GET'])
@require_auth
@require_admin
def list_all_applications():
    """
    GET /api/admin/applications
    Returns all applications across all users with owner context.
    """
    try:
        db   = db_session()
        apps = db.query(Application).order_by(Application.created_at.desc()).all()

        # Single user-id → email lookup
        user_ids = {a.created_by_user_id for a in apps if a.created_by_user_id}
        user_map = {}
        if user_ids:
            users    = db.query(User).filter(User.id.in_(user_ids)).all()
            user_map = {str(u.id): u.email for u in users}

        enriched = []
        for app in apps:
            a = app.to_dict()
            a['created_by_email'] = user_map.get(str(app.created_by_user_id)) if app.created_by_user_id else None
            # Latest deployment status
            latest_dep = (
                db.query(Deployment)
                .filter_by(application_id=app.id)
                .order_by(Deployment.started_at.desc())
                .first()
            )
            a['last_deployment_status'] = latest_dep.status if latest_dep else None
            # Instance info
            mapping = (
                db.query(ApplicationInstance)
                .filter_by(application_id=app.id)
                .order_by(ApplicationInstance.created_at.desc())
                .first()
            )
            inst = db.query(EC2Instance).filter_by(id=mapping.instance_id).first() if mapping else None
            a['instance_id'] = inst.instance_id if inst else None
            a['public_ip']   = inst.public_ip   if inst else None
            enriched.append(a)

        return jsonify({'success': True, 'count': len(enriched), 'applications': enriched})
    except Exception as e:
        logger.error('admin list_all_applications error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@admin_bp.route('/platform-stats', methods=['GET'])
@require_auth
@require_admin
def platform_stats():
    """
    GET /api/admin/platform-stats
    Aggregated platform-wide statistics for the admin dashboard.
    """
    try:
        db = db_session()

        total_users   = db.query(User).count()
        active_users  = db.query(User).filter_by(is_active=True).count()

        total_deps    = db.query(Deployment).count()
        success_deps  = db.query(Deployment).filter_by(status='success').count()
        failed_deps   = db.query(Deployment).filter_by(status='failed').count()
        running_deps  = db.query(Deployment).filter_by(status='in_progress').count()

        total_apps    = db.query(Application).count()
        active_apps   = db.query(Application).filter_by(status='active').count()

        total_instances   = db.query(EC2Instance).count()
        running_instances = db.query(EC2Instance).filter_by(status='running').count()

        return jsonify({
            'success': True,
            'stats': {
                'users':       {'total': total_users, 'active': active_users},
                'deployments': {'total': total_deps, 'success': success_deps,
                                'failed': failed_deps, 'in_progress': running_deps},
                'applications': {'total': total_apps, 'active': active_apps},
                'instances':    {'total': total_instances, 'running': running_instances},
            },
        })
    except Exception as e:
        logger.error('admin platform_stats error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
