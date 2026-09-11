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


class Consumption(AuditMixin, Base):
    __tablename__ = "consumption"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "package_id"], ["package.tenant_id", "package.package_id"],
                             name="fk_consumption_package", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "school_receiving_id"], ["school_receiving.tenant_id", "school_receiving.school_receiving_id"], name="fk_consumption_school_receiving", ondelete="RESTRICT"),
        CheckConstraint("consumed_quantity IS NULL OR (consumed_quantity >= 0 AND consumed_quantity < 'Infinity'::numeric)", name="ck_consumption_consumed_quantity"),
        CheckConstraint("discarded_quantity IS NULL OR (discarded_quantity >= 0 AND discarded_quantity < 'Infinity'::numeric)", name="ck_consumption_discarded_quantity"),
        UniqueConstraint("tenant_id", "consumption_id", name="uq_consumption_tenant_id"),
        UniqueConstraint("tenant_id", "package_id", name="uq_consumption_package"),
        CheckConstraint("version >= 1", name="ck_consumption_version"),
        Index("ix_consumption_consumed_at", "consumed_at"),
        Index("ix_consumption_created_at", "created_at"),
    )
    consumption_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    package_id: Mapped[UUID]
    consumed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    remaining_minutes: Mapped[int | None]
    safe: Mapped[bool | None]
    school_receiving_id: Mapped[UUID | None]
    consumed_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    discarded_quantity: Mapped[Decimal | None] = mapped_column(Numeric(14, 6))
    notes: Mapped[str | None] = mapped_column(String(2000))
    uom: Mapped[str | None] = mapped_column(String(30))
    timer_status: Mapped[str | None] = mapped_column(String(30))
