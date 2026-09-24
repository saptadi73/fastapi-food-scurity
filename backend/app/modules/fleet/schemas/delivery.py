from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator, model_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page, VersionInput
from app.modules.packaging.schemas.packages import PackageData


class ManifestItem(VersionInput, LocationInput):
    package_id: UUID
    school_id: UUID


class DeliveryInput(LocationInput):
    kitchen_id: UUID
    vehicle: UUID
    driver: UUID
    average_speed_kmph: Decimal | None = Field(default=None, gt=0, max_digits=6, decimal_places=2)
    items: list[ManifestItem] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_packages(self):
        if len({i.package_id for i in self.items}) != len(self.items):
            raise ValueError('Each package must appear once')
        return self


class DeliveryAction(VersionInput, LocationInput):
    pass


class DepartureInput(DeliveryAction):
    estimated_arrival_time: datetime | None = None

    @field_validator('estimated_arrival_time')
    @classmethod
    def future(cls, value):
        if value is None:
            return None
        if value.tzinfo is None or value <= datetime.now(UTC):
            raise ValueError('Future timezone-aware arrival estimate required')
        return value.astimezone(UTC)


class DeliveryData(AuditData):
    delivery_id: UUID
    kitchen_id: UUID | None
    vehicle: UUID
    driver: UUID
    departure_time: datetime | None
    arrival_time: datetime | None
    estimated_arrival_time: datetime | None
    estimated_distance_km: Decimal | None
    estimated_duration_minutes: int | None
    status: str

    @field_validator('departure_time', 'arrival_time', 'estimated_arrival_time')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC) if value else None


class DeliveryItemData(AuditData):
    delivery_item_id: UUID
    delivery_id: UUID
    package_id: UUID
    school_id: UUID
    package: PackageData


class DeliveryDetail(DeliveryData):
    items: list[DeliveryItemData]


class DeliveryEnvelope(Envelope):
    data: DeliveryDetail


class DeliveryPage(Page):
    items: list[DeliveryData]


class DeliveryPageEnvelope(Envelope):
    data: DeliveryPage


class DeliveryPackageVehicleSummary(AuditData):
    vehicle: UUID
    delivery_count: int
    package_count: int
    total_quantity: Decimal
    uom: str | None


class DeliveryPackageDestinationSummary(AuditData):
    school_id: UUID
    delivery_count: int
    package_count: int
    total_quantity: Decimal
    uom: str | None


class DeliveryPackageVehiclePage(Page):
    items: list[DeliveryPackageVehicleSummary]


class DeliveryPackageDestinationPage(Page):
    items: list[DeliveryPackageDestinationSummary]


class DeliveryPackageVehiclePageEnvelope(Envelope):
    data: DeliveryPackageVehiclePage


class DeliveryPackageDestinationPageEnvelope(Envelope):
    data: DeliveryPackageDestinationPage


class DeliveryGpsSnapshot(BaseModel):
    gps_log_id: UUID
    recorded_at: datetime
    latitude: Decimal
    longitude: Decimal
    speed: Decimal | None
    heading: Decimal | None

    @field_validator('recorded_at')
    @classmethod
    def gps_utc(cls, value):
        return value.astimezone(UTC)


class DeliveryTemperatureSnapshot(BaseModel):
    temperature_log_id: UUID
    device_uuid: UUID
    recorded_at: datetime
    temperature: Decimal
    unit: str

    @field_validator('recorded_at')
    @classmethod
    def temperature_utc(cls, value):
        return value.astimezone(UTC)


class DeliveryTrackingData(BaseModel):
    delivery_id: UUID
    vehicle: UUID
    status: str
    destination_count: int
    latest_gps: DeliveryGpsSnapshot | None
    latest_temperature: DeliveryTemperatureSnapshot | None
    remaining_distance_km: Decimal | None
    remaining_duration_minutes: int | None
    estimated_arrival_time: datetime | None
    calculated_at: datetime

    @field_validator('estimated_arrival_time', 'calculated_at')
    @classmethod
    def tracking_utc(cls, value):
        return value.astimezone(UTC) if value else None


class DeliveryTrackingEnvelope(Envelope):
    data: DeliveryTrackingData


class DeliveryHistoryPoint(DeliveryGpsSnapshot):
    nearest_school_id: UUID | None
    distance_to_nearest_meters: Decimal | None
    inside_geofence: bool


class DeliveryGeofenceEvent(BaseModel):
    event_type: str
    school_id: UUID
    gps_log_id: UUID
    recorded_at: datetime
    distance_meters: Decimal

    @field_validator('recorded_at')
    @classmethod
    def event_utc(cls, value):
        return value.astimezone(UTC)


class DeliveryHistoryData(BaseModel):
    delivery_id: UUID
    vehicle: UUID
    status: str
    window_started_at: datetime
    window_ended_at: datetime
    geofence_radius_meters: int
    points: list[DeliveryHistoryPoint]
    geofence_events: list[DeliveryGeofenceEvent]
    truncated: bool

    @field_validator('window_started_at', 'window_ended_at')
    @classmethod
    def history_utc(cls, value):
        return value.astimezone(UTC)


class DeliveryHistoryEnvelope(Envelope):
    data: DeliveryHistoryData
