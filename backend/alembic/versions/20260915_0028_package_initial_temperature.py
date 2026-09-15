"""package initial temperature

Revision ID: 20260915_0028
Revises: 20260915_0027
Create Date: 2026-09-15 10:25:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0028'
down_revision = '20260915_0027'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('package', sa.Column('initial_temperature', sa.Numeric(precision=6, scale=2), nullable=True))
    op.create_check_constraint(
        'ck_package_initial_temperature',
        'package',
        "initial_temperature IS NULL OR initial_temperature <> 'NaN'::numeric",
    )


def downgrade() -> None:
    op.drop_constraint('ck_package_initial_temperature', 'package', type_='check')
    op.drop_column('package', 'initial_temperature')
