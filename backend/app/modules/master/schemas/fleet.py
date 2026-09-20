from datetime import datetime
from decimal import Decimal
from typing import Annotated, Literal
from uuid import UUID, uuid4

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


class DeviceInput(LocationInput):
    zone_id: UUID | None = None
    device_uuid: UUID = Field(default_factory=uuid4)
    device_name: str = Field(min_length=1, max_length=200)
    device_type: str = Field(min_length=1, max_length=50)
    firmware: str | None = Field(default=None, max_length=100)
    hardware: str | None = Field(default=None, max_length=100)
    mqtt_topic: str | None = Field(default=None, max_length=512)
    mqtt_event: str | None = Field(default=None, max_length=200)
    mqtt_sensor: int | None = Field(default=None, ge=0)
    status: Literal['REGISTERED', 'ACTIVE', 'INACTIVE'] = 'REGISTERED'
    last_online: datetime | None = None


class DeviceUpdate(DeviceInput, VersionInput):
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


class DeviceData(AuditData):
    device_id: UUID
    device_uuid: UUID
    zone_id: UUID | None
    device_name: str
    device_type: str
    firmware: str | None
    hardware: str | None
    mqtt_topic: str | None
    mqtt_event: str | None
    mqtt_sensor: int | None
    status: str
    last_online: datetime | None


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


class DeviceEnvelope(Envelope):
    data: DeviceData


class DevicePage(Page):
    items: list[DeviceData]


class DevicePageEnvelope(Envelope):
    data: DevicePage


class DeviceBindingInput(LocationInput):
    device_id: UUID
    vehicle_id: UUID


class DeviceBindingUpdate(DeviceBindingInput, VersionInput):
    pass


class DeviceBindingData(AuditData):
    binding_id: UUID
    device_id: UUID
    vehicle_id: UUID


class DeviceBindingEnvelope(Envelope):
    data: DeviceBindingData


class DeviceBindingPage(Page):
    items: list[DeviceBindingData]


class DeviceBindingPageEnvelope(Envelope):
    data: DeviceBindingPage
