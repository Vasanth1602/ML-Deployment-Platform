"""
EC2 Instances API Blueprint
Routes: /api/instances, /api/instances/sync,
        /api/instances/<id>/stop, /api/instances/<id>/start,
        /api/instances/<id>/terminate, /api/stats
"""

from flask import Blueprint, request, jsonify
import logging

from ..database.connection import db_session
from ..database.models import EC2Instance, Deployment, Application
from ..database.repositories import EC2InstanceRepository

logger = logging.getLogger(__name__)
instances_bp = Blueprint('instances', __name__)


def _get_orchestrator():
    """Lazy import orchestrator to avoid circular imports at module load time."""
    from ..api.deployments import _orchestrator
    return _orchestrator


@instances_bp.route('/api/instances', methods=['GET'])
def list_instances():
    """
    List EC2 instances — merges DB records with live AWS state.
    Query params:
        source  db | aws | merged (default: merged)
    """
    source = request.args.get('source', 'merged')
    try:
        db = db_session()
        db_instances = db.query(EC2Instance).order_by(EC2Instance.created_at.desc()).all()
        db_map = {inst.instance_id: inst for inst in db_instances}

        if source == 'db':
            return jsonify({'success': True, 'source': 'db',
                            'instances': [i.to_dict() for i in db_instances]})

        # Fetch live state from AWS (may fail if not configured)
        aws_instances = []
        try:
            aws_instances = _get_orchestrator().aws_manager.list_instances()
        except Exception as aws_err:
            logger.warning('AWS list_instances unavailable: %s', aws_err)
            if source == 'aws':
                return jsonify({'success': False,
                                'error': f'AWS unavailable: {aws_err}'}), 503

        aws_map = {i['instance_id']: i for i in aws_instances}
        merged  = []
        for db_inst in db_instances:
            row = db_inst.to_dict()
            if db_inst.instance_id in aws_map:
                live = aws_map[db_inst.instance_id]
                row['aws_state']   = live['state']
                row['state_match'] = (db_inst.status == live['state'])
                row['source']      = 'db+aws'
            else:
                row['aws_state']   = None
                row['state_match'] = False
                row['source']      = 'db_only'
            merged.append(row)

        for aws_id, live in aws_map.items():
            if aws_id not in db_map:
                live['source']      = 'aws_only'
                live['state_match'] = None
                merged.append(live)

        return jsonify({'success': True, 'source': 'merged',
                        'count': len(merged), 'instances': merged})
    except Exception as e:
        logger.error('list_instances error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@instances_bp.route('/api/instances/sync', methods=['POST'])
def sync_instance_states():
    """Sync DB instance statuses with live AWS states."""
    try:
        db = db_session()
        ec2_repo     = EC2InstanceRepository(db)
        db_instances = db.query(EC2Instance).all()

        if not db_instances:
            return jsonify({'success': True, 'message': 'No instances to sync', 'changes': []})

        try:
            aws_instances = _get_orchestrator().aws_manager.list_instances()
        except Exception as aws_err:
            return jsonify({'success': False, 'error': f'Cannot reach AWS: {aws_err}'}), 503

        aws_map  = {i['instance_id']: i['state'] for i in aws_instances}
        state_map = {
            'running': 'running', 'stopped': 'stopped', 'stopping': 'stopping',
            'pending': 'pending', 'shutting-down': 'terminating', 'terminated': 'terminated',
        }

        changes = []
        for inst in db_instances:
            aws_state  = aws_map.get(inst.instance_id)
            new_status = 'terminated' if aws_state is None else state_map.get(aws_state, aws_state)

            if inst.status != new_status:
                old_status = inst.status
                ec2_repo.update_status(inst.id, new_status)
                changes.append({'instance_id': inst.instance_id,
                                 'old_status': old_status, 'new_status': new_status})
                logger.info('sync: %s  %s → %s', inst.instance_id, old_status, new_status)

        db.commit()
        return jsonify({
            'success': True,
            'synced': len(db_instances),
            'changes': changes,
            'message': f'{len(changes)} instance(s) updated' if changes else 'All statuses already in sync',
        })
    except Exception as e:
        logger.error('sync_instance_states error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@instances_bp.route('/api/instances/<instance_id>/stop', methods=['POST'])
def stop_instance(instance_id):
    """Stop an EC2 instance and update its DB status."""
    try:
        _get_orchestrator().aws_manager.stop_instance(instance_id)
        db       = db_session()
        ec2_repo = EC2InstanceRepository(db)
        inst     = ec2_repo.get_by_aws_id(instance_id)
        if inst:
            ec2_repo.update_status(inst.id, 'stopped')
            db.commit()
        return jsonify({'success': True, 'message': f'Instance {instance_id} stop initiated'})
    except Exception as e:
        logger.error('stop_instance error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@instances_bp.route('/api/instances/<instance_id>/start', methods=['POST'])
def start_instance(instance_id):
    """Start a stopped EC2 instance and update its DB status."""
    try:
        _get_orchestrator().aws_manager.start_instance(instance_id)
        db       = db_session()
        ec2_repo = EC2InstanceRepository(db)
        inst     = ec2_repo.get_by_aws_id(instance_id)
        if inst:
            ec2_repo.update_status(inst.id, 'running')
            db.commit()
        return jsonify({'success': True, 'message': f'Instance {instance_id} start initiated'})
    except Exception as e:
        logger.error('start_instance error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


@instances_bp.route('/api/instances/<instance_id>/terminate', methods=['POST'])
def terminate_instance(instance_id):
    """Terminate an EC2 instance and update its DB status."""
    try:
        _get_orchestrator().aws_manager.terminate_instance(instance_id)
        db       = db_session()
        ec2_repo = EC2InstanceRepository(db)
        inst     = ec2_repo.get_by_aws_id(instance_id)
        if inst:
            ec2_repo.update_status(inst.id, 'terminated')
            db.commit()
        return jsonify({'success': True, 'message': f'Instance {instance_id} termination initiated'})
    except Exception as e:
        logger.error('terminate_instance error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500


# ── Dashboard Stats ───────────────────────────────────────────────────────────

@instances_bp.route('/api/stats', methods=['GET'])
def get_stats():
    """Dashboard summary counts — used by the frontend status bar."""
    try:
        db = db_session()

        total_deps   = db.query(Deployment).count()
        success_deps = db.query(Deployment).filter_by(status='success').count()
        failed_deps  = db.query(Deployment).filter_by(status='failed').count()
        running_deps = db.query(Deployment).filter_by(status='in_progress').count()

        total_instances   = db.query(EC2Instance).count()
        running_instances = db.query(EC2Instance).filter_by(status='running').count()

        total_apps  = db.query(Application).count()
        active_apps = db.query(Application).filter_by(status='active').count()

        return jsonify({
            'success': True,
            # Flat stats — consumed directly by Dashboard.jsx
            'stats': {
                'total_applications':  total_apps,
                'active_deployments':  running_deps,
                'failed_deployments':  failed_deps,
                'running_instances':   running_instances,
            },
            # Detailed breakdown — available for future use
            'deployments': {
                'total': total_deps, 'success': success_deps,
                'failed': failed_deps, 'in_progress': running_deps,
            },
            'instances':    {'total': total_instances, 'running': running_instances},
            'applications': {'total': total_apps, 'active': active_apps},
        })
    except Exception as e:
        logger.error('get_stats error: %s', e)
        return jsonify({'success': False, 'error': str(e)}), 500
