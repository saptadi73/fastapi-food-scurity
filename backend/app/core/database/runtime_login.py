"""Administrative runtime login bootstrap; callers keep passwords out of output."""
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

LOGIN = 'fsos_app'
MARKER = 'FSOS managed runtime login v1'


async def provision_runtime_login(connection, password: str, *, allow_existing: bool = False) -> bool:
    await connection.execute(text('SELECT pg_advisory_xact_lock(20260911, 18)'))
    role = (await connection.execute(text("""
        SELECT oid, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole, rolreplication, rolbypassrls,
               shobj_description(oid,'pg_authid') AS marker FROM pg_roles WHERE rolname='fsos_app'
    """))).mappings().one_or_none()
    if role:
        if not allow_existing or role['marker'] != MARKER or not role['rolcanlogin'] or any(role[k] for k in
                ('rolsuper','rolcreatedb','rolcreaterole','rolreplication','rolbypassrls')):
            raise ValueError('Existing runtime login is not compatible with this bootstrap')
        memberships = (await connection.execute(text("""
            SELECT r.rolname, m.admin_option FROM pg_auth_members m
            JOIN pg_roles r ON r.oid=m.roleid WHERE m.member=:oid
        """), {'oid': role['oid']})).all()
        if any(name != 'fsos_runtime' or admin for name, admin in memberships):
            raise ValueError('Runtime login has unexpected memberships')
        if await connection.scalar(text("""
            SELECT EXISTS (SELECT 1 FROM pg_shdepend WHERE refclassid='pg_authid'::regclass
                           AND refobjid=:oid AND deptype='o')
        """), {'oid': role['oid']}):
            raise ValueError('Runtime login must not own database objects')
    else:
        if not password or len(password) < 32:
            raise ValueError('Strong generated password required')
        # PostgreSQL role DDL requires a string literal. Escape it; never print SQL/errors.
        literal = password.replace("'", "''")
        await connection.execute(text("SET LOCAL password_encryption='scram-sha-256'"))
        await connection.exec_driver_sql(
            "CREATE ROLE fsos_app LOGIN INHERIT NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS "
            f"PASSWORD '{literal}'"
        )
        await connection.execute(text("COMMENT ON ROLE fsos_app IS 'FSOS managed runtime login v1'"))
    await connection.execute(text('GRANT fsos_runtime TO fsos_app'))
    return role is None


async def verify_runtime_login(url: str) -> dict:
    engine = create_async_engine(url, hide_parameters=True)
    try:
        async with engine.connect() as connection:
            result = (await connection.execute(text("""
                SELECT current_user AS login, r.rolsuper, r.rolcreatedb, r.rolcreaterole, r.rolbypassrls,
                    has_schema_privilege(current_user,'public','CREATE') AS can_create,
                    has_database_privilege(current_user,current_database(),'TEMP') AS can_temp,
                    has_table_privilege(current_user,'public.kitchen','SELECT') AS can_read,
                    has_table_privilege(current_user,'public.alarm_rule_revision','INSERT') AS can_forge_history,
                    has_function_privilege(current_user,'public.fsos_create_telemetry_partitions(date,integer)','EXECUTE') AS can_maintain
                FROM pg_roles r WHERE r.rolname=current_user
            """))).mappings().one()
            if result['login'] != LOGIN or not result['can_read'] or any(result[k] for k in
                    ('rolsuper','rolcreatedb','rolcreaterole','rolbypassrls','can_create','can_temp','can_forge_history','can_maintain')):
                raise ValueError('Runtime privilege verification failed')
            await connection.execute(text('SELECT version_num FROM public.alembic_version'))
            return {'login': LOGIN, 'restricted': True}
    finally:
        await engine.dispose()
