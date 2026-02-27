"""
Applications API Blueprint
Routes: /api/applications, /api/applications/<app_id>
"""

from flask import Blueprint, request, jsonify
import logging

from ..database.connection import db_session
from ..database.models import Application, Deployment, EC2Instance
from ..database.repositories import ApplicationRepository, DeploymentRepository

logger = logging.getLogger(__name__)
applications_bp = Blueprint('applications', __name__)


@applications_bp.route('/api/applications', methods=['GET'])
def list_applications():
    """List all applications with latest deployment + instance info."""
    try:
        db = db_session()

        apps = db.query(Application).order_by(Application.created_at.desc()).all()
        enriched = []

        for app_obj in apps:
            latest_deployment = (
                db.query(Deployment)
                .filter_by(application_id=app_obj.id)
                .order_by(Deployment.started_at.desc())
                .first()
            )

            # Lookup instance via ApplicationInstance mapping table
            from ..database.models import ApplicationInstance
            mapping = (
                db.query(ApplicationInstance)
                .filter_by(application_id=app_obj.id)
                .order_by(ApplicationInstance.created_at.desc())
                .first()
            )
            latest_instance = (
                db.query(EC2Instance).filter_by(id=mapping.instance_id).first()
                if mapping else None
            )

            app_data = app_obj.to_dict()
            app_data.update({
                'deployment_status': latest_deployment.status if latest_deployment else None,
                'deployment_url':    latest_deployment.deployment_url if latest_deployment else None,
                'instance_id':       latest_instance.instance_id if latest_instance else None,
            })
            enriched.append(app_data)

        return jsonify({
            'success': True,
            'count': len(enriched),
            'applications': enriched,
        })

    except Exception as e:
        logger.error('list_applications error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@applications_bp.route('/api/applications/<app_id>', methods=['GET'])
def get_application(app_id):
    """Get one application and its recent deployments."""
    try:
        db       = db_session()
        repo     = ApplicationRepository(db)
        dep_repo = DeploymentRepository(db)

        app_obj = repo.get_by_id(app_id)
        if app_obj is None:
            return jsonify({'success': False, 'error': 'Application not found'}), 404

        recent = dep_repo.list_by_application(app_id, limit=10)
        return jsonify({
            'success': True,
            'application': app_obj.to_dict(),
            'recent_deployments': [d.to_dict() for d in recent],
        })
    except Exception as e:
        logger.error('get_application error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
