from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.core.responses.envelope import Envelope


class MQTTEventData(BaseModel):
    message_uuid: UUID
    tenant_id: UUID
    topic: str
    qos: int
    received_at: datetime
    processed: bool
    payload_json: Any | None
    payload_text: str | None

    @field_validator('received_at')
    @classmethod
    def received_utc(cls, value):
        return value.astimezone(UTC)


class MQTTEventPage(BaseModel):
    items: list[MQTTEventData]
    offset: int
    limit: int
    next_offset: int | None


class MQTTEventPageEnvelope(Envelope):
    data: MQTTEventPage


class MQTTTopicData(BaseModel):
    topic: str
    event_count: int
    latest_received_at: datetime

    @field_validator('latest_received_at')
    @classmethod
    def latest_utc(cls, value):
        return value.astimezone(UTC)


class MQTTTopicPage(BaseModel):
    items: list[MQTTTopicData]
    offset: int
    limit: int
    next_offset: int | None


class MQTTTopicPageEnvelope(Envelope):
    data: MQTTTopicPage
