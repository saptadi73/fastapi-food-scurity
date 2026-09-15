from datetime import UTC, datetime
from typing import Literal
from uuid import UUID

from pydantic import Field, field_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page, VersionInput


class NotificationMarkSentInput(VersionInput, LocationInput):
    sent_at: datetime | None = None

    @field_validator('sent_at')
    @classmethod
    def not_future(cls, value):
        if value is None:
            return None
        value = value.astimezone(UTC)
        if value > datetime.now(UTC):
            raise ValueError('sent_at must not be in the future')
        return value


class NotificationMarkFailedInput(VersionInput, LocationInput):
    failure_reason: str = Field(min_length=1, max_length=4000)


class NotificationData(AuditData):
    notification_id: UUID
    entity_type: str
    entity_uuid: UUID
    event_type: str
    channel: str
    recipient: str | None
    subject: str
    message: str
    status: str
    scheduled_at: datetime
    sent_at: datetime | None
    failure_reason: str | None

    @field_validator('scheduled_at', 'sent_at')
    @classmethod
    def utc_times(cls, value):
        return value.astimezone(UTC) if value is not None else None


class NotificationPage(Page):
    items: list[NotificationData]


class NotificationEnvelope(Envelope):
    data: NotificationData


class NotificationPageEnvelope(Envelope):
    data: NotificationPage


NotificationStatus = Literal['PENDING', 'SENT', 'FAILED', 'CANCELLED']
NotificationChannel = Literal['DASHBOARD', 'EMAIL', 'WHATSAPP', 'TELEGRAM']
