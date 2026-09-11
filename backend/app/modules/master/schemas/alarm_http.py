from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.rules import AlarmRuleInput, RuleInput


class AlarmRuleUpdate(AlarmRuleInput):
    expected_version: int = Field(gt=0, le=2147483647)


class AlarmRuleActivation(RuleInput):
    enabled: bool
    expected_version: int = Field(gt=0, le=2147483647)


class AlarmRuleData(BaseModel):
    alarm_rule_id: UUID
    tenant_id: UUID
    rule_code: str
    rule_name: str
    rule_category: str
    priority: Literal['CRITICAL', 'HIGH', 'MEDIUM', 'LOW', 'INFO']
    condition: dict[str, Any]
    action: dict[str, Any]
    enabled: bool
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


class AlarmRevisionData(BaseModel):
    revision_id: UUID
    tenant_id: UUID
    rule_id: UUID
    version: int
    captured_at: datetime
    snapshot: AlarmRuleData

    @field_validator('captured_at')
    @classmethod
    def utc_time(cls, value):
        return value.astimezone(UTC)


class AlarmPage(BaseModel):
    items: list[AlarmRuleData]
    offset: int
    limit: int


class RevisionPage(BaseModel):
    items: list[AlarmRevisionData]
    offset: int
    limit: int


class AlarmEnvelope(Envelope):
    data: AlarmRuleData


class AlarmPageEnvelope(Envelope):
    data: AlarmPage


class AlarmHistoryEnvelope(Envelope):
    data: RevisionPage
