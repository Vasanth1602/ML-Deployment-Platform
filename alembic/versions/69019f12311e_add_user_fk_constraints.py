"""add_user_fk_constraints

Revision ID: 69019f12311e
Revises: 72974bdac6e8
Create Date: 2026-03-11 14:00:00.000000

Adds FK constraints to already-existing nullable columns:
  - applications.created_by_user_id   → users.id
  - deployments.triggered_by_user_id  → users.id

NOTE: The columns already exist (added by a previous architect anticipating auth).
      This migration only adds the FK relationship — it does NOT add columns.

FIX: Migration b1c2d3e4f5a6 converted all UUID FK columns (including
     applications.created_by_user_id / deployments.triggered_by_user_id) to
     native PostgreSQL UUID. However, migration 72974bdac6e8 created users.id
     as CHAR(36), causing a type mismatch when adding the FK.
     This migration first converts users.id → native UUID, then adds the FKs.
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers, used by Alembic.
revision: str = '69019f12311e'
down_revision: Union[str, None] = '72974bdac6e8'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _is_postgresql() -> bool:
    return op.get_bind().dialect.name == 'postgresql'


def upgrade() -> None:
    # ── Step 1: Convert users.id from CHAR(36) → native UUID (PostgreSQL only)
    # This is required because b1c2d3e4f5a6 already converted the FK columns
    # on the referencing tables to native UUID, so types must match.
    if _is_postgresql():
        op.execute(
            "ALTER TABLE users ALTER COLUMN id TYPE UUID USING id::uuid"
        )

    # ── Step 2: Add FK constraints now that types are compatible
    # applications.created_by_user_id → users.id
    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_applications_created_by_user',
            'users',
            ['created_by_user_id'], ['id'],
            ondelete='SET NULL',
        )

    # deployments.triggered_by_user_id → users.id
    with op.batch_alter_table('deployments', schema=None) as batch_op:
        batch_op.create_foreign_key(
            'fk_deployments_triggered_by_user',
            'users',
            ['triggered_by_user_id'], ['id'],
            ondelete='SET NULL',
        )


def downgrade() -> None:
    with op.batch_alter_table('deployments', schema=None) as batch_op:
        batch_op.drop_constraint('fk_deployments_triggered_by_user', type_='foreignkey')

    with op.batch_alter_table('applications', schema=None) as batch_op:
        batch_op.drop_constraint('fk_applications_created_by_user', type_='foreignkey')

    # Revert users.id back to CHAR(36)
    if _is_postgresql():
        op.execute(
            "ALTER TABLE users ALTER COLUMN id TYPE CHAR(36) USING id::text"
        )
