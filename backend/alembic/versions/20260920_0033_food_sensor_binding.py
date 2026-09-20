"""bind food temperature sensors to production and holding"""

import sqlalchemy as sa

from alembic import op

revision = '20260920_0033'
down_revision = '20260915_0032'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'food_sensor_binding',
        sa.Column('binding_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('device_uuid', sa.Uuid(), nullable=False),
        sa.Column('production_batch_id', sa.Uuid(), nullable=False),
        sa.Column('package_id', sa.Uuid(), nullable=True),
        sa.Column('phase', sa.String(length=20), nullable=False),
        sa.Column('started_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('ended_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('deleted_by', sa.Uuid(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.CheckConstraint("phase IN ('PRODUCTION', 'HOLDING')", name='ck_food_sensor_binding_phase'),
        sa.CheckConstraint('ended_at IS NULL OR ended_at >= started_at', name='ck_food_sensor_binding_time'),
        sa.CheckConstraint('version >= 1', name='ck_food_sensor_binding_version'),
        sa.ForeignKeyConstraint(['tenant_id', 'device_uuid'], ['device.tenant_id', 'device.device_uuid'], ondelete='RESTRICT', name='fk_food_sensor_binding_device'),
        sa.ForeignKeyConstraint(['tenant_id', 'production_batch_id'], ['production_batch.tenant_id', 'production_batch.production_batch_id'], ondelete='RESTRICT', name='fk_food_sensor_binding_production'),
        sa.ForeignKeyConstraint(['tenant_id', 'package_id'], ['package.tenant_id', 'package.package_id'], ondelete='RESTRICT', name='fk_food_sensor_binding_package'),
        sa.PrimaryKeyConstraint('binding_id'),
    )
    op.create_index('ix_food_sensor_binding_tenant_package', 'food_sensor_binding', ['tenant_id', 'package_id', 'started_at'])
    op.create_index('ix_food_sensor_binding_tenant_production', 'food_sensor_binding', ['tenant_id', 'production_batch_id', 'started_at'])
    op.add_column('temperature_log', sa.Column('package_uuid', sa.Uuid(), nullable=True))
    op.add_column('temperature_log', sa.Column('production_batch_uuid', sa.Uuid(), nullable=True))
    op.create_foreign_key('fk_temperature_package', 'temperature_log', 'package', ['tenant_id', 'package_uuid'], ['tenant_id', 'package_id'], ondelete='RESTRICT')
    op.create_foreign_key('fk_temperature_production', 'temperature_log', 'production_batch', ['tenant_id', 'production_batch_uuid'], ['tenant_id', 'production_batch_id'], ondelete='RESTRICT')
    op.create_index('ix_temperature_package_time', 'temperature_log', ['tenant_id', 'package_uuid', 'recorded_at'])
    op.create_index('ix_temperature_production_time', 'temperature_log', ['tenant_id', 'production_batch_uuid', 'recorded_at'])


def downgrade() -> None:
    op.drop_index('ix_temperature_production_time', table_name='temperature_log')
    op.drop_index('ix_temperature_package_time', table_name='temperature_log')
    op.drop_constraint('fk_temperature_production', 'temperature_log', type_='foreignkey')
    op.drop_constraint('fk_temperature_package', 'temperature_log', type_='foreignkey')
    op.drop_column('temperature_log', 'production_batch_uuid')
    op.drop_column('temperature_log', 'package_uuid')
    op.drop_index('ix_food_sensor_binding_tenant_production', table_name='food_sensor_binding')
    op.drop_index('ix_food_sensor_binding_tenant_package', table_name='food_sensor_binding')
    op.drop_table('food_sensor_binding')
