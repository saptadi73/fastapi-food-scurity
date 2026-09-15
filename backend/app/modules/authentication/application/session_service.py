"""Session-backed tokens. Caller commits outcomes before delivering tokens or errors."""
import hashlib
import hmac
import re
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from pydantic import SecretStr
from sqlalchemy import insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database.scope import ActorScope
from app.modules.authentication.application.account_service import (
    AccountService,
    InvalidCredentialsError,
)
from app.modules.authentication.infrastructure.access_tokens import (
    AccessTokenCodec,
    InvalidAccessTokenError,
)
from app.modules.authentication.infrastructure.orm import AuthSession, RefreshToken


@dataclass(frozen=True)
class TokenPair:
    access_token: SecretStr
    refresh_token: SecretStr
    refresh_expires_at: datetime
    token_type: str = 'Bearer'
    expires_in: int = 900


@dataclass(frozen=True)
class RefreshOutcome:
    status: str
    tokens: TokenPair | None = None


class SessionService:
    def __init__(self, session: AsyncSession, codec: AccessTokenCodec):
        self.session, self.codec = session, codec
        self.accounts = AccountService(session)

    async def _pair(self, account, family):
        token_id = uuid4()
        raw = f'{token_id}.{secrets.token_urlsafe(48)}'
        access = self.codec.issue(account.user_id, account.tenant_id,
            roles=list(account.roles), permissions=list(account.permissions), session_id=family['session_id'])
        await self.session.execute(insert(RefreshToken.__table__).values(
            token_id=token_id, tenant_id=account.tenant_id, session_id=family['session_id'],
            token_hash=hashlib.sha256(raw.encode('ascii')).hexdigest(), created_at=datetime.now(UTC),
        ))
        return TokenPair(SecretStr(access), SecretStr(raw), family['expires_at'])

    async def login(self, tenant, username: str, password: str) -> TokenPair:
        account = await self.accounts.authenticate(tenant, username, password)
        now = datetime.now(UTC)
        family = {'session_id': uuid4(), 'tenant_id': account.tenant_id, 'user_id': account.user_id,
                  'created_at': now, 'expires_at': now + timedelta(days=7)}
        await self.session.execute(insert(AuthSession.__table__).values(**family))
        return await self._pair(account, family)

    async def _lookup(self, raw):
        if not isinstance(raw, str) or not re.fullmatch(r'[0-9a-f-]{36}\.[A-Za-z0-9_-]{64}', raw):
            return None
        try:
            token_id = UUID(raw[:36])
        except ValueError:
            return None
        if str(token_id) != raw[:36]:
            return None
        t, s = RefreshToken.__table__, AuthSession.__table__
        row = (await self.session.execute(select(t, s.c.user_id).join(s,
            (t.c.tenant_id == s.c.tenant_id) & (t.c.session_id == s.c.session_id),
        ).where(t.c.token_id == token_id))).mappings().one_or_none()
        if row is None or not hmac.compare_digest(row['token_hash'], hashlib.sha256(raw.encode('ascii')).hexdigest()):
            return None
        return row

    async def _lock_family(self, row):
        return (await self.session.execute(select(AuthSession.__table__).where(
            AuthSession.session_id == row['session_id'], AuthSession.tenant_id == row['tenant_id'],
        ).with_for_update())).mappings().one()

    async def refresh(self, raw: str) -> RefreshOutcome:
        row = await self._lookup(raw)
        if row is None:
            return RefreshOutcome('INVALID')
        try:
            # Lock actor/RBAC before the session, matching login and access resolution order.
            account = await self.accounts.snapshot(row['tenant_id'], row['user_id'])
        except InvalidCredentialsError:
            return RefreshOutcome('INVALID')
        family = await self._lock_family(row)
        now = datetime.now(UTC)
        if family['revoked_at'] is not None or family['expires_at'] <= now:
            return RefreshOutcome('INVALID')
        # Re-read after serialization: another request may have consumed this token.
        used_at = await self.session.scalar(select(RefreshToken.used_at).where(RefreshToken.token_id == row['token_id']))
        if used_at is not None:
            await self._revoke(family['session_id'], now)
            # Do not raise: the caller must commit this revocation even while rejecting the request.
            return RefreshOutcome('REUSED')
        await self.session.execute(update(RefreshToken.__table__).where(RefreshToken.token_id == row['token_id']).values(used_at=now))
        return RefreshOutcome('ROTATED', await self._pair(account, family))

    async def _revoke(self, session_id, now):
        await self.session.execute(update(AuthSession.__table__).where(
            AuthSession.session_id == session_id, AuthSession.revoked_at.is_(None),
        ).values(revoked_at=now))

    async def logout(self, raw: str) -> bool:
        """Proof of refresh-token possession revokes its family, including a previously used token."""
        row = await self._lookup(raw)
        if row is None:
            return False
        family = await self._lock_family(row)
        await self._revoke(family['session_id'], datetime.now(UTC))
        return True

    async def resolve_access(self, token: str) -> ActorScope:
        identity = self.codec.decode(token)
        if identity.session_id is None:
            raise InvalidAccessTokenError('Session-bound access token required')
        scope = await self.accounts.resolve_access(token, self.codec)
        family = (await self.session.execute(select(AuthSession.__table__).where(
            AuthSession.session_id == identity.session_id, AuthSession.tenant_id == scope.tenant_id,
            AuthSession.user_id == scope.actor_id,
        ).with_for_update(read=True))).mappings().one_or_none()
        if family is None or family['revoked_at'] is not None or family['expires_at'] <= datetime.now(UTC):
            raise InvalidAccessTokenError('Invalid or expired access token')
        return scope
