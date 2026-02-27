"""Convert CHAR(36) UUID columns to native PostgreSQL UUID type

Revision ID: b1c2d3e4f5a6
Revises: 465a230b0d66
Create Date: 2026-02-23

Why this migration exists:
    The initial schema (465a230b0d66) used CHAR(36) for all UUID columns
    because the project started with SQLite (which has no native UUID type).
    
    When migrated to PostgreSQL, the GUID TypeDecorator in models.py correctly
    uses native UUID type — but the actual DB columns are still CHAR(36).
    
    PostgreSQL refuses to compare CHAR vs UUID without an explicit cast:
        "operator does not exist: character varying = uuid"
    
    This migration converts ALL UUID primary keys and foreign keys from
    CHAR(36) → UUID using PostgreSQL's USING cast.
    
    SQLite note: downgrade() is a no-op on SQLite (CHAR(36) stays as-is).
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector


# revision identifiers
revision: str = 'b1c2d3e4f5a6'
down_revision: Union[str, None] = '465a230b0d66'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# All UUID columns grouped by table: (table, column)
# Order matters — FK columns must be converted after the PK they reference
UUID_COLUMNS = [
    # Tables with no FK dependencies first
    ('tenants',               'id'),
    ('ec2_instances',         'id'),

    # Applications depends on tenants
    ('applications',          'id'),
    ('applications',          'tenant_id'),
    ('applications',          'created_by_user_id'),

    # Deployments depends on tenants + applications
    ('deployments',           'id'),
    ('deployments',           'tenant_id'),
    ('deployments',           'application_id'),
    ('deployments',           'triggered_by_user_id'),

    # Deployment steps
    ('deployment_steps',      'id'),
    ('deployment_steps',      'deployment_id'),

    # Deployment logs (FK to deployments)
    ('deployment_logs',       'deployment_id'),

    # Application instances (FK to applications + ec2_instances)
    ('application_instances', 'id'),
    ('application_instances', 'application_id'),
    ('application_instances', 'instance_id'),

    # Instance metrics (FK to ec2_instances)
    ('instance_metrics',      'instance_id'),

    # Secrets
    ('secrets',               'id'),
    ('secrets',               'tenant_id'),
    ('secrets',               'application_id'),

    # Environment variables
    ('environment_variables', 'id'),
    ('environment_variables', 'tenant_id'),
    ('environment_variables', 'application_id'),
    ('environment_variables', 'created_by_user_id'),
    ('environment_variables', 'secret_id'),
]


def is_postgresql() -> bool:
    return op.get_bind().dialect.name == 'postgresql'


def upgrade() -> None:
    if not is_postgresql():
        # SQLite doesn't support ALTER COLUMN — nothing to do
        return

    conn = op.get_bind()

    # Drop FK constraints first (PostgreSQL won't let you ALTER a column
    # that is referenced by a FK constraint)
    # We'll recreate them after conversion.
    conn.execute(sa.text("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN (
                SELECT tc.constraint_name, tc.table_name
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
            ) LOOP
                EXECUTE 'ALTER TABLE ' || quote_ident(r.table_name) ||
                        ' DROP CONSTRAINT IF EXISTS ' || quote_ident(r.constraint_name) || ' CASCADE';
            END LOOP;
        END;
        $$;
    """))

    # Convert each UUID column from CHAR(36) → UUID
    for table, column in UUID_COLUMNS:
        conn.execute(sa.text(f"""
            ALTER TABLE {table}
            ALTER COLUMN {column}
            TYPE UUID USING {column}::UUID;
        """))

    # Recreate foreign key constraints
    fk_constraints = [
        # (child_table, child_col, parent_table, parent_col, name, on_delete)
        ('applications',          'tenant_id',      'tenants',      'id', None,                  'CASCADE'),
        ('deployments',           'tenant_id',      'tenants',      'id', None,                  'CASCADE'),
        ('deployments',           'application_id', 'applications', 'id', None,                  'CASCADE'),
        ('deployment_steps',      'deployment_id',  'deployments',  'id', None,                  'CASCADE'),
        ('deployment_logs',       'deployment_id',  'deployments',  'id', None,                  'CASCADE'),
        ('application_instances', 'application_id', 'applications', 'id', None,                  'CASCADE'),
        ('application_instances', 'instance_id',    'ec2_instances','id', None,                  'CASCADE'),
        ('instance_metrics',      'instance_id',    'ec2_instances','id', None,                  'CASCADE'),
        ('secrets',               'tenant_id',      'tenants',      'id', None,                  'CASCADE'),
        ('secrets',               'application_id', 'applications', 'id', None,                  'CASCADE'),
        ('environment_variables', 'tenant_id',      'tenants',      'id', None,                  'CASCADE'),
        ('environment_variables', 'application_id', 'applications', 'id', None,                  'CASCADE'),
        ('environment_variables', 'secret_id',      'secrets',      'id', None,                  'SET NULL'),
    ]

    for child_table, child_col, parent_table, parent_col, fk_name, on_delete in fk_constraints:
        if fk_name is None:
            fk_name = f'fk_{child_table}_{child_col}'
        conn.execute(sa.text(f"""
            ALTER TABLE {child_table}
            ADD CONSTRAINT {fk_name}
            FOREIGN KEY ({child_col})
            REFERENCES {parent_table}({parent_col})
            ON DELETE {on_delete};
        """))


def downgrade() -> None:
    if not is_postgresql():
        return

    conn = op.get_bind()

    # Drop recreated FK constraints
    conn.execute(sa.text("""
        DO $$
        DECLARE r RECORD;
        BEGIN
            FOR r IN (
                SELECT tc.constraint_name, tc.table_name
                FROM information_schema.table_constraints tc
                WHERE tc.constraint_type = 'FOREIGN KEY'
                  AND tc.table_schema = 'public'
            ) LOOP
                EXECUTE 'ALTER TABLE ' || quote_ident(r.table_name) ||
                        ' DROP CONSTRAINT IF EXISTS ' || quote_ident(r.constraint_name) || ' CASCADE';
            END LOOP;
        END;
        $$;
    """))

    # Convert back to CHAR(36)
    for table, column in reversed(UUID_COLUMNS):
        conn.execute(sa.text(f"""
            ALTER TABLE {table}
            ALTER COLUMN {column}
            TYPE CHAR(36) USING {column}::TEXT;
        """))
