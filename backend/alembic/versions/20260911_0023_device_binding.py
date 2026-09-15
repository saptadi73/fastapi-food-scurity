"""device_binding

Revision ID: 20260911_0023
Revises: 20260911_0022
Create Date: 2026-09-14 10:00:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260911_0023'
down_revision = '20260911_0022'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table('device_binding',
    sa.Column('binding_id', sa.Uuid(), nullable=False),
    sa.Column('tenant_id', sa.Uuid(), nullable=False),
    sa.Column('device_id', sa.Uuid(), nullable=False),
    sa.Column('vehicle_id', sa.Uuid(), nullable=False),
    sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
    sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
    sa.Column('created_by', sa.Uuid(), nullable=True),
    sa.Column('updated_by', sa.Uuid(), nullable=True),
    sa.Column('deleted_by', sa.Uuid(), nullable=True),
    sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
    sa.CheckConstraint('version >= 1', name='ck_device_binding_version'),
    sa.ForeignKeyConstraint(['tenant_id', 'device_id'], ['device.tenant_id', 'device.device_id'],
                           name='fk_device_binding_tenant_device', ondelete='RESTRICT'),
    sa.ForeignKeyConstraint(['tenant_id', 'vehicle_id'], ['vehicle.tenant_id', 'vehicle.vehicle_id'],
                           name='fk_device_binding_tenant_vehicle', ondelete='RESTRICT'),
    sa.UniqueConstraint('tenant_id', 'device_id', 'vehicle_id', name='uq_device_binding_pair'),
    sa.PrimaryKeyConstraint('binding_id'),
    )
    op.create_index('ix_device_binding_created_at', 'device_binding', ['created_at'], unique=False)
    op.create_index('ix_device_binding_tenant_device', 'device_binding', ['tenant_id', 'device_id'], unique=False)
    op.create_index('ix_device_binding_tenant_vehicle', 'device_binding', ['tenant_id', 'vehicle_id'], unique=False)


def downgrade() -> None:
    op.drop_index('ix_device_binding_tenant_vehicle', table_name='device_binding')
    op.drop_index('ix_device_binding_tenant_device', table_name='device_binding')
    op.drop_index('ix_device_binding_created_at', table_name='device_binding')
    op.drop_table('device_binding')
