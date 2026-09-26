"""Add system_setting table (configurable operational values)

Revision ID: e5b7c9d2f3a4
Revises: d4a6b8c1e2f3
Create Date: 2026-09-26 10:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'e5b7c9d2f3a4'
down_revision: Union[str, Sequence[str], None] = 'd4a6b8c1e2f3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('system_setting',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        # `key` is the natural identifier (unique); `id` stays the PK.
        sa.Column('key', sa.String(length=100), nullable=False),
        sa.Column('value', sa.String(length=500), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        # Plain indexed id (no FK), matching AuditEvent.user_id.
        sa.Column('updated_by', sa.Integer(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_system_setting_key', 'system_setting', ['key'], unique=True)
    op.create_index('ix_system_setting_updated_by', 'system_setting', ['updated_by'])

    # Seed the known keys with their defaults so the settings UI and the
    # services can rely on a complete, consistent set. These reproduce the
    # values that were previously hardcoded in backup.py / logging.py.
    op.bulk_insert(
        sa.table(
            'system_setting',
            sa.column('key', sa.String),
            sa.column('value', sa.String),
            sa.column('description', sa.String),
        ),
        [
            {'key': 'backup.retention.count', 'value': '15',
             'description': 'How many database backups to keep on disk'},
            {'key': 'backup.disk_space.min_mb', 'value': '50',
             'description': 'Minimum free disk space (MB) required before a backup runs'},
            {'key': 'log.rotation.size_mb', 'value': '10',
             'description': 'Rotate the log file once it reaches this size (MB)'},
            {'key': 'log.retention.days', 'value': '30',
             'description': 'Delete rotated log files after this many days'},
            {'key': 'sales.warranty.default_months', 'value': '12',
             'description': 'Default warranty applied to a new invoice line'},
            {'key': 'sales.invoice.prefix', 'value': 'N°',
             'description': 'Prefix used when generating invoice numbers'},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_system_setting_updated_by', table_name='system_setting')
    op.drop_index('ix_system_setting_key', table_name='system_setting')
    op.drop_table('system_setting')
