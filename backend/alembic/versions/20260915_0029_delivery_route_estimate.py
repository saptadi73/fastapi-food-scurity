"""delivery route estimate

Revision ID: 20260915_0029
Revises: 20260915_0028
Create Date: 2026-09-15 10:45:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0029'
down_revision = '20260915_0028'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint('ck_delivery_eta', 'delivery', type_='check')
    op.add_column('delivery', sa.Column('estimated_distance_km', sa.Numeric(precision=10, scale=3), nullable=True))
    op.add_column('delivery', sa.Column('estimated_duration_minutes', sa.Integer(), nullable=True))
    op.create_check_constraint(
        'ck_delivery_eta',
        'delivery',
        'estimated_arrival_time IS NULL OR departure_time IS NULL OR estimated_arrival_time > departure_time',
    )
    op.create_check_constraint(
        'ck_delivery_estimated_distance',
        'delivery',
        "estimated_distance_km IS NULL OR (estimated_distance_km >= 0 AND estimated_distance_km <> 'NaN'::numeric)",
    )
    op.create_check_constraint(
        'ck_delivery_estimated_duration',
        'delivery',
        'estimated_duration_minutes IS NULL OR estimated_duration_minutes >= 0',
    )


def downgrade() -> None:
    op.drop_constraint('ck_delivery_estimated_duration', 'delivery', type_='check')
    op.drop_constraint('ck_delivery_estimated_distance', 'delivery', type_='check')
    op.drop_constraint('ck_delivery_eta', 'delivery', type_='check')
    op.drop_column('delivery', 'estimated_duration_minutes')
    op.drop_column('delivery', 'estimated_distance_km')
    op.create_check_constraint(
        'ck_delivery_eta',
        'delivery',
        'estimated_arrival_time IS NULL OR (departure_time IS NOT NULL AND estimated_arrival_time > departure_time)',
    )
