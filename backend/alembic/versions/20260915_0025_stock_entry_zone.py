"""stock entry zone

Revision ID: 20260915_0025
Revises: 20260915_0024
Create Date: 2026-09-15 09:20:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0025'
down_revision = '20260915_0024'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('stock_entry', sa.Column('zone_id', sa.Uuid(), nullable=True))
    op.create_foreign_key(
        'fk_stock_entry_zone',
        'stock_entry',
        'storage_zone',
        ['tenant_id', 'zone_id'],
        ['tenant_id', 'zone_id'],
        ondelete='RESTRICT',
    )
    op.create_index('ix_stock_zone', 'stock_entry', ['tenant_id', 'zone_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_stock_zone', table_name='stock_entry')
    op.drop_constraint('fk_stock_entry_zone', 'stock_entry', type_='foreignkey')
    op.drop_column('stock_entry', 'zone_id')
