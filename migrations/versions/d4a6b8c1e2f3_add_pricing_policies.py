"""Add pricing policies table (volume tiers and customer-specific discounts)

Revision ID: d4a6b8c1e2f3
Revises: c9e5f3b7d2a1
Create Date: 2026-09-26 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd4a6b8c1e2f3'
down_revision: Union[str, Sequence[str], None] = 'c9e5f3b7d2a1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('pricing_policy',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('product_id', sa.Integer(), nullable=False),
        # NULL means a global policy applying to every customer.
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('min_quantity', sa.Integer(), nullable=False, server_default='1'),
        sa.Column('discount_percent', sa.Numeric(precision=5, scale=2), nullable=False, server_default='0.00'),
        # Reuses the existing salechannel enum; SQLAlchemy stores enum NAMES.
        sa.Column('channel', sa.Enum('WEBSITE', 'STORE', 'MOBILE_APP', name='salechannel'), nullable=False, server_default='STORE'),
        sa.Column('valid_from', sa.DateTime(), nullable=False),
        sa.Column('valid_until', sa.DateTime(), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('label', sa.String(length=100), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.ForeignKeyConstraint(['product_id'], ['product.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
    )
    op.create_index('ix_pricing_policy_product_id', 'pricing_policy', ['product_id'])
    op.create_index('ix_pricing_policy_customer_id', 'pricing_policy', ['customer_id'])
    # The pricing query filters on product + quantity.
    op.create_index('ix_pricing_policy_lookup', 'pricing_policy', ['product_id', 'min_quantity'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_pricing_policy_lookup', table_name='pricing_policy')
    op.drop_index('ix_pricing_policy_customer_id', table_name='pricing_policy')
    op.drop_index('ix_pricing_policy_product_id', table_name='pricing_policy')
    op.drop_table('pricing_policy')
