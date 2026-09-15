from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class NotificationOutbox(AuditMixin, Base):
    __tablename__ = "notification_outbox"
    __table_args__ = (
        UniqueConstraint("tenant_id", "notification_id", name="uq_notification_outbox_tenant_id"),
        CheckConstraint("entity_type IN ('RECALL','COMPLAINT','DELIVERY','PACKAGE','PRODUCTION_BATCH')",
                        name="ck_notification_entity_type"),
        CheckConstraint("length(trim(event_type)) > 0", name="ck_notification_event_type"),
        CheckConstraint("channel IN ('DASHBOARD','EMAIL','WHATSAPP','TELEGRAM')", name="ck_notification_channel"),
        CheckConstraint("status IN ('PENDING','SENT','FAILED','CANCELLED')", name="ck_notification_status"),
        CheckConstraint("length(trim(subject)) > 0", name="ck_notification_subject"),
        CheckConstraint("length(trim(message)) > 0", name="ck_notification_message"),
        CheckConstraint("sent_at IS NULL OR sent_at >= scheduled_at", name="ck_notification_sent_time"),
        CheckConstraint("version >= 1", name="ck_notification_version"),
        Index("ix_notification_tenant_status", "tenant_id", "status"),
        Index("ix_notification_tenant_entity", "tenant_id", "entity_type", "entity_uuid"),
        Index("ix_notification_created_at", "created_at"),
        Index("ix_notification_scheduled_at", "scheduled_at"),
    )
    notification_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    entity_type: Mapped[str] = mapped_column(String(50))
    entity_uuid: Mapped[UUID]
    event_type: Mapped[str] = mapped_column(String(100))
    channel: Mapped[str] = mapped_column(String(20), default="DASHBOARD", server_default="DASHBOARD")
    recipient: Mapped[str | None] = mapped_column(String(200))
    subject: Mapped[str] = mapped_column(String(200))
    message: Mapped[str] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String(20), default="PENDING", server_default="PENDING")
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    failure_reason: Mapped[str | None] = mapped_column(Text)
