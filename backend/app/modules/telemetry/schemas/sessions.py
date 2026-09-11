from datetime import UTC, datetime
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, field_validator

from app.core.responses.envelope import Envelope


class DeviceSessionData(BaseModel):
    session_id: UUID
    tenant_id: UUID
    device_uuid: UUID
    connected_at: datetime
    disconnected_at: datetime | None
    ip_address: str | None
    firmware: str | None
    recorded_at: datetime
    mqtt_message_id: UUID | None
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    created_by: UUID | None
    updated_by: UUID | None
    deleted_by: UUID | None
    version: int
    effective_disconnected_at: datetime | None
    is_open: bool
    session_end_id: UUID | None

    @field_validator('ip_address', mode='before')
    @classmethod
    def ip_text(cls, value):
        return str(value) if value is not None else None

    @field_validator('recorded_at', 'created_at', 'updated_at', 'deleted_at', 'connected_at', 'disconnected_at', 'effective_disconnected_at')
    @classmethod
    def utc_times(cls, value):
        return value.astimezone(UTC) if value is not None else None


class DeviceSessionPage(BaseModel):
    items: list[DeviceSessionData]
    offset: int
    limit: int
    next_offset: int | None


class DeviceSessionEnvelope(Envelope):
    data: DeviceSessionData


class DeviceSessionPageEnvelope(Envelope):
    data: DeviceSessionPage


class CloseSessionPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    disconnected_at: AwareDatetime

    @field_validator('disconnected_at', mode='before')
    @classmethod
    def timestamp_string(cls, value):
        if not isinstance(value, str) or 'T' not in value:
            raise ValueError('ISO 8601 datetime string with timezone required')
        return value
