from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class Receiving(AuditMixin, Base):
    __tablename__ = "receiving"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["supplier.tenant_id", "supplier.supplier_id"],
                             name="fk_receiving_supplier", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "kitchen_id"], ["kitchen.tenant_id", "kitchen.kitchen_id"],
                             name="fk_receiving_kitchen", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "operator"], ["app_user.tenant_id", "app_user.user_id"],
                             name="fk_receiving_operator", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "receiving_id", name="uq_receiving_tenant_id"),
        UniqueConstraint("tenant_id", "receiving_id", "supplier_id", name="uq_receiving_supplier"),
        CheckConstraint("version >= 1", name="ck_receiving_version"),
        Index("ix_receiving_tenant_supplier", "tenant_id", "supplier_id"),
        Index("ix_receiving_tenant_kitchen", "tenant_id", "kitchen_id"),
        Index("ix_receiving_tenant_operator", "tenant_id", "operator"),
        Index("ix_receiving_received_at", "received_at"),
        Index("ix_receiving_created_at", "created_at"),
    )
    receiving_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    supplier_id: Mapped[UUID]
    kitchen_id: Mapped[UUID]
    operator: Mapped[UUID]
    received_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="CREATED", server_default="CREATED")


class RawMaterialBatch(AuditMixin, Base):
    __tablename__ = "raw_material_batch"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "receiving_id", "supplier_id"],
                             ["receiving.tenant_id", "receiving.receiving_id", "receiving.supplier_id"],
                             name="fk_raw_batch_receiving_supplier", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "raw_material_id"], ["raw_material.tenant_id", "raw_material.raw_material_id"],
                             name="fk_raw_batch_material", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "raw_material_batch_id", name="uq_raw_batch_tenant_id"),
        UniqueConstraint("tenant_id", "receiving_id", "raw_material_batch_id", name="uq_raw_batch_receiving"),
        UniqueConstraint("tenant_id", "batch_code", name="uq_raw_batch_code"),
        UniqueConstraint("tenant_id", "qr_code", name="uq_raw_batch_qr"),
        CheckConstraint("length(trim(batch_code)) > 0", name="ck_raw_batch_code"),
        CheckConstraint("qr_code IS NULL OR length(trim(qr_code)) > 0", name="ck_raw_batch_qr"),
        CheckConstraint("version >= 1", name="ck_raw_batch_version"),
        Index("ix_raw_batch_tenant_material", "tenant_id", "raw_material_id"),
        Index("ix_raw_batch_created_at", "created_at"),
    )
    raw_material_batch_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    raw_material_id: Mapped[UUID]
    receiving_id: Mapped[UUID]
    supplier_id: Mapped[UUID]
    batch_code: Mapped[str] = mapped_column(String(100))
    expired_date: Mapped[date | None] = mapped_column(Date)
    status: Mapped[str] = mapped_column(String(30), default="CREATED", server_default="CREATED")
    qr_code: Mapped[str | None] = mapped_column(String(255))


class ReceivingItem(AuditMixin, Base):
    __tablename__ = "receiving_item"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "receiving_id", "raw_material_batch_id"],
                             ["raw_material_batch.tenant_id", "raw_material_batch.receiving_id",
                              "raw_material_batch.raw_material_batch_id"],
                             name="fk_receiving_item_batch", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "receiving_item_id", name="uq_receiving_item_tenant_id"),
        UniqueConstraint("tenant_id", "raw_material_batch_id", name="uq_receiving_item_batch"),
        CheckConstraint("quantity > 0 AND quantity <> 'NaN'::numeric", name="ck_receiving_item_quantity"),
        CheckConstraint("temperature IS NULL OR temperature <> 'NaN'::numeric", name="ck_receiving_item_temperature"),
        CheckConstraint("length(trim(uom)) > 0", name="ck_receiving_item_uom"),
        CheckConstraint("version >= 1", name="ck_receiving_item_version"),
        Index("ix_receiving_item_tenant_receiving", "tenant_id", "receiving_id"),
        Index("ix_receiving_item_created_at", "created_at"),
    )
    receiving_item_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    receiving_id: Mapped[UUID]
    raw_material_batch_id: Mapped[UUID]
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    uom: Mapped[str] = mapped_column(String(30))
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    accepted: Mapped[bool | None]
