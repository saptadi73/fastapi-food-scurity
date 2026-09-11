from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, ForeignKey, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class EventLog(AuditMixin, Base):
    __tablename__ = "event_log"
    __table_args__ = (
        UniqueConstraint("tenant_id", "event_uuid", name="uq_event_tenant_uuid"),
        CheckConstraint("length(trim(event_type)) > 0", name="ck_event_type"),
        CheckConstraint("length(trim(entity_type)) > 0", name="ck_event_entity_type"),
        CheckConstraint("jsonb_typeof(payload) = 'object'", name="ck_event_payload"),
        CheckConstraint("deleted_at IS NULL AND deleted_by IS NULL", name="ck_event_not_deleted"),
        CheckConstraint("version >= 1", name="ck_event_version"),
        Index("ix_event_entity_timeline", "tenant_id", "entity_type", "entity_uuid", "created_at"),
        Index("ix_event_type_timeline", "tenant_id", "event_type", "created_at"),
        Index("ix_event_created_at", "created_at"),
    )
    event_uuid: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(ForeignKey("tenant.tenant_id", ondelete="RESTRICT"))
    event_type: Mapped[str] = mapped_column(String(100))
    entity_type: Mapped[str] = mapped_column(String(100))
    entity_uuid: Mapped[UUID]
    payload: Mapped[dict] = mapped_column(JSONB)
