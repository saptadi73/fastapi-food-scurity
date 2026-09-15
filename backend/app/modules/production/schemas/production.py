from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page, Temperature, VersionInput

Quantity = Annotated[Decimal, Field(gt=0, max_digits=14, decimal_places=6)]


class ProductionInput(LocationInput):
    batch_code: str = Field(min_length=1, max_length=100)
    kitchen: UUID
    menu: UUID
    planned_quantity: Quantity


class SourceInput(VersionInput, LocationInput):
    raw_material_batch_id: UUID
    storage_id: UUID
    quantity: Quantity


class StartInput(VersionInput, LocationInput):
    items: list[SourceInput] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_batches(self):
        if len({i.raw_material_batch_id for i in self.items}) != len(self.items):
            raise ValueError('Each material batch may appear once per production')
        return self


class FinishInput(VersionInput, LocationInput):
    actual_quantity: Decimal = Field(ge=0, max_digits=14, decimal_places=6)
    initial_temperature: Temperature | None = None


class CancelInput(VersionInput, LocationInput):
    pass


class RecipeLine(BaseModel):
    recipe_id: UUID
    version: int
    raw_material_id: UUID
    quantity: Decimal
    required_quantity: Decimal
    uom: str


class RecipeSnapshot(BaseModel):
    schema_version: int
    food_version: int
    food_category: str | None = None
    holding_limit_minutes: int | None = None
    uom: str
    items: list[RecipeLine]


class ProductionData(AuditData):
    production_batch_id: UUID
    batch_code: str
    kitchen: UUID
    menu: UUID
    planned_quantity: Decimal | None
    actual_quantity: Decimal | None
    initial_temperature: Decimal | None
    recipe_snapshot: RecipeSnapshot | None
    status: str
    started_at: datetime | None
    finished_at: datetime | None
    holding_started_at: datetime | None
    holding_expired_at: datetime | None

    @field_validator('started_at', 'finished_at', 'holding_started_at', 'holding_expired_at')
    @classmethod
    def utc(cls, value):
        from datetime import UTC
        return value.astimezone(UTC) if value else None


class ProductionItemData(AuditData):
    production_item_id: UUID
    production_batch_id: UUID
    raw_material_batch_id: UUID
    storage_id: UUID | None
    batch_version: int | None
    quantity: Decimal
    uom: str


class ProductionDetail(ProductionData):
    items: list[ProductionItemData]


class ProductionEnvelope(Envelope):
    data: ProductionDetail


class ProductionPage(Page):
    items: list[ProductionData]


class ProductionPageEnvelope(Envelope):
    data: ProductionPage
