from datetime import datetime
from decimal import Decimal
from uuid import UUID, uuid4

from geoalchemy2 import Geometry, WKBElement
from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Computed,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class Tenant(AuditMixin, Base):
    __tablename__ = "tenant"
    __table_args__ = (
        UniqueConstraint("tenant_code", name="uq_tenant_code"),
        CheckConstraint("version >= 1", name="ck_tenant_version"),
        Index("ix_tenant_created_at", "created_at"),
    )

    tenant_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_code: Mapped[str] = mapped_column(String(50))
    tenant_name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class Storage(AuditMixin, Base):
    __tablename__ = "storage"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "kitchen_id"],
                             ["kitchen.tenant_id", "kitchen.kitchen_id"],
                             name="fk_storage_tenant_kitchen", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "storage_id", name="uq_storage_tenant_id"),
        UniqueConstraint("kitchen_id", "storage_code", name="uq_storage_kitchen_code"),
        CheckConstraint("temperature_min <= temperature_max", name="ck_storage_temperature_range"),
        CheckConstraint("version >= 1", name="ck_storage_version"),
        Index("ix_storage_tenant_kitchen", "tenant_id", "kitchen_id"),
        Index("ix_storage_created_at", "created_at"),
        Index("ix_storage_location", "location", postgresql_using="gist"),
    )
    storage_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    kitchen_id: Mapped[UUID]
    storage_code: Mapped[str] = mapped_column(String(50))
    storage_name: Mapped[str] = mapped_column(String(200))
    storage_type: Mapped[str] = mapped_column(String(50))
    temperature_min: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    temperature_max: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    location: Mapped[WKBElement | None] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class StorageZone(AuditMixin, Base):
    __tablename__ = "storage_zone"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "storage_id"],
                             ["storage.tenant_id", "storage.storage_id"],
                             name="fk_zone_tenant_storage", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "zone_id", name="uq_zone_tenant_id"),
        UniqueConstraint("storage_id", "zone_code", name="uq_zone_storage_code"),
        CheckConstraint("version >= 1", name="ck_zone_version"),
        Index("ix_zone_tenant_storage", "tenant_id", "storage_id"),
        Index("ix_zone_created_at", "created_at"),
    )
    zone_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    storage_id: Mapped[UUID]
    zone_code: Mapped[str] = mapped_column(String(50))
    zone_name: Mapped[str] = mapped_column(String(200))


class Device(AuditMixin, Base):
    __tablename__ = "device"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "zone_id"],
                             ["storage_zone.tenant_id", "storage_zone.zone_id"],
                             name="fk_device_tenant_zone", ondelete="RESTRICT"),
        UniqueConstraint("device_uuid", name="uq_device_uuid"),
        UniqueConstraint("tenant_id", "device_uuid", name="uq_device_tenant_uuid"),
        UniqueConstraint("tenant_id", "device_id", name="uq_device_tenant_id"),
        CheckConstraint("version >= 1", name="ck_device_version"),
        Index("ix_device_tenant_zone", "tenant_id", "zone_id"),
        Index("ix_device_created_at", "created_at"),
    )
    device_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    device_uuid: Mapped[UUID] = mapped_column(default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    zone_id: Mapped[UUID | None]
    device_name: Mapped[str] = mapped_column(String(200))
    device_type: Mapped[str] = mapped_column(String(50))
    firmware: Mapped[str | None] = mapped_column(String(100))
    hardware: Mapped[str | None] = mapped_column(String(100))
    mqtt_topic: Mapped[str | None] = mapped_column(String(512))
    mqtt_event: Mapped[str | None] = mapped_column(String(200))
    mqtt_sensor: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(30), default="REGISTERED", server_default="REGISTERED")
    last_online: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class DeviceBinding(AuditMixin, Base):
    __tablename__ = "device_binding"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "device_id"], ["device.tenant_id", "device.device_id"],
                             name="fk_device_binding_tenant_device", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "vehicle_id"], ["vehicle.tenant_id", "vehicle.vehicle_id"],
                             name="fk_device_binding_tenant_vehicle", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "device_id", "vehicle_id", name="uq_device_binding_pair"),
        CheckConstraint("version >= 1", name="ck_device_binding_version"),
        Index("ix_device_binding_tenant_device", "tenant_id", "device_id"),
        Index("ix_device_binding_tenant_vehicle", "tenant_id", "vehicle_id"),
        Index("ix_device_binding_created_at", "created_at"),
    )
    binding_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    device_id: Mapped[UUID]
    vehicle_id: Mapped[UUID]


class Kitchen(AuditMixin, Base):
    __tablename__ = "kitchen"
    __table_args__ = (
        UniqueConstraint("tenant_id", "kitchen_code", name="uq_kitchen_tenant_code"),
        UniqueConstraint("tenant_id", "kitchen_id", name="uq_kitchen_tenant_id"),
        CheckConstraint("capacity >= 0", name="ck_kitchen_capacity"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_kitchen_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_kitchen_longitude"),
        CheckConstraint(
            "(latitude IS NULL) = (longitude IS NULL)", name="ck_kitchen_coordinate_pair"
        ),
        CheckConstraint("version >= 1", name="ck_kitchen_version"),
        Index("ix_kitchen_created_at", "created_at"),
        Index("ix_kitchen_tenant_id", "tenant_id"),
        Index("ix_kitchen_location", "location", postgresql_using="gist"),
    )

    kitchen_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    kitchen_code: Mapped[str] = mapped_column(String(50))
    kitchen_name: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    # Point akan dihasilkan dari latitude/longitude, bukan ditulis secara terpisah.
    location: Mapped[WKBElement | None] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False),
        Computed(
            "CASE WHEN latitude IS NULL OR longitude IS NULL THEN NULL "
            "ELSE ST_SetSRID(ST_MakePoint(longitude::double precision, "
            "latitude::double precision), 4326) END", persisted=True
        ),
    )
    address: Mapped[str | None] = mapped_column(Text)
    capacity: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class PackagingType(AuditMixin, Base):
    __tablename__ = "packaging_type"
    __table_args__ = (
        UniqueConstraint("tenant_id", "package_type_id", name="uq_packaging_tenant_id"),
        UniqueConstraint("tenant_id", "code", name="uq_packaging_tenant_code"),
        CheckConstraint("volume > 0 AND volume <> 'NaN'::numeric", name="ck_packaging_volume"),
        CheckConstraint("version >= 1", name="ck_packaging_version"),
        Index("ix_packaging_created_at", "created_at"),
    )
    package_type_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    code: Mapped[str] = mapped_column(String(50))
    name: Mapped[str] = mapped_column(String(200))
    material: Mapped[str | None] = mapped_column(String(100))
    # Satuan volume: milliliter, dijelaskan dalam panduan database.
    volume: Mapped[Decimal | None] = mapped_column(Numeric(12, 3))


class AlarmRule(AuditMixin, Base):
    __tablename__ = "alarm_rule"
    __table_args__ = (
        UniqueConstraint("tenant_id", "alarm_rule_id", name="uq_alarm_rule_tenant_id"),
        UniqueConstraint("tenant_id", "rule_code", name="uq_alarm_rule_tenant_code"),
        CheckConstraint("priority IN ('CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO')",
                        name="ck_alarm_rule_priority"),
        CheckConstraint("jsonb_typeof(condition) = 'object' AND condition <> '{}'::jsonb",
                        name="ck_alarm_rule_condition"),
        CheckConstraint("jsonb_typeof(action) = 'object' AND action <> '{}'::jsonb",
                        name="ck_alarm_rule_action"),
        CheckConstraint("version >= 1", name="ck_alarm_rule_version"),
        Index("ix_alarm_rule_tenant_enabled", "tenant_id", "enabled"),
        Index("ix_alarm_rule_created_at", "created_at"),
    )
    alarm_rule_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    rule_code: Mapped[str] = mapped_column(String(50))
    rule_name: Mapped[str] = mapped_column(String(200))
    rule_category: Mapped[str] = mapped_column(String(100))
    priority: Mapped[str] = mapped_column(String(20))
    condition: Mapped[dict] = mapped_column(JSONB)
    action: Mapped[dict] = mapped_column(JSONB)
    enabled: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")


class HoldingRule(AuditMixin, Base):
    __tablename__ = "holding_rule"
    __table_args__ = (
        UniqueConstraint("tenant_id", "holding_rule_id", name="uq_holding_rule_tenant_id"),
        UniqueConstraint("tenant_id", "food_category", name="uq_holding_rule_tenant_category"),
        CheckConstraint("maximum_minutes > 0", name="ck_holding_rule_maximum"),
        CheckConstraint("warning_minutes >= 0 AND warning_minutes <= maximum_minutes",
                        name="ck_holding_rule_warning"),
        CheckConstraint("discard_minutes >= maximum_minutes", name="ck_holding_rule_discard"),
        CheckConstraint("version >= 1", name="ck_holding_rule_version"),
        Index("ix_holding_rule_created_at", "created_at"),
    )
    holding_rule_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    food_category: Mapped[str] = mapped_column(String(100))
    maximum_minutes: Mapped[int]
    warning_minutes: Mapped[int]
    discard_minutes: Mapped[int]


class RuleRevision:
    revision_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    rule_id: Mapped[UUID]
    version: Mapped[int]
    snapshot: Mapped[dict] = mapped_column(JSONB)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


def rule_revision_constraints(kind):
    return (
        UniqueConstraint("tenant_id", "rule_id", "version", name=f"uq_{kind}_revision_version"),
        ForeignKeyConstraint(["tenant_id", "rule_id"], [f"{kind}_rule.tenant_id", f"{kind}_rule.{kind}_rule_id"],
                             name=f"fk_{kind}_revision_rule", ondelete="RESTRICT"),
        CheckConstraint("version >= 1", name=f"ck_{kind}_revision_version"),
        CheckConstraint("jsonb_typeof(snapshot) = 'object'", name=f"ck_{kind}_revision_snapshot"),
    )


class AlarmRuleRevision(RuleRevision, Base):
    __tablename__ = "alarm_rule_revision"
    __table_args__ = rule_revision_constraints("alarm")


class HoldingRuleRevision(RuleRevision, Base):
    __tablename__ = "holding_rule_revision"
    __table_args__ = rule_revision_constraints("holding")


class Supplier(AuditMixin, Base):
    __tablename__ = "supplier"
    __table_args__ = (
        UniqueConstraint("tenant_id", "supplier_id", name="uq_supplier_tenant_id"),
        UniqueConstraint("tenant_id", "supplier_code", name="uq_supplier_tenant_code"),
        CheckConstraint("version >= 1", name="ck_supplier_version"),
        Index("ix_supplier_created_at", "created_at"),
    )
    supplier_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    supplier_code: Mapped[str] = mapped_column(String(50))
    supplier_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    email: Mapped[str | None] = mapped_column(String(254))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class RawMaterial(AuditMixin, Base):
    __tablename__ = "raw_material"
    __table_args__ = (
        UniqueConstraint("tenant_id", "raw_material_id", name="uq_material_tenant_id"),
        UniqueConstraint("tenant_id", "material_code", name="uq_material_tenant_code"),
        CheckConstraint("recommended_temperature_min <= recommended_temperature_max",
                        name="ck_material_temperature_range"),
        CheckConstraint("maximum_storage_hours >= 0", name="ck_material_storage_hours"),
        CheckConstraint("length(trim(uom)) > 0", name="ck_material_uom"),
        CheckConstraint("version >= 1", name="ck_material_version"),
        Index("ix_material_created_at", "created_at"),
    )
    raw_material_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    material_code: Mapped[str] = mapped_column(String(50))
    material_name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))
    uom: Mapped[str] = mapped_column(String(30))
    storage_type: Mapped[str | None] = mapped_column(String(50))
    recommended_temperature_min: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    recommended_temperature_max: Mapped[Decimal | None] = mapped_column(Numeric(6, 2))
    maximum_storage_hours: Mapped[Decimal | None] = mapped_column(Numeric(10, 2))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class FoodItem(AuditMixin, Base):
    __tablename__ = "food_item"
    __table_args__ = (
        UniqueConstraint("tenant_id", "food_item_id", name="uq_food_tenant_id"),
        UniqueConstraint("tenant_id", "food_code", name="uq_food_tenant_code"),
        CheckConstraint("holding_limit_minutes >= 0", name="ck_food_holding_limit"),
        CheckConstraint("length(trim(uom)) > 0", name="ck_food_uom"),
        CheckConstraint("version >= 1", name="ck_food_version"),
        Index("ix_food_created_at", "created_at"),
    )
    food_item_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    food_code: Mapped[str] = mapped_column(String(50))
    food_name: Mapped[str] = mapped_column(String(200))
    category: Mapped[str | None] = mapped_column(String(100))
    uom: Mapped[str] = mapped_column(String(30))
    holding_limit_minutes: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class Recipe(AuditMixin, Base):
    __tablename__ = "recipe"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "food_item_id"], ["food_item.tenant_id", "food_item.food_item_id"],
                             name="fk_recipe_tenant_food", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "raw_material_id"], ["raw_material.tenant_id", "raw_material.raw_material_id"],
                             name="fk_recipe_tenant_material", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "food_item_id", "raw_material_id", name="uq_recipe_food_material"),
        CheckConstraint("quantity > 0", name="ck_recipe_quantity"),
        CheckConstraint("length(trim(uom)) > 0", name="ck_recipe_uom"),
        CheckConstraint("version >= 1", name="ck_recipe_version"),
        Index("ix_recipe_tenant_material", "tenant_id", "raw_material_id"),
        Index("ix_recipe_created_at", "created_at"),
    )
    recipe_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    food_item_id: Mapped[UUID]
    raw_material_id: Mapped[UUID]
    quantity: Mapped[Decimal] = mapped_column(Numeric(14, 6))
    uom: Mapped[str] = mapped_column(String(30))


class SupplierMaterial(AuditMixin, Base):
    __tablename__ = "supplier_material"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "supplier_id"], ["supplier.tenant_id", "supplier.supplier_id"],
                             name="fk_supplier_material_supplier", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "raw_material_id"], ["raw_material.tenant_id", "raw_material.raw_material_id"],
                             name="fk_supplier_material_material", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "supplier_id", "raw_material_id", name="uq_supplier_material_pair"),
        CheckConstraint("version >= 1", name="ck_supplier_material_version"),
        Index("ix_supplier_material_tenant_material", "tenant_id", "raw_material_id"),
        Index("ix_supplier_material_created_at", "created_at"),
    )
    supplier_material_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    supplier_id: Mapped[UUID]
    raw_material_id: Mapped[UUID]


class Driver(AuditMixin, Base):
    __tablename__ = "driver"
    __table_args__ = (
        UniqueConstraint("tenant_id", "driver_id", name="uq_driver_tenant_id"),
        UniqueConstraint("tenant_id", "driver_code", name="uq_driver_tenant_code"),
        CheckConstraint("version >= 1", name="ck_driver_version"),
        Index("ix_driver_created_at", "created_at"),
    )
    driver_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    driver_code: Mapped[str] = mapped_column(String(50))
    driver_name: Mapped[str] = mapped_column(String(200))
    phone: Mapped[str | None] = mapped_column(String(30))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class Vehicle(AuditMixin, Base):
    __tablename__ = "vehicle"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "gps_device"], ["device.tenant_id", "device.device_id"],
                             name="fk_vehicle_tenant_device", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "driver_id"], ["driver.tenant_id", "driver.driver_id"],
                             name="fk_vehicle_tenant_driver", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "vehicle_id", name="uq_vehicle_tenant_id"),
        UniqueConstraint("tenant_id", "vehicle_code", name="uq_vehicle_tenant_code"),
        UniqueConstraint("tenant_id", "plate_number", name="uq_vehicle_tenant_plate"),
        CheckConstraint("capacity >= 0", name="ck_vehicle_capacity"),
        CheckConstraint("version >= 1", name="ck_vehicle_version"),
        Index("ix_vehicle_tenant_device", "tenant_id", "gps_device"),
        Index("ix_vehicle_tenant_driver", "tenant_id", "driver_id"),
        Index("ix_vehicle_created_at", "created_at"),
        Index("ix_vehicle_location", "location", postgresql_using="gist"),
    )
    vehicle_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    vehicle_code: Mapped[str] = mapped_column(String(50))
    plate_number: Mapped[str] = mapped_column(String(30))
    vehicle_type: Mapped[str] = mapped_column(String(50))
    capacity: Mapped[Decimal | None] = mapped_column(Numeric(12, 2))
    gps_device: Mapped[UUID | None]
    driver_id: Mapped[UUID | None]
    location: Mapped[WKBElement | None] = mapped_column(Geometry("POINT", srid=4326, spatial_index=False))
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")


class School(AuditMixin, Base):
    __tablename__ = "school"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "kitchen_id"], ["kitchen.tenant_id", "kitchen.kitchen_id"],
                             name="fk_school_tenant_kitchen", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "school_id", name="uq_school_tenant_id"),
        UniqueConstraint("tenant_id", "school_code", name="uq_school_tenant_code"),
        CheckConstraint("student_count >= 0", name="ck_school_student_count"),
        CheckConstraint("latitude BETWEEN -90 AND 90", name="ck_school_latitude"),
        CheckConstraint("longitude BETWEEN -180 AND 180", name="ck_school_longitude"),
        CheckConstraint("(latitude IS NULL) = (longitude IS NULL)", name="ck_school_coordinate_pair"),
        CheckConstraint("version >= 1", name="ck_school_version"),
        Index("ix_school_tenant_kitchen", "tenant_id", "kitchen_id"),
        Index("ix_school_created_at", "created_at"),
        Index("ix_school_location", "location", postgresql_using="gist"),
    )
    school_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    kitchen_id: Mapped[UUID]
    school_code: Mapped[str] = mapped_column(String(50))
    school_name: Mapped[str] = mapped_column(String(200))
    latitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    longitude: Mapped[Decimal | None] = mapped_column(Numeric(9, 6))
    location: Mapped[WKBElement | None] = mapped_column(
        Geometry("POINT", srid=4326, spatial_index=False),
        Computed("CASE WHEN latitude IS NULL OR longitude IS NULL THEN NULL "
                 "ELSE ST_SetSRID(ST_MakePoint(longitude::double precision, "
                 "latitude::double precision), 4326) END", persisted=True),
    )
    address: Mapped[str | None] = mapped_column(Text)
    student_count: Mapped[int | None]
    status: Mapped[str] = mapped_column(String(30), default="ACTIVE", server_default="ACTIVE")
