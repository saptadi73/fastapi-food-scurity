"""Pemeriksaan read-only koneksi, versi PostgreSQL, extension, dan revisi schema."""
import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import text

from app.core.database.session import close_database, get_engine


async def main() -> int:
    try:
        async with asyncio.timeout(10):
            async with get_engine().connect() as connection:
                version = int(await connection.scalar(text("SHOW server_version_num")))
                extensions = set((await connection.execute(text(
                    "SELECT extname FROM pg_extension WHERE extname IN ('postgis', 'pgcrypto')"
                ))).scalars())
                migrated = await connection.scalar(text(
                    "SELECT to_regclass('public.alembic_version') IS NOT NULL"
                ))
                revisions = list((await connection.execute(text(
                    "SELECT version_num FROM alembic_version"
                ))).scalars()) if migrated else []
                ready = version // 10000 == 18 and extensions == {'postgis', 'pgcrypto'}
                print(json.dumps({
                    "connected": True, "postgresql_major": version // 10000,
                    "extensions": sorted(extensions), "migration_revisions": revisions,
                    "database_prerequisites_ready": ready,
                }, indent=2))
                return 0 if ready else 1
    except Exception as exc:  # noqa: BLE001 - CLI harus menyembunyikan detail kredensial
        # Jangan print URL/exception text karena dapat memuat kredensial.
        print(json.dumps({"connected": False, "error_type": type(exc).__name__,
                          "action": "Periksa DATABASE_URL, layanan, dan hak akses."}))
        return 1
    finally:
        await close_database()


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
