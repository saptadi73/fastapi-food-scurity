"""Create the FSOS_DEV fixture and backfill its registry in one transaction."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config.settings import get_settings
from app.core.database.development_seed import seed_development
from app.core.database.session import close_database, get_engine


async def main():
    try:
        # Check before connecting, too: production must not acquire a seed connection.
        if get_settings().environment != 'development':
            raise ValueError('Development only')
        async with async_sessionmaker(get_engine())() as session, session.begin():
            result = await seed_development(session, environment=get_settings().environment)
        print(json.dumps(result, indent=2))
        return 0
    except Exception as exc:  # noqa: BLE001 - keep database details out of CLI output
        print(json.dumps({'error_type': type(exc).__name__, 'action': 'Check environment, migration head and reserved fixture conflicts.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
