"""Add mobile scan inbox table

Revision ID: a1b2c3d4e5f6
Revises: f6c8d0e3a4b5
Create Date: 2026-11-23 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = 'd1e2f3a4b5c6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        'mobile_scan',
        sa.Column('relay_scan_id', sa.String(length=36), nullable=False),
        sa.Column('client_id', sa.String(length=36), nullable=True),
        sa.Column('captured_at', sa.DateTime(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='uploaded'),
        sa.Column('local_file_path', sa.String(length=500), nullable=True),
        sa.Column('file_hash', sa.String(length=64), nullable=True),
        sa.Column('purchase_id', sa.Integer(), sa.ForeignKey('purchase.id'), nullable=True),
        sa.Column('purchase_reference', sa.String(length=50), nullable=True),
        sa.Column('message', sa.String(length=500), nullable=True),
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('relay_scan_id'),
    )
    with op.batch_alter_table('mobile_scan') as batch:
        batch.create_index(batch.f('ix_mobile_scan_relay_scan_id'), ['relay_scan_id'], unique=True)
        batch.create_index(batch.f('ix_mobile_scan_status'), ['status'], unique=False)
        batch.create_index(batch.f('ix_mobile_scan_file_hash'), ['file_hash'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('mobile_scan') as batch:
        batch.drop_index(batch.f('ix_mobile_scan_file_hash'))
        batch.drop_index(batch.f('ix_mobile_scan_status'))
        batch.drop_index(batch.f('ix_mobile_scan_relay_scan_id'))
    op.drop_table('mobile_scan')