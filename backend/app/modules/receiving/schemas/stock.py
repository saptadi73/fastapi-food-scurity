from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, VersionInput
from app.modules.production.schemas.production import ProductionItemData


class PutawayInput(VersionInput, LocationInput):
    storage_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=6)


class StockEntryData(AuditData):
    stock_entry_id: UUID
    raw_material_batch_id: UUID
    storage_id: UUID
    quantity: Decimal
    batch_version: int


class StockEntryEnvelope(Envelope):
    data: StockEntryData


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
