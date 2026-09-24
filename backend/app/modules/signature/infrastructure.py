from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKeyConstraint, Index, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database.mixins import AuditMixin
from app.core.database.session import Base


class SignatureEvidence(AuditMixin, Base):
    __tablename__ = 'signature_evidence'
    __table_args__ = (
        ForeignKeyConstraint(['tenant_id', 'signed_by'], ['app_user.tenant_id', 'app_user.user_id'],
                             name='fk_signature_tenant_user', ondelete='RESTRICT'),
        UniqueConstraint('tenant_id', 'signature_id', name='uq_signature_tenant_id'),
        UniqueConstraint('tenant_id', 'entity_type', 'entity_id', 'purpose', name='uq_signature_target_purpose'),
        CheckConstraint("entity_type IN ('SCHOOL_RECEIVING','COMPLAINT')", name='ck_signature_entity_type'),
        CheckConstraint("content_type IN ('image/png','image/webp')", name='ck_signature_content_type'),
        CheckConstraint("length(sha256_hex) = 64", name='ck_signature_sha256'),
        CheckConstraint("length(trim(purpose)) > 0", name='ck_signature_purpose'),
        CheckConstraint("jsonb_typeof(signer_snapshot) = 'object'", name='ck_signature_snapshot'),
        CheckConstraint("status = 'CAPTURED'", name='ck_signature_status'),
        CheckConstraint('size_bytes > 0', name='ck_signature_size'),
        CheckConstraint('version >= 1', name='ck_signature_version'),
        Index('ix_signature_target', 'tenant_id', 'entity_type', 'entity_id'),
        Index('ix_signature_signed_at', 'signed_at'),
    )
    signature_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID]
    entity_type: Mapped[str] = mapped_column(String(30))
    entity_id: Mapped[UUID]
    purpose: Mapped[str] = mapped_column(String(100))
    signed_by: Mapped[UUID]
    signed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    signer_snapshot: Mapped[dict] = mapped_column(JSONB)
    file_id: Mapped[UUID]
    storage_reference: Mapped[str] = mapped_column(String(1024))
    content_type: Mapped[str] = mapped_column(String(30))
    size_bytes: Mapped[int]
    sha256_hex: Mapped[str] = mapped_column(String(64))
    status: Mapped[str] = mapped_column(String(20), default='CAPTURED', server_default='CAPTURED')
