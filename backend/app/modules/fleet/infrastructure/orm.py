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
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class Delivery(AuditMixin, Base):
    __tablename__ = "delivery"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "vehicle"], ["vehicle.tenant_id", "vehicle.vehicle_id"],
                             name="fk_delivery_vehicle", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "driver"], ["driver.tenant_id", "driver.driver_id"],
                             name="fk_delivery_driver", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "delivery_id", name="uq_delivery_tenant_id"),
        CheckConstraint("arrival_time IS NULL OR (departure_time IS NOT NULL AND arrival_time >= departure_time)",
                        name="ck_delivery_time_order"),
        CheckConstraint("version >= 1", name="ck_delivery_version"),
        Index("ix_delivery_tenant_vehicle", "tenant_id", "vehicle"),
        Index("ix_delivery_tenant_driver", "tenant_id", "driver"),
        Index("ix_delivery_departure_time", "departure_time"),
        Index("ix_delivery_created_at", "created_at"),
    )
    delivery_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    vehicle: Mapped[UUID]
    driver: Mapped[UUID]
    departure_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    arrival_time: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    status: Mapped[str] = mapped_column(String(30), default="CREATED", server_default="CREATED")


class DeliveryItem(AuditMixin, Base):
    __tablename__ = "delivery_item"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "delivery_id"], ["delivery.tenant_id", "delivery.delivery_id"],
                             name="fk_delivery_item_delivery", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "package_id"], ["package.tenant_id", "package.package_id"],
                             name="fk_delivery_item_package", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "school_id"], ["school.tenant_id", "school.school_id"],
                             name="fk_delivery_item_school", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "delivery_item_id", name="uq_delivery_item_tenant_id"),
        UniqueConstraint("tenant_id", "delivery_id", "package_id", name="uq_delivery_item_package"),
        UniqueConstraint("tenant_id", "delivery_id", "package_id", "school_id", name="uq_delivery_item_destination"),
        CheckConstraint("version >= 1", name="ck_delivery_item_version"),
        Index("ix_delivery_item_tenant_package", "tenant_id", "package_id"),
        Index("ix_delivery_item_tenant_school", "tenant_id", "school_id"),
        Index("ix_delivery_item_created_at", "created_at"),
    )
    delivery_item_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    delivery_id: Mapped[UUID]
    package_id: Mapped[UUID]
    school_id: Mapped[UUID]


class SchoolReceiving(AuditMixin, Base):
    __tablename__ = "school_receiving"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "delivery_id", "package", "school"],
                             ["delivery_item.tenant_id", "delivery_item.delivery_id",
                              "delivery_item.package_id", "delivery_item.school_id"],
                             name="fk_school_receiving_destination", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "school_receiving_id", name="uq_school_receiving_tenant_id"),
        UniqueConstraint("tenant_id", "delivery_id", "package", name="uq_school_receiving_package"),
        CheckConstraint("temperature IS NULL OR temperature <> 'NaN'::numeric", name="ck_school_receiving_temperature"),
        CheckConstraint("version >= 1", name="ck_school_receiving_version"),
        Index("ix_school_receiving_tenant_school", "tenant_id", "school"),
        Index("ix_school_receiving_tenant_package", "tenant_id", "package"),
        Index("ix_school_receiving_received_time", "received_time"),
        Index("ix_school_receiving_created_at", "created_at"),
    )
    school_receiving_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    delivery_id: Mapped[UUID]
    school: Mapped[UUID]
    package: Mapped[UUID]
    received_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    temperature: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    accepted: Mapped[bool | None]
    photo: Mapped[str | None] = mapped_column(String(1024))
