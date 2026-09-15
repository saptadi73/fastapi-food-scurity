from datetime import UTC, date, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Temperature, VersionInput


class ItemInput(LocationInput):
    raw_material_id: UUID
    batch_code: str = Field(min_length=1, max_length=100)
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    temperature: Temperature | None = None
    condition: str | None = Field(default=None, min_length=1, max_length=100)
    photo: str | None = Field(default=None, min_length=1, max_length=1024)
    expired_date: date | None = None
    qr_code: str | None = Field(default=None, min_length=1, max_length=255)


class ReceivingInput(LocationInput):
    supplier_id: UUID
    kitchen_id: UUID
    received_at: datetime
    items: list[ItemInput] = Field(min_length=1, max_length=100)

    @field_validator('received_at')
    @classmethod
    def timestamp(cls, value):
        if value.tzinfo is None or value > datetime.now(UTC):
            raise ValueError('Timezone required; received_at must not be in the future')
        return value.astimezone(UTC)

    @model_validator(mode='after')
    def unique_batches(self):
        codes = [i.batch_code for i in self.items]
        qrs = [i.qr_code for i in self.items if i.qr_code is not None]
        if len(set(codes)) != len(codes) or len(set(qrs)) != len(qrs):
            raise ValueError('Batch codes and nonnull QR codes must be unique')
        return self


class Decision(BaseModel):
    model_config = ConfigDict(extra='forbid')
    receiving_item_id: UUID
    accepted: StrictBool


class CompleteInput(VersionInput):
    model_config = ConfigDict(extra='forbid')
    items: list[Decision] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_items(self):
        if len({i.receiving_item_id for i in self.items}) != len(self.items):
            raise ValueError('Each item must appear exactly once')
        return self


class CancelInput(VersionInput):
    model_config = ConfigDict(extra='forbid')


class BatchData(AuditData):
    raw_material_batch_id: UUID
    raw_material_id: UUID
    receiving_id: UUID
    supplier_id: UUID
    batch_code: str
    expired_date: date | None
    status: str
    qr_code: str | None


class ItemData(AuditData):
    receiving_item_id: UUID
    receiving_id: UUID
    raw_material_batch_id: UUID
    quantity: Decimal
    uom: str
    temperature: Decimal | None
    condition: str | None
    photo: str | None
    accepted: bool | None
    batch: BatchData


class ReceivingData(AuditData):
    receiving_id: UUID
    supplier_id: UUID
    kitchen_id: UUID
    operator: UUID
    received_at: datetime
    status: str

    @field_validator('received_at')
    @classmethod
    def received_utc(cls, value):
        return value.astimezone(UTC)


class ReceivingDetail(ReceivingData):
    items: list[ItemData]


class ReceivingEnvelope(Envelope):
    data: ReceivingDetail


class BatchEnvelope(Envelope):
    data: BatchData


class ReceivingPage(BaseModel):
    items: list[ReceivingData]
    offset: int
    limit: int
    next_offset: int | None


class BatchPage(BaseModel):
    items: list[BatchData]
    offset: int
    limit: int
    next_offset: int | None


class ReceivingPageEnvelope(Envelope):
    data: ReceivingPage


class BatchPageEnvelope(Envelope):
    data: BatchPage
