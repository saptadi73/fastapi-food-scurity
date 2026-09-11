from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.core.responses.envelope import Envelope


class AlarmData(BaseModel):
    alarm_id: UUID
    tenant_id: UUID
    device_uuid: UUID
    alarm_code: str
    severity: str
    description: str | None
    acknowledged: bool
    recorded_at: datetime
    mqtt_message_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    created_by: UUID | None
    updated_by: UUID | None
    deleted_by: UUID | None
    version: int
    effective_acknowledged: bool
    acknowledgment_id: UUID | None
    acknowledged_at: datetime | None
    acknowledged_by: UUID | None

    @field_validator('recorded_at', 'created_at', 'updated_at', 'deleted_at', 'acknowledged_at')
    @classmethod
    def utc_times(cls, value):
        return value.astimezone(UTC) if value is not None else None


class AlarmPage(BaseModel):
    items: list[AlarmData]
    offset: int
    limit: int
    next_offset: int | None


class AlarmEnvelope(Envelope):
    data: AlarmData


class AlarmPageEnvelope(Envelope):
    data: AlarmPage
