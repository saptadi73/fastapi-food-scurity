from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import EmailStr, Field, model_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import (
    AuditData,
    LocationInput,
    Page,
    Temperature,
    VersionInput,
)


class SupplierInput(LocationInput):
    supplier_code: str = Field(min_length=1, max_length=50)
    supplier_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    email: EmailStr | None = Field(default=None, max_length=254)
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'


class RawMaterialInput(LocationInput):
    material_code: str = Field(min_length=1, max_length=50)
    material_name: str = Field(min_length=1, max_length=200)
    category: str | None = Field(default=None, max_length=100)
    uom: str = Field(min_length=1, max_length=30)
    storage_type: Literal['COLD_STORAGE', 'FREEZER', 'DRY_STORAGE'] | None = None
    recommended_temperature_min: Temperature | None = None
    recommended_temperature_max: Temperature | None = None
    maximum_storage_hours: Annotated[Decimal, Field(ge=0, le=99999999.99, max_digits=10, decimal_places=2)] | None = None
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'

    @model_validator(mode='after')
    def temperatures(self):
        if self.recommended_temperature_min is not None and self.recommended_temperature_max is not None and self.recommended_temperature_min > self.recommended_temperature_max:
            raise ValueError('Minimum temperature must not exceed maximum')
        return self


class SupplierMaterialInput(LocationInput):
    supplier_id: UUID
    raw_material_id: UUID


class SupplierUpdate(SupplierInput, VersionInput):
    pass


class RawMaterialUpdate(RawMaterialInput, VersionInput):
    pass


class SupplierMaterialUpdate(SupplierMaterialInput, VersionInput):
    pass


class SupplierData(AuditData):
    supplier_id: UUID
    supplier_code: str
    supplier_name: str
    phone: str | None
    email: str | None
    status: str


class RawMaterialData(AuditData):
    raw_material_id: UUID
    material_code: str
    material_name: str
    category: str | None
    uom: str
    storage_type: str | None
    recommended_temperature_min: Decimal | None
    recommended_temperature_max: Decimal | None
    maximum_storage_hours: Decimal | None
    status: str


class SupplierMaterialData(AuditData):
    supplier_material_id: UUID
    supplier_id: UUID
    raw_material_id: UUID


class SupplierEnvelope(Envelope):
    data: SupplierData


class SupplierPage(Page):
    items: list[SupplierData]


class SupplierPageEnvelope(Envelope):
    data: SupplierPage


class RawMaterialEnvelope(Envelope):
    data: RawMaterialData


class RawMaterialPage(Page):
    items: list[RawMaterialData]


class RawMaterialPageEnvelope(Envelope):
    data: RawMaterialPage


class SupplierMaterialEnvelope(Envelope):
    data: SupplierMaterialData


class SupplierMaterialPage(Page):
    items: list[SupplierMaterialData]


class SupplierMaterialPageEnvelope(Envelope):
    data: SupplierMaterialPage
