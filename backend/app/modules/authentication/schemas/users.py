from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr, model_validator

from app.core.responses.envelope import Envelope


class LocationAssignmentInput(BaseModel):
    model_config = ConfigDict(extra='forbid')
    location_type: str = Field(pattern='^(KITCHEN|SCHOOL)$')
    kitchen_id: UUID | None = None
    school_id: UUID | None = None

    @model_validator(mode='after')
    def exactly_one_target(self):
        valid = ((self.location_type == 'KITCHEN' and self.kitchen_id is not None and self.school_id is None)
                 or (self.location_type == 'SCHOOL' and self.school_id is not None and self.kitchen_id is None))
        if not valid:
            raise ValueError('Location type and target must match')
        return self


class UserCreate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    username: str = Field(min_length=1, max_length=100, pattern=r'^[A-Za-z0-9._-]+$')
    fullname: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    job_title: str | None = Field(default=None, min_length=1, max_length=150)
    password: SecretStr = Field(min_length=12, max_length=72)
    role_ids: list[UUID] = Field(min_length=1)
    location_assignments: list[LocationAssignmentInput] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_references(self):
        if len(self.role_ids) != len(set(self.role_ids)):
            raise ValueError('role_ids must be unique')
        targets = [(item.location_type, item.kitchen_id or item.school_id) for item in self.location_assignments]
        if len(targets) != len(set(targets)):
            raise ValueError('location_assignments must be unique')
        return self


class UserUpdate(BaseModel):
    model_config = ConfigDict(extra='forbid')
    expected_version: int = Field(ge=1)
    fullname: str = Field(min_length=1, max_length=200)
    email: str = Field(min_length=3, max_length=254, pattern=r'^[^\s@]+@[^\s@]+\.[^\s@]+$')
    job_title: str | None = Field(default=None, min_length=1, max_length=150)
    status: str = Field(pattern='^(ACTIVE|INACTIVE|LOCKED)$')
    password: SecretStr | None = Field(default=None, min_length=12, max_length=72)
    role_ids: list[UUID] = Field(min_length=1)
    location_assignments: list[LocationAssignmentInput] = Field(default_factory=list)

    @model_validator(mode='after')
    def unique_references(self):
        if len(self.role_ids) != len(set(self.role_ids)):
            raise ValueError('role_ids must be unique')
        targets = [(item.location_type, item.kitchen_id or item.school_id) for item in self.location_assignments]
        if len(targets) != len(set(targets)):
            raise ValueError('location_assignments must be unique')
        return self


class LocationAssignmentData(BaseModel):
    assignment_id: UUID
    location_type: str
    kitchen_id: UUID | None
    school_id: UUID | None


class RoleData(BaseModel):
    role_id: UUID
    role_code: str
    role_name: str


class UserData(BaseModel):
    user_id: UUID
    username: str
    fullname: str
    email: str
    job_title: str | None
    status: str
    version: int
    created_at: datetime
    roles: list[RoleData]
    location_assignments: list[LocationAssignmentData]


class UserPageData(BaseModel):
    items: list[UserData]
    total: int
    offset: int
    limit: int
    next_offset: int | None


class RoleListEnvelope(Envelope):
    data: list[RoleData]


class UserEnvelope(Envelope):
    data: UserData


class UserPageEnvelope(Envelope):
    data: UserPageData
