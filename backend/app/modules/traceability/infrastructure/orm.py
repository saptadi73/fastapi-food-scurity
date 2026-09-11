from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class DigitalAsset(AuditMixin, Base):
    __tablename__ = "digital_asset"
    __table_args__ = (
        UniqueConstraint("tenant_id", "asset_uuid", name="uq_asset_tenant_uuid"),
        UniqueConstraint("tenant_id", "asset_uuid", "asset_type", name="uq_asset_tenant_type"),
        UniqueConstraint("tenant_id", "asset_type", "entity_uuid", name="uq_asset_entity"),
        UniqueConstraint("tenant_id", "asset_type", "code", name="uq_asset_code"),
        CheckConstraint("length(trim(asset_type)) > 0", name="ck_asset_type"),
        CheckConstraint("length(trim(code)) > 0", name="ck_asset_code"),
        CheckConstraint("version >= 1", name="ck_asset_version"),
        Index("ix_asset_created_at", "created_at"),
    )
    asset_uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    asset_type: Mapped[str] = mapped_column(String(50))
    entity_uuid: Mapped[UUID]
    code: Mapped[str] = mapped_column(String(100))
    name: Mapped[str] = mapped_column(String(200))
    status: Mapped[str] = mapped_column(String(30), default="CREATED", server_default="CREATED")


class AssetRelationship(AuditMixin, Base):
    __tablename__ = "asset_relationship"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "parent_uuid"], ["digital_asset.tenant_id", "digital_asset.asset_uuid"],
                             name="fk_relationship_parent", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "child_uuid"], ["digital_asset.tenant_id", "digital_asset.asset_uuid"],
                             name="fk_relationship_child", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "relationship_uuid", name="uq_relationship_tenant_uuid"),
        UniqueConstraint("tenant_id", "parent_uuid", "child_uuid", "relationship_type", name="uq_relationship_edge"),
        CheckConstraint("parent_uuid <> child_uuid", name="ck_relationship_self"),
        CheckConstraint("relationship_type IN ('SUPPLIED','STORED','USED','PRODUCED','PACKAGED','LOADED','DELIVERED','RECEIVED','CONSUMED','REPORTED','RECALLED')",
                        name="ck_relationship_type"),
        CheckConstraint("version >= 1", name="ck_relationship_version"),
        Index("ix_relationship_tenant_child", "tenant_id", "child_uuid"),
        Index("ix_relationship_created_at", "created_at"),
    )
    relationship_uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    parent_uuid: Mapped[UUID]
    child_uuid: Mapped[UUID]
    relationship_type: Mapped[str] = mapped_column(String(30))


class AssetMovement(AuditMixin, Base):
    __tablename__ = "asset_movement"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "asset_uuid", "asset_type"],
                             ["digital_asset.tenant_id", "digital_asset.asset_uuid", "digital_asset.asset_type"],
                             name="fk_movement_asset_type", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "from_location"], ["digital_asset.tenant_id", "digital_asset.asset_uuid"],
                             name="fk_movement_from", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "to_location"], ["digital_asset.tenant_id", "digital_asset.asset_uuid"],
                             name="fk_movement_to", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "operator"], ["app_user.tenant_id", "app_user.user_id"],
                             name="fk_movement_operator", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "movement_id", name="uq_movement_tenant_id"),
        CheckConstraint("movement_type IN ('RECEIVING','STORAGE','ISSUE','PRODUCTION','PACKAGING','VEHICLE_LOADING','DELIVERY','SCHOOL_RECEIVING','CONSUMED','COMPLAINT','RECALL','DISCARD')",
                        name="ck_movement_type"),
        CheckConstraint("version >= 1", name="ck_movement_version"),
        CheckConstraint("deleted_at IS NULL AND deleted_by IS NULL", name="ck_movement_not_deleted"),
        Index("ix_movement_asset_time", "tenant_id", "asset_uuid", "movement_time"),
        Index("ix_movement_tenant_from", "tenant_id", "from_location"),
        Index("ix_movement_tenant_to", "tenant_id", "to_location"),
        Index("ix_movement_tenant_operator", "tenant_id", "operator"),
        Index("ix_movement_created_at", "created_at"),
    )
    movement_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    asset_type: Mapped[str] = mapped_column(String(50))
    asset_uuid: Mapped[UUID]
    movement_type: Mapped[str] = mapped_column(String(30))
    from_location: Mapped[UUID | None]
    to_location: Mapped[UUID | None]
    operator: Mapped[UUID | None]
    movement_time: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remarks: Mapped[str | None] = mapped_column(Text)
