"""Read-only readiness for the services currently required by the API."""
import asyncio
from functools import lru_cache

from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import text

from app.core.config.settings import BACKEND_DIR, get_settings
from app.core.database.session import get_engine


@lru_cache
def expected_revisions() -> frozenset[str]:
    config = Config()
    config.set_main_option("script_location", str(BACKEND_DIR / "alembic"))
    return frozenset(ScriptDirectory.from_config(config).get_heads())


async def check_readiness() -> dict[str, str]:
    """No URL, exception text or database identifiers are exposed to callers."""
    checks = {"postgresql": "unavailable", "extensions": "unchecked", "schema": "unchecked"}
    try:
        async with asyncio.timeout(get_settings().readiness_timeout_seconds):
            async with get_engine().connect() as connection:
                version = int(await connection.scalar(text("SHOW server_version_num")))
                checks["postgresql"] = "ok" if version // 10000 == 18 else "unsupported"
                extensions = set((await connection.execute(text(
                    "SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'pgcrypto')"
                ))).scalars())
                checks["extensions"] = "ok" if extensions == {"postgis", "pgcrypto"} else "missing"
                migrated = await connection.scalar(text(
                    "SELECT to_regclass('public.alembic_version') IS NOT NULL"
                ))
                revisions = set((await connection.execute(text(
                    "SELECT version_num FROM public.alembic_version"
                ))).scalars()) if migrated else set()
                heads = expected_revisions()
                checks["schema"] = "ok" if heads and revisions == heads else "mismatch"
    except TimeoutError:
        checks["postgresql"] = "timeout"
    except Exception:  # noqa: BLE001 - health probes must not leak credentials or SQL
        checks["postgresql"] = "unavailable"
    return checks
