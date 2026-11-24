"""Add pinned price to product table

Revision ID: c2f9e1a4b7d6
Revises: a1b2c3d4e5f6
Create Date: 2026-11-24 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c2f9e1a4b7d6'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('product') as batch:
        batch.add_column(sa.Column('pinned_price', sa.Numeric(12, 2), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('product') as batch:
        batch.drop_column('pinned_price')
