"""Tenant-scoped administrative backfill; requires an existing authorized actor."""
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
        scope = ActorScope(args.tenant, args.actor)
        cursor = None
        processed = 0
        while True:
            async with factory() as session, session.begin():
                batch = await RegistryService(session, scope).backfill(args.asset_type, after_id=cursor, limit=args.batch_size)
            processed += batch['processed']
            if batch['processed'] == 0:
                break
            cursor = batch['last_id']
        print(json.dumps({'processed': processed, 'asset_type': args.asset_type}))
        return 0
    except Exception as exc:  # noqa: BLE001 - do not expose connection details
        print(json.dumps({'error_type': type(exc).__name__, 'action': 'Check scope, permission and source data; rerun is safe.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--tenant', type=UUID, required=True)
    parser.add_argument('--actor', type=UUID, required=True)
    parser.add_argument('--asset-type', choices=sorted(SOURCES), required=True)
    parser.add_argument('--batch-size', type=int, default=100, choices=range(1, 201), metavar='1..200')
    raise SystemExit(asyncio.run(run(parser.parse_args())))
