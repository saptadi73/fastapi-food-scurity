from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class Complaint(AuditMixin, Base):
    __tablename__ = "complaint"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "package_id"], ["package.tenant_id", "package.package_id"],
                             name="fk_complaint_package", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "school_id"], ["school.tenant_id", "school.school_id"],
                             name="fk_complaint_school", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "complaint_id", name="uq_complaint_tenant_id"),
        CheckConstraint("length(trim(description)) > 0", name="ck_complaint_description"),
        CheckConstraint("version >= 1", name="ck_complaint_version"),
        Index("ix_complaint_tenant_package", "tenant_id", "package_id"),
        Index("ix_complaint_tenant_school", "tenant_id", "school_id"),
        Index("ix_complaint_reported_at", "reported_at"),
        Index("ix_complaint_created_at", "created_at"),
    )
    complaint_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    package_id: Mapped[UUID]
    school_id: Mapped[UUID]
    description: Mapped[str] = mapped_column(Text)
    reported_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
