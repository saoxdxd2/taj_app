"""Add supplier invoice import fields and layout profiles

Revision ID: d1e2f3a4b5c6
Revises: c9d1e3f5a7b9
Create Date: 2026-11-22 22:36:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'd1e2f3a4b5c6'
down_revision: Union[str, Sequence[str], None] = 'c9d1e3f5a7b9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns():
    return [
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('purchase') as batch:
        batch.add_column(sa.Column('purchase_date', sa.Date(), nullable=True))
        batch.add_column(sa.Column('supplier_invoice_no', sa.String(length=50), nullable=True))
        batch.add_column(sa.Column('source_file_hash', sa.String(length=64), nullable=True))
        batch.add_column(sa.Column('source_file_name', sa.String(length=255), nullable=True))
        batch.create_index(op.f('ix_purchase_supplier_invoice_no'), ['supplier_invoice_no'])
        batch.create_index(op.f('ix_purchase_source_file_hash'), ['source_file_hash'])
        batch.create_unique_constraint(
            'uq_purchase_supplier_invoice', ['supplier_id', 'supplier_invoice_no']
        )

    op.create_table(
        'supplier_invoice_profile',
        *_base_columns(),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.Column('name', sa.String(length=255), nullable=False),
        sa.Column('fingerprint', sa.String(length=40), nullable=False),
        sa.Column('rules_json', sa.Text(), nullable=False),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('last_used_at', sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('supplier_id', 'fingerprint', name='uq_supplier_invoice_profile'),
    )
    op.create_index(
        op.f('ix_supplier_invoice_profile_supplier_id'),
        'supplier_invoice_profile', ['supplier_id'],
    )
    op.create_index(
        op.f('ix_supplier_invoice_profile_fingerprint'),
        'supplier_invoice_profile', ['fingerprint'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_supplier_invoice_profile_fingerprint'), table_name='supplier_invoice_profile')
    op.drop_index(op.f('ix_supplier_invoice_profile_supplier_id'), table_name='supplier_invoice_profile')
    op.drop_table('supplier_invoice_profile')

    with op.batch_alter_table('purchase') as batch:
        batch.drop_constraint('uq_purchase_supplier_invoice', type_='unique')
        batch.drop_index(op.f('ix_purchase_source_file_hash'))
        batch.drop_index(op.f('ix_purchase_supplier_invoice_no'))
        batch.drop_column('source_file_name')
        batch.drop_column('source_file_hash')
        batch.drop_column('supplier_invoice_no')
        batch.drop_column('purchase_date')
