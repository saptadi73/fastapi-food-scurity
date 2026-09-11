"""Administrative grants for current services; no login/password provisioning."""
from sqlalchemy import text

from app.core.database.session import Base
from app.core.events import orm as event_orm  # noqa: F401
from app.modules.authentication.infrastructure import orm as auth_orm  # noqa: F401
from app.modules.telemetry.infrastructure import orm as telemetry_orm  # noqa: F401
from app.modules.traceability.infrastructure.registry import SOURCES

ROLE = 'fsos_runtime'
MARKER = 'FSOS managed runtime role v1'
INSERT_TABLES = ('kitchen', 'digital_asset', 'alarm_rule', 'holding_rule', 'alarm_acknowledgment', 'device_session_end')
UPDATES = {
    'kitchen': 'kitchen_code,kitchen_name,latitude,longitude,address,capacity,status,updated_at,updated_by,deleted_at,deleted_by,version',
    'digital_asset': 'name,status,updated_at,updated_by,deleted_at,deleted_by,version',
    'alarm_rule': 'rule_code,rule_name,rule_category,priority,condition,action,enabled,updated_at,updated_by,version',
    'holding_rule': 'food_category,maximum_minutes,warning_minutes,discard_minutes,updated_at,updated_by,version',
}


async def provision_runtime_role(connection):
    await connection.execute(text('SELECT pg_advisory_xact_lock(20260911, 17)'))
    if not await connection.scalar(text("SELECT EXISTS (SELECT 1 FROM alembic_version WHERE version_num='20260911_0016')")):
        raise ValueError('Runtime grant profile requires migration 0016; review it when schema changes')
    existing = (await connection.execute(text("""
        SELECT oid, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls,
               shobj_description(oid, 'pg_authid') AS marker FROM pg_roles WHERE rolname='fsos_runtime'
    """))).mappings().one_or_none()
    if existing:
        if existing['marker'] != MARKER or any(existing[k] for k in
                ('rolcanlogin','rolsuper','rolcreatedb','rolcreaterole','rolreplication','rolbypassrls')):
            raise ValueError('Existing runtime role is not the expected managed restricted role')
        if await connection.scalar(text('SELECT EXISTS (SELECT 1 FROM pg_auth_members WHERE member=:oid)'), {'oid': existing['oid']}):
            raise ValueError('Runtime role must not inherit another role')
    else:
        await connection.execute(text('CREATE ROLE fsos_runtime NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS'))
        await connection.execute(text("COMMENT ON ROLE fsos_runtime IS 'FSOS managed runtime role v1'"))
    database = await connection.scalar(text('SELECT current_database()'))
    quoted_database = connection.dialect.identifier_preparer.quote(database)
    await connection.execute(text(f'REVOKE CREATE, TEMPORARY ON DATABASE {quoted_database} FROM PUBLIC, fsos_runtime'))
    await connection.execute(text('REVOKE CREATE ON SCHEMA public FROM PUBLIC, fsos_runtime'))
    await connection.execute(text('GRANT USAGE ON SCHEMA public TO fsos_runtime'))
    await connection.execute(text(f'GRANT CONNECT ON DATABASE {quoted_database} TO fsos_runtime'))
    # Explicit profile, without default privileges that silently authorize future tables.
    for name in sorted(Base.metadata.tables):
        quoted = connection.dialect.identifier_preparer.quote(name)
        await connection.execute(text(f'REVOKE ALL ON TABLE public.{quoted} FROM fsos_runtime'))
        # Table revocation does not revoke previous column grants.
        columns = ','.join(connection.dialect.identifier_preparer.quote(c.name) for c in Base.metadata.tables[name].columns)
        for privilege in ('SELECT', 'INSERT', 'UPDATE', 'REFERENCES'):
            await connection.execute(text(f'REVOKE {privilege} ({columns}) ON public.{quoted} FROM fsos_runtime'))
        await connection.execute(text(f'GRANT SELECT ON TABLE public.{quoted} TO fsos_runtime'))
    await connection.execute(text('GRANT SELECT ON public.alembic_version TO fsos_runtime'))
    for table in INSERT_TABLES:
        await connection.execute(text(f'GRANT INSERT ON public.{table} TO fsos_runtime'))
    for table, columns in UPDATES.items():
        await connection.execute(text(f'GRANT UPDATE ({columns}) ON public.{table} TO fsos_runtime'))
    lock_tables = {a.model.__tablename__ for a in SOURCES.values()} | {
        'tenant','app_user','role','permission','user_role','role_permission','alarm_log','device_session',
    }
    for table in sorted(lock_tables):
        await connection.execute(text(f'GRANT UPDATE (version) ON public.{table} TO fsos_runtime'))
    await connection.execute(text('REVOKE ALL ON FUNCTION public.fsos_create_telemetry_partitions(date, integer) FROM PUBLIC, fsos_runtime'))
    await connection.execute(text('GRANT EXECUTE ON FUNCTION public.fsos_capture_rule_revision() TO fsos_runtime'))
    return {'role': ROLE, 'login': False, 'database': database, 'profile_revision': '20260911_0016'}
