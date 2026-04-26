"""add_admin_cancellation_enum

Revision ID: 3dd7b2dba912
Revises: cd0ad2d4e243
Create Date: 2026-04-26 17:59:17.000263

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '3dd7b2dba912'
down_revision = 'cd0ad2d4e243'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Disable transaction to allow ALTER TYPE
    with op.get_context().autocommit_block():
        op.execute("ALTER TYPE bookingstatus ADD VALUE IF NOT EXISTS 'CANCELLED_BY_ADMIN'")
        op.execute("ALTER TYPE bookingstatus ADD VALUE IF NOT EXISTS 'CANCELLED_BY_USER'")


def downgrade() -> None:
    pass
