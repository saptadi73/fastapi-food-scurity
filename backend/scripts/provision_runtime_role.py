"""Provision a NOLOGIN privilege group; run using the migration/owner connection."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.database.runtime_role import provision_runtime_role
from app.core.database.session import close_database, get_admin_engine


async def main():
    try:
        async with get_admin_engine().begin() as connection:
            result = await provision_runtime_role(connection)
        print(json.dumps(result))
        return 0
    except Exception as exc:  # noqa: BLE001 - do not expose credentials
        print(json.dumps({'error_type': type(exc).__name__, 'action': 'Check admin connection, migration head and role conflicts.'}))
        return 1
    finally:
        await close_database()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
