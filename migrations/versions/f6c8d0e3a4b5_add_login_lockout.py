"""Add login lockout columns to user

Revision ID: f6c8d0e3a4b5
Revises: e5b7c9d2f3a4
Create Date: 2026-09-26 20:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f6c8d0e3a4b5'
down_revision: Union[str, Sequence[str], None] = 'e5b7c9d2f3a4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('user') as batch:
        # Consecutive failed logins for this account.
        batch.add_column(sa.Column(
            'failed_login_count', sa.Integer(), nullable=False, server_default='0'
        ))
        # Set once the account is locked out; NULL means not locked.
        # A successful login clears it.
        batch.add_column(sa.Column('locked_until', sa.DateTime(), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('user') as batch:
        batch.drop_column('locked_until')
        batch.drop_column('failed_login_count')
