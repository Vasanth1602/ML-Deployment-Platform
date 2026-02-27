"""initial_schema

Revision ID: 465a230b0d66
Revises: 
Create Date: 2026-02-19 09:05:01.982609

Notes:
  - GUID columns use sa.CHAR(36) — stored as UUID strings in SQLite.
    PostgreSQL migration will use native UUID type instead.
  - render_as_batch=True in env.py handles SQLite's lack of ALTER TABLE.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers
revision: str = '465a230b0d66'
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

GUID = sa.CHAR(36)   # alias for readability — same as our GUID TypeDecorator on SQLite


def upgrade() -> None:
    # ── ec2_instances — platform-owned, no tenant_id ─────────────────────
    op.create_table('ec2_instances',
        sa.Column('id', GUID, nullable=False),
        sa.Column('instance_id', sa.String(length=50), nullable=False),
        sa.Column('public_ip', sa.String(length=50), nullable=True),
        sa.Column('private_ip', sa.String(length=50), nullable=True),
        sa.Column('instance_type', sa.String(length=50), nullable=False),
        sa.Column('region', sa.String(length=50), nullable=False),
        sa.Column('availability_zone', sa.String(length=50), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('max_applications', sa.Integer(), nullable=True),
        sa.Column('current_applications', sa.Integer(), nullable=True),
        sa.Column('security_group_id', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_health_check', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instance_id'),
    )

    # ── tenants ────────────────────────────────────────────────────────────
    op.create_table('tenants',
        sa.Column('id', GUID, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('plan_tier', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('slug'),
    )

    # ── applications ───────────────────────────────────────────────────────
    op.create_table('applications',
        sa.Column('id', GUID, nullable=False),
        sa.Column('tenant_id', GUID, nullable=False),
        sa.Column('created_by_user_id', GUID, nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('slug', sa.String(length=100), nullable=False),
        sa.Column('github_url', sa.Text(), nullable=False),
        sa.Column('repo_owner', sa.String(length=255), nullable=True),
        sa.Column('repo_name', sa.String(length=255), nullable=True),
        sa.Column('branch', sa.String(length=100), nullable=True),
        sa.Column('container_port', sa.Integer(), nullable=False),
        sa.Column('container_name', sa.String(length=255), nullable=True),
        sa.Column('image_name', sa.String(length=255), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('nginx_enabled', sa.Boolean(), nullable=True),
        sa.Column('auto_deploy', sa.Boolean(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('last_deployed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('tenant_id', 'slug', name='uq_app_tenant_slug'),
    )

    # ── instance_metrics — Integer PK (SQLite compat; BIGSERIAL on PG later) ─────────────────────
    op.create_table('instance_metrics',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('instance_id', GUID, nullable=False),
        sa.Column('recorded_at', sa.DateTime(), nullable=False),
        sa.Column('cpu_usage', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('memory_usage', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('disk_usage', sa.DECIMAL(precision=5, scale=2), nullable=True),
        sa.Column('network_in_bytes', sa.BigInteger(), nullable=True),
        sa.Column('network_out_bytes', sa.BigInteger(), nullable=True),
        sa.Column('active_containers', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['instance_id'], ['ec2_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── application_instances — many-to-many mapping ──────────────────────
    op.create_table('application_instances',
        sa.Column('id', GUID, nullable=False),
        sa.Column('application_id', GUID, nullable=False),
        sa.Column('instance_id', GUID, nullable=False),
        sa.Column('host_port', sa.Integer(), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('removed_at', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['instance_id'], ['ec2_instances.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('instance_id', 'host_port', name='uq_instance_port'),
    )

    # ── deployments ────────────────────────────────────────────────────────
    op.create_table('deployments',
        sa.Column('id', GUID, nullable=False),
        sa.Column('tenant_id', GUID, nullable=False),
        sa.Column('application_id', GUID, nullable=False),
        sa.Column('triggered_by_user_id', GUID, nullable=True),
        sa.Column('short_id', sa.String(length=8), nullable=True),
        sa.Column('github_commit_sha', sa.String(length=40), nullable=True),
        sa.Column('github_commit_message', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.Column('deployment_url', sa.Text(), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── secrets — ARN references only ─────────────────────────────────────
    op.create_table('secrets',
        sa.Column('id', GUID, nullable=False),
        sa.Column('tenant_id', GUID, nullable=False),
        sa.Column('application_id', GUID, nullable=True),
        sa.Column('secret_name', sa.String(length=255), nullable=False),
        sa.Column('aws_secret_arn', sa.String(length=255), nullable=False),
        sa.Column('secret_type', sa.String(length=50), nullable=True),
        sa.Column('description', sa.Text(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('last_rotated', sa.DateTime(), nullable=True),
        sa.Column('rotation_enabled', sa.Boolean(), nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── deployment_logs — Integer PK (SQLite compat; BIGSERIAL on PG later) ──────────────────────
    op.create_table('deployment_logs',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('deployment_id', GUID, nullable=False),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.Column('log_level', sa.String(length=20), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── deployment_steps ──────────────────────────────────────────────────
    op.create_table('deployment_steps',
        sa.Column('id', GUID, nullable=False),
        sa.Column('deployment_id', GUID, nullable=False),
        sa.Column('step_number', sa.Integer(), nullable=False),
        sa.Column('step_name', sa.String(length=255), nullable=False),
        sa.Column('status', sa.String(length=50), nullable=True),
        sa.Column('message', sa.Text(), nullable=True),
        sa.Column('started_at', sa.DateTime(), nullable=True),
        sa.Column('completed_at', sa.DateTime(), nullable=True),
        sa.Column('duration_seconds', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['deployment_id'], ['deployments.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )

    # ── environment_variables ─────────────────────────────────────────────
    op.create_table('environment_variables',
        sa.Column('id', GUID, nullable=False),
        sa.Column('tenant_id', GUID, nullable=False),
        sa.Column('application_id', GUID, nullable=False),
        sa.Column('key', sa.String(length=255), nullable=False),
        sa.Column('value_plaintext', sa.Text(), nullable=True),
        sa.Column('value_source', sa.String(length=20), nullable=False),
        sa.Column('secret_id', GUID, nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.Column('created_by_user_id', GUID, nullable=True),
        sa.ForeignKeyConstraint(['application_id'], ['applications.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['secret_id'], ['secrets.id'], ondelete='SET NULL'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenants.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('application_id', 'key', name='uq_env_app_key'),
    )


def downgrade() -> None:
    op.drop_table('environment_variables')
    op.drop_table('deployment_steps')
    op.drop_table('deployment_logs')
    op.drop_table('secrets')
    op.drop_table('deployments')
    op.drop_table('application_instances')
    op.drop_table('instance_metrics')
    op.drop_table('applications')
    op.drop_table('tenants')
    op.drop_table('ec2_instances')
