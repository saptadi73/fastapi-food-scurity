from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import Field

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page, VersionInput


class FoodItemInput(LocationInput):
    food_code: str = Field(min_length=1, max_length=50)
    food_name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    uom: str = Field(min_length=1, max_length=30)
    holding_limit_minutes: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'


class RecipeInput(LocationInput):
    food_item_id: UUID
    raw_material_id: UUID
    quantity: Decimal = Field(gt=0, max_digits=14, decimal_places=6)
    uom: str = Field(min_length=1, max_length=30)


class FoodItemUpdate(FoodItemInput, VersionInput):
    pass


class RecipeUpdate(RecipeInput, VersionInput):
    pass


class FoodItemData(AuditData):
    food_item_id: UUID
    food_code: str
    food_name: str
    category: str | None
    uom: str
    holding_limit_minutes: int | None
    status: str


class RecipeData(AuditData):
    recipe_id: UUID
    food_item_id: UUID
    raw_material_id: UUID
    quantity: Decimal
    uom: str


class FoodItemEnvelope(Envelope):
    data: FoodItemData


class RecipeEnvelope(Envelope):
    data: RecipeData


class FoodItemPage(Page):
    items: list[FoodItemData]


class RecipePage(Page):
    items: list[RecipeData]


class FoodItemPageEnvelope(Envelope):
    data: FoodItemPage


class RecipePageEnvelope(Envelope):
    data: RecipePage
