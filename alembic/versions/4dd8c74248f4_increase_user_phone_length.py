"""increase_user_phone_length

Revision ID: 4dd8c74248f4
Revises: 42b070653d86
Create Date: 2026-04-25 19:19:45.520656

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '4dd8c74248f4'
down_revision = '42b070653d86'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.alter_column('users', 'phone',
               existing_type=sa.VARCHAR(length=15),
               type_=sa.String(length=20),
               existing_nullable=False)


def downgrade() -> None:
    op.alter_column('users', 'phone',
               existing_type=sa.String(length=20),
               type_=sa.VARCHAR(length=15),
               existing_nullable=False)
