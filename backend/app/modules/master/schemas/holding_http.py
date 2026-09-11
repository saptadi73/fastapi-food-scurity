from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.rules import HoldingRuleInput


class HoldingRuleUpdate(HoldingRuleInput):
    expected_version: int = Field(gt=0, le=2147483647)


class HoldingRuleData(BaseModel):
    holding_rule_id: UUID
    tenant_id: UUID
    food_category: str
    maximum_minutes: int
    warning_minutes: int
    discard_minutes: int
    version: int
    created_at: datetime
    updated_at: datetime
    created_by: UUID | None
    updated_by: UUID | None
    deleted_at: datetime | None
    deleted_by: UUID | None

    @field_validator('created_at', 'updated_at', 'deleted_at')
    @classmethod
    def utc_times(cls, value):
        return value.astimezone(UTC) if value is not None else None


class HoldingRevisionData(BaseModel):
    revision_id: UUID
    tenant_id: UUID
    rule_id: UUID
    version: int
    captured_at: datetime
    snapshot: HoldingRuleData

    @field_validator('captured_at')
    @classmethod
    def utc_time(cls, value):
        return value.astimezone(UTC)


class HoldingPage(BaseModel):
    items: list[HoldingRuleData]
    offset: int
    limit: int


class RevisionPage(BaseModel):
    items: list[HoldingRevisionData]
    offset: int
    limit: int


class HoldingEnvelope(Envelope):
    data: HoldingRuleData


class HoldingPageEnvelope(Envelope):
    data: HoldingPage


class HoldingHistoryEnvelope(Envelope):
    data: RevisionPage
