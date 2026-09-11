"""Inspect one tenant/type registry page. Exit 0 clean, 2 findings, 1 failure."""
import argparse
import asyncio
import json
import sys
from pathlib import Path
from uuid import UUID

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.database.scope import ActorScope
from app.core.database.session import close_database, get_engine
from app.modules.traceability.application.registry_service import RegistryService
from app.modules.traceability.infrastructure.registry import SOURCES


async def run(args):
    try:
        factory = async_sessionmaker(get_engine())
        async with factory() as session, session.begin():
            result = await RegistryService(session, ActorScope(args.tenant, args.actor)).reconcile(
                args.asset_type, after_id=args.after, limit=args.batch_size,
            )
        print(json.dumps(result, default=str))
        return 2 if result['issue_count'] else 0
    except Exception as exc:  # noqa: BLE001 - never expose SQL or connection details
        print(json.dumps({'error_type': type(exc).__name__, 'action': 'Check scope, permission and parameters; no assets were changed.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', type=UUID, required=True)
    parser.add_argument('--actor', type=UUID, required=True)
    parser.add_argument('--asset-type', choices=sorted(SOURCES), required=True)
    parser.add_argument('--after', type=UUID)
    parser.add_argument('--batch-size', type=int, default=100, choices=range(1, 201), metavar='1..200')
    raise SystemExit(asyncio.run(run(parser.parse_args())))
