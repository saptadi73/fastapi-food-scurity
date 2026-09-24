import hashlib
import hmac
from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from sqlalchemy import insert, select

from app.core.config.settings import get_settings
from app.core.database.scope import ActorScope
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.authentication.infrastructure.orm import Role, User, UserLocationAssignment, UserRole
from app.modules.complaint.infrastructure.orm import Complaint
from app.modules.fleet.infrastructure.orm import SchoolReceiving
from app.modules.signature.infrastructure import SignatureEvidence


class SignatureConflictError(Exception):
    pass


class SignatureNotFoundError(Exception):
    pass


class SignatureService:
    def __init__(self, db, scope: ActorScope):
        self.db, self.scope = db, scope

    @property
    def audit(self):
        return {'tenant_id': self.scope.tenant_id, 'created_by': self.scope.actor_id,
                'updated_by': self.scope.actor_id}

    @staticmethod
    def permission(entity_type, action='sign'):
        if entity_type == 'SCHOOL_RECEIVING':
            return 'SchoolReceiving.Sign' if action == 'sign' else 'Signature.Verify'
        if entity_type == 'COMPLAINT':
            return 'Complaint.Sign' if action == 'sign' else 'Signature.Verify'
        raise SignatureConflictError('Unsupported signature entity type')

    async def target_school(self, entity_type: str, entity_id: UUID):
        model, key, school_column = ((SchoolReceiving, SchoolReceiving.school_receiving_id, SchoolReceiving.school)
                                     if entity_type == 'SCHOOL_RECEIVING'
                                     else (Complaint, Complaint.complaint_id, Complaint.school_id))
        row = (await self.db.execute(select(key, school_column).where(
            model.tenant_id == self.scope.tenant_id, key == entity_id,
            model.deleted_at.is_(None)).with_for_update(read=True))).one_or_none()
        if row is None:
            raise SignatureNotFoundError('Signature target not found in tenant')
        return row[1]

    async def require_location(self, school_id: UUID):
        assignment = await self.db.scalar(select(UserLocationAssignment.assignment_id).where(
            UserLocationAssignment.tenant_id == self.scope.tenant_id,
            UserLocationAssignment.user_id == self.scope.actor_id,
            UserLocationAssignment.location_type == 'SCHOOL',
            UserLocationAssignment.school_id == school_id,
            UserLocationAssignment.deleted_at.is_(None)).limit(1))
        if assignment is None:
            raise SignatureConflictError('Active signer assignment to target school required')

    async def signer_snapshot(self):
        user = (await self.db.execute(select(User.fullname, User.job_title).where(
            User.tenant_id == self.scope.tenant_id, User.user_id == self.scope.actor_id,
            User.status == 'ACTIVE', User.deleted_at.is_(None)))).one()
        roles = (await self.db.scalars(select(Role.role_code).select_from(UserRole).join(
            Role, (Role.tenant_id == UserRole.tenant_id) & (Role.role_id == UserRole.role_id)).where(
            UserRole.tenant_id == self.scope.tenant_id, UserRole.user_id == self.scope.actor_id,
            UserRole.deleted_at.is_(None), Role.deleted_at.is_(None)).order_by(Role.role_code))).all()
        return {'user_id': str(self.scope.actor_id), 'fullname': user.fullname,
                'job_title': user.job_title, 'roles': list(roles)}

    @staticmethod
    def validate_image(content_type: str, content: bytes):
        if content_type == 'image/png' and content.startswith(b'\x89PNG\r\n\x1a\n'):
            return '.png'
        if content_type == 'image/webp' and len(content) >= 12 and content[:4] == b'RIFF' and content[8:12] == b'WEBP':
            return '.webp'
        raise SignatureConflictError('Signature content does not match PNG/WebP MIME type')

    async def capture(self, entity_type: str, entity_id: UUID, purpose: str,
                      content_type: str, content: bytes):
        await require_permission(self.db, self.scope, self.permission(entity_type))
        school_id = await self.target_school(entity_type, entity_id)
        await self.require_location(school_id)
        if not purpose.strip() or len(purpose.strip()) > 100:
            raise SignatureConflictError('Purpose must contain 1 to 100 characters')
        maximum = min(get_settings().upload_max_bytes, 2 * 1024 * 1024)
        if not content or len(content) > maximum:
            raise SignatureConflictError('Signature image must contain 1 byte to 2 MiB')
        extension = self.validate_image(content_type, content)
        duplicate = await self.db.scalar(select(SignatureEvidence.signature_id).where(
            SignatureEvidence.tenant_id == self.scope.tenant_id,
            SignatureEvidence.entity_type == entity_type, SignatureEvidence.entity_id == entity_id,
            SignatureEvidence.purpose == purpose.strip()).limit(1))
        if duplicate is not None:
            raise SignatureConflictError('Signature purpose already captured for target')
        signature_id, file_id, now = uuid4(), uuid4(), datetime.now(UTC)
        digest = hashlib.sha256(content).hexdigest()
        directory = get_settings().upload_dir / str(self.scope.tenant_id) / 'signatures'
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / f'{file_id}{extension}'
        path.write_bytes(content)
        reference = f'signature/{self.scope.tenant_id}/{file_id}{extension}'
        await self.db.execute(insert(SignatureEvidence).values(
            signature_id=signature_id, entity_type=entity_type, entity_id=entity_id,
            purpose=purpose.strip(), signed_by=self.scope.actor_id, signed_at=now,
            signer_snapshot=await self.signer_snapshot(), file_id=file_id,
            storage_reference=reference, content_type=content_type, size_bytes=len(content),
            sha256_hex=digest, status='CAPTURED', created_at=now, updated_at=now, **self.audit))
        result = await self.get_by_id(signature_id, authorize=False)
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type='signature.captured',
            entity_type=entity_type, entity_uuid=entity_id,
            payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                     'signature_id': str(signature_id), 'purpose': purpose.strip(),
                     'sha256_hex': digest}, **self.audit))
        return result

    async def get_target(self, entity_type: str, entity_id: UUID):
        await require_permission(self.db, self.scope, self.permission(entity_type, 'verify'))
        row = (await self.db.execute(select(SignatureEvidence.__table__).where(
            SignatureEvidence.tenant_id == self.scope.tenant_id,
            SignatureEvidence.entity_type == entity_type, SignatureEvidence.entity_id == entity_id,
            SignatureEvidence.deleted_at.is_(None)).order_by(SignatureEvidence.signed_at.desc()).limit(1)
        )).mappings().one_or_none()
        if row is None:
            raise SignatureNotFoundError('Signature not found')
        return self.public(row)

    async def get_by_id(self, signature_id: UUID, authorize=True):
        if authorize:
            await require_permission(self.db, self.scope, 'Signature.Verify')
        row = (await self.db.execute(select(SignatureEvidence.__table__).where(
            SignatureEvidence.tenant_id == self.scope.tenant_id,
            SignatureEvidence.signature_id == signature_id,
            SignatureEvidence.deleted_at.is_(None)))).mappings().one_or_none()
        if row is None:
            raise SignatureNotFoundError('Signature not found')
        return self.public(row)

    @staticmethod
    def public(row):
        keys = ('signature_id','entity_type','entity_id','purpose','signed_by','signed_at',
                'signer_snapshot','file_id','content_type','size_bytes','sha256_hex','status','version')
        return {key: row[key] for key in keys}

    def image_path(self, evidence):
        extension = '.png' if evidence['content_type'] == 'image/png' else '.webp'
        return get_settings().upload_dir / str(self.scope.tenant_id) / 'signatures' / f"{evidence['file_id']}{extension}"

    async def verify(self, signature_id: UUID):
        evidence = await self.get_by_id(signature_id)
        path = self.image_path(evidence)
        if not path.is_file():
            calculated, status = '', 'MISSING'
        else:
            calculated = hashlib.sha256(path.read_bytes()).hexdigest()
            status = 'VERIFIED' if hmac.compare_digest(calculated, evidence['sha256_hex']) else 'MISMATCH'
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type='signature.verified',
            entity_type=evidence['entity_type'], entity_uuid=evidence['entity_id'],
            payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                     'signature_id': str(signature_id), 'verification_status': status}, **self.audit))
        return {**evidence, 'verification_status': status, 'calculated_sha256_hex': calculated}
