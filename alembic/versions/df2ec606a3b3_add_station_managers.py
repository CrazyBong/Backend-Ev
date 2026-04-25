"""add_station_managers

Revision ID: df2ec606a3b3
Revises: 4dd8c74248f4
Create Date: 2026-04-26 00:45:29.696129

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'df2ec606a3b3'
down_revision = '4dd8c74248f4'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'station_managers',
        sa.Column('user_id', sa.UUID(), nullable=False),
        sa.Column('station_id', sa.UUID(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['station_id'], ['stations.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'station_id')
    )


def downgrade() -> None:
    op.drop_table('station_managers')
