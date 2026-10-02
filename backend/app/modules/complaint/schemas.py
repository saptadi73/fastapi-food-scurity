from datetime import UTC, datetime
from typing import Any, Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page


class ComplaintInput(LocationInput):
    package_id: UUID | None = None
    package_code: str | None = Field(default=None, min_length=1, max_length=100)
    school_id: UUID
    description: str = Field(min_length=1, max_length=4000)
    category: Literal['DAMAGE', 'CONTAMINATION', 'PARASITE', 'ANIMAL', 'ILLNESS', 'EXPIRED', 'TEMPERATURE', 'OTHER'] = 'OTHER'
    severity: Literal['LOW', 'MEDIUM', 'HIGH', 'CRITICAL'] = 'MEDIUM'
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
    category: str
    severity: str
    status: str
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


class BatchIncidentImpactEnvelope(Envelope):
    data: dict[str, Any]


class PackageIncidentAlertItem(BaseModel):
    complaint_id: UUID
    category: str
    severity: str
    status: str
    description: str
    reported_at: datetime
    source_package_id: UUID


class IncidentRecommendedAction(BaseModel):
    code: str
    label: str
    required: bool


class PackageIncidentAlertData(BaseModel):
    package_id: UUID
    production_batch_id: UUID
    production_batch_code: str
    has_active_incident: bool
    highest_severity: str | None
    primary_complaint_id: UUID | None
    alerts: list[PackageIncidentAlertItem]
    affected_package_count: int
    delivered_count: int
    received_count: int
    consumed_count: int
    recalled_count: int
    recall_id: UUID | None
    recall_status: str
    recall_reason: str | None
    recommended_actions: list[IncidentRecommendedAction]


class PackageIncidentAlertEnvelope(Envelope):
    data: PackageIncidentAlertData
