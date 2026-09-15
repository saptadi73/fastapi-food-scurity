"""recall withdrawal evidence

Revision ID: 20260915_0030
Revises: 20260915_0029
Create Date: 2026-09-15 11:20:00.000000
"""
import sqlalchemy as sa

from alembic import op

revision = '20260915_0030'
down_revision = '20260915_0029'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'recall_withdrawal',
        sa.Column('withdrawal_id', sa.Uuid(), nullable=False),
        sa.Column('tenant_id', sa.Uuid(), nullable=False),
        sa.Column('recall_id', sa.Uuid(), nullable=False),
        sa.Column('package_id', sa.Uuid(), nullable=True),
        sa.Column('evidence_code', sa.String(length=100), nullable=False),
        sa.Column('quantity', sa.Numeric(precision=12, scale=3), nullable=True),
        sa.Column('uom', sa.String(length=20), nullable=True),
        sa.Column('condition_note', sa.Text(), nullable=False),
        sa.Column('photo', sa.String(length=1024), nullable=True),
        sa.Column('withdrawn_at', sa.DateTime(timezone=True), nullable=False),
        sa.Column('completed_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default='1', nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', sa.Uuid(), nullable=True),
        sa.Column('updated_by', sa.Uuid(), nullable=True),
        sa.Column('deleted_by', sa.Uuid(), nullable=True),
        sa.CheckConstraint("length(trim(evidence_code)) > 0", name='ck_recall_withdrawal_evidence_code'),
        sa.CheckConstraint("length(trim(condition_note)) > 0", name='ck_recall_withdrawal_condition'),
        sa.CheckConstraint("quantity IS NULL OR (quantity >= 0 AND quantity <> 'NaN'::numeric)",
                           name='ck_recall_withdrawal_quantity'),
        sa.CheckConstraint("(quantity IS NULL AND uom IS NULL) OR (quantity IS NOT NULL AND uom IS NOT NULL)",
                           name='ck_recall_withdrawal_quantity_uom'),
        sa.CheckConstraint('completed_at IS NULL OR completed_at >= withdrawn_at',
                           name='ck_recall_withdrawal_completed_time'),
        sa.CheckConstraint('version >= 1', name='ck_recall_withdrawal_version'),
        sa.CheckConstraint('deleted_at IS NULL AND deleted_by IS NULL', name='ck_recall_withdrawal_not_deleted'),
        sa.ForeignKeyConstraint(['tenant_id', 'recall_id'], ['recall.tenant_id', 'recall.recall_id'],
                                name='fk_recall_withdrawal_recall', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id', 'package_id'], ['package.tenant_id', 'package.package_id'],
                                name='fk_recall_withdrawal_package', ondelete='RESTRICT'),
        sa.PrimaryKeyConstraint('withdrawal_id'),
        sa.UniqueConstraint('tenant_id', 'withdrawal_id', name='uq_recall_withdrawal_tenant_id'),
        sa.UniqueConstraint('tenant_id', 'evidence_code', name='uq_recall_withdrawal_evidence_code'),
    )
    op.create_index('ix_recall_withdrawal_tenant_recall', 'recall_withdrawal', ['tenant_id', 'recall_id'])
    op.create_index('ix_recall_withdrawal_tenant_package', 'recall_withdrawal', ['tenant_id', 'package_id'])
    op.create_index('ix_recall_withdrawal_withdrawn_at', 'recall_withdrawal', ['withdrawn_at'])
    op.create_index('ix_recall_withdrawal_created_at', 'recall_withdrawal', ['created_at'])
    op.execute("CREATE TRIGGER recall_withdrawal_immutable BEFORE UPDATE OR DELETE ON recall_withdrawal FOR EACH ROW EXECUTE FUNCTION public.fsos_reject_event_mutation()")
    op.execute("CREATE TRIGGER recall_withdrawal_no_truncate BEFORE TRUNCATE ON recall_withdrawal FOR EACH STATEMENT EXECUTE FUNCTION public.fsos_reject_event_mutation()")


def downgrade() -> None:
    op.execute('DROP TRIGGER IF EXISTS recall_withdrawal_no_truncate ON recall_withdrawal')
    op.execute('DROP TRIGGER IF EXISTS recall_withdrawal_immutable ON recall_withdrawal')
    op.drop_index('ix_recall_withdrawal_created_at', table_name='recall_withdrawal')
    op.drop_index('ix_recall_withdrawal_withdrawn_at', table_name='recall_withdrawal')
    op.drop_index('ix_recall_withdrawal_tenant_package', table_name='recall_withdrawal')
    op.drop_index('ix_recall_withdrawal_tenant_recall', table_name='recall_withdrawal')
    op.drop_table('recall_withdrawal')
