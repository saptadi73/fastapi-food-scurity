from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKeyConstraint,
    Index,
    Numeric,
    String,
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


class RecallWithdrawal(AuditMixin, Base):
    __tablename__ = "recall_withdrawal"
    __table_args__ = (
        ForeignKeyConstraint(["tenant_id", "recall_id"], ["recall.tenant_id", "recall.recall_id"],
                             name="fk_recall_withdrawal_recall", ondelete="RESTRICT"),
        ForeignKeyConstraint(["tenant_id", "package_id"], ["package.tenant_id", "package.package_id"],
                             name="fk_recall_withdrawal_package", ondelete="RESTRICT"),
        UniqueConstraint("tenant_id", "withdrawal_id", name="uq_recall_withdrawal_tenant_id"),
        UniqueConstraint("tenant_id", "evidence_code", name="uq_recall_withdrawal_evidence_code"),
        CheckConstraint("length(trim(evidence_code)) > 0", name="ck_recall_withdrawal_evidence_code"),
        CheckConstraint("length(trim(condition_note)) > 0", name="ck_recall_withdrawal_condition"),
        CheckConstraint("quantity IS NULL OR (quantity >= 0 AND quantity <> 'NaN'::numeric)",
                        name="ck_recall_withdrawal_quantity"),
        CheckConstraint("(quantity IS NULL AND uom IS NULL) OR (quantity IS NOT NULL AND uom IS NOT NULL)",
                        name="ck_recall_withdrawal_quantity_uom"),
        CheckConstraint("completed_at IS NULL OR completed_at >= withdrawn_at",
                        name="ck_recall_withdrawal_completed_time"),
        CheckConstraint("version >= 1", name="ck_recall_withdrawal_version"),
        CheckConstraint("deleted_at IS NULL AND deleted_by IS NULL", name="ck_recall_withdrawal_not_deleted"),
        Index("ix_recall_withdrawal_tenant_recall", "tenant_id", "recall_id"),
        Index("ix_recall_withdrawal_tenant_package", "tenant_id", "package_id"),
        Index("ix_recall_withdrawal_withdrawn_at", "withdrawn_at"),
        Index("ix_recall_withdrawal_created_at", "created_at"),
    )
    withdrawal_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    recall_id: Mapped[UUID]
    package_id: Mapped[UUID | None]
    evidence_code: Mapped[str] = mapped_column(String(100))
    quantity: Mapped[float | None] = mapped_column(Numeric(12, 3))
    uom: Mapped[str | None] = mapped_column(String(20))
    condition_note: Mapped[str] = mapped_column(Text)
    photo: Mapped[str | None] = mapped_column(String(1024))
    withdrawn_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
