"""Phase 1 core ERP: payments, checks, deposits, returns, warranty, attributes

Revision ID: a7c3e9f1b2d4
Revises: 1d48d6ed797c
Create Date: 2026-08-25 20:25:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a7c3e9f1b2d4'
down_revision: Union[str, Sequence[str], None] = '1d48d6ed797c'
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
    # --- New columns on existing tables (SQLite-safe batch mode) ---
    with op.batch_alter_table('invoice') as batch:
        batch.add_column(sa.Column('due_date', sa.DateTime(), nullable=True))
        batch.add_column(sa.Column('notes', sa.String(), nullable=True))

    with op.batch_alter_table('invoice_item') as batch:
        batch.add_column(sa.Column('unit_cost', sa.Numeric(12, 2), nullable=False,
                                   server_default='0.00'))
        batch.add_column(sa.Column('description_override', sa.String(length=255), nullable=True))
        batch.add_column(sa.Column('warranty_months', sa.Integer(), nullable=False,
                                   server_default='12'))
        batch.add_column(sa.Column('warranty_end_date', sa.DateTime(), nullable=True))

    with op.batch_alter_table('stock_level') as batch:
        batch.add_column(sa.Column('min_quantity', sa.Integer(), nullable=False,
                                   server_default='0'))

    with op.batch_alter_table('supplier') as batch:
        batch.add_column(sa.Column('payment_terms_days', sa.Integer(), nullable=False,
                                   server_default='0'))

    # --- checks (check ledger / calendrier des chèques) ---
    op.create_table('checks',
        *_base_columns(),
        sa.Column('check_number', sa.String(length=50), nullable=False),
        sa.Column('direction', sa.Enum('INCOMING', 'OUTGOING', name='checkdirection'), nullable=False),
        sa.Column('status', sa.Enum('PENDING', 'DEPOSITED', 'CLEARED', 'BOUNCED', 'CANCELLED', name='checkstatus'),
                  nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('due_date', sa.DateTime(), nullable=False),
        sa.Column('bank', sa.String(length=100), nullable=True),
        sa.Column('party_name', sa.String(length=100), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=True),
        sa.Column('supplier_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.ForeignKeyConstraint(['supplier_id'], ['supplier.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_checks_check_number'), 'checks', ['check_number'])
    op.create_index(op.f('ix_checks_direction'), 'checks', ['direction'])
    op.create_index(op.f('ix_checks_status'), 'checks', ['status'])
    op.create_index(op.f('ix_checks_due_date'), 'checks', ['due_date'])

    # --- payment ---
    op.create_table('payment',
        *_base_columns(),
        sa.Column('invoice_id', sa.Integer(), nullable=False),
        sa.Column('method', sa.Enum('CASH', 'CHECK', 'TRANSFER', name='paymentmethod'), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('check_id', sa.Integer(), nullable=True),
        sa.Column('reference', sa.String(length=100), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoice.id']),
        sa.ForeignKeyConstraint(['check_id'], ['checks.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_payment_invoice_id'), 'payment', ['invoice_id'])

    # --- customer_deposit ('bons') ---
    op.create_table('customer_deposit',
        *_base_columns(),
        sa.Column('deposit_number', sa.String(length=50), nullable=False),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('amount_used', sa.Numeric(12, 2), nullable=False),
        sa.Column('state', sa.Enum('OPEN', 'SETTLED', 'CANCELLED', name='depositstate'), nullable=False),
        sa.Column('method', sa.Enum('CASH', 'CHECK', 'TRANSFER', name='paymentmethod'), nullable=False),
        sa.Column('check_id', sa.Integer(), nullable=True),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.ForeignKeyConstraint(['check_id'], ['checks.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_customer_deposit_deposit_number'), 'customer_deposit', ['deposit_number'], unique=True)
    op.create_index(op.f('ix_customer_deposit_customer_id'), 'customer_deposit', ['customer_id'])

    # --- sales_return ---
    op.create_table('sales_return',
        *_base_columns(),
        sa.Column('return_number', sa.String(length=50), nullable=False),
        sa.Column('invoice_id', sa.Integer(), nullable=True),
        sa.Column('customer_id', sa.Integer(), nullable=False),
        sa.Column('return_type', sa.Enum('REFUND', 'EXCHANGE', name='returntype'), nullable=False),
        sa.Column('state', sa.Enum('DRAFT', 'VALIDATED', 'ARCHIVED', name='returnstate'), nullable=False),
        sa.Column('total_amount', sa.Numeric(12, 2), nullable=False),
        sa.Column('notes', sa.String(), nullable=True),
        sa.ForeignKeyConstraint(['invoice_id'], ['invoice.id']),
        sa.ForeignKeyConstraint(['customer_id'], ['customer.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_sales_return_return_number'), 'sales_return', ['return_number'], unique=True)

    # --- return_item ---
    op.create_table('return_item',
        *_base_columns(),
        sa.Column('return_id', sa.Integer(), nullable=False),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('quantity', sa.Integer(), nullable=False),
        sa.Column('unit_price', sa.Numeric(12, 2), nullable=False),
        sa.Column('reason', sa.String(length=255), nullable=True),
        sa.Column('restock', sa.Boolean(), nullable=False),
        sa.Column('sent_to_factory', sa.Boolean(), nullable=False),
        sa.ForeignKeyConstraint(['return_id'], ['sales_return.id']),
        sa.ForeignKeyConstraint(['product_id'], ['product.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_return_item_return_id'), 'return_item', ['return_id'])

    # --- attribute_def (dynamic attributes) ---
    op.create_table('attribute_def',
        *_base_columns(),
        sa.Column('key', sa.String(length=50), nullable=False),
        sa.Column('label', sa.String(length=100), nullable=False),
        sa.Column('data_type', sa.Enum('TEXT', 'NUMBER', name='attributedatatype'), nullable=False),
        sa.Column('unit', sa.String(length=20), nullable=True),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('key'),
    )
    op.create_index(op.f('ix_attribute_def_key'), 'attribute_def', ['key'], unique=True)
    op.create_index(op.f('ix_attribute_def_label'), 'attribute_def', ['label'])

    # --- product_attribute ---
    op.create_table('product_attribute',
        *_base_columns(),
        sa.Column('product_id', sa.Integer(), nullable=False),
        sa.Column('attribute_def_id', sa.Integer(), nullable=False),
        sa.Column('value_text', sa.String(length=255), nullable=False),
        sa.ForeignKeyConstraint(['product_id'], ['product.id']),
        sa.ForeignKeyConstraint(['attribute_def_id'], ['attribute_def.id']),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index(op.f('ix_product_attribute_product_id'), 'product_attribute', ['product_id'])
    op.create_index(op.f('ix_product_attribute_attribute_def_id'), 'product_attribute', ['attribute_def_id'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_table('product_attribute')
    op.drop_table('attribute_def')
    op.drop_table('return_item')
    op.drop_table('sales_return')
    op.drop_table('customer_deposit')
    op.drop_table('payment')
    op.drop_table('checks')

    with op.batch_alter_table('supplier') as batch:
        batch.drop_column('payment_terms_days')

    with op.batch_alter_table('stock_level') as batch:
        batch.drop_column('min_quantity')

    with op.batch_alter_table('invoice_item') as batch:
        batch.drop_column('warranty_end_date')
        batch.drop_column('warranty_months')
        batch.drop_column('description_override')
        batch.drop_column('unit_cost')

    with op.batch_alter_table('invoice') as batch:
        batch.drop_column('notes')
        batch.drop_column('due_date')