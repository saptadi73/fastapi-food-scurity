"""Strict access-token codec. Signature validation alone does not authorize database access."""
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import jwt
from pydantic import SecretStr

ISSUER = 'fsos'
AUDIENCE = 'fsos-api'
LIFETIME_SECONDS = 15 * 60
MAX_TOKEN_LENGTH = 16384


class InvalidAccessTokenError(Exception):
    pass


@dataclass(frozen=True)
class AccessIdentity:
    user_id: UUID
    tenant_id: UUID
    token_id: UUID
    expires_at: int
    session_id: UUID | None = None


class AccessTokenCodec:
    def __init__(self, secret: SecretStr):
        key = secret.get_secret_value()
        if len(key.encode('utf-8')) < 32:
            raise ValueError('JWT signing secret must contain at least 32 bytes')
        self._secret = secret

    def issue(self, user_id: UUID, tenant_id: UUID, *, roles: list[str], permissions: list[str], session_id: UUID | None = None) -> str:
        if not isinstance(user_id, UUID) or not isinstance(tenant_id, UUID):
            raise TypeError('UUID user and tenant required')
        for values in (roles, permissions):
            if not isinstance(values, list) or len(values) > 100 or any(
                not isinstance(v, str) or not v.strip() or len(v) > 100 for v in values
            ):
                raise ValueError('Bounded role/permission string lists required')
        if session_id is not None and not isinstance(session_id, UUID):
            raise TypeError('UUID session required')
        now = int(datetime.now(UTC).timestamp())
        token = jwt.encode({
            'sub': str(user_id), 'tenant': str(tenant_id), 'jti': str(uuid4()),
            'iss': ISSUER, 'aud': AUDIENCE, 'iat': now, 'nbf': now,
            'exp': now + LIFETIME_SECONDS, 'token_type': 'access',
            'role': sorted(set(roles)), 'permission': sorted(set(permissions)),
            **({'sid': str(session_id)} if session_id is not None else {}),
        }, self._secret.get_secret_value(), algorithm='HS256', headers={'typ': 'JWT'})
        if len(token) > MAX_TOKEN_LENGTH:
            raise ValueError('Token claims exceed size limit')
        return token

    def decode(self, token: str) -> AccessIdentity:
        try:
            if not isinstance(token, str) or not token or len(token) > MAX_TOKEN_LENGTH:
                raise ValueError('Invalid token size')
            header = jwt.get_unverified_header(token)
            if header.get('typ') != 'JWT' or header.get('crit') or header.get('alg') != 'HS256':
                raise ValueError('Unsupported token header')
            claims = jwt.decode(
                token, self._secret.get_secret_value(), algorithms=['HS256'],
                issuer=ISSUER, audience=AUDIENCE,
                options={'require': ['sub', 'tenant', 'jti', 'iss', 'aud', 'iat', 'nbf', 'exp', 'token_type', 'role', 'permission'],
                         'strict_aud': True},
            )
            if claims['token_type'] != 'access':
                raise ValueError('Wrong token purpose')
            if any(type(claims[k]) is not int for k in ('iat', 'nbf', 'exp')):
                raise ValueError('Integer timestamps required')
            if claims['nbf'] != claims['iat'] or claims['exp'] - claims['iat'] != LIFETIME_SECONDS:
                raise ValueError('Invalid token lifetime')
            for name in ('role', 'permission'):
                values = claims[name]
                if not isinstance(values, list) or len(values) > 100 or any(
                    not isinstance(v, str) or not v.strip() or len(v) > 100 for v in values
                ):
                    raise ValueError('Invalid authorization snapshot')
            identifiers = []
            for name in ('sub', 'tenant', 'jti'):
                value = claims[name]
                if not isinstance(value, str) or str(UUID(value)) != value:
                    raise ValueError('Canonical UUID required')
                identifiers.append(UUID(value))
            sid = claims.get('sid')
            if 'sid' in claims and (not isinstance(sid, str) or str(UUID(sid)) != sid):
                raise ValueError('Canonical session UUID required')
            return AccessIdentity(*identifiers, expires_at=claims['exp'], session_id=UUID(sid) if sid else None)
        except (jwt.PyJWTError, ValueError, TypeError, KeyError, AttributeError):
            raise InvalidAccessTokenError('Invalid or expired access token') from None
