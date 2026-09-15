from datetime import UTC, datetime
from typing import Any
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page


class ComplaintInput(LocationInput):
    package_id: UUID | None = None
    package_code: str | None = Field(default=None, min_length=1, max_length=100)
    school_id: UUID
    description: str = Field(min_length=1, max_length=4000)
    photo: str | None = Field(default=None, min_length=1, max_length=1024)

    @model_validator(mode='after')
    def package_identifier(self):
        if (self.package_id is None) == (self.package_code is None):
            raise ValueError('Supply exactly one of package_id or package_code')
        return self


class ComplaintData(AuditData):
    complaint_id: UUID
    package_id: UUID
    school_id: UUID
    description: str
    photo: str | None
    reported_at: datetime

    @field_validator('reported_at')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC)


class ComplaintEnvelope(Envelope):
    data: ComplaintData


class ComplaintPage(Page):
    items: list[ComplaintData]


class ComplaintPageEnvelope(Envelope):
    data: ComplaintPage


class ComplaintReportData(AuditData):
    complaint_id: UUID
    package_id: UUID
    school_id: UUID
    description: str
    photo: str | None
    reported_at: datetime
    package: dict[str, Any]
    production_batch: dict[str, Any] | None
    current_location: dict[str, Any] | None
    delivery_manifest: list[dict[str, Any]]
    school_receivings: list[dict[str, Any]]
    consumption: dict[str, Any] | None
    raw_materials: list[dict[str, Any]]
    traceability: dict[str, Any]

    @field_validator('reported_at')
    @classmethod
    def report_utc(cls, value):
        return value.astimezone(UTC)


class ComplaintReportEnvelope(Envelope):
    data: ComplaintReportData


class ComplaintReportPage(Page):
    items: list[ComplaintReportData]


class ComplaintReportPageEnvelope(Envelope):
    data: ComplaintReportPage
