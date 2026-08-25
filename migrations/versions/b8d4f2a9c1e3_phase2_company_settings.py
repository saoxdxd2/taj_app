"""Phase 2: company settings (legal identity printed on factures)

Revision ID: b8d4f2a9c1e3
Revises: a7c3e9f1b2d4
Create Date: 2026-08-25 22:05:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b8d4f2a9c1e3'
down_revision: Union[str, Sequence[str], None] = 'a7c3e9f1b2d4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('company_settings',
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('company_name', sa.String(length=150), nullable=False,
                  server_default='TAJ FROID'),
        sa.Column('ice_number', sa.String(length=50), nullable=True),
        sa.Column('rc_number', sa.String(length=50), nullable=True),
        sa.Column('if_number', sa.String(length=50), nullable=True),
        sa.Column('patente_number', sa.String(length=50), nullable=True),
        sa.Column('cnss_number', sa.String(length=50), nullable=True),
        sa.Column('address_street', sa.String(length=255), nullable=True),
        sa.Column('address_city', sa.String(length=100), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('email', sa.String(length=255), nullable=True),
        sa.Column('bank_name', sa.String(length=100), nullable=True),
        sa.Column('bank_rib', sa.String(length=50), nullable=True),
        sa.Column('invoice_footer_note', sa.String(length=500), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('company_settings')