from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.responses.envelope import Envelope


class TelemetryTimestamp(BaseModel):
    recorded_at: datetime | None = None

    @field_validator('recorded_at')
    @classmethod
    def timestamp(cls, value):
        if value is None:
            return None
        if value.tzinfo is None or value > datetime.now(UTC):
            raise ValueError('Timezone required; recorded_at must not be in the future')
        return value.astimezone(UTC)


class GpsIngestInput(TelemetryTimestamp):
    vehicle_uuid: UUID
    latitude: Decimal = Field(ge=-90, le=90, max_digits=9, decimal_places=6)
    longitude: Decimal = Field(ge=-180, le=180, max_digits=9, decimal_places=6)
    speed: Decimal | None = Field(default=None, ge=0, max_digits=9, decimal_places=3)
    heading: Decimal | None = Field(default=None, ge=0, lt=360, max_digits=6, decimal_places=3)
    altitude: Decimal | None = Field(default=None, max_digits=12, decimal_places=3)
    hdop: Decimal | None = Field(default=None, ge=0, max_digits=9, decimal_places=3)
    satellite: int | None = Field(default=None, ge=0)


class TemperatureIngestInput(TelemetryTimestamp):
    device_uuid: UUID
    storage_uuid: UUID | None = None
    temperature: Decimal = Field(max_digits=8, decimal_places=3)
    unit: Literal['C', 'F', 'K'] = 'C'


class GpsIngestData(BaseModel):
    gps_log_id: UUID
    tenant_id: UUID
    vehicle_uuid: UUID
    recorded_at: datetime
    latitude: Decimal
    longitude: Decimal
    speed: Decimal | None
    heading: Decimal | None
    altitude: Decimal | None
    hdop: Decimal | None
    satellite: int | None

    @field_validator('recorded_at')
    @classmethod
    def recorded_utc(cls, value):
        return value.astimezone(UTC)


class TemperatureIngestData(BaseModel):
    temperature_log_id: UUID
    tenant_id: UUID
    device_uuid: UUID
    storage_uuid: UUID | None
    recorded_at: datetime
    temperature: Decimal
    unit: str

    @field_validator('recorded_at')
    @classmethod
    def temperature_utc(cls, value):
        return value.astimezone(UTC)


class GpsIngestEnvelope(Envelope):
    data: GpsIngestData


class TemperatureIngestEnvelope(Envelope):
    data: TemperatureIngestData
