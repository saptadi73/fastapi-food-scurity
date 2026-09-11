"""Development-only local .env switch after successful login verification. No passwords printed."""
import asyncio
import json
import os
import secrets
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dotenv import dotenv_values, set_key
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import create_async_engine

from app.core.config.settings import BACKEND_DIR
from app.core.database.runtime_login import LOGIN, provision_runtime_login, verify_runtime_login
from app.core.database.runtime_role import provision_runtime_role


async def main():
    engine = None
    try:
        if any(key in os.environ for key in ('DATABASE_URL', 'ADMIN_DATABASE_URL', 'ENVIRONMENT')):
            raise ValueError('Use local .env without environment overrides for this bootstrap')
        env_file = BACKEND_DIR / '.env'
        pending = BACKEND_DIR / '.env.runtime.pending'
        config = dotenv_values(env_file)
        if config.get('ENVIRONMENT', 'development') != 'development':
            raise ValueError('Automatic local configuration is development only')
        admin_url = config.get('ADMIN_DATABASE_URL') or config.get('DATABASE_URL')
        if not admin_url or make_url(admin_url).username == LOGIN:
            raise ValueError('Separate owner connection required')
        runtime_url = config.get('DATABASE_URL')
        allow_existing = bool(runtime_url and make_url(runtime_url).username == LOGIN)
        if pending.exists() and not allow_existing:
            staged = dotenv_values(pending)
            if staged.get('ADMIN_DATABASE_URL') != admin_url:
                raise ValueError('Pending configuration belongs to another admin connection')
            runtime_url = staged.get('DATABASE_URL')
            allow_existing = True
        if not allow_existing:
            runtime_url = make_url(admin_url).set(username=LOGIN, password=secrets.token_urlsafe(48)).render_as_string(hide_password=False)
        runtime = make_url(runtime_url)
        admin = make_url(admin_url)
        if runtime.username != LOGIN or (runtime.drivername, runtime.host, runtime.port, runtime.database, runtime.query) != (
                admin.drivername, admin.host, admin.port, admin.database, admin.query):
            raise ValueError('Runtime and admin destinations must match')
        engine = create_async_engine(admin_url, hide_parameters=True)
        async with engine.begin() as connection:
            await provision_runtime_role(connection)
            created = await provision_runtime_login(connection, runtime.password or '', allow_existing=allow_existing)
            # Preserve the candidate secret before committing the login. Pending is Git-ignored.
            pending.write_text(env_file.read_text(encoding='utf-8'), encoding='utf-8')
            set_key(pending, 'ADMIN_DATABASE_URL', admin_url)
            set_key(pending, 'DATABASE_URL', runtime_url)
        result = await verify_runtime_login(runtime_url)
        os.replace(pending, env_file)
        print(json.dumps({**result, 'created': created, 'local_configuration_updated': True}))
        return 0
    except Exception as exc:  # noqa: BLE001 - never echo credentials/SQL
        print(json.dumps({'error_type': type(exc).__name__, 'action': 'Check owner connection and role conflicts; pending file supports retry without rotating password.'}))
        return 1
    finally:
        if engine is not None:
            await engine.dispose()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
