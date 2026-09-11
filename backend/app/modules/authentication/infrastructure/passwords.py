"""Password primitives; call async wrappers from async request/service code."""
import asyncio
import re

import bcrypt

MIN_CHARACTERS = 12
MAX_BYTES = 72
_HASH = re.compile(r'\$2b\$12\$[./A-Za-z0-9]{53}\Z')
# Public dummy hash, never assigned to an account. Missing/invalid accounts still do bcrypt work.
_DUMMY_HASH = '$2b$12$jnCvetPomXZ4tpHoLKOU5.0JBuJoQnd95m1JGXwvlp2L9/XMhK2Zi'


def _encode(password: str) -> bytes:
    if not isinstance(password, str) or not MIN_CHARACTERS <= len(password) <= MAX_BYTES:
        raise ValueError('Password must contain at least 12 characters and at most 72 UTF-8 bytes')
    try:
        value = password.encode('utf-8')
    except UnicodeEncodeError:
        raise ValueError('Password must be valid UTF-8') from None
    if len(value) > MAX_BYTES or '\x00' in password:
        raise ValueError('Password exceeds 72 UTF-8 bytes or contains NUL')
    return value


def hash_password(password: str) -> str:
    return bcrypt.hashpw(_encode(password), bcrypt.gensalt(rounds=12)).decode('ascii')


def verify_password(password: str, stored_hash: str | None) -> bool:
    try:
        value = _encode(password)
        if not isinstance(stored_hash, str) or not _HASH.fullmatch(stored_hash):
            return False
        return bcrypt.checkpw(value, stored_hash.encode('ascii'))
    except ValueError:
        return False


async def hash_password_async(password: str) -> str:
    return await asyncio.to_thread(hash_password, password)


async def verify_password_async(password: str, stored_hash: str | None) -> bool:
    return await asyncio.to_thread(verify_password, password, stored_hash)


def _verify_login_password(password: str, stored_hash: str | None) -> bool:
    valid_input = True
    try:
        value = _encode(password)
    except ValueError:
        value, valid_input = b'invalid-login-candidate', False
    valid_hash = isinstance(stored_hash, str) and _HASH.fullmatch(stored_hash) is not None
    candidate = stored_hash if valid_hash else _DUMMY_HASH
    try:
        matched = bcrypt.checkpw(value, candidate.encode('ascii'))
    except ValueError:
        bcrypt.checkpw(value, _DUMMY_HASH.encode('ascii'))
        return False
    return valid_input and valid_hash and matched


async def verify_login_password_async(password: str, stored_hash: str | None) -> bool:
    return await asyncio.to_thread(_verify_login_password, password, stored_hash)
