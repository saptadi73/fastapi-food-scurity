from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, VersionInput
from app.modules.production.schemas.production import ProductionItemData


class PutawayInput(VersionInput, LocationInput):
    storage_id: UUID
    zone_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=6)


class StockEntryData(AuditData):
    stock_entry_id: UUID
    raw_material_batch_id: UUID
    storage_id: UUID
    zone_id: UUID | None
    quantity: Decimal
    batch_version: int


class StockEntryEnvelope(Envelope):
    data: StockEntryData


class ManualStockIssueInput(VersionInput, LocationInput):
    storage_id: UUID
    zone_id: UUID | None = None
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    issued_at: datetime | None = None
    reason: str = Field(min_length=1, max_length=200)
    reference_code: str | None = Field(default=None, min_length=1, max_length=100)

    @field_validator('issued_at')
    @classmethod
    def timestamp(cls, value):
        if value is None:
            return None
        if value.tzinfo is None or value > datetime.now(UTC):
            raise ValueError('Timezone required; issued_at must not be in the future')
        return value.astimezone(UTC)


class ManualStockIssueData(AuditData):
    stock_issue_id: UUID
    raw_material_batch_id: UUID
    storage_id: UUID
    zone_id: UUID | None
    quantity: Decimal
    batch_version: int
    issued_at: datetime
    reason: str
    reference_code: str | None

    @field_validator('issued_at')
    @classmethod
    def issued_utc(cls, value):
        return value.astimezone(UTC)


class ManualStockIssueEnvelope(Envelope):
    data: ManualStockIssueData


class StorageBalance(BaseModel):
    storage_id: UUID
    quantity: Decimal
    issued_quantity: Decimal
    available_quantity: Decimal


class StockBalance(BaseModel):
    raw_material_batch_id: UUID
    version: int
    uom: str
    accepted_quantity: Decimal
    putaway_quantity: Decimal
    unallocated_quantity: Decimal
    issued_quantity: Decimal
    available_quantity: Decimal
    storages: list[StorageBalance]


class StockBalanceEnvelope(Envelope):
    data: StockBalance


class StockPage(BaseModel):
    items: list[StockEntryData]
    offset: int
    limit: int
    next_offset: int | None


class StockPageEnvelope(Envelope):
    data: StockPage


class StockIssuePage(BaseModel):
    items: list[ProductionItemData]
    offset: int
    limit: int
    next_offset: int | None


class StockIssuePageEnvelope(Envelope):
    data: StockIssuePage


class ManualStockIssuePage(BaseModel):
    items: list[ManualStockIssueData]
    offset: int
    limit: int
    next_offset: int | None


class ManualStockIssuePageEnvelope(Envelope):
    data: ManualStockIssuePage
