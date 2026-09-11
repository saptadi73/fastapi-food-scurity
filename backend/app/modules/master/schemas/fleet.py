from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID

from pydantic import Field

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import (
    AuditData,
    Coordinates,
    LocationInput,
    Page,
    VersionInput,
)


class DriverInput(LocationInput):
    driver_code: str = Field(min_length=1, max_length=50)
    driver_name: str = Field(min_length=1, max_length=200)
    phone: str | None = Field(default=None, max_length=30)
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'


class VehicleInput(Coordinates):
    vehicle_code: str = Field(min_length=1, max_length=50)
    plate_number: str = Field(min_length=1, max_length=30)
    vehicle_type: str = Field(min_length=1, max_length=50)
    capacity: Annotated[Decimal, Field(ge=0, le=9999999999.99, max_digits=12, decimal_places=2)] | None = None
    gps_device: UUID | None = None
    driver_id: UUID | None = None
    status: Literal['ACTIVE', 'INACTIVE'] = 'ACTIVE'


class DriverUpdate(DriverInput, VersionInput):
    pass


class VehicleUpdate(VehicleInput, VersionInput):
    pass


class DriverData(AuditData):
    driver_id: UUID
    driver_code: str
    driver_name: str
    phone: str | None
    status: str


class VehicleData(AuditData):
    vehicle_id: UUID
    vehicle_code: str
    plate_number: str
    vehicle_type: str
    capacity: Decimal | None
    gps_device: UUID | None
    driver_id: UUID | None
    latitude: Decimal | None
    longitude: Decimal | None
    status: str


class DriverEnvelope(Envelope):
    data: DriverData


class DriverPage(Page):
    items: list[DriverData]


class DriverPageEnvelope(Envelope):
    data: DriverPage


class VehicleEnvelope(Envelope):
    data: VehicleData


class VehiclePage(Page):
    items: list[VehicleData]


class VehiclePageEnvelope(Envelope):
    data: VehiclePage
