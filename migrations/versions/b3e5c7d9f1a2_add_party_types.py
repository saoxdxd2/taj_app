"""Add party type (Entreprise/Individuel) and individual names

Revision ID: b3e5c7d9f1a2
Revises: a2f4c6d8e0b1
Create Date: 2026-11-22 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'b3e5c7d9f1a2'
down_revision: Union[str, Sequence[str], None] = 'a2f4c6d8e0b1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Existing rows are companies; individuals get first/last names."""
    for table in ('customer', 'supplier'):
        op.add_column(
            table,
            sa.Column(
                'party_type',
                sa.Enum('ENTERPRISE', 'INDIVIDUAL', name='partytype'),
                nullable=False,
                server_default='ENTERPRISE',
            ),
        )
        op.add_column(table, sa.Column('first_name', sa.String(length=100), nullable=True))
        op.add_column(table, sa.Column('last_name', sa.String(length=100), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    for table in ('customer', 'supplier'):
        with op.batch_alter_table(table) as batch:
            batch.drop_column('last_name')
            batch.drop_column('first_name')
            batch.drop_column('party_type')
