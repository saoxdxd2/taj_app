"""Add payment accounts, payment method catalog and account movements

Revision ID: a2f4c6d8e0b1
Revises: f6c8d0e3a4b5
Create Date: 2026-11-22 19:30:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a2f4c6d8e0b1'
down_revision: Union[str, Sequence[str], None] = 'f6c8d0e3a4b5'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _base_columns():
    """Standard audit columns shared by every BaseModel table."""
    return [
        sa.Column('id', sa.Integer(), autoincrement=True, nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('updated_at', sa.DateTime(timezone=True), nullable=True),
    ]


def upgrade() -> None:
    """Upgrade schema."""
    # --- payment_account (cash drawer or bank account) ---
    op.create_table('payment_account',
        *_base_columns(),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('account_number', sa.String(length=100), nullable=True),
        sa.Column('bank', sa.String(length=100), nullable=True),
        sa.Column('account_type', sa.Enum('CASH', 'BANK', name='accounttype'),
                  nullable=False),
        sa.Column('opening_balance', sa.Numeric(12, 2), nullable=False,
                  server_default='0.00'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payment_account_name'), 'payment_account', ['name'], unique=True)

    # --- payment_method_option (moyens de paiement) ---
    op.create_table('payment_method_option',
        *_base_columns(),
        sa.Column('name', sa.String(length=50), nullable=False),
        sa.Column('description', sa.String(length=255), nullable=True),
        sa.Column('requires_reference', sa.Boolean(), nullable=False, server_default='0'),
        sa.Column('deposit_account_id', sa.Integer(), nullable=True),
        sa.Column('withdrawal_account_id', sa.Integer(), nullable=True),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.Column('sort_order', sa.Integer(), nullable=False, server_default='0'),
        sa.ForeignKeyConstraint(['deposit_account_id'], ['payment_account.id']),
        sa.ForeignKeyConstraint(['withdrawal_account_id'], ['payment_account.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payment_method_option_name'),
                    'payment_method_option', ['name'], unique=True)

    # --- account_movement (append-only ledger) ---
    op.create_table('account_movement',
        *_base_columns(),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('direction', sa.Enum('IN', 'OUT', name='movementdirection'),
                  nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('movement_date', sa.DateTime(), nullable=False),
        sa.Column('movement_type', sa.Enum(
            'DEPOSIT', 'WITHDRAWAL', 'TRANSFER', 'SALE_PAYMENT',
            'PURCHASE_PAYMENT', 'EXPENSE', 'ADJUSTMENT', name='movementtype',
        ), nullable=False),
        sa.Column('method_id', sa.Integer(), nullable=True),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('description', sa.String(length=255), nullable=False),
        sa.Column('transfer_group', sa.String(length=36), nullable=True),
        sa.Column('user_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['payment_account.id']),
        sa.ForeignKeyConstraint(['method_id'], ['payment_method_option.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_account_movement_account_id'), 'account_movement', ['account_id'])
    op.create_index(op.f('ix_account_movement_direction'), 'account_movement', ['direction'])
    op.create_index(op.f('ix_account_movement_movement_date'), 'account_movement', ['movement_date'])
    op.create_index(op.f('ix_account_movement_transfer_group'), 'account_movement', ['transfer_group'])

    # Seed the five methods shown in the reference screens. Accounts are
    # intentionally not seeded: they belong to the shop and are created
    # from the Accounts tab.
    op.bulk_insert(
        sa.table(
            'payment_method_option',
            sa.column('name', sa.String),
            sa.column('description', sa.String),
            sa.column('requires_reference', sa.Boolean),
            sa.column('is_active', sa.Boolean),
            sa.column('sort_order', sa.Integer),
        ),
        [
            {'name': 'Virement bancaire', 'description': 'Virement bancaire',
             'requires_reference': True, 'is_active': True, 'sort_order': 1},
            {'name': 'Espèce', 'description': 'Paiement en espèces',
             'requires_reference': False, 'is_active': True, 'sort_order': 2},
            {'name': 'TPE', 'description': 'Terminal de paiement électronique',
             'requires_reference': True, 'is_active': True, 'sort_order': 3},
            {'name': 'Chèque', 'description': 'Chèque bancaire',
             'requires_reference': True, 'is_active': True, 'sort_order': 4},
            {'name': 'Versement', 'description': 'Versement en agence',
             'requires_reference': False, 'is_active': True, 'sort_order': 5},
        ],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_account_movement_transfer_group'), table_name='account_movement')
    op.drop_index(op.f('ix_account_movement_movement_date'), table_name='account_movement')
    op.drop_index(op.f('ix_account_movement_direction'), table_name='account_movement')
    op.drop_index(op.f('ix_account_movement_account_id'), table_name='account_movement')
    op.drop_table('account_movement')

    op.drop_index(op.f('ix_payment_method_option_name'), table_name='payment_method_option')
    op.drop_table('payment_method_option')

    op.drop_index(op.f('ix_payment_account_name'), table_name='payment_account')
    op.drop_table('payment_account')
