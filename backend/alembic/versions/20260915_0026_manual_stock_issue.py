"""manual stock issue

Revision ID: 20260915_0026
Revises: 20260915_0025
Create Date: 2026-09-15 09:40:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0026'
down_revision = '20260915_0025'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'stock_issue',
        sa.Column('stock_issue_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('raw_material_batch_id', sa.Uuid(), nullable=False),
        sa.Column('storage_id', sa.Uuid(), nullable=False),
        sa.Column('zone_id', sa.Uuid(), nullable=True),
        sa.Column('quantity', sa.Numeric(precision=14, scale=6), nullable=False),
        sa.Column('batch_version', sa.Integer(), nullable=False),
        sa.Column('issued_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('reason', sa.String(length=200), nullable=False),
        sa.Column('reference_code', sa.String(length=100), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('deleted_by', sa.Uuid(), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric", name='ck_stock_issue_quantity'),
        sa.CheckConstraint('batch_version >= 1', name='ck_stock_issue_batch_version'),
        sa.CheckConstraint("length(trim(reason)) > 0", name='ck_stock_issue_reason'),
        sa.CheckConstraint("reference_code IS NULL OR length(trim(reference_code)) > 0", name='ck_stock_issue_reference_code'),
        sa.CheckConstraint('deleted_at IS NULL AND deleted_by IS NULL', name='ck_stock_issue_not_deleted'),
        sa.ForeignKeyConstraint(['tenant_id', 'raw_material_batch_id'], ['raw_material_batch.tenant_id', 'raw_material_batch.raw_material_batch_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id', 'storage_id'], ['storage.tenant_id', 'storage.storage_id'], ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id', 'zone_id'], ['storage_zone.tenant_id', 'storage_zone.zone_id'], ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('stock_issue_id'),
        sa.UniqueConstraint('tenant_id', 'raw_material_batch_id', 'batch_version', name='uq_stock_issue_batch_version'),
    )
    op.create_index('ix_stock_issue_storage', 'stock_issue', ['tenant_id', 'storage_id'], unique=False)
    op.create_index('ix_stock_issue_zone', 'stock_issue', ['tenant_id', 'zone_id'], unique=False)
    op.create_index('ix_stock_issue_issued_at', 'stock_issue', ['issued_at'], unique=False)
    op.execute("CREATE TRIGGER stock_issue_immutable BEFORE UPDATE OR DELETE ON stock_issue FOR EACH ROW EXECUTE FUNCTION public.fsos_reject_event_mutation()")
    op.execute("CREATE TRIGGER stock_issue_no_truncate BEFORE TRUNCATE ON stock_issue FOR EACH STATEMENT EXECUTE FUNCTION public.fsos_reject_event_mutation()")


def downgrade() -> None:
    op.drop_index('ix_stock_issue_issued_at', table_name='stock_issue')
    op.drop_index('ix_stock_issue_zone', table_name='stock_issue')
    op.drop_index('ix_stock_issue_storage', table_name='stock_issue')
    op.drop_table('stock_issue')
