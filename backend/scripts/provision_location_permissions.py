"""Explicit location grants for an existing development role, using ADMIN_DATABASE_URL."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config.settings import get_settings
from app.core.database.location_permissions import (
    LOCATION_PERMISSIONS,
    provision_location_permissions,
)
from app.core.database.session import close_database, get_admin_engine


async def run(args):
    try:
        environment = get_settings().environment
        if environment != 'development':
            raise ValueError('Development only')
        factory = async_sessionmaker(get_admin_engine())
        async with factory() as session, session.begin():
            result = await provision_location_permissions(session, tenant_id=args.tenant, actor_id=args.actor,
                role_id=args.role, permissions=args.permission, environment=environment, apply=args.apply)
        print(json.dumps(result, default=str))
        return 0
    except Exception as exc:  # noqa: BLE001 - do not print SQL or credentials
        print(json.dumps({'error_type': type(exc).__name__, 'action': 'Check development environment, admin connection, active actor/tenant/role and revoked grants. No revoked row is restored.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', type=UUID, required=True)
    parser.add_argument('--actor', type=UUID, required=True)
    parser.add_argument('--role', type=UUID, required=True)
    parser.add_argument('--permission', choices=LOCATION_PERMISSIONS, action='append', required=True)
    parser.add_argument('--apply', action='store_true', help='Create missing permissions and grants; default only checks')
    raise SystemExit(asyncio.run(run(parser.parse_args())))
