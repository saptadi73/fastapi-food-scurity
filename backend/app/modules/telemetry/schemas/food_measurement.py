from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from app.core.responses.envelope import Envelope


class FoodTemperatureMeasurementInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    device_id: UUID
    context_type: Literal['RECEIVING', 'PRODUCTION_COMPLETE', 'PACKAGING', 'SCHOOL_RECEIVING']
    context_id: UUID | None = None
    maximum_age_seconds: int = Field(default=60, ge=5, le=300)


class FoodTemperatureMeasurementData(BaseModel):
    device_id: UUID
    device_uuid: UUID
    device_name: str
    temperature_log_id: UUID
    temperature: str
    unit: str
    recorded_at: datetime
    age_seconds: int
    context_type: str
    context_id: UUID | None
    valid: bool


class FoodTemperatureMeasurementEnvelope(Envelope):
    data: FoodTemperatureMeasurementData
