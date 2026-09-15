from datetime import UTC, datetime
from decimal import Decimal
from uuid import UUID

from pydantic import Field, field_validator, model_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page, VersionInput


class RecallInput(LocationInput):
    production_batch_id: UUID
    reason: str = Field(min_length=1, max_length=4000)


class RecallCloseInput(VersionInput, LocationInput):
    pass


class RecallExecuteInput(VersionInput, LocationInput):
    pass


class RecallWithdrawalInput(VersionInput, LocationInput):
    package_id: UUID | None = None
    evidence_code: str = Field(min_length=1, max_length=100)
    quantity: Decimal | None = Field(default=None, ge=0, max_digits=12, decimal_places=3)
    uom: str | None = Field(default=None, min_length=1, max_length=20)
    condition_note: str = Field(min_length=1, max_length=4000)
    photo: str | None = Field(default=None, max_length=1024)
    withdrawn_at: datetime | None = None
    completed_at: datetime | None = None

    @field_validator('withdrawn_at', 'completed_at')
    @classmethod
    def not_future(cls, value):
        if value is None:
            return None
        value = value.astimezone(UTC)
        if value > datetime.now(UTC):
            raise ValueError('time must not be in the future')
        return value

    @model_validator(mode='after')
    def quantity_uom_pair(self):
        if (self.quantity is None) != (self.uom is None):
            raise ValueError('quantity and uom must be supplied together')
        if self.completed_at is not None and self.withdrawn_at is not None and self.completed_at < self.withdrawn_at:
            raise ValueError('completed_at must not be before withdrawn_at')
        return self


class AffectedPackageData(AuditData):
    package_id: UUID
    package_code: str
    production_batch_id: UUID
    package_number: int
    quantity: Decimal | None
    status: str


class RecallData(AuditData):
    recall_id: UUID
    production_batch_id: UUID
    reason: str
    started_at: datetime
    completed_at: datetime | None
    affected_packages: list[AffectedPackageData] = Field(default_factory=list)

    @field_validator('started_at', 'completed_at')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC) if value else None


class RecallWithdrawalData(AuditData):
    withdrawal_id: UUID
    recall_id: UUID
    package_id: UUID | None
    evidence_code: str
    quantity: Decimal | None
    uom: str | None
    condition_note: str
    photo: str | None
    withdrawn_at: datetime
    completed_at: datetime | None

    @field_validator('withdrawn_at', 'completed_at')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC) if value else None


class RecallEnvelope(Envelope):
    data: RecallData


class RecallWithdrawalEnvelope(Envelope):
    data: RecallWithdrawalData


class RecallPage(Page):
    items: list[RecallData]


class RecallPageEnvelope(Envelope):
    data: RecallPage


class RecallWithdrawalPage(Page):
    items: list[RecallWithdrawalData]


class RecallWithdrawalPageEnvelope(Envelope):
    data: RecallWithdrawalPage
