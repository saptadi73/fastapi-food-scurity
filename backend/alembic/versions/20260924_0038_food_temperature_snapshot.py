"""permission for on-demand food temperature snapshot"""

from alembic import op

revision = '20260924_0038'
down_revision = '20260924_0037'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("""
      INSERT INTO permission (permission_id, tenant_id, permission_code, description, created_at, updated_at, version)
      SELECT gen_random_uuid(), t.tenant_id, 'FoodTemperature.Read',
             'Select a fresh food probe sample for operator-confirmed measurement', now(), now(), 1
      FROM tenant t WHERE t.deleted_at IS NULL
      ON CONFLICT (tenant_id, permission_code) DO NOTHING
    """)
    op.execute("""
      INSERT INTO role_permission (role_permission_id, tenant_id, role_id, permission_id, created_at, updated_at, version)
      SELECT gen_random_uuid(), r.tenant_id, r.role_id, p.permission_id, now(), now(), 1
      FROM role r JOIN permission p ON p.tenant_id=r.tenant_id
      WHERE r.deleted_at IS NULL AND p.deleted_at IS NULL
        AND r.role_code IN ('FRONTEND_ADMIN','TENANT_ADMIN','DEV_MAINTENANCE')
        AND p.permission_code='FoodTemperature.Read'
      ON CONFLICT (tenant_id, role_id, permission_id) DO NOTHING
    """)


def downgrade() -> None:
    pass
