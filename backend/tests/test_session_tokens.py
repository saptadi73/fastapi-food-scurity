import asyncio
import os
from datetime import UTC, datetime, timedelta
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import delete, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.runtime_role import provision_runtime_role
from app.modules.authentication.application.session_service import SessionService
from app.modules.authentication.infrastructure.access_tokens import (
    AccessTokenCodec,
    InvalidAccessTokenError,
)
from app.modules.authentication.infrastructure.orm import AuthSession, RefreshToken, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import Tenant

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')
CODEC = AccessTokenCodec(SecretStr('session-tests-only-signing-secret-minimum-32-bytes'))
PASSWORD = 'session fixture password'


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_session_rotation_revocation_and_runtime():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            tx = await c.begin()
            try:
                async with AsyncSession(bind=c) as db:
                    await seed_development(db, environment='development')
                    await db.execute(update(User.__table__).where(User.user_id == seed_id('actor')).values(password_hash=await hash_password_async(PASSWORD)))
                    await provision_runtime_role(c)
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    service = SessionService(db, CODEC)
                    pair = await service.login(seed_id('tenant'), 'dev-maintenance', PASSWORD)
                    raw, access = pair.refresh_token.get_secret_value(), pair.access_token.get_secret_value()
                    assert raw not in repr(pair) and access not in repr(pair)
                    assert (await service.resolve_access(access)).actor_id == seed_id('actor')
                    stored = await db.scalar(select(RefreshToken.token_hash))
                    assert len(stored) == 64 and stored not in raw
                    assert (await service.refresh(raw[:-1] + ('A' if raw[-1] != 'A' else 'B'))).status == 'INVALID'
                    rotated = await service.refresh(raw)
                    assert rotated.status == 'ROTATED'
                    assert rotated.tokens.refresh_expires_at == pair.refresh_expires_at
                    assert rotated.tokens.refresh_token != pair.refresh_token
                    assert (await service.refresh(raw)).status == 'REUSED'
                    assert (await service.refresh(rotated.tokens.refresh_token.get_secret_value())).status == 'INVALID'
                    for token in (access, rotated.tokens.access_token.get_secret_value()):
                        with pytest.raises(InvalidAccessTokenError):
                            await service.resolve_access(token)
                    second = await service.login(seed_id('tenant'), 'dev-maintenance', PASSWORD)
                    second_raw = second.refresh_token.get_secret_value()
                    assert await service.logout(second_raw)
                    revoked = await db.scalar(select(AuthSession.revoked_at).where(AuthSession.session_id == CODEC.decode(second.access_token.get_secret_value()).session_id))
                    assert await service.logout(second_raw)
                    assert revoked == await db.scalar(select(AuthSession.revoked_at).where(AuthSession.session_id == CODEC.decode(second.access_token.get_secret_value()).session_id))
                    assert not await service.logout('malformed')
                    with pytest.raises(InvalidAccessTokenError):
                        await service.resolve_access(CODEC.issue(seed_id('actor'), seed_id('tenant'), roles=[], permissions=[]))
                    expired = await service.login(seed_id('tenant'), 'dev-maintenance', PASSWORD)
                    expired_id = CODEC.decode(expired.access_token.get_secret_value()).session_id
                    await c.execute(text('RESET ROLE'))
                    now = datetime.now(UTC)
                    await db.execute(update(AuthSession.__table__).where(AuthSession.session_id == expired_id).values(created_at=now-timedelta(days=8), expires_at=now-timedelta(days=1)))
                    assert (await service.refresh(expired.refresh_token.get_secret_value())).status == 'INVALID'
                    with pytest.raises(InvalidAccessTokenError):
                        await service.resolve_access(expired.access_token.get_secret_value())
            finally:
                await tx.rollback()
    finally:
        await engine.dispose()


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_concurrent_refresh_commits_family_revocation():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    factory = async_sessionmaker(engine)
    tenant, actor = uuid4(), uuid4()
    try:
        async with factory() as db, db.begin():
            await db.execute(insert(Tenant.__table__).values(tenant_id=tenant, tenant_code=str(tenant), tenant_name='Concurrent token test'))
            await db.execute(insert(User.__table__).values(user_id=actor, tenant_id=tenant, username='tester', fullname='Fixture', email='test@example.invalid', status='ACTIVE', password_hash=await hash_password_async(PASSWORD)))
            pair = await SessionService(db, CODEC).login(tenant, 'tester', PASSWORD)

        async def rotate():
            async with factory() as db, db.begin():
                return await SessionService(db, CODEC).refresh(pair.refresh_token.get_secret_value())

        results = await asyncio.gather(rotate(), rotate())
        assert sorted(r.status for r in results) == ['REUSED', 'ROTATED']
        winner = next(r.tokens for r in results if r.status == 'ROTATED')
        async with factory() as db, db.begin():
            assert (await SessionService(db, CODEC).refresh(winner.refresh_token.get_secret_value())).status == 'INVALID'
            with pytest.raises(InvalidAccessTokenError):
                await SessionService(db, CODEC).resolve_access(winner.access_token.get_secret_value())
    finally:
        async with factory() as db, db.begin():
            for model in (RefreshToken, AuthSession, User, Tenant):
                await db.execute(delete(model.__table__).where(model.tenant_id == tenant))
        await engine.dispose()
