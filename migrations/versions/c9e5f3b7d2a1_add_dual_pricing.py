"""Add dual pricing fields to product table

Revision ID: c9e5f3b7d2a1
Revises: b8d4f2a9c1e3
Create Date: 2026-09-08 21:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'c9e5f3b7d2a1'
down_revision: Union[str, Sequence[str], None] = 'b8d4f2a9c1e3'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('product') as batch:
        batch.add_column(sa.Column('sale_price_website', sa.Numeric(12, 2), nullable=False, server_default='0.00'))
        batch.add_column(sa.Column('total_sold_website', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('total_sold_store', sa.Integer(), nullable=False, server_default='0'))
        batch.add_column(sa.Column('revenue_website', sa.Numeric(15, 2), nullable=False, server_default='0.00'))
        batch.add_column(sa.Column('revenue_store', sa.Numeric(15, 2), nullable=False, server_default='0.00'))
    
    with op.batch_alter_table('invoice') as batch:
        batch.add_column(sa.Column('channel', sa.Enum('WEBSITE', 'STORE', 'MOBILE_APP', name='salechannel'), nullable=False, server_default='STORE'))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('invoice') as batch:
        batch.drop_column('channel')
    
    with op.batch_alter_table('product') as batch:
        batch.drop_column('revenue_store')
        batch.drop_column('revenue_website')
        batch.drop_column('total_sold_store')
        batch.drop_column('total_sold_website')
        batch.drop_column('sale_price_website')
