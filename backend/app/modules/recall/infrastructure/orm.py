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


class Recall(AuditMixin, Base):
    __tablename__ = "recall"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "production_batch_id"],
                             ["production_batch.tenant_id", "production_batch.production_batch_id"],
                             name="fk_recall_production", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "recall_id", name="uq_recall_tenant_id"),
        CheckConstraint("length(trim(reason)) > 0", name="ck_recall_reason"),
        CheckConstraint("completed_at IS NULL OR completed_at >= started_at", name="ck_recall_time_order"),
        CheckConstraint("version >= 1", name="ck_recall_version"),
        Index("ix_recall_tenant_production", "tenant_id", "production_batch_id"),
        Index("ix_recall_started_at", "started_at"),
        Index("ix_recall_created_at", "created_at"),
    )
    recall_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    production_batch_id: Mapped[UUID]
    reason: Mapped[str] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
