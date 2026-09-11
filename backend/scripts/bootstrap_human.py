"""Create a development human account via ADMIN_DATABASE_URL; password is prompted, never an argument."""
import argparse
import asyncio
import getpass
import json
import sys
import warnings
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config.settings import get_settings
from app.core.database.human_bootstrap import (
    HumanAccountInput,
    check_human_account,
    create_human_account,
)
from app.core.database.session import close_database, get_admin_engine


def prompt_password():
    if not sys.stdin.isatty():
        raise ValueError('Interactive terminal required for hidden password entry')
    with warnings.catch_warnings():
        warnings.simplefilter('error', getpass.GetPassWarning)
        password = getpass.getpass('Password (12 characters minimum, 72 UTF-8 bytes maximum): ')
        confirmation = getpass.getpass('Repeat password: ')
    if password != confirmation:
        raise ValueError('Passwords do not match')
    return password


async def run(args):
    try:
        environment = get_settings().environment
        if environment != 'development':
            raise ValueError('Development only')
        profile = {}
        for field, label in (('username', 'Username'), ('fullname', 'Full name'), ('email', 'Email')):
            value = getattr(args, field)
            if value is None:
                if not sys.stdin.isatty():
                    raise ValueError('Profile arguments or interactive terminal required')
                value = input(f'{label}: ')
            profile[field] = value
        payload = HumanAccountInput(tenant_id=args.tenant, actor_id=args.actor,
            **profile, role_ids=args.role)
        factory = async_sessionmaker(get_admin_engine())
        async with factory() as session, session.begin():
            preview = await check_human_account(session, payload, environment=environment)
        if args.check:
            print(json.dumps(preview, default=str))
            return 0
        # No DB locks remain while the operator types; create rechecks after prompting.
        password = prompt_password()
        async with factory() as session, session.begin():
            result = await create_human_account(session, payload, password, environment=environment)
        print(json.dumps(result, default=str))
        return 0
    except ValidationError as exc:
        print(json.dumps({'error_type': 'ValidationError', 'fields': ['.'.join(map(str, e['loc'])) for e in exc.errors()]}))
        return 1
    except (Exception, KeyboardInterrupt) as exc:  # noqa: BLE001 - never print SQL, password or hash
        print(json.dumps({'error_type': type(exc).__name__, 'action': 'Check environment, input, active tenant/actor/roles, duplicate identity, and hidden password entry. No existing account is overwritten.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', type=UUID, required=True)
    parser.add_argument('--actor', type=UUID, required=True)
    parser.add_argument('--role', type=UUID, action='append', required=True, help='Existing tenant role UUID; repeat for multiple roles')
    parser.add_argument('--username', help='Prompted interactively if omitted')
    parser.add_argument('--fullname', help='Prompted interactively if omitted')
    parser.add_argument('--email', help='Prompted interactively if omitted')
    parser.add_argument('--check', action='store_true', help='Read-only validation, no password prompt or account creation')
    raise SystemExit(asyncio.run(run(parser.parse_args())))
