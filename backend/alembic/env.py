import asyncio

from sqlalchemy import text

from alembic import context
from app.core.config.settings import get_settings
from app.core.database.session import Base, get_admin_engine
from app.core.events import orm as event_orm  # noqa: F401
from app.modules.authentication.infrastructure import orm as auth_orm  # noqa: F401
from app.modules.complaint.infrastructure import orm as complaint_orm  # noqa: F401
from app.modules.consumption.infrastructure import orm as consumption_orm  # noqa: F401
from app.modules.fleet.infrastructure import orm as fleet_orm  # noqa: F401
from app.modules.master.infrastructure import orm  # noqa: F401
from app.modules.production.infrastructure import orm as production_orm  # noqa: F401
from app.modules.recall.infrastructure import orm as recall_orm  # noqa: F401
from app.modules.receiving.infrastructure import orm as receiving_orm  # noqa: F401
from app.modules.telemetry.infrastructure import orm as telemetry_orm  # noqa: F401
from app.modules.traceability.infrastructure import orm as traceability_orm  # noqa: F401

# Registrasi model tanpa membuat tabel saat startup.
target_metadata = Base.metadata
partition_tables: set[str] = set()


def include_object(obj, name, type_, reflected, compare_to):
    # Tabel referensi ini milik PostGIS, bukan model aplikasi.
    return not (type_ == "table" and (name == "spatial_ref_sys" or name in partition_tables))


def run_migrations_offline():
    url = get_settings().admin_database_url.get_secret_value()
    if not url:
        raise RuntimeError("Isi ADMIN_DATABASE_URL untuk migrasi.")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"}, compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    partition_tables.clear()
    partition_tables.update(connection.execute(text("""
        SELECT child.relname FROM pg_inherits i
        JOIN pg_class child ON child.oid=i.inhrelid
        JOIN pg_class parent ON parent.oid=i.inhparent
        JOIN pg_namespace ns ON ns.oid=parent.relnamespace
        WHERE ns.nspname='public' AND child.relispartition
          AND parent.relname IN ('temperature_log','humidity_log','gps_log','heartbeat_log')
    """)).scalars())
    # Tutup transaksi read-only introspeksi sebelum Alembic mengelola transaksi DDL.
    connection.commit()
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    engine = get_admin_engine()
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
