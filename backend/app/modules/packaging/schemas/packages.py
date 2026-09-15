from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page, Temperature, VersionInput


class HoldingPolicy(BaseModel):
    schema_version: int
    rule_id: UUID | None
    rule_version: int | None
    food_category: str | None
    maximum_minutes: int
    warning_minutes: int
    discard_minutes: int


class PackageInput(VersionInput, LocationInput):
    production_batch_id: UUID
    package_type_id: UUID
    package_code: str = Field(min_length=1, max_length=100)
    package_number: int = Field(gt=0, le=2147483647, strict=True)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    initial_temperature: Temperature | None = None


class HoldingInput(VersionInput, LocationInput):
    pass


class HoldingFinishInput(HoldingInput):
    outcome: Literal['RELEASED', 'DISCARDED']


class PackageData(AuditData):
    package_id: UUID
    asset_uuid: UUID | None
    package_code: str
    production_batch_id: UUID
    package_type_id: UUID | None
    package_number: int
    quantity: Decimal | None
    initial_temperature: Decimal | None
    uom: str | None
    status: str
    effective_status: str
    qr_payload: str
    holding_started_at: datetime | None
    holding_finished_at: datetime | None
    expired_at: datetime | None
    remaining_minutes: int | None
    remaining_seconds: int | None
    timer_status: str
    holding_eligible: bool
    calculated_at: datetime
    holding_policy: HoldingPolicy | None

    @field_validator('holding_started_at', 'holding_finished_at', 'expired_at', 'calculated_at')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC) if value else None


class PackageEnvelope(Envelope):
    data: PackageData


class PackagePage(Page):
    items: list[PackageData]


class PackagePageEnvelope(Envelope):
    data: PackagePage


class AllocationData(BaseModel):
    production_batch_id: UUID
    version: int
    actual_quantity: Decimal | None
    allocated_quantity: Decimal
    unallocated_quantity: Decimal | None
    uom: str | None
    holding_policy: HoldingPolicy | None


class AllocationEnvelope(Envelope):
    data: AllocationData
