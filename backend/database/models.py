"""
Database Models — SQLAlchemy ORM
=================================
Each class = one database table.
Each attribute = one column.

Table list:
  1.  Tenant             — multi-tenant org management
  2.  EC2Instance        — platform-owned AWS instances (no tenant_id)
  3.  Application        — deployed GitHub repos
  4.  ApplicationInstance— mapping: which app runs on which instance + port
  5.  Deployment         — every deploy attempt (history)
  6.  DeploymentStep     — granular steps (EC2, Docker, NGINX …)
  7.  DeploymentLog      — real-time log lines (BIGSERIAL PK)
  8.  Secret             — AWS Secrets Manager ARN references only
  9.  EnvironmentVariable— app config: plaintext OR secret reference
  10. InstanceMetric     — CPU / memory / disk metrics (BIGSERIAL PK)
"""

import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, BigInteger, Column, DateTime, ForeignKey,
    Integer, String, Text, UniqueConstraint, DECIMAL,
)
from sqlalchemy.types import TypeDecorator, CHAR
from sqlalchemy.orm import relationship, DeclarativeBase


# ─────────────────────────────────────────────────────────────────────────────
# Base
# ─────────────────────────────────────────────────────────────────────────────
class Base(DeclarativeBase):
    pass


# ─────────────────────────────────────────────────────────────────────────────
# GUID helper — stores UUID as CHAR(36) in SQLite, native UUID in PostgreSQL
# ─────────────────────────────────────────────────────────────────────────────
class GUID(TypeDecorator):
    """Platform-independent UUID type."""
    impl = CHAR
    cache_ok = True

    def load_dialect_impl(self, dialect):
        if dialect.name == 'postgresql':
            from sqlalchemy.dialects.postgresql import UUID
            return dialect.type_descriptor(UUID(as_uuid=True))
        return dialect.type_descriptor(CHAR(36))

    def process_bind_param(self, value, dialect):
        if value is None:
            return value
        return str(value)

    def process_result_value(self, value, dialect):
        if value is None:
            return value
        return str(value)


def _uuid() -> str:
    return str(uuid.uuid4())


def _short_id() -> str:
    """8-char human-readable display ID (e.g. 8029fe0e)."""
    return str(uuid.uuid4())[:8]


# ─────────────────────────────────────────────────────────────────────────────
# 1. Tenant
# ─────────────────────────────────────────────────────────────────────────────
class Tenant(Base):
    """
    Represents an organisation / workspace.
    All user data is scoped to a tenant via tenant_id columns.
    For single-tenant use: one default tenant is created automatically.
    """
    __tablename__ = 'tenants'

    id         = Column(GUID, primary_key=True, default=_uuid)
    name       = Column(String(255), nullable=False)
    slug       = Column(String(100), unique=True, nullable=False)   # e.g. "acme-corp"
    plan_tier  = Column(String(50), default='free')                 # free | pro | enterprise
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active  = Column(Boolean, default=True)

    # relationships
    applications = relationship('Application', back_populates='tenant',
                                cascade='all, delete-orphan')
    deployments  = relationship('Deployment', back_populates='tenant',
                                cascade='all, delete-orphan')
    secrets      = relationship('Secret', back_populates='tenant',
                                cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Tenant slug={self.slug!r}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'plan_tier': self.plan_tier,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 2. EC2Instance  (platform-owned — no tenant_id)
# ─────────────────────────────────────────────────────────────────────────────
class EC2Instance(Base):
    """
    Tracks AWS EC2 instances used by the platform.
    Intentionally NOT scoped to a tenant — one instance can host apps
    from multiple tenants (proper multi-tenant SaaS design).
    """
    __tablename__ = 'ec2_instances'

    id                   = Column(GUID, primary_key=True, default=_uuid)
    instance_id          = Column(String(50), unique=True, nullable=False)  # AWS i-xxxxx
    public_ip            = Column(String(50))
    private_ip           = Column(String(50))
    instance_type        = Column(String(50), nullable=False)  # t3.micro, etc.
    region               = Column(String(50), nullable=False)
    availability_zone    = Column(String(50))
    status               = Column(String(50), default='pending')  # running | stopped | terminated
    max_applications     = Column(Integer, default=10)
    current_applications = Column(Integer, default=0)
    security_group_id    = Column(String(50))
    created_at           = Column(DateTime, default=datetime.utcnow)
    last_health_check    = Column(DateTime)

    # relationships
    application_mappings = relationship('ApplicationInstance', back_populates='instance',
                                        cascade='all, delete-orphan')
    metrics              = relationship('InstanceMetric', back_populates='instance',
                                        cascade='all, delete-orphan')

    def __repr__(self):
        return f'<EC2Instance id={self.instance_id!r} ip={self.public_ip!r} status={self.status!r}>'

    def to_dict(self):
        return {
            'id': self.id,
            'instance_id': self.instance_id,
            'public_ip': self.public_ip,
            'instance_type': self.instance_type,
            'region': self.region,
            'status': self.status,
            'current_applications': self.current_applications,
            'created_at': self.created_at.isoformat() if self.created_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 3. Application
# ─────────────────────────────────────────────────────────────────────────────
class Application(Base):
    """
    A GitHub repository deployed by the platform.
    Does NOT hold ec2_instance_id — use ApplicationInstance for the mapping.
    """
    __tablename__ = 'applications'
    __table_args__ = (
        UniqueConstraint('tenant_id', 'slug', name='uq_app_tenant_slug'),
    )

    id                = Column(GUID, primary_key=True, default=_uuid)
    tenant_id         = Column(GUID, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    created_by_user_id= Column(GUID)   # FK to users table (added with auth phase)
    name              = Column(String(255), nullable=False)
    slug              = Column(String(100), nullable=False)
    github_url        = Column(Text, nullable=False)
    repo_owner        = Column(String(255))
    repo_name         = Column(String(255))
    branch            = Column(String(100), default='main')
    container_port    = Column(Integer, nullable=False)   # port inside Docker container
    container_name    = Column(String(255))               # Docker container name
    image_name        = Column(String(255))               # Docker image name
    status            = Column(String(50), default='pending')  # pending | active | stopped | failed | deleted
    nginx_enabled     = Column(Boolean, default=True)
    auto_deploy       = Column(Boolean, default=False)
    created_at        = Column(DateTime, default=datetime.utcnow)
    updated_at        = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_deployed_at  = Column(DateTime)

    # relationships
    tenant             = relationship('Tenant', back_populates='applications')
    deployments        = relationship('Deployment', back_populates='application',
                                      cascade='all, delete-orphan')
    instance_mappings  = relationship('ApplicationInstance', back_populates='application',
                                      cascade='all, delete-orphan')
    environment_variables = relationship('EnvironmentVariable', back_populates='application',
                                          cascade='all, delete-orphan')

    def __repr__(self):
        return f'<Application name={self.name!r} status={self.status!r}>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'slug': self.slug,
            'github_url': self.github_url,
            'repo_name': self.repo_name,
            'branch': self.branch,
            'container_port': self.container_port,
            'status': self.status,
            'nginx_enabled': self.nginx_enabled,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_deployed_at': self.last_deployed_at.isoformat() if self.last_deployed_at else None,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 4. ApplicationInstance  (mapping table — many-to-many)
# ─────────────────────────────────────────────────────────────────────────────
class ApplicationInstance(Base):
    """
    Maps an Application to an EC2Instance with a host_port.

    Why separate table?
      - One instance can host many apps (different ports)
      - One app can be on many instances (blue-green, scaling)
      - Historical tracking of where apps were deployed
      - Port conflict prevention per instance
    """
    __tablename__ = 'application_instances'
    __table_args__ = (
        UniqueConstraint('instance_id', 'host_port', name='uq_instance_port'),
    )

    id             = Column(GUID, primary_key=True, default=_uuid)
    application_id = Column(GUID, ForeignKey('applications.id', ondelete='CASCADE'), nullable=False)
    instance_id    = Column(GUID, ForeignKey('ec2_instances.id', ondelete='CASCADE'), nullable=False)
    host_port      = Column(Integer, nullable=False)    # port on the EC2 host (e.g. 8000)
    status         = Column(String(50), default='active')   # active | migrating | removed
    created_at     = Column(DateTime, default=datetime.utcnow)
    removed_at     = Column(DateTime)                   # soft-delete for history

    # relationships
    application = relationship('Application', back_populates='instance_mappings')
    instance    = relationship('EC2Instance', back_populates='application_mappings')

    def __repr__(self):
        return (f'<ApplicationInstance app={self.application_id} '
                f'instance={self.instance_id} port={self.host_port} status={self.status!r}>')


# ─────────────────────────────────────────────────────────────────────────────
# 5. Deployment
# ─────────────────────────────────────────────────────────────────────────────
class Deployment(Base):
    """
    Records every deploy attempt — success or failure.
    This replaces the in-memory dict in deployment_orchestrator.py.
    """
    __tablename__ = 'deployments'

    id                    = Column(GUID, primary_key=True, default=_uuid)
    tenant_id             = Column(GUID, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    application_id        = Column(GUID, ForeignKey('applications.id', ondelete='CASCADE'), nullable=False)
    triggered_by_user_id  = Column(GUID)              # FK to users (added in auth phase)
    short_id              = Column(String(8), default=_short_id)  # display-only, e.g. "8029fe0e"
    github_commit_sha     = Column(String(40))
    github_commit_message = Column(Text)
    status                = Column(String(50), default='pending')  # pending|in_progress|success|failed|cancelled
    error_message         = Column(Text)
    started_at            = Column(DateTime, default=datetime.utcnow)
    completed_at          = Column(DateTime)
    duration_seconds      = Column(Integer)
    deployment_url        = Column(Text)

    # relationships
    tenant      = relationship('Tenant', back_populates='deployments')
    application = relationship('Application', back_populates='deployments')
    steps       = relationship('DeploymentStep', back_populates='deployment',
                               cascade='all, delete-orphan',
                               order_by='DeploymentStep.step_number')
    logs        = relationship('DeploymentLog', back_populates='deployment',
                               cascade='all, delete-orphan',
                               order_by='DeploymentLog.id')

    def __repr__(self):
        return f'<Deployment short_id={self.short_id!r} status={self.status!r}>'

    def to_dict(self):
        return {
            'id': self.id,
            'short_id': self.short_id,
            'application_id': self.application_id,
            'status': self.status,
            'error_message': self.error_message,
            'started_at': self.started_at.isoformat() if self.started_at else None,
            'completed_at': self.completed_at.isoformat() if self.completed_at else None,
            'duration_seconds': self.duration_seconds,
            'deployment_url': self.deployment_url,
            'github_commit_sha': self.github_commit_sha,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 6. DeploymentStep
# ─────────────────────────────────────────────────────────────────────────────
class DeploymentStep(Base):
    """
    Granular step inside a deployment.
    Matches the progress steps shown in the frontend progress bar.
    Examples: 'EC2 Created', 'Docker Installed', 'NGINX Configured', 'Health Check'
    """
    __tablename__ = 'deployment_steps'

    id               = Column(GUID, primary_key=True, default=_uuid)
    deployment_id    = Column(GUID, ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False)
    step_number      = Column(Integer, nullable=False)
    step_name        = Column(String(255), nullable=False)
    status           = Column(String(50), default='pending')  # pending|in_progress|success|failed|skipped
    message          = Column(Text)
    started_at       = Column(DateTime)
    completed_at     = Column(DateTime)
    duration_seconds = Column(Integer)

    # relationships
    deployment = relationship('Deployment', back_populates='steps')

    def __repr__(self):
        return f'<DeploymentStep #{self.step_number} {self.step_name!r} [{self.status}]>'

    def to_dict(self):
        return {
            'step_number': self.step_number,
            'step_name': self.step_name,
            'status': self.status,
            'message': self.message,
            'duration_seconds': self.duration_seconds,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 7. DeploymentLog  (BIGSERIAL PK — high-volume table)
# ─────────────────────────────────────────────────────────────────────────────
class DeploymentLog(Base):
    """
    Individual log lines from a deployment.
    Uses BIGSERIAL (BigInteger auto-increment) instead of UUID for:
      - Faster inserts  (no UUID generation overhead)
      - Smaller indexes (8 bytes vs 16 bytes)
      - Natural ordering by insertion order
    """
    __tablename__ = 'deployment_logs'

    # SQLite note: BigInteger maps to BIGINT which SQLite won't auto-increment.
    # Integer (below) maps to INTEGER — SQLite's native 64-bit auto-increment type.
    # PostgreSQL migration will ALTER to BIGSERIAL when we move to RDS.
    id            = Column(Integer, primary_key=True, autoincrement=True)
    deployment_id = Column(GUID, ForeignKey('deployments.id', ondelete='CASCADE'), nullable=False)
    timestamp     = Column(DateTime, default=datetime.utcnow)
    log_level     = Column(String(20), default='INFO')   # DEBUG | INFO | WARNING | ERROR
    message       = Column(Text, nullable=False)

    # relationships
    deployment = relationship('Deployment', back_populates='logs')

    def __repr__(self):
        return f'<DeploymentLog id={self.id} [{self.log_level}] {(self.message or "")[:60]!r}>'

    def to_dict(self):
        return {
            'id': self.id,
            'timestamp': self.timestamp.isoformat() if self.timestamp else None,
            'log_level': self.log_level,
            'message': self.message,
        }


# ─────────────────────────────────────────────────────────────────────────────
# 8. Secret
# ─────────────────────────────────────────────────────────────────────────────
class Secret(Base):
    """
    Stores ONLY references (ARNs) to secrets in AWS Secrets Manager.
    NEVER stores actual secret values — those stay in AWS.

    Usage:
      1. Secret saved to AWS Secrets Manager -> you receive an ARN
      2. Store ARN here
      3. At runtime: call boto3 to fetch the real value using the ARN
    """
    __tablename__ = 'secrets'

    id               = Column(GUID, primary_key=True, default=_uuid)
    tenant_id        = Column(GUID, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    application_id   = Column(GUID, ForeignKey('applications.id', ondelete='CASCADE'))
    secret_name      = Column(String(255), nullable=False)
    aws_secret_arn   = Column(String(255), nullable=False)       # ONLY reference, never the value
    secret_type      = Column(String(50))                        # database | api_key | oauth | custom
    description      = Column(Text)
    created_at       = Column(DateTime, default=datetime.utcnow)
    last_rotated     = Column(DateTime)
    rotation_enabled = Column(Boolean, default=False)

    # relationships
    tenant   = relationship('Tenant', back_populates='secrets')
    env_vars = relationship('EnvironmentVariable', back_populates='secret')

    def __repr__(self):
        return f'<Secret name={self.secret_name!r} type={self.secret_type!r}>'


# ─────────────────────────────────────────────────────────────────────────────
# 9. EnvironmentVariable
# ─────────────────────────────────────────────────────────────────────────────
class EnvironmentVariable(Base):
    """
    App environment variables with a clear plaintext vs secret distinction.

    value_source = 'plaintext'  → use value_plaintext directly  (e.g. NODE_ENV=production)
    value_source = 'secret'     → look up secret_id in secrets table, fetch ARN, call AWS
    """
    __tablename__ = 'environment_variables'
    __table_args__ = (
        UniqueConstraint('application_id', 'key', name='uq_env_app_key'),
    )

    id                 = Column(GUID, primary_key=True, default=_uuid)
    tenant_id          = Column(GUID, ForeignKey('tenants.id', ondelete='CASCADE'), nullable=False)
    application_id     = Column(GUID, ForeignKey('applications.id', ondelete='CASCADE'), nullable=False)
    key                = Column(String(255), nullable=False)      # variable name, e.g. DATABASE_URL
    value_plaintext    = Column(Text)                             # non-sensitive values only
    value_source       = Column(String(20), nullable=False, default='plaintext')  # 'plaintext' | 'secret'
    secret_id          = Column(GUID, ForeignKey('secrets.id', ondelete='SET NULL'))
    created_at         = Column(DateTime, default=datetime.utcnow)
    updated_at         = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by_user_id = Column(GUID)

    # relationships
    application = relationship('Application', back_populates='environment_variables')
    secret      = relationship('Secret', back_populates='env_vars')

    def __repr__(self):
        return f'<EnvVar key={self.key!r} source={self.value_source!r}>'

    def to_dict(self):
        return {
            'id': self.id,
            'key': self.key,
            'value_source': self.value_source,
            # Never expose value_plaintext or secret ARN in API responses directly
        }


# ─────────────────────────────────────────────────────────────────────────────
# 10. InstanceMetric  (BIGSERIAL PK — high-volume time-series)
# ─────────────────────────────────────────────────────────────────────────────
class InstanceMetric(Base):
    """
    Periodic metric snapshots per EC2 instance (CPU, memory, disk, network).
    Uses BIGSERIAL PK for high-volume write performance.
    Plan for data retention: archive rows older than 30 days.
    """
    __tablename__ = 'instance_metrics'

    # Same SQLite fix as DeploymentLog — Integer here, BIGSERIAL on PostgreSQL.
    id                = Column(Integer, primary_key=True, autoincrement=True)
    instance_id       = Column(GUID, ForeignKey('ec2_instances.id', ondelete='CASCADE'), nullable=False)
    recorded_at       = Column(DateTime, default=datetime.utcnow, nullable=False)
    cpu_usage         = Column(DECIMAL(5, 2))     # percentage  0.00–100.00
    memory_usage      = Column(DECIMAL(5, 2))     # percentage  0.00–100.00
    disk_usage        = Column(DECIMAL(5, 2))     # percentage  0.00–100.00
    network_in_bytes  = Column(BigInteger)
    network_out_bytes = Column(BigInteger)
    active_containers = Column(Integer)

    # relationships
    instance = relationship('EC2Instance', back_populates='metrics')

    def __repr__(self):
        return (f'<InstanceMetric instance={self.instance_id} '
                f'cpu={self.cpu_usage}% mem={self.memory_usage}% @ {self.recorded_at}>')

    def to_dict(self):
        return {
            'id': self.id,
            'recorded_at': self.recorded_at.isoformat() if self.recorded_at else None,
            'cpu_usage': float(self.cpu_usage) if self.cpu_usage is not None else None,
            'memory_usage': float(self.memory_usage) if self.memory_usage is not None else None,
            'disk_usage': float(self.disk_usage) if self.disk_usage is not None else None,
            'network_in_bytes': self.network_in_bytes,
            'network_out_bytes': self.network_out_bytes,
            'active_containers': self.active_containers,
        }
