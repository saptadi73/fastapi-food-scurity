"""receiving item condition photo

Revision ID: 20260915_0024
Revises: 20260911_0023
Create Date: 2026-09-15 09:00:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0024'
down_revision = '20260911_0023'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('receiving_item', sa.Column('condition', sa.String(length=100), nullable=True))
    op.add_column('receiving_item', sa.Column('photo', sa.String(length=1024), nullable=True))
    op.create_check_constraint(
        'ck_receiving_item_condition',
        'receiving_item',
        "condition IS NULL OR length(trim(condition)) > 0",
    )
    op.create_check_constraint(
        'ck_receiving_item_photo',
        'receiving_item',
        "photo IS NULL OR length(trim(photo)) > 0",
    )


def downgrade() -> None:
    op.drop_constraint('ck_receiving_item_photo', 'receiving_item', type_='check')
    op.drop_constraint('ck_receiving_item_condition', 'receiving_item', type_='check')
    op.drop_column('receiving_item', 'photo')
    op.drop_column('receiving_item', 'condition')
