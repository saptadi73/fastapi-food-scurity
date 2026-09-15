"""production initial temperature

Revision ID: 20260915_0027
Revises: 20260915_0026
Create Date: 2026-09-15 10:05:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0027'
down_revision = '20260915_0026'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('production_batch', sa.Column('initial_temperature', sa.Numeric(precision=6, scale=2), nullable=True))
    op.create_check_constraint(
        'ck_production_initial_temperature',
        'production_batch',
        "initial_temperature IS NULL OR initial_temperature <> 'NaN'::numeric",
    )


def downgrade() -> None:
    op.drop_constraint('ck_production_initial_temperature', 'production_batch', type_='check')
    op.drop_column('production_batch', 'initial_temperature')
