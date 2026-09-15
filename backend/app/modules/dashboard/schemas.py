from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.core.responses.envelope import Envelope


class DashboardHomeData(BaseModel):
    complaints_open: int
    recalls_open: int
    deliveries_in_transit: int
    packages_recalled: int
    packages_delivered: int
    packages_received: int
    packages_consumed: int
    packages_discarded: int
    production_completed: int
    raw_batches_available: int


class DashboardHomeEnvelope(Envelope):
    data: DashboardHomeData


class DashboardStorageData(BaseModel):
    storages_active: int
    storage_zones: int
    raw_batches_accepted: int
    stock_entries: int
    temperature_logs: int


class DashboardFleetData(BaseModel):
    vehicles_active: int
    drivers_active: int
    deliveries_created: int
    deliveries_in_transit: int
    deliveries_completed: int
    gps_logs: int


class DashboardHoldingData(BaseModel):
    packages_created: int
    packages_packaged: int
    packages_released: int
    packages_expired: int
    packages_recalled: int
    holding_logs: int
    alarms_open: int


class DashboardRecallData(BaseModel):
    complaints_open: int
    recalls_open: int
    recalls_completed: int
    packages_recalled: int
    recall_movements: int


class DashboardNotificationData(BaseModel):
    pending: int
    sent: int
    failed: int
    cancelled: int
    dashboard_pending: int
    email_pending: int
    whatsapp_pending: int
    telegram_pending: int


class DashboardStorageEnvelope(Envelope):
    data: DashboardStorageData


class DashboardStorageTemperatureData(BaseModel):
    storage_id: UUID
    storage_name: str
    storage_type: str
    temperature_min: Decimal | None
    temperature_max: Decimal | None
    device_uuid: UUID | None
    temperature_log_id: UUID | None
    recorded_at: datetime | None
    temperature: Decimal | None
    unit: str | None
    status: str

    @field_validator('recorded_at')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC) if value else None


class DashboardStorageTemperaturePage(BaseModel):
    items: list[DashboardStorageTemperatureData]
    offset: int
    limit: int
    next_offset: int | None


class DashboardStorageTemperaturePageEnvelope(Envelope):
    data: DashboardStorageTemperaturePage


class DashboardFleetEnvelope(Envelope):
    data: DashboardFleetData


class DashboardHoldingEnvelope(Envelope):
    data: DashboardHoldingData


class DashboardRecallEnvelope(Envelope):
    data: DashboardRecallData


class DashboardNotificationEnvelope(Envelope):
    data: DashboardNotificationData
