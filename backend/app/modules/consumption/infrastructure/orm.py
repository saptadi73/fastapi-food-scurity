from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class Consumption(AuditMixin, Base):
    __tablename__ = "consumption"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "package_id"], ["package.tenant_id", "package.package_id"],
                             name="fk_consumption_package", ondelete="RESTRICT"),
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
