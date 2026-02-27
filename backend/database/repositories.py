"""
Repository Layer — Phase 3
============================
All database operations live here, one class per table group.
The orchestrator calls these instead of touching db.query() directly.

Pattern:
  repo = DeploymentRepository(db)
  dep  = repo.create(tenant_id, app_id)
  repo.add_step(dep.id, 1, 'EC2 Created', 'success')
  repo.mark_success(dep.id, 'http://1.2.3.4')

WHY a repository layer?
  - Single responsibility: DB logic in one place, not scattered across routes/orchestrator
  - Testable: swap real DB for a mock without touching orchestrator logic
  - Readable: `repo.mark_success(id, url)` vs 10 lines of raw SQLAlchemy everywhere
"""

import re
import logging
from datetime import datetime
from typing import Optional, List

from sqlalchemy.orm import Session

from .models import (
    Application, ApplicationInstance, EC2Instance,
    Deployment, DeploymentStep, DeploymentLog,
    EnvironmentVariable, Tenant,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# TenantRepository
# ─────────────────────────────────────────────────────────────────────────────
class TenantRepository:
    def __init__(self, db: Session):
        self.db = db

    def get_default(self) -> Optional[Tenant]:
        """Return the default (single-tenant) workspace."""
        return self.db.query(Tenant).filter_by(slug='default').first()

    def get_by_id(self, tenant_id: str) -> Optional[Tenant]:
        return self.db.query(Tenant).filter_by(id=tenant_id).first()


# ─────────────────────────────────────────────────────────────────────────────
# ApplicationRepository
# ─────────────────────────────────────────────────────────────────────────────
class ApplicationRepository:
    def __init__(self, db: Session):
        self.db = db

    def _make_slug(self, name: str) -> str:
        """Convert a name to a URL-safe slug: 'My App!' → 'my-app'."""
        slug = re.sub(r'[^a-z0-9]+', '-', name.lower()).strip('-')
        return slug or 'app'

    def create(self, tenant_id: str, name: str, github_url: str,
               container_port: int, **kwargs) -> Application:
        """
        Create a new application record.
        kwargs: any additional Application columns (repo_owner, branch, etc.)
        """
        slug = self._make_slug(name)

        # Make slug unique if collision (append short suffix)
        existing = self.db.query(Application).filter_by(
            tenant_id=tenant_id, slug=slug).first()
        if existing:
            import uuid
            slug = f"{slug}-{str(uuid.uuid4())[:4]}"

        app = Application(
            tenant_id=tenant_id,
            name=name,
            slug=slug,
            github_url=github_url,
            container_port=container_port,
            **kwargs,
        )
        self.db.add(app)
        self.db.flush()   # get the ID without committing
        logger.debug('ApplicationRepository.create: %s (id=%s)', name, app.id[:8])
        return app

    def get_by_id(self, app_id: str) -> Optional[Application]:
        return self.db.query(Application).filter_by(id=app_id).first()

    def get_by_github_url(self, tenant_id: str, github_url: str) -> Optional[Application]:
        return self.db.query(Application).filter_by(
            tenant_id=tenant_id, github_url=github_url).first()

    def get_or_create(self, tenant_id: str, name: str, github_url: str,
                      container_port: int, **kwargs) -> Application:
        """
        Return existing app for this tenant+github_url, or create a new one.
        Useful so repeated deploys of the same repo update the same app record.
        """
        existing = self.get_by_github_url(tenant_id, github_url)
        if existing:
            return existing
        return self.create(tenant_id, name, github_url, container_port, **kwargs)

    def update_status(self, app_id: str, status: str):
        self.db.query(Application).filter_by(id=app_id).update({
            'status': status,
            'updated_at': datetime.utcnow(),
        })

    def update_last_deployed(self, app_id: str):
        self.db.query(Application).filter_by(id=app_id).update({
            'last_deployed_at': datetime.utcnow(),
            'updated_at': datetime.utcnow(),
        })

    def list_by_tenant(self, tenant_id: str) -> List[Application]:
        return (self.db.query(Application)
                .filter_by(tenant_id=tenant_id)
                .order_by(Application.created_at.desc())
                .all())


# ─────────────────────────────────────────────────────────────────────────────
# EC2InstanceRepository
# ─────────────────────────────────────────────────────────────────────────────
class EC2InstanceRepository:
    def __init__(self, db: Session):
        self.db = db

    def create(self, aws_instance_id: str, public_ip: str,
               instance_type: str, region: str, **kwargs) -> EC2Instance:
        """Record a newly-created EC2 instance."""
        instance = EC2Instance(
            instance_id=aws_instance_id,
            public_ip=public_ip,
            instance_type=instance_type,
            region=region,
            status='running',
            **kwargs,
        )
        self.db.add(instance)
        self.db.flush()
        logger.debug('EC2InstanceRepository.create: %s', aws_instance_id)
        return instance

    def get_by_aws_id(self, aws_instance_id: str) -> Optional[EC2Instance]:
        return self.db.query(EC2Instance).filter_by(instance_id=aws_instance_id).first()

    def get_by_id(self, db_id: str) -> Optional[EC2Instance]:
        return self.db.query(EC2Instance).filter_by(id=db_id).first()

    def update_status(self, db_id: str, status: str):
        self.db.query(EC2Instance).filter_by(id=db_id).update({
            'status': status,
            'last_health_check': datetime.utcnow(),
        })

    def link_application(self, app_id: str, instance_db_id: str,
                         host_port: int) -> ApplicationInstance:
        """Create the many-to-many mapping between an app and an instance."""
        mapping = ApplicationInstance(
            application_id=app_id,
            instance_id=instance_db_id,
            host_port=host_port,
            status='active',
        )
        self.db.add(mapping)
        self.db.flush()
        return mapping


# ─────────────────────────────────────────────────────────────────────────────
# DeploymentRepository
# ─────────────────────────────────────────────────────────────────────────────
class DeploymentRepository:
    def __init__(self, db: Session):
        self.db = db

    # ── Create ────────────────────────────────────────────────────────────
    def create(self, tenant_id: str, application_id: str, **kwargs) -> Deployment:
        """
        Start a new deployment record.
        The caller must commit() after the first real step completes.
        """
        dep = Deployment(
            tenant_id=tenant_id,
            application_id=application_id,
            status='in_progress',
            **kwargs,
        )
        self.db.add(dep)
        self.db.flush()   # get dep.id + dep.short_id before committing
        logger.info('Deployment started: short_id=%s', dep.short_id)
        return dep

    # ── Read ──────────────────────────────────────────────────────────────
    def get_by_id(self, dep_id: str) -> Optional[Deployment]:
        return self.db.query(Deployment).filter_by(id=dep_id).first()

    def get_by_short_id(self, short_id: str) -> Optional[Deployment]:
        return self.db.query(Deployment).filter_by(short_id=short_id).first()

    def list_all(self, limit: int = 50) -> List[Deployment]:
        return (self.db.query(Deployment)
                .order_by(Deployment.started_at.desc())
                .limit(limit).all())

    def list_by_application(self, app_id: str, limit: int = 20) -> List[Deployment]:
        return (self.db.query(Deployment)
                .filter_by(application_id=app_id)
                .order_by(Deployment.started_at.desc())
                .limit(limit).all())

    # ── Status updates ────────────────────────────────────────────────────
    def mark_success(self, dep_id: str, deployment_url: str = None):
        """Mark deployment complete. Caller must commit()."""
        now = datetime.utcnow()
        dep = self.get_by_id(dep_id)
        if dep and dep.started_at:
            duration = int((now - dep.started_at).total_seconds())
        else:
            duration = None
        self.db.query(Deployment).filter_by(id=dep_id).update({
            'status': 'success',
            'completed_at': now,
            'duration_seconds': duration,
            'deployment_url': deployment_url,
        })
        logger.info('Deployment %s marked success (duration=%ss)', dep_id[:8], duration)

    def mark_failed(self, dep_id: str, error_message: str):
        """Mark deployment failed. Caller must commit()."""
        now = datetime.utcnow()
        dep = self.get_by_id(dep_id)
        if dep and dep.started_at:
            duration = int((now - dep.started_at).total_seconds())
        else:
            duration = None
        self.db.query(Deployment).filter_by(id=dep_id).update({
            'status': 'failed',
            'completed_at': now,
            'duration_seconds': duration,
            'error_message': error_message,
        })
        logger.info('Deployment %s marked failed: %s', dep_id[:8], error_message[:80])

    # ── Steps ─────────────────────────────────────────────────────────────
    def add_step(self, deployment_id: str, step_number: int, step_name: str,
                 status: str = 'success', message: str = None) -> DeploymentStep:
        """
        Record a completed deployment step.
        Example: repo.add_step(dep.id, 1, 'EC2 Created', 'success')
        """
        now = datetime.utcnow()
        step = DeploymentStep(
            deployment_id=deployment_id,
            step_number=step_number,
            step_name=step_name,
            status=status,
            message=message,
            started_at=now,
            completed_at=now,
        )
        self.db.add(step)
        self.db.flush()
        return step

    # ── Logs ──────────────────────────────────────────────────────────────
    def add_log(self, deployment_id: str, message: str,
                level: str = 'INFO') -> DeploymentLog:
        """Append a log line to a deployment."""
        log = DeploymentLog(
            deployment_id=deployment_id,
            message=message,
            log_level=level,
        )
        self.db.add(log)
        self.db.flush()
        return log

    def get_logs(self, deployment_id: str, limit: int = 500) -> List[DeploymentLog]:
        return (self.db.query(DeploymentLog)
                .filter_by(deployment_id=deployment_id)
                .order_by(DeploymentLog.id.asc())
                .limit(limit).all())
