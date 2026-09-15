"""notification outbox

Revision ID: 20260915_0031
Revises: 20260915_0030
Create Date: 2026-09-15 11:45:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0031'
down_revision = '20260915_0030'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'notification_outbox',
        sa.Column('notification_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_uuid', sa.Uuid(), nullable=False),
        sa.Column('event_type', sa.String(length=100), nullable=False),
        sa.Column('channel', sa.String(length=20), server_default='DASHBOARD', nullable=False),
        sa.Column('recipient', sa.String(length=200), nullable=True),
        sa.Column('subject', sa.String(length=200), nullable=False),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('status', sa.String(length=20), server_default='PENDING', nullable=False),
        sa.Column('scheduled_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('sent_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('failure_reason', sa.Text(), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('deleted_by', sa.Uuid(), nullable=True),
        sa.CheckConstraint("entity_type IN ('RECALL','COMPLAINT','DELIVERY','PACKAGE','PRODUCTION_BATCH')",
                           name='ck_notification_entity_type'),
        sa.CheckConstraint("length(trim(event_type)) > 0", name='ck_notification_event_type'),
        sa.CheckConstraint("channel IN ('DASHBOARD','EMAIL','WHATSAPP','TELEGRAM')", name='ck_notification_channel'),
        sa.CheckConstraint("status IN ('PENDING','SENT','FAILED','CANCELLED')", name='ck_notification_status'),
        sa.CheckConstraint("length(trim(subject)) > 0", name='ck_notification_subject'),
        sa.CheckConstraint("length(trim(message)) > 0", name='ck_notification_message'),
        sa.CheckConstraint('sent_at IS NULL OR sent_at >= scheduled_at', name='ck_notification_sent_time'),
        sa.CheckConstraint('version >= 1', name='ck_notification_version'),
        sa.ForeignKeyConstraint(['tenant_id'], ['tenant.tenant_id'], name='fk_notification_tenant',
                                ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('notification_id'),
        sa.UniqueConstraint('tenant_id', 'notification_id', name='uq_notification_outbox_tenant_id'),
    )
    op.create_index('ix_notification_tenant_status', 'notification_outbox', ['tenant_id', 'status'])
    op.create_index('ix_notification_tenant_entity', 'notification_outbox',
                    ['tenant_id', 'entity_type', 'entity_uuid'])
    op.create_index('ix_notification_created_at', 'notification_outbox', ['created_at'])
    op.create_index('ix_notification_scheduled_at', 'notification_outbox', ['scheduled_at'])


def downgrade() -> None:
    op.drop_index('ix_notification_scheduled_at', table_name='notification_outbox')
    op.drop_index('ix_notification_created_at', table_name='notification_outbox')
    op.drop_index('ix_notification_tenant_entity', table_name='notification_outbox')
    op.drop_index('ix_notification_tenant_status', table_name='notification_outbox')
    op.drop_table('notification_outbox')
