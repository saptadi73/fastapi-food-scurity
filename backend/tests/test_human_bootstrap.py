import os
from uuid import uuid4

import pytest
from pydantic import ValidationError
from sqlalchemy import func, insert, select, text, update
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine

from app.core.database.development_seed import seed_development, seed_id
from app.core.database.human_bootstrap import (
    BootstrapConflictError,
    HumanAccountInput,
    check_human_account,
    create_human_account,
)
from app.core.database.runtime_role import provision_runtime_role
from app.modules.authentication.application.account_service import AccountService
from app.modules.authentication.infrastructure.orm import Role, User, UserRole
from app.modules.authentication.infrastructure.passwords import verify_password
from app.modules.master.infrastructure.orm import Tenant
from scripts import bootstrap_human

TEST_URL = os.environ.get('FSOS_TEST_DATABASE_URL', '')


def payload(**changes):
    return HumanAccountInput(**{
        'tenant_id': seed_id('tenant'), 'actor_id': seed_id('actor'),
        'role_ids': [seed_id('role')], 'username': 'human-operator',
        'fullname': 'Human Operator', 'email': 'operator@example.org', **changes,
    })


@pytest.mark.skipif(not TEST_URL, reason='Migrated test database required')
async def test_human_bootstrap_validation_atomicity_and_login():
    assert (make_url(TEST_URL).database or '').startswith('fsos_test')
    engine = create_async_engine(TEST_URL)
    try:
        async with engine.connect() as c:
            tx = await c.begin()
            identifier = None
            try:
                async with AsyncSession(bind=c) as session:
                    await seed_development(session, environment='development')
                    data = payload()
                    count = await session.scalar(select(func.count()).select_from(User))
                    preview = await check_human_account(session, data, environment='development')
                    assert preview['roles'] == ['DEV_MAINTENANCE'] and preview['will_create']
                    assert await session.scalar(select(func.count()).select_from(User)) == count
                    password = 'chosen bootstrap passphrase'
                    created = await create_human_account(session, data, password, environment='development')
                    identifier = created['user_id']
                    row = (await session.execute(select(User.__table__).where(User.user_id == identifier))).mappings().one()
                    assert row['created_by'] == row['updated_by'] == seed_id('actor')
                    assert row['status'] == 'ACTIVE' and verify_password(password, row['password_hash'])
                    assert 'password_hash' not in created and password not in str(created)
                    user_role = (await session.execute(select(UserRole.__table__).where(UserRole.user_id == identifier))).mappings().one()
                    assert user_role['role_id'] == seed_id('role') and user_role['created_by'] == seed_id('actor')
                    account = await AccountService(session).authenticate(data.tenant_id, ' HUMAN-OPERATOR ', password)
                    assert account.user_id == identifier and 'AssetRegistry.Sync' in account.permissions
                    for duplicate in (payload(username=' HUMAN-OPERATOR ', email='other@example.org'), payload(username='new-user')):
                        with pytest.raises(BootstrapConflictError):
                            await create_human_account(session, duplicate, 'different passphrase', environment='development')
                    assert row['password_hash'] == await session.scalar(select(User.__table__.c.password_hash).where(User.user_id == identifier))
                    for model, key, entity in ((User, User.user_id, seed_id('actor')), (Tenant, Tenant.tenant_id, seed_id('tenant')), (Role, Role.role_id, seed_id('role'))):
                        async with session.begin_nested() as nested:
                            await session.execute(update(model.__table__).where(key == entity).values(deleted_at=func.now()))
                            with pytest.raises(BootstrapConflictError):
                                await check_human_account(session, payload(username='fresh', email='fresh@example.org'), environment='development')
                            await nested.rollback()
                    other = uuid4()
                    foreign_role = uuid4()
                    await session.execute(insert(Tenant.__table__).values(tenant_id=other, tenant_code=str(other), tenant_name='Other'))
                    await session.execute(insert(Role.__table__).values(role_id=foreign_role, tenant_id=other, role_code='OTHER', role_name='Other'))
                    with pytest.raises(BootstrapConflictError):
                        await check_human_account(session, payload(username='fresh', email='fresh@example.org', role_ids=[foreign_role]), environment='development')
                    await provision_runtime_role(c)
                    await c.execute(text('SET LOCAL ROLE fsos_runtime'))
                    with pytest.raises(DBAPIError) as error:
                        async with session.begin_nested():
                            await create_human_account(session, payload(username='fresh', email='fresh@example.org'), password, environment='development')
                    assert error.value.orig.sqlstate == '42501'
                    await c.execute(text('RESET ROLE'))
                    assert await session.scalar(select(User.__table__.c.password_hash).where(User.user_id == seed_id('actor'))) is None
            finally:
                await tx.rollback()
            assert await c.scalar(select(User.user_id).where(User.user_id == identifier)) is None
    finally:
        await engine.dispose()


@pytest.mark.parametrize('changes', [
    {'username': '  '}, {'username': 'bad\x00'}, {'fullname': '\ud800'},
    {'email': 'invalid'}, {'role_ids': []}, {'role_ids': [seed_id('role'), seed_id('role')]},
])
def test_human_input_validation(changes):
    with pytest.raises(ValidationError):
        payload(**changes)


async def test_production_bootstrap_rejected_before_database():
    with pytest.raises(ValueError):
        await create_human_account(None, payload(), 'valid passphrase', environment='production')


def test_hidden_prompt_rejects_pipe_and_mismatch(monkeypatch):
    monkeypatch.setattr(bootstrap_human.sys.stdin, 'isatty', lambda: False)
    with pytest.raises(ValueError):
        bootstrap_human.prompt_password()
    monkeypatch.setattr(bootstrap_human.sys.stdin, 'isatty', lambda: True)
    values = iter(['first passphrase', 'different passphrase'])
    monkeypatch.setattr(bootstrap_human.getpass, 'getpass', lambda _: next(values))
    with pytest.raises(ValueError):
        bootstrap_human.prompt_password()
