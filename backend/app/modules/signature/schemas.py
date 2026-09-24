from datetime import datetime
from uuid import UUID

from pydantic import BaseModel

from app.core.responses.envelope import Envelope


class SignatureData(BaseModel):
    signature_id: UUID
    entity_type: str
    entity_id: UUID
    purpose: str
    signed_by: UUID
    signed_at: datetime
    signer_snapshot: dict
    file_id: UUID
    content_type: str
    size_bytes: int
    sha256_hex: str
    status: str
    version: int


class SignatureVerificationData(SignatureData):
    verification_status: str
    calculated_sha256_hex: str


class SignatureEnvelope(Envelope):
    data: SignatureData


class SignatureVerificationEnvelope(Envelope):
    data: SignatureVerificationData
