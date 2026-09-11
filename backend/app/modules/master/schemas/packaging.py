from decimal import Decimal
from uuid import UUID

from pydantic import Field

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, LocationInput, Page, VersionInput


class PackagingTypeInput(LocationInput):
    code: str = Field(min_length=1, max_length=50)
    name: str = Field(min_length=1, max_length=200)
    material: str | None = Field(default=None, max_length=100)
    volume: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=3)


class PackagingTypeUpdate(PackagingTypeInput, VersionInput):
    pass


class PackagingTypeData(AuditData):
    package_type_id: UUID
    code: str
    name: str
    material: str | None
    volume: Decimal | None


class PackagingTypeEnvelope(Envelope):
    data: PackagingTypeData


class PackagingTypePage(Page):
    items: list[PackagingTypeData]


class PackagingTypePageEnvelope(Envelope):
    data: PackagingTypePage
