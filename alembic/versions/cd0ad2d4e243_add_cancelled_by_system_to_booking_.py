"""add_cancelled_by_system_to_booking_status

Revision ID: cd0ad2d4e243
Revises: df2ec606a3b3
Create Date: 2026-04-26 17:02:47.933702

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'cd0ad2d4e243'
down_revision = 'df2ec606a3b3'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Disable transaction to allow ALTER TYPE
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE bookingstatus ADD VALUE IF NOT EXISTS 'CANCELLED_BY_SYSTEM'")

def downgrade() -> None:
    # Removing ENUM values is unsupported in Postgres easily, typically left as is
    pass
