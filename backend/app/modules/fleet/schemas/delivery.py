from datetime import UTC, datetime
from uuid import UUID

from pydantic import Field, field_validator, model_validator

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
    items: list[ManifestItem] = Field(min_length=1, max_length=100)

    @model_validator(mode='after')
    def unique_packages(self):
        if len({i.package_id for i in self.items}) != len(self.items):
            raise ValueError('Each package must appear once')
        return self


class DeliveryAction(VersionInput, LocationInput):
    pass


class DepartureInput(DeliveryAction):
    estimated_arrival_time: datetime

    @field_validator('estimated_arrival_time')
    @classmethod
    def future(cls, value):
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
