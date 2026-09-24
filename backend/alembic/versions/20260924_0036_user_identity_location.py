"""tenant user administration and operational location assignment"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = '20260924_0036'
down_revision = '20260921_0035'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('app_user', sa.Column('job_title', sa.String(150), nullable=True))
    op.create_table('user_location_assignment',
        sa.Column('assignment_id', postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column('tenant_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('user_id', postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column('location_type', sa.String(20), nullable=False),
        sa.Column('kitchen_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('school_id', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column('deleted_at', sa.DateTime(timezone=True), nullable=True),
        sa.Column('created_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('updated_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('deleted_by', postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column('version', sa.Integer(), server_default=sa.text('1'), nullable=False),
        sa.ForeignKeyConstraint(['tenant_id','user_id'], ['app_user.tenant_id','app_user.user_id'], name='fk_user_location_tenant_user', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id','kitchen_id'], ['kitchen.tenant_id','kitchen.kitchen_id'], name='fk_user_location_tenant_kitchen', ondelete='RESTRICT'),
        sa.ForeignKeyConstraint(['tenant_id','school_id'], ['school.tenant_id','school.school_id'], name='fk_user_location_tenant_school', ondelete='RESTRICT'),
        sa.CheckConstraint("location_type IN ('KITCHEN','SCHOOL')", name='ck_user_location_type'),
        sa.CheckConstraint("(location_type='KITCHEN' AND kitchen_id IS NOT NULL AND school_id IS NULL) OR (location_type='SCHOOL' AND school_id IS NOT NULL AND kitchen_id IS NULL)", name='ck_user_location_target'),
        sa.CheckConstraint('version >= 1', name='ck_user_location_version'))
    op.create_index('ix_user_location_tenant_user', 'user_location_assignment', ['tenant_id','user_id'])
    op.create_index('uq_user_location_kitchen_active', 'user_location_assignment', ['tenant_id','user_id','kitchen_id'], unique=True, postgresql_where=sa.text('deleted_at IS NULL AND kitchen_id IS NOT NULL'))
    op.create_index('uq_user_location_school_active', 'user_location_assignment', ['tenant_id','user_id','school_id'], unique=True, postgresql_where=sa.text('deleted_at IS NULL AND school_id IS NOT NULL'))
    op.execute("""
      INSERT INTO permission (permission_id, tenant_id, permission_code, description, created_at, updated_at, version)
      SELECT gen_random_uuid(), t.tenant_id, p.code, p.description, now(), now(), 1
      FROM tenant t CROSS JOIN (VALUES
        ('User.Read','Read tenant users and roles'), ('User.Write','Register and administer tenant users'),
        ('Role.Assign','Assign tenant roles to users')) p(code, description)
      WHERE t.deleted_at IS NULL ON CONFLICT (tenant_id, permission_code) DO NOTHING
    """)
    op.execute("""
      INSERT INTO role_permission (role_permission_id, tenant_id, role_id, permission_id, created_at, updated_at, version)
      SELECT gen_random_uuid(), r.tenant_id, r.role_id, p.permission_id, now(), now(), 1
      FROM role r JOIN permission p ON p.tenant_id=r.tenant_id
      WHERE r.deleted_at IS NULL AND p.deleted_at IS NULL
        AND r.role_code IN ('FRONTEND_ADMIN','TENANT_ADMIN','DEV_MAINTENANCE')
        AND p.permission_code IN ('User.Read','User.Write','Role.Assign')
      ON CONFLICT (tenant_id, role_id, permission_id) DO NOTHING
    """)


def downgrade() -> None:
    op.drop_index('uq_user_location_school_active', table_name='user_location_assignment')
    op.drop_index('uq_user_location_kitchen_active', table_name='user_location_assignment')
    op.drop_index('ix_user_location_tenant_user', table_name='user_location_assignment')
    op.drop_table('user_location_assignment')
    op.drop_column('app_user', 'job_title')
