from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, SecretStr

from app.core.responses.envelope import Envelope


class LoginPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    tenant_id: UUID
    username: str = Field(min_length=1, max_length=100, strict=True)
    password: SecretStr = Field(min_length=1, max_length=72)


class RefreshPayload(BaseModel):
    model_config = ConfigDict(extra='forbid')
    refresh_token: SecretStr = Field(min_length=1, max_length=101)


class TokensData(BaseModel):
    access_token: str
    refresh_token: str
    refresh_expires_at: datetime
    token_type: str
    expires_in: int


class IdentityData(BaseModel):
    user_id: UUID
    tenant_id: UUID
    roles: list[str]
    permissions: list[str]


class LogoutData(BaseModel):
    logged_out: bool


class TokensEnvelope(Envelope):
    data: TokensData


class IdentityEnvelope(Envelope):
    data: IdentityData


class LogoutEnvelope(Envelope):
    data: LogoutData
