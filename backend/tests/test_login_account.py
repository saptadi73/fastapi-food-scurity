"""Integration checks run after the migration roundtrip fixture in test_database."""
import os
from uuid import uuid4

import pytest
from pydantic import SecretStr
from sqlalchemy import func, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.runtime_role import provision_runtime_role
from app.modules.authentication.application import account_service as module
from app.modules.authentication.application.account_service import (
    AccountService,
    InvalidCredentialsError,
)
from app.modules.authentication.infrastructure.access_tokens import AccessTokenCodec
from app.modules.authentication.infrastructure.authorization import (
    PermissionDeniedError,
    require_permission,
)
from app.modules.authentication.infrastructure.orm import RolePermission, User
from app.modules.authentication.infrastructure.passwords import hash_password_async
from app.modules.master.infrastructure.orm import Tenant

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')


@pytest.mark.parametrize('username', [None, 'bad\x00name', '\ud800', '   '])
async def test_invalid_username_never_reaches_database(username):
    with pytest.raises(InvalidCredentialsError):
        await AccountService(None).authenticate(uuid4(), username, 'valid passphrase')


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_account_authentication_and_live_scope(monkeypatch):
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            transaction = await c.begin()
            try:
                async with AsyncSession(bind=c) as session:
                    await seed_development(session, environment='development')
                    tenant, actor = seed_id('tenant'), seed_id('actor')
                    service = AccountService(session)
                    password = 'test account passphrase'
                    with pytest.raises(InvalidCredentialsError):
                        await service.authenticate(tenant, 'dev-maintenance', password)
                    hashed = await hash_password_async(password)
                    await session.execute(update(User.__table__).where(User.user_id == actor).values(password_hash=hashed))
                    await provision_runtime_role(c)
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    account = await service.authenticate(tenant, ' DEV-MAINTENANCE ', password)
                    assert account.user_id == actor and account.tenant_id == tenant
                    assert account.roles == ('DEV_MAINTENANCE',)
                    assert 'AssetRegistry.Sync' in account.permissions
                    assert password not in repr(account) and hashed not in repr(account)
                    for tenant_id, username, supplied in (
                        (uuid4(), 'dev-maintenance', password), (tenant, 'missing', password),
                        (tenant, 'dev-maintenance', 'wrong password'), (tenant, 'dev-maintenance', 'short'),
                    ):
                        with pytest.raises(InvalidCredentialsError, match='^Invalid credentials$'):
                            await service.authenticate(tenant_id, username, supplied)
                    codec = AccessTokenCodec(SecretStr('test-only-account-codec-key-at-least-32-bytes'))
                    token = codec.issue(actor, tenant, roles=list(account.roles), permissions=list(account.permissions))
                    scope = await service.resolve_access(token, codec)
                    await require_permission(session, scope, 'AssetRegistry.Sync')
                    await c.execute(text('RESET ROLE'))
                    await session.execute(update(RolePermission.__table__).where(RolePermission.tenant_id == tenant).values(deleted_at=func.now()))
                    assert (await service.authenticate(tenant, 'dev-maintenance', password)).permissions == ()
                    scope = await service.resolve_access(token, codec)
                    with pytest.raises(PermissionDeniedError):
                        await require_permission(session, scope, 'AssetRegistry.Sync')
                    for model, key, identifier in ((User, User.user_id, actor), (Tenant, Tenant.tenant_id, tenant)):
                        for fields in ({'status': 'INACTIVE'}, {'deleted_at': func.now()}):
                            async with session.begin_nested() as savepoint:
                                await session.execute(update(model.__table__).where(key == identifier).values(**fields))
                                with pytest.raises(InvalidCredentialsError):
                                    await service.authenticate(tenant, 'dev-maintenance', password)
                                with pytest.raises(InvalidCredentialsError):
                                    await service.resolve_access(token, codec)
                                await savepoint.rollback()
                    original = module.verify_login_password_async

                    async def password_changed_during_check(supplied, stored):
                        result = await original(supplied, stored)
                        await session.execute(update(User.__table__).where(User.user_id == actor).values(password_hash=None))
                        return result

                    monkeypatch.setattr(module, 'verify_login_password_async', password_changed_during_check)
                    with pytest.raises(InvalidCredentialsError):
                        await service.authenticate(tenant, 'dev-maintenance', password)
            finally:
                await transaction.rollback()
    finally:
        await engine.dispose()
