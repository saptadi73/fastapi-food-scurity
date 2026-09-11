"""Master data tahap pertama: tenant dan kitchen.

Revision ID: 20260911_0001
Revises: None
"""
import sqlalchemy as sa
from geoalchemy2 import Geometry

from alembic import op

revision = "20260911_0001"
down_revision = None
branch_labels = None
depends_on = None


def audit_columns():
    return [
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True)),
        sa.Column("created_by", sa.Uuid()),
        sa.Column("updated_by", sa.Uuid()),
        sa.Column("deleted_by", sa.Uuid()),
        sa.Column("version", sa.Integer(), server_default=sa.text("1"), nullable=False),
    ]


def upgrade():
    # Extension diprovision admin terlebih dahulu; migrasi aplikasi tidak butuh superuser.
    op.execute("""
        DO $$ BEGIN
          IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'postgis')
             OR NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname = 'pgcrypto') THEN
            RAISE EXCEPTION 'Provision PostGIS dan pgcrypto sebelum migrasi FSOS.';
          END IF;
        END $$;
    """)
    op.create_table(
        "tenant",
        sa.Column("tenant_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_code", sa.String(50), nullable=False),
        sa.Column("tenant_name", sa.String(200), nullable=False),
        sa.Column("status", sa.String(30), server_default="ACTIVE", nullable=False),
        *audit_columns(),
        sa.UniqueConstraint("tenant_code", name="uq_tenant_code"),
        sa.CheckConstraint("version >= 1", name="ck_tenant_version"),
    )
    op.create_index("ix_tenant_created_at", "tenant", ["created_at"])
    op.create_table(
        "kitchen",
        sa.Column("kitchen_id", sa.Uuid(), primary_key=True),
        sa.Column("tenant_id", sa.Uuid(), sa.ForeignKey("tenant.tenant_id", ondelete="RESTRICT"), nullable=False),
        sa.Column("kitchen_code", sa.String(50), nullable=False),
        sa.Column("kitchen_name", sa.String(200), nullable=False),
        sa.Column("latitude", sa.Numeric(9, 6)),
        sa.Column("longitude", sa.Numeric(9, 6)),
        sa.Column("location", Geometry("POINT", srid=4326, spatial_index=False), sa.Computed(
            "CASE WHEN latitude IS NULL OR longitude IS NULL THEN NULL "
            "ELSE ST_SetSRID(ST_MakePoint(longitude::double precision, "
            "latitude::double precision), 4326) END", persisted=True
        )),
        sa.Column("address", sa.Text()),
        sa.Column("capacity", sa.Integer()),
        sa.Column("status", sa.String(30), server_default="ACTIVE", nullable=False),
        *audit_columns(),
        sa.UniqueConstraint("tenant_id", "kitchen_code", name="uq_kitchen_tenant_code"),
        sa.UniqueConstraint("tenant_id", "kitchen_id", name="uq_kitchen_tenant_id"),
        sa.CheckConstraint("capacity >= 0", name="ck_kitchen_capacity"),
        sa.CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_kitchen_latitude"),
        sa.CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_kitchen_longitude"),
        sa.CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="ck_kitchen_coordinate_pair"),
        sa.CheckConstraint("version >= 1", name="ck_kitchen_version"),
    )
    op.create_index("ix_kitchen_created_at", "kitchen", ["created_at"])
    op.create_index("ix_kitchen_tenant_id", "kitchen", ["tenant_id"])
    op.create_index("ix_kitchen_location", "kitchen", ["location"], postgresql_using="gist")


def downgrade():
    op.drop_table("kitchen")
    op.drop_table("tenant")
    # Extension dimiliki provisioning dan mungkin dipakai objek lain; jangan drop.
