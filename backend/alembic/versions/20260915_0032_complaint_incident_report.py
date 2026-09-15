"""complaint incident report evidence

Revision ID: 20260915_0032
Revises: 20260915_0031
Create Date: 2026-09-15 12:10:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0032'
down_revision = '20260915_0031'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('complaint', sa.Column('photo', sa.Text(), nullable=True))
    op.create_check_constraint('ck_complaint_photo', 'complaint',
                               "photo IS NULL OR length(trim(photo)) > 0")


def downgrade() -> None:
    op.drop_constraint('ck_complaint_photo', 'complaint', type_='check')
    op.drop_column('complaint', 'photo')
