"""Add imported bank statements and reconciliation tables

Revision ID: c9d1e3f5a7b9
Revises: b3e5c7d9f1a2
Create Date: 2026-11-22 20:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = 'c9d1e3f5a7b9'
down_revision: Union[str, Sequence[str], None] = 'b3e5c7d9f1a2'
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
    op.create_table(
        'bank_statement',
        *_base_columns(),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('file_name', sa.String(length=255), nullable=False),
        sa.Column('file_hash', sa.String(length=64), nullable=False),
        sa.Column('bank_profile', sa.String(length=50), nullable=False),
        sa.Column('account_number', sa.String(length=50), nullable=True),
        sa.Column('period_start', sa.Date(), nullable=True),
        sa.Column('period_end', sa.Date(), nullable=True),
        sa.Column('opening_balance', sa.Numeric(12, 2), nullable=True),
        sa.Column('closing_balance', sa.Numeric(12, 2), nullable=True),
        sa.Column('declared_debit_total', sa.Numeric(12, 2), nullable=True),
        sa.Column('declared_credit_total', sa.Numeric(12, 2), nullable=True),
        sa.Column('status', sa.Enum('OPEN', 'RECONCILED', name='statementstatus'),
                  nullable=False, server_default='OPEN'),
        sa.Column('reconciled_at', sa.DateTime(), nullable=True),
        sa.Column('imported_by', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['payment_account.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bank_statement_account_id'), 'bank_statement', ['account_id'])
    op.create_index(op.f('ix_bank_statement_file_hash'), 'bank_statement', ['file_hash'], unique=True)

    op.create_table(
        'bank_transaction',
        *_base_columns(),
        sa.Column('statement_id', sa.Integer(), nullable=False),
        sa.Column('line_no', sa.Integer(), nullable=False),
        sa.Column('operation_date', sa.Date(), nullable=False),
        sa.Column('value_date', sa.Date(), nullable=True),
        sa.Column('label', sa.String(length=255), nullable=False),
        sa.Column('details', sa.Text(), nullable=True),
        sa.Column('debit', sa.Numeric(12, 2), nullable=True),
        sa.Column('credit', sa.Numeric(12, 2), nullable=True),
        sa.Column('counterparty', sa.String(length=150), nullable=True),
        sa.Column('counterparty_rib', sa.String(length=50), nullable=True),
        sa.Column('reference', sa.String(length=50), nullable=True),
        sa.Column('category', sa.Enum(
            'UNCLASSIFIED', 'CUSTOMER_RECEIPT', 'CUSTOMER_CHEQUE_BATCH',
            'SUPPLIER_PAYMENT', 'CHEQUE_ISSUED', 'BANK_FEE', 'TAX',
            'INTERNAL_TRANSFER', 'OTHER', name='transactioncategory',
        ), nullable=False, server_default='UNCLASSIFIED'),
        sa.Column('status', sa.Enum('PENDING', 'MATCHED', 'IGNORED',
                                    name='transactionstatus'),
                  nullable=False, server_default='PENDING'),
        sa.Column('match_method', sa.Enum('MANUAL', 'SUGGESTED', 'RULE',
                                          name='matchmethod'), nullable=True),
        sa.Column('match_note', sa.String(length=255), nullable=True),
        sa.ForeignKeyConstraint(['statement_id'], ['bank_statement.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bank_transaction_statement_id'), 'bank_transaction', ['statement_id'])
    op.create_index(op.f('ix_bank_transaction_operation_date'), 'bank_transaction', ['operation_date'])
    op.create_index(op.f('ix_bank_transaction_status'), 'bank_transaction', ['status'])

    op.create_table(
        'bank_allocation',
        *_base_columns(),
        sa.Column('transaction_id', sa.Integer(), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('purchase_id', sa.Integer(), nullable=True),
        sa.Column('payment_id', sa.Integer(), nullable=True),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.ForeignKeyConstraint(['transaction_id'], ['bank_transaction.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoice.id']),
        sa.ForeignKeyConstraint(['purchase_id'], ['purchase.id']),
        sa.ForeignKeyConstraint(['payment_id'], ['payment.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bank_allocation_transaction_id'), 'bank_allocation', ['transaction_id'])
    op.create_index(op.f('ix_bank_allocation_invoice_id'), 'bank_allocation', ['invoice_id'])
    op.create_index(op.f('ix_bank_allocation_purchase_id'), 'bank_allocation', ['purchase_id'])

    op.create_table(
        'bank_rule',
        *_base_columns(),
        sa.Column('name', sa.String(length=100), nullable=False),
        sa.Column('pattern', sa.String(length=255), nullable=False),
        sa.Column('direction', sa.Enum('ANY', 'IN', 'OUT', name='ruledirection'),
                  nullable=False, server_default='ANY'),
        sa.Column('category', sa.Enum(
            'UNCLASSIFIED', 'CUSTOMER_RECEIPT', 'CUSTOMER_CHEQUE_BATCH',
            'SUPPLIER_PAYMENT', 'CHEQUE_ISSUED', 'BANK_FEE', 'TAX',
            'INTERNAL_TRANSFER', 'OTHER', name='transactioncategory',
        ), nullable=False),
        sa.Column('counterparty', sa.String(length=150), nullable=True),
        sa.Column('priority', sa.Integer(), nullable=False, server_default='100'),
        sa.Column('is_active', sa.Boolean(), nullable=False, server_default='1'),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_bank_rule_name'), 'bank_rule', ['name'], unique=True)

    op.create_table(
        'bank_counterparty',
        *_base_columns(),
        sa.Column('account_id', sa.Integer(), nullable=False),
        sa.Column('rib', sa.String(length=50), nullable=False),
        sa.Column('name', sa.String(length=150), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(['account_id'], ['payment_account.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier.id']),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('account_id', 'rib', name='uq_bank_counterparty_rib'),
    )
    op.create_index(op.f('ix_bank_counterparty_account_id'), 'bank_counterparty', ['account_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_bank_counterparty_account_id'), table_name='bank_counterparty')
    op.drop_table('bank_counterparty')

    op.drop_index(op.f('ix_bank_rule_name'), table_name='bank_rule')
    op.drop_table('bank_rule')

    op.drop_index(op.f('ix_bank_allocation_purchase_id'), table_name='bank_allocation')
    op.drop_index(op.f('ix_bank_allocation_invoice_id'), table_name='bank_allocation')
    op.drop_index(op.f('ix_bank_allocation_transaction_id'), table_name='bank_allocation')
    op.drop_table('bank_allocation')

    op.drop_index(op.f('ix_bank_transaction_status'), table_name='bank_transaction')
    op.drop_index(op.f('ix_bank_transaction_operation_date'), table_name='bank_transaction')
    op.drop_index(op.f('ix_bank_transaction_statement_id'), table_name='bank_transaction')
    op.drop_table('bank_transaction')

    op.drop_index(op.f('ix_bank_statement_file_hash'), table_name='bank_statement')
    op.drop_index(op.f('ix_bank_statement_account_id'), table_name='bank_statement')
    op.drop_table('bank_statement')
