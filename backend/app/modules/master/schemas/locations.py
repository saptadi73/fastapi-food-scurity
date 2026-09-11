from datetime import UTC, datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.core.responses.envelope import Envelope

Latitude = Annotated[Decimal, Field(ge=-90, le=90, max_digits=9, decimal_places=6)]
Longitude = Annotated[Decimal, Field(ge=-180, le=180, max_digits=9, decimal_places=6)]
Temperature = Annotated[Decimal, Field(ge=-9999.99, le=9999.99, max_digits=6, decimal_places=2)]


class LocationInput(BaseModel):
    model_config = ConfigDict(extra='forbid', str_strip_whitespace=True)

    @field_validator('*', mode='before')
    @classmethod
    def safe_values(cls, value):
        if isinstance(value, bool):
            raise ValueError('Boolean is not accepted for this field')  # noqa: TRY004 - Pydantic validators require ValueError
        if isinstance(value, str):
            if '\x00' in value:
                raise ValueError('NUL is not accepted')
            try:
                value.encode('utf-8')
            except UnicodeEncodeError:
                raise ValueError('Valid UTF-8 required') from None
        return value


class Coordinates(LocationInput):
    latitude: Latitude | None = None
    longitude: Longitude | None = None

    @model_validator(mode='after')
    def coordinate_pair(self):
        if (self.latitude is None) != (self.longitude is None):
            raise ValueError('Latitude and longitude must be supplied together')
        return self


class KitchenInput(Coordinates):
    kitchen_code: str = Field(min_length=1, max_length=50)
    kitchen_name: str = Field(min_length=1, max_length=200)
    address: str | None = None
    capacity: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'


class StorageInput(Coordinates):
    kitchen_id: UUID
    storage_code: str = Field(min_length=1, max_length=50)
    storage_name: str = Field(min_length=1, max_length=200)
    storage_type: Literal['COLD_STORAGE', 'FREEZER', 'DRY_STORAGE']
    temperature_min: Temperature | None = None
    temperature_max: Temperature | None = None
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'

    @model_validator(mode='after')
    def temperature_range(self):
        if self.temperature_min is not None and self.temperature_max is not None and self.temperature_min > self.temperature_max:
            raise ValueError('temperature_min must not exceed temperature_max')
        return self


class ZoneInput(LocationInput):
    storage_id: UUID
    zone_code: str = Field(min_length=1, max_length=50)
    zone_name: str = Field(min_length=1, max_length=200)


class VersionInput(BaseModel):
    expected_version: int = Field(gt=0, le=2147483647, strict=True)


class KitchenUpdate(KitchenInput, VersionInput):
    pass


class StorageUpdate(StorageInput, VersionInput):
    pass


class ZoneUpdate(ZoneInput, VersionInput):
    pass


class AuditData(BaseModel):
    tenant_id: UUID
    version: int
    created_at: datetime
    updated_at: datetime
    deleted_at: datetime | None
    created_by: UUID | None
    updated_by: UUID | None
    deleted_by: UUID | None

    @field_validator('created_at', 'updated_at', 'deleted_at')
    @classmethod
    def utc_times(cls, value):
        return value.astimezone(UTC) if value is not None else None


class KitchenData(AuditData):
    kitchen_id: UUID
    kitchen_code: str
    kitchen_name: str
    latitude: Decimal | None
    longitude: Decimal | None
    address: str | None
    capacity: int | None
    status: str


class StorageData(AuditData):
    storage_id: UUID
    kitchen_id: UUID
    storage_code: str
    storage_name: str
    storage_type: str
    temperature_min: Decimal | None
    temperature_max: Decimal | None
    latitude: Decimal | None
    longitude: Decimal | None
    status: str


class ZoneData(AuditData):
    zone_id: UUID
    storage_id: UUID
    zone_code: str
    zone_name: str


class Page(BaseModel):
    offset: int
    limit: int
    next_offset: int | None


class KitchenEnvelope(Envelope):
    data: KitchenData


class KitchenPage(Page):
    items: list[KitchenData]


class KitchenPageEnvelope(Envelope):
    data: KitchenPage


class StorageEnvelope(Envelope):
    data: StorageData


class StoragePage(Page):
    items: list[StorageData]


class StoragePageEnvelope(Envelope):
    data: StoragePage


class ZoneEnvelope(Envelope):
    data: ZoneData


class ZonePage(Page):
    items: list[ZoneData]


class ZonePageEnvelope(Envelope):
    data: ZonePage


class SchoolInput(Coordinates):
    kitchen_id: UUID
    school_code: str = Field(min_length=1, max_length=50)
    school_name: str = Field(min_length=1, max_length=200)
    address: str | None = None
    student_count: int | None = Field(default=None, ge=0, le=2147483647, strict=True)
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'


class SchoolUpdate(SchoolInput, VersionInput):
    pass


class SchoolData(AuditData):
    school_id: UUID
    kitchen_id: UUID
    school_code: str
    school_name: str
    latitude: Decimal | None
    longitude: Decimal | None
    address: str | None
    student_count: int | None
    status: str


class SchoolEnvelope(Envelope):
    data: SchoolData


class SchoolPage(Page):
    items: list[SchoolData]


class SchoolPageEnvelope(Envelope):
    data: SchoolPage
