"""complaint classification and batch incident state"""

from alembic import op
import sqlalchemy as sa

revision = '20261001_0039'
down_revision = '20260924_0038'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('complaint', sa.Column('category', sa.String(40), server_default='OTHER', nullable=False))
    op.add_column('complaint', sa.Column('severity', sa.String(20), server_default='MEDIUM', nullable=False))
    op.add_column('complaint', sa.Column('status', sa.String(20), server_default='OPEN', nullable=False))
    op.create_check_constraint('ck_complaint_category', 'complaint', "category IN ('DAMAGE','CONTAMINATION','PARASITE','ANIMAL','ILLNESS','EXPIRED','TEMPERATURE','OTHER')")
    op.create_check_constraint('ck_complaint_severity', 'complaint', "severity IN ('LOW','MEDIUM','HIGH','CRITICAL')")
    op.create_check_constraint('ck_complaint_status', 'complaint', "status IN ('OPEN','INVESTIGATING','RESOLVED','CLOSED')")
    op.create_index('ix_complaint_tenant_status', 'complaint', ['tenant_id','status','reported_at'])


def downgrade() -> None:
    op.drop_index('ix_complaint_tenant_status', table_name='complaint')
    op.drop_constraint('ck_complaint_status', 'complaint', type_='check')
    op.drop_constraint('ck_complaint_severity', 'complaint', type_='check')
    op.drop_constraint('ck_complaint_category', 'complaint', type_='check')
    op.drop_column('complaint', 'status')
    op.drop_column('complaint', 'severity')
    op.drop_column('complaint', 'category')
