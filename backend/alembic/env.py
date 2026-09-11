import asyncio

from alembic import context
from app.core.config.settings import get_settings
from app.core.database.session import Base, get_engine
from app.modules.authentication.infrastructure import orm as auth_orm  # noqa: F401
from app.modules.master.infrastructure import orm  # noqa: F401
from app.modules.production.infrastructure import orm as production_orm  # noqa: F401
from app.modules.receiving.infrastructure import orm as receiving_orm  # noqa: F401

# Registrasi model tanpa membuat tabel saat startup.
target_metadata = Base.metadata


def include_object(obj, name, type_, reflected, compare_to):
    # Tabel referensi ini milik PostGIS, bukan model aplikasi.
    return not (type_ == "table" and name == "spatial_ref_sys")


def run_migrations_offline():
    url = get_settings().database_url.get_secret_value()
    if not url:
        raise RuntimeError("Isi DATABASE_URL di backend/.env terlebih dahulu.")
    context.configure(
        url=url, target_metadata=target_metadata, literal_binds=True,
        dialect_opts={"paramstyle": "named"}, compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection):
    context.configure(
        connection=connection, target_metadata=target_metadata, compare_type=True,
        include_object=include_object,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_migrations_online():
    engine = get_engine()
    try:
        async with engine.connect() as connection:
            await connection.run_sync(do_run_migrations)
    finally:
        await engine.dispose()


if context.is_offline_mode():
    run_migrations_offline()
else:
    asyncio.run(run_migrations_online())
