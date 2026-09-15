from datetime import UTC, datetime
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

from app.core.responses.envelope import Envelope
from app.modules.master.schemas.locations import AuditData, Page


class AssetData(AuditData):
    asset_uuid: UUID
    asset_type: str
    entity_uuid: UUID
    code: str
    name: str
    status: str


class RelationshipData(AuditData):
    relationship_uuid: UUID
    parent_uuid: UUID
    child_uuid: UUID
    relationship_type: str


class MovementData(AuditData):
    movement_id: UUID
    asset_type: str
    asset_uuid: UUID
    movement_type: str
    from_location: UUID | None
    to_location: UUID | None
    operator: UUID | None
    movement_time: datetime
    remarks: str | None

    @field_validator('movement_time')
    @classmethod
    def utc(cls, value):
        return value.astimezone(UTC)


class RelationshipPage(Page):
    items: list[RelationshipData]


class MovementPage(Page):
    items: list[MovementData]


class TraceGraphData(BaseModel):
    root_asset_uuid: UUID
    direction: str
    depth: int
    nodes: list[AssetData] = Field(default_factory=list)
    edges: list[RelationshipData] = Field(default_factory=list)
    truncated: bool


class AssetPassportData(BaseModel):
    asset: AssetData
    parents: list[RelationshipData] = Field(default_factory=list)
    children: list[RelationshipData] = Field(default_factory=list)
    movements: list[MovementData] = Field(default_factory=list)


class ImpactData(BaseModel):
    root_asset_uuid: UUID
    depth: int
    impacted_assets: list[AssetData] = Field(default_factory=list)
    affected_counts: dict[str, int] = Field(default_factory=dict)
    package_assets: list[AssetData] = Field(default_factory=list)
    complaint_assets: list[AssetData] = Field(default_factory=list)
    recall_assets: list[AssetData] = Field(default_factory=list)
    edges: list[RelationshipData] = Field(default_factory=list)
    truncated: bool


class AssetEnvelope(Envelope):
    data: AssetData


class RelationshipPageEnvelope(Envelope):
    data: RelationshipPage


class MovementPageEnvelope(Envelope):
    data: MovementPage


class TraceGraphEnvelope(Envelope):
    data: TraceGraphData


class AssetPassportEnvelope(Envelope):
    data: AssetPassportData


class ImpactEnvelope(Envelope):
    data: ImpactData
