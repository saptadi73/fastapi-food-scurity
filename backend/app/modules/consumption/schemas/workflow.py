from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field, StrictBool, field_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import (
    AuditData,
    LocationInput,
    Page,
    Temperature,
    VersionInput,
)

Quantity = Annotated[Decimal, Field(ge=0, max_digits=14, decimal_places=6)]


class ReceiptInput(VersionInput, LocationInput):
    delivery_id: UUID
    package: UUID
    school: UUID
    received_quantity: Quantity
    condition: Literal['GOOD', 'DAMAGED', 'MISSING']
    accepted: StrictBool
    temperature: Temperature | None = None
    photo: str | None = Field(default=None, min_length=1, max_length=1024)
    notes: str | None = Field(default=None, min_length=1, max_length=2000)

    @field_validator('*', mode='before')
    @classmethod
    def safe_values(cls, value, info):
        if info.field_name == 'accepted':
            return value
        return LocationInput.safe_values(value)


class ConsumptionInput(VersionInput, LocationInput):
    package_id: UUID
    consumed_quantity: Quantity
    discarded_quantity: Quantity
    notes: str | None = Field(default=None, min_length=1, max_length=2000)


class ReceiptData(AuditData):
    school_receiving_id: UUID
    delivery_id: UUID
    package: UUID
    school: UUID
    received_time: datetime
    expected_quantity: Decimal | None
    received_quantity: Decimal | None
    discrepancy_quantity: Decimal | None
    condition: str | None
    accepted: bool | None
    temperature: Decimal | None
    photo: str | None
    notes: str | None
    uom: str | None
    timer_status: str | None

    @field_validator('received_time')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC)


class ConsumptionData(AuditData):
    consumption_id: UUID
    package_id: UUID
    school_receiving_id: UUID | None
    consumed_at: datetime
    consumed_quantity: Decimal | None
    discarded_quantity: Decimal | None
    remaining_minutes: int | None
    safe: bool | None
    notes: str | None
    uom: str | None
    timer_status: str | None

    @field_validator('consumed_at')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC)


class ReceiptEnvelope(Envelope):
    data: ReceiptData


class ConsumptionEnvelope(Envelope):
    data: ConsumptionData


class ReceiptPage(Page):
    items: list[ReceiptData]


class ConsumptionPage(Page):
    items: list[ConsumptionData]


class ReceiptPageEnvelope(Envelope):
    data: ReceiptPage


class ConsumptionPageEnvelope(Envelope):
    data: ConsumptionPage
