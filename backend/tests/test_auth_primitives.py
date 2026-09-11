from datetime import UTC, datetime
from uuid import uuid4

import bcrypt
import jwt
import pytest
from pydantic import SecretStr

from app.modules.authentication.infrastructure.access_tokens import (
    AccessTokenCodec,
    InvalidAccessTokenError,
)
from app.modules.authentication.infrastructure.passwords import (
    hash_password,
    hash_password_async,
    verify_login_password_async,
    verify_password,
    verify_password_async,
)

SECRET = SecretStr('test-only-signing-key-with-at-least-32-bytes')


@pytest.mark.parametrize('password,stored', [('valid passphrase', None), ('short', None), ('valid passphrase', 'broken')])
async def test_login_dummy_work(password, stored, monkeypatch):
    original = bcrypt.checkpw
    calls = []

    def check(value, hashed):
        calls.append(hashed)
        return original(value, hashed)

    monkeypatch.setattr(bcrypt, 'checkpw', check)
    assert await verify_login_password_async(password, stored) is False
    assert len(calls) == 1 and calls[0].startswith(b'$2b$12$')


async def test_password_hashing_and_verification():
    password = '  example passphrase  '
    hashed = await hash_password_async(password)
    assert hashed.startswith('$2b$12$') and password not in hashed
    assert await verify_password_async(password, hashed)
    assert not verify_password(password.strip(), hashed)
    assert not verify_password('wrong passphrase', hashed)
    assert hashed != hash_password(password)
    assert verify_password('x' * 72, hash_password('x' * 72))
    for invalid in (None, '', 'malformed', bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds=4)).decode()):
        assert not verify_password(password, invalid)


@pytest.mark.parametrize('password', ['', 'short', 'x' * 73, '\u00e9' * 37, 'valid but nul\x00', '\ud800' * 12, None])
def test_password_policy_rejects_invalid_values(password):
    with pytest.raises(ValueError):
        hash_password(password)
    assert not verify_password(password, None)


def test_access_token_roundtrip_and_configuration():
    codec = AccessTokenCodec(SECRET)
    user, tenant = uuid4(), uuid4()
    token = codec.issue(user, tenant, roles=['Viewer'], permissions=['Alarm.Read'])
    identity = codec.decode(token)
    assert identity.user_id == user and identity.tenant_id == tenant
    second = codec.decode(codec.issue(user, tenant, roles=[], permissions=[]))
    assert identity.token_id != second.token_id
    claims = jwt.decode(token, SECRET.get_secret_value(), algorithms=['HS256'], audience='fsos-api')
    assert claims['exp'] - claims['iat'] == 900
    assert claims['permission'] == ['Alarm.Read']
    assert SECRET.get_secret_value() not in repr(codec)
    with pytest.raises(ValueError):
        AccessTokenCodec(SecretStr(''))
    with pytest.raises(InvalidAccessTokenError):
        AccessTokenCodec(SecretStr('a-different-test-only-key-with-32-bytes')).decode(token)


@pytest.mark.parametrize('change', [
    {'iss': 'other'}, {'aud': 'other'}, {'aud': ['fsos-api']}, {'token_type': 'refresh'},
    {'sub': 'not-uuid'}, {'tenant': None}, {'jti': 10}, {'permission': 'Admin'},
    {'role': [None]}, {'exp': 1}, {'iat': True}, {'nbf': 1}, {'exp': '9999999999'},
])
def test_signed_invalid_claims_are_rejected(change):
    codec = AccessTokenCodec(SECRET)
    token = codec.issue(uuid4(), uuid4(), roles=[], permissions=[])
    claims = jwt.decode(token, SECRET.get_secret_value(), algorithms=['HS256'], audience='fsos-api')
    claims.update(change)
    invalid = jwt.encode(claims, SECRET.get_secret_value(), algorithm='HS256')
    with pytest.raises(InvalidAccessTokenError):
        codec.decode(invalid)


def test_missing_claims_future_tokens_and_algorithms():
    codec = AccessTokenCodec(SECRET)
    token = codec.issue(uuid4(), uuid4(), roles=[], permissions=[])
    claims = jwt.decode(token, SECRET.get_secret_value(), algorithms=['HS256'], audience='fsos-api')
    for field in claims:
        changed = {k: v for k, v in claims.items() if k != field}
        with pytest.raises(InvalidAccessTokenError):
            codec.decode(jwt.encode(changed, SECRET.get_secret_value(), algorithm='HS256'))
    future = int(datetime.now(UTC).timestamp()) + 3600
    for times in ({'iat': future, 'nbf': future, 'exp': future + 900}, {'exp': claims['exp'] + 1}):
        with pytest.raises(InvalidAccessTokenError):
            codec.decode(jwt.encode({**claims, **times}, SECRET.get_secret_value(), algorithm='HS256'))
    for invalid in ('bad-token', '', 'x' * 16385, None,
                    jwt.encode(claims, '', algorithm='none'),
                    jwt.encode(claims, 'x' * 64, algorithm='HS512'),
                    jwt.encode(claims, SECRET.get_secret_value(), algorithm='HS256', headers={'typ': 'refresh'})):
        with pytest.raises(InvalidAccessTokenError):
            codec.decode(invalid)
