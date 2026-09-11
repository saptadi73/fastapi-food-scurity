from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class ProductionBatch(AuditMixin, Base):
    __tablename__ = "production_batch"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "kitchen"], ["kitchen.tenant_id", "kitchen.kitchen_id"],
                             name="fk_production_kitchen", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "menu"], ["food_item.tenant_id", "food_item.food_item_id"],
                             name="fk_production_menu", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "production_batch_id", name="uq_production_tenant_id"),
        UniqueConstraint("tenant_id", "batch_code", name="uq_production_batch_code"),
        CheckConstraint("length(trim(batch_code)) > 0", name="ck_production_batch_code"),
        CheckConstraint("finished_at IS NULL OR (started_at IS NOT NULL AND finished_at >= started_at)",
                        name="ck_production_time_order"),
        CheckConstraint("holding_expired_at IS NULL OR (holding_started_at IS NOT NULL AND holding_expired_at >= holding_started_at)",
                        name="ck_production_holding_order"),
        CheckConstraint("version >= 1", name="ck_production_version"),
        CheckConstraint("planned_quantity IS NULL OR (planned_quantity > 0 AND planned_quantity <> 'NaN'::numeric)", name='ck_production_planned'),
        CheckConstraint("actual_quantity IS NULL OR (planned_quantity IS NOT NULL AND actual_quantity >= 0 AND actual_quantity <= planned_quantity AND actual_quantity <> 'NaN'::numeric)", name='ck_production_actual'),
        Index("ix_production_tenant_kitchen", "tenant_id", "kitchen"),
        Index("ix_production_tenant_menu", "tenant_id", "menu"),
        Index("ix_production_created_at", "created_at"),
    )
    production_batch_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    batch_code: Mapped[str] = mapped_column(String(100))
    kitchen: Mapped[UUID]
    menu: Mapped[UUID]
    planned_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    actual_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    holding_policy: Mapped[dict | None] = mapped_column(JSONB)
    recipe_snapshot: Mapped[dict | None] = mapped_column(JSONB)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    holding_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    holding_expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="CREATED", server_default="CREATED")


class ProductionItem(AuditMixin, Base):
    __tablename__ = "production_item"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "production_batch_id"],
                             ["production_batch.tenant_id", "production_batch.production_batch_id"],
                             name="fk_production_item_batch", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "raw_material_batch_id"],
                             ["raw_material_batch.tenant_id", "raw_material_batch.raw_material_batch_id"],
                             name="fk_production_item_material", ondelete="RESTRICT"),
        ForeignKeyConstraint(['tenant_id', 'storage_id'], ['storage.tenant_id', 'storage.storage_id'], name='production_item_tenant_id_storage_id_fkey', ondelete='RESTRICT'),
        CheckConstraint('(storage_id IS NULL) = (batch_version IS NULL)', name='ck_production_item_location_version'),
        UniqueConstraint("tenant_id", "production_item_id", name="uq_production_item_tenant_id"),
        UniqueConstraint("tenant_id", "production_batch_id", "raw_material_batch_id", name="uq_production_item_material"),
        CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric", name="ck_production_item_quantity"),
        CheckConstraint("length(trim(uom)) > 0", name="ck_production_item_uom"),
        CheckConstraint("version >= 1", name="ck_production_item_version"),
        Index("ix_production_item_tenant_material", "tenant_id", "raw_material_batch_id"),
        Index("ix_production_item_created_at", "created_at"),
    )
    storage_id: Mapped[UUID | None]
    batch_version: Mapped[int | None]
    production_item_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    production_batch_id: Mapped[UUID]
    raw_material_batch_id: Mapped[UUID]
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    uom: Mapped[str] = mapped_column(String(30))


class Package(AuditMixin, Base):
    __tablename__ = "package"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "production_batch_id"],
                             ["production_batch.tenant_id", "production_batch.production_batch_id"],
                             name="fk_package_production", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "package_type_id"],
                             ["packaging_type.tenant_id", "packaging_type.package_type_id"],
                             name="fk_package_type", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "package_id", name="uq_package_tenant_id"),
        UniqueConstraint("tenant_id", "package_code", name="uq_package_code"),
        UniqueConstraint("tenant_id", "production_batch_id", "package_number", name="uq_package_batch_number"),
        CheckConstraint("length(trim(package_code)) > 0", name="ck_package_code"),
        CheckConstraint("package_number > 0", name="ck_package_number"),
        CheckConstraint("version >= 1", name="ck_package_version"),
        CheckConstraint("quantity IS NULL OR (quantity > 0 AND quantity <> 'NaN'::numeric)", name='ck_package_quantity'),
        Index("ix_package_tenant_type", "tenant_id", "package_type_id"),
        Index("ix_package_expired_at", "expired_at"),
        Index("ix_package_created_at", "created_at"),
    )
    package_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    package_code: Mapped[str] = mapped_column(String(100))
    production_batch_id: Mapped[UUID]
    package_type_id: Mapped[UUID | None]
    package_number: Mapped[int]
    quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    holding_started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    holding_finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    # Snapshot dapat negatif setelah expired; bukan bukti bahwa paket aman dikonsumsi.
    remaining_minutes: Mapped[int | None]
    expired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="CREATED", server_default="CREATED")
