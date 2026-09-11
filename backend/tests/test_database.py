"""Integration test pada database kosong bernama fsos_test*, tidak pada database aplikasi."""
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from uuid import uuid4

import pytest
from registry_checks import verify_registry
from sqlalchemy import text
from sqlalchemy.engine import make_url
from sqlalchemy.exc import DBAPIError, IntegrityError
from sqlalchemy.ext.asyncio import create_async_engine

BACKEND = Path(__file__).resolve().parents[1]
TEST_URL = os.environ.get("FSOS_TEST_DATABASE_URL", "")


@pytest.mark.skipif(not TEST_URL, reason="FSOS_TEST_DATABASE_URL belum disediakan")
@pytest.mark.asyncio
async def test_migration_roundtrip_and_constraints():
    assert (make_url(TEST_URL).database or "").startswith("fsos_test")
    engine = create_async_engine(TEST_URL)
    env = {**os.environ, "DATABASE_URL": TEST_URL, "ADMIN_DATABASE_URL": TEST_URL}

    def migrate(target):
        result = subprocess.run(
            [sys.executable, "-m", "alembic", target[0], target[1]],
            cwd=BACKEND, env=env, capture_output=True, text=True, timeout=30, check=False,
        )
        assert result.returncode == 0, result.stderr

    try:
        async with engine.connect() as c:
            assert await c.scalar(text("SELECT to_regclass('public.tenant')")) is None
        migrate(("upgrade", "head"))
        async with engine.begin() as c:
            tenant_a, tenant_b, kitchen_id = uuid4(), uuid4(), uuid4()
            await c.execute(text(
                "INSERT INTO tenant (tenant_id, tenant_code, tenant_name) "
                "VALUES (:a, 'A', 'Tenant A'), (:b, 'B', 'Tenant B')"
            ), {"a": tenant_a, "b": tenant_b})
            params = {"id": kitchen_id, "tenant": tenant_a, "code": "K01"}
            statement = text(
                "INSERT INTO kitchen (kitchen_id, tenant_id, kitchen_code, kitchen_name, "
                "latitude, longitude, capacity) "
                "VALUES (:id, :tenant, :code, 'Kitchen', -6.2, 106.8, 100)"
            )
            await c.execute(statement, params)
            point = (await c.execute(text(
                "SELECT ST_X(location), ST_Y(location), version, created_at IS NOT NULL "
                "FROM kitchen WHERE kitchen_id=:id"
            ), {"id": kitchen_id})).one()
            assert point == (106.8, -6.2, 1, True)
            for invalid in (
                {**params, "id": uuid4()},  # duplikat kode dalam tenant
                {**params, "id": uuid4(), "tenant": uuid4()},  # tenant tidak ada
            ):
                with pytest.raises(IntegrityError):
                    async with c.begin_nested():
                        await c.execute(statement, invalid)
            await c.execute(statement, {**params, "id": uuid4(), "tenant": tenant_b})
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(text("UPDATE kitchen SET latitude=100 WHERE kitchen_id=:id"),
                                    {"id": kitchen_id})
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(text("DELETE FROM tenant WHERE tenant_id=:id"), {"id": tenant_a})
            storage_id, zone_id, device_uuid = uuid4(), uuid4(), uuid4()
            await c.execute(text(
                "INSERT INTO storage (storage_id, tenant_id, kitchen_id, storage_code, "
                "storage_name, storage_type, temperature_min, temperature_max) "
                "VALUES (:id, :tenant, :kitchen, 'S01', 'Cold room', 'COLD_STORAGE', 0, 5)"
            ), {"id": storage_id, "tenant": tenant_a, "kitchen": kitchen_id})
            await c.execute(text(
                "INSERT INTO storage_zone (zone_id, tenant_id, storage_id, zone_code, zone_name) "
                "VALUES (:id, :tenant, :storage, 'Z01', 'Rack A')"
            ), {"id": zone_id, "tenant": tenant_a, "storage": storage_id})
            device_sql = text(
                "INSERT INTO device (device_id, device_uuid, tenant_id, zone_id, device_name, device_type) "
                "VALUES (:id, :uuid, :tenant, :zone, 'Sensor', 'TEMPERATURE')"
            )
            await c.execute(device_sql, {"id": uuid4(), "uuid": device_uuid,
                                         "tenant": tenant_a, "zone": zone_id})
            # Perangkat dapat diregistrasikan sebelum penempatan zone.
            await c.execute(device_sql, {"id": uuid4(), "uuid": uuid4(),
                                         "tenant": tenant_b, "zone": None})
            for query, values in (
                ("UPDATE storage SET tenant_id=:tenant WHERE storage_id=:id",
                 {"tenant": tenant_b, "id": storage_id}),
                ("UPDATE storage_zone SET tenant_id=:tenant WHERE zone_id=:id",
                 {"tenant": tenant_b, "id": zone_id}),
                ("UPDATE device SET tenant_id=:tenant WHERE device_uuid=:id",
                 {"tenant": tenant_b, "id": device_uuid}),
                ("UPDATE storage SET temperature_min=10 WHERE storage_id=:id", {"id": storage_id}),
                ("DELETE FROM storage_zone WHERE zone_id=:id", {"id": zone_id}),
                ("DELETE FROM storage WHERE storage_id=:id", {"id": storage_id}),
            ):
                with pytest.raises(IntegrityError):
                    async with c.begin_nested():
                        await c.execute(text(query), values)
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(device_sql, {"id": uuid4(), "uuid": device_uuid,
                                                 "tenant": tenant_b, "zone": None})
            await verify_fleet_school(c, tenant_a, tenant_b, kitchen_id)
            await verify_food_master(c, tenant_a, tenant_b)
            await verify_packaging_rules(c, tenant_a, tenant_b)
            await verify_identity(c, tenant_a, tenant_b)
            await verify_receiving(c, tenant_a, tenant_b, kitchen_id)
            await verify_production(c, tenant_a, tenant_b, kitchen_id)
            await verify_delivery(c, tenant_a, tenant_b, kitchen_id)
            await verify_consumption_recall(c, tenant_a, tenant_b)
            await verify_asset_graph(c, tenant_a, tenant_b)
            await verify_event_log(c, tenant_a)
            await verify_telemetry(c, tenant_a, tenant_b)
            await verify_remaining_telemetry(c, tenant_a, tenant_b)
            await verify_rule_history(c, tenant_a, tenant_b)
            await verify_registry(c, tenant_a, tenant_b)
        migrate(("downgrade", "20260911_0015"))
        async with engine.connect() as c:
            assert await c.scalar(text("SELECT prosecdef FROM pg_proc WHERE oid='public.fsos_capture_rule_revision()'::regprocedure")) is False
        migrate(("downgrade", "20260911_0014"))
        async with engine.connect() as c:
            assert await c.scalar(text("SELECT to_regclass('public.alarm_rule_revision')")) is None
            assert await c.scalar(text("SELECT to_regclass('public.holding_rule_revision')")) is None
            assert await c.scalar(text("SELECT count(*) FROM alarm_rule")) == 2
            assert await c.scalar(text("SELECT max(version) FROM alarm_rule")) == 2
        migrate(("downgrade", "20260911_0013"))
        async with engine.connect() as c:
            for table in ('device_health_log', 'alarm_log', 'holding_log', 'signal_log',
                          'battery_log', 'device_session', 'alarm_acknowledgment', 'device_session_end'):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {'name': table}) is None
            assert await c.scalar(text("SELECT count(*) FROM humidity_log")) == 3
            assert await c.scalar(text("SELECT to_regprocedure('public.fsos_validate_telemetry_completion()')")) is None
        migrate(("downgrade", "20260911_0012"))
        async with engine.connect() as c:
            for table in ('temperature_log', 'humidity_log', 'gps_log', 'heartbeat_log', 'mqtt_message_log'):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {'name': table}) is None
            assert await c.scalar(text("SELECT count(*) FROM event_log")) == 2
        migrate(("downgrade", "20260911_0011"))
        async with engine.connect() as c:
            assert await c.scalar(text("SELECT to_regclass('public.event_log')")) is None
            assert await c.scalar(text("SELECT count(*) FROM digital_asset")) == 3
            assert await c.scalar(text("SELECT count(*) FROM asset_relationship")) == 1
            assert await c.scalar(text("SELECT count(*) FROM asset_movement")) == 1
            assert await c.scalar(text("SELECT to_regprocedure('public.fsos_reject_event_mutation()')")) is None
        migrate(("downgrade", "20260911_0010"))
        async with engine.connect() as c:
            for table in ("digital_asset", "asset_relationship", "asset_movement"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM recall")) == 2
            assert await c.scalar(text("SELECT count(*) FROM complaint")) == 2
            assert await c.scalar(text("SELECT count(*) FROM consumption")) == 1
        migrate(("downgrade", "20260911_0009"))
        async with engine.connect() as c:
            for table in ("consumption", "complaint", "recall"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM delivery")) == 3
            assert await c.scalar(text("SELECT count(*) FROM delivery_item")) == 1
            assert await c.scalar(text("SELECT count(*) FROM school_receiving")) == 1
        migrate(("downgrade", "20260911_0008"))
        async with engine.connect() as c:
            for table in ("delivery", "delivery_item", "school_receiving"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM production_batch")) == 2
            assert await c.scalar(text("SELECT count(*) FROM production_item")) == 1
            assert await c.scalar(text("SELECT count(*) FROM package")) == 1
        migrate(("downgrade", "20260911_0007"))
        async with engine.connect() as c:
            for table in ("production_batch", "production_item", "package"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM receiving")) == 2
            assert await c.scalar(text("SELECT count(*) FROM raw_material_batch")) == 1
            assert await c.scalar(text("SELECT count(*) FROM receiving_item")) == 1
        migrate(("downgrade", "20260911_0006"))
        async with engine.connect() as c:
            for table in ("receiving", "raw_material_batch", "receiving_item"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM app_user")) == 2
            assert await c.scalar(text("SELECT count(*) FROM supplier")) == 3
        migrate(("downgrade", "20260911_0005"))
        async with engine.connect() as c:
            for table in ("app_user", "role", "permission", "user_role", "role_permission"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM alarm_rule")) == 2
            assert await c.scalar(text("SELECT count(*) FROM holding_rule")) == 2
            assert await c.scalar(text("SELECT count(*) FROM packaging_type")) == 2
        migrate(("downgrade", "20260911_0004"))
        async with engine.connect() as c:
            for table in ("packaging_type", "alarm_rule", "holding_rule"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM supplier")) == 3
            assert await c.scalar(text("SELECT count(*) FROM recipe")) == 1
            assert await c.scalar(text("SELECT count(*) FROM supplier_material")) == 2
        migrate(("downgrade", "20260911_0003"))
        async with engine.connect() as c:
            for table in ("supplier", "raw_material", "food_item", "recipe", "supplier_material"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM vehicle")) == 2
            assert await c.scalar(text("SELECT count(*) FROM school")) == 1
            assert await c.scalar(text("SELECT count(*) FROM driver")) == 2
        migrate(("downgrade", "20260911_0002"))
        async with engine.connect() as c:
            for table in ("driver", "vehicle", "school"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM device")) == 2
            assert await c.scalar(text("SELECT count(*) FROM storage")) == 1
            assert await c.scalar(text("SELECT count(*) FROM storage_zone")) == 1
        # Rollback tahap kedua mempertahankan data tenant/kitchen tahap pertama.
        migrate(("downgrade", "20260911_0001"))
        async with engine.connect() as c:
            for table in ("storage", "storage_zone", "device"):
                assert await c.scalar(text("SELECT to_regclass(:name)"), {"name": table}) is None
            assert await c.scalar(text("SELECT count(*) FROM tenant")) == 2
            assert await c.scalar(text("SELECT count(*) FROM kitchen")) == 2
        migrate(("downgrade", "base"))
        async with engine.connect() as c:
            assert await c.scalar(text("SELECT to_regclass('public.kitchen')")) is None
            assert await c.scalar(text("SELECT to_regclass('public.tenant')")) is None
            assert await c.scalar(text("SELECT count(*) FROM pg_extension WHERE extname='postgis'")) == 1
        migrate(("upgrade", "head"))
    finally:
        await engine.dispose()


async def verify_fleet_school(c, tenant_a, tenant_b, kitchen_id):
    driver_a, driver_b, vehicle, school = (uuid4() for _ in range(4))
    for driver, tenant in ((driver_a, tenant_a), (driver_b, tenant_b)):
        await c.execute(text(
            "INSERT INTO driver (driver_id, tenant_id, driver_code, driver_name) "
            "VALUES (:id, :tenant, 'D01', 'Driver')"
        ), {"id": driver, "tenant": tenant})
    gps_a = await c.scalar(text("SELECT device_id FROM device WHERE tenant_id=:t"), {"t": tenant_a})
    gps_b = await c.scalar(text("SELECT device_id FROM device WHERE tenant_id=:t"), {"t": tenant_b})
    vehicle_sql = text(
        "INSERT INTO vehicle (vehicle_id, tenant_id, vehicle_code, plate_number, vehicle_type, "
        "capacity, driver_id, gps_device) VALUES (:id, :tenant, :code, :plate, 'VAN', 100, :driver, :gps)"
    )
    params = {"id": vehicle, "tenant": tenant_a, "code": "V01", "plate": "B 1234 AB",
              "driver": driver_a, "gps": gps_a}
    await c.execute(vehicle_sql, params)
    await c.execute(vehicle_sql, {**params, "id": uuid4(), "tenant": tenant_b,
                                  "driver": None, "gps": None})
    for invalid in (
        {**params, "id": uuid4(), "code": "V02", "plate": "B 5678 AB", "driver": driver_b},
        {**params, "id": uuid4(), "code": "V02", "plate": "B 5678 AB", "gps": gps_b},
        {**params, "id": uuid4(), "plate": "B 5678 AB"},
        {**params, "id": uuid4(), "code": "V02"},
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(vehicle_sql, invalid)
    school_sql = text(
        "INSERT INTO school (school_id, tenant_id, kitchen_id, school_code, school_name, "
        "latitude, longitude, student_count) "
        "VALUES (:id, :tenant, :kitchen, :code, 'School', -6.2, 106.8, 100)"
    )
    school_params = {"id": school, "tenant": tenant_a, "kitchen": kitchen_id, "code": "SCH01"}
    await c.execute(school_sql, school_params)
    assert (await c.execute(text(
        "SELECT ST_X(location), ST_Y(location), version FROM school WHERE school_id=:id"
    ), {"id": school})).one() == (106.8, -6.2, 1)
    for invalid in ({**school_params, "id": uuid4()},
                    {**school_params, "id": uuid4(), "tenant": tenant_b}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(school_sql, invalid)
    for query, identifier in (
        ("UPDATE school SET student_count=-1 WHERE school_id=:id", school),
        ("UPDATE school SET latitude=91 WHERE school_id=:id", school),
        ("UPDATE school SET longitude=NULL WHERE school_id=:id", school),
        ("UPDATE vehicle SET capacity=-1 WHERE vehicle_id=:id", vehicle),
        ("DELETE FROM driver WHERE driver_id=:id", driver_a),
        ("DELETE FROM device WHERE device_id=:id", gps_a),
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text(query), {"id": identifier})


async def verify_food_master(c, tenant_a, tenant_b):
    ids = {}
    inserts = {
        "supplier": ("supplier_id", "supplier_code, supplier_name", "'SUP01', 'Supplier'"),
        "raw_material": ("raw_material_id", "material_code, material_name, uom", "'RM01', 'Rice', 'kg'"),
        "food_item": ("food_item_id", "food_code, food_name, uom", "'FOOD01', 'Rice menu', 'portion'"),
    }
    for table, (pk, fields, values) in inserts.items():
        # SQL identifiers and literals here come only from the fixed mapping above.
        statement = text(f"INSERT INTO {table} ({pk}, tenant_id, {fields}) VALUES (:id, :tenant, {values})")
        for tenant in (tenant_a, tenant_b):
            ids[table, tenant] = uuid4()
            await c.execute(statement, {"id": ids[table, tenant], "tenant": tenant})
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(statement, {"id": uuid4(), "tenant": tenant_a})
    recipe_id, link_id = uuid4(), uuid4()
    recipe_sql = text(
        "INSERT INTO recipe (recipe_id, tenant_id, food_item_id, raw_material_id, quantity, uom) "
        "VALUES (:id, :tenant, :food, :material, :quantity, :uom)"
    )
    recipe = {"id": recipe_id, "tenant": tenant_a, "food": ids['food_item', tenant_a],
              "material": ids['raw_material', tenant_a], "quantity": '0.125000', "uom": 'kg'}
    await c.execute(recipe_sql, recipe)
    assert str(await c.scalar(text("SELECT quantity FROM recipe WHERE recipe_id=:id"),
                              {"id": recipe_id})) == '0.125000'
    for invalid in (
        {**recipe, "id": uuid4()},
        {**recipe, "id": uuid4(), "food": ids['food_item', tenant_b]},
        {**recipe, "id": uuid4(), "material": ids['raw_material', tenant_b]},
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(recipe_sql, invalid)
    link_sql = text(
        "INSERT INTO supplier_material (supplier_material_id, tenant_id, supplier_id, raw_material_id) "
        "VALUES (:id, :tenant, :supplier, :material)"
    )
    link = {"id": link_id, "tenant": tenant_a, "supplier": ids['supplier', tenant_a],
            "material": ids['raw_material', tenant_a]}
    await c.execute(link_sql, link)
    for invalid in (
        {**link, "id": uuid4()},
        {**link, "id": uuid4(), "supplier": ids['supplier', tenant_b]},
        {**link, "id": uuid4(), "material": ids['raw_material', tenant_b]},
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(link_sql, invalid)
    supplier2 = uuid4()
    await c.execute(text("INSERT INTO supplier (supplier_id, tenant_id, supplier_code, supplier_name) "
                         "VALUES (:id, :t, 'SUP02', 'Second supplier')"), {"id": supplier2, "t": tenant_a})
    await c.execute(link_sql, {**link, "id": uuid4(), "supplier": supplier2})
    for query, identifier in (
        ("UPDATE recipe SET quantity=0 WHERE recipe_id=:id", recipe_id),
        ("UPDATE recipe SET quantity=-1 WHERE recipe_id=:id", recipe_id),
        ("UPDATE recipe SET uom=' ' WHERE recipe_id=:id", recipe_id),
        ("UPDATE raw_material SET maximum_storage_hours=-1 WHERE raw_material_id=:id", ids['raw_material', tenant_a]),
        (("UPDATE raw_material SET recommended_temperature_min=5, recommended_temperature_max=0 "
          "WHERE raw_material_id=:id"), ids['raw_material', tenant_a]),
        ("UPDATE food_item SET holding_limit_minutes=-1 WHERE food_item_id=:id", ids['food_item', tenant_a]),
        ("DELETE FROM supplier WHERE supplier_id=:id", ids['supplier', tenant_a]),
        ("DELETE FROM raw_material WHERE raw_material_id=:id", ids['raw_material', tenant_a]),
        ("DELETE FROM food_item WHERE food_item_id=:id", ids['food_item', tenant_a]),
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text(query), {"id": identifier})


async def verify_packaging_rules(c, tenant_a, tenant_b):
    statements = {
        "packaging_type": text(
            "INSERT INTO packaging_type (package_type_id, tenant_id, code, name, volume) "
            "VALUES (:id, :tenant, 'BOX01', 'Box', 750.125)"
        ),
        "alarm_rule": text(
            "INSERT INTO alarm_rule (alarm_rule_id, tenant_id, rule_code, rule_name, "
            "rule_category, priority, condition, action) "
            "VALUES (:id, :tenant, 'TEMP_HIGH', 'High temperature', 'temperature_high', "
            "'HIGH', '{\"field\":\"temperature\"}', '{\"type\":\"alarm\"}')"
        ),
        "holding_rule": text(
            "INSERT INTO holding_rule (holding_rule_id, tenant_id, food_category, "
            "maximum_minutes, warning_minutes, discard_minutes) "
            "VALUES (:id, :tenant, 'TEST_CATEGORY', 120, 30, 120)"
        ),
    }
    ids = {}
    for table, statement in statements.items():
        for tenant in (tenant_a, tenant_b):
            identifier = uuid4()
            ids[table, tenant] = identifier
            await c.execute(statement, {"id": identifier, "tenant": tenant})
        for invalid_tenant in (tenant_a, uuid4()):
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, {"id": uuid4(), "tenant": invalid_tenant})
    assert await c.scalar(text("SELECT enabled FROM alarm_rule WHERE alarm_rule_id=:id"),
                          {"id": ids['alarm_rule', tenant_a]}) is False
    invalid_updates = {
        "packaging_type": ("package_type_id", ["volume=0", "volume=-1", "volume='NaN'"]),
        "holding_rule": ("holding_rule_id", [
            "maximum_minutes=0", "warning_minutes=-1", "warning_minutes=121", "discard_minutes=119"
        ]),
        "alarm_rule": ("alarm_rule_id", [
            "priority='INVALID'", "condition='{}'", "condition='[]'", "condition='null'",
            "action='{}'", "action='[]'", "action='null'"
        ]),
    }
    for table, (pk, assignments) in invalid_updates.items():
        for assignment in assignments:
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    # Identifiers and assignments are fixed test literals, never user input.
                    await c.execute(text(f"UPDATE {table} SET {assignment} WHERE {pk}=:id"),
                                    {"id": ids[table, tenant_a]})


async def verify_identity(c, tenant_a, tenant_b):
    statements = {
        "app_user": text("INSERT INTO app_user (user_id, tenant_id, username, fullname, email) "
                         "VALUES (:id, :tenant, 'operator', 'Operator', 'operator@example.test')"),
        "role": text("INSERT INTO role (role_id, tenant_id, role_code, role_name) "
                     "VALUES (:id, :tenant, 'VIEWER', 'Viewer')"),
        "permission": text("INSERT INTO permission (permission_id, tenant_id, permission_code) "
                           "VALUES (:id, :tenant, 'Device.Read')"),
    }
    ids = {}
    for table, statement in statements.items():
        for tenant in (tenant_a, tenant_b):
            ids[table, tenant] = uuid4()
            await c.execute(statement, {"id": ids[table, tenant], "tenant": tenant})
        for invalid_tenant in (tenant_a, uuid4()):
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, {"id": uuid4(), "tenant": invalid_tenant})
    assert (await c.execute(text("SELECT status, password_hash FROM app_user WHERE user_id=:id"),
                            {"id": ids['app_user', tenant_a]})).one() == ('INACTIVE', None)
    for username, email in (
        (' OPERATOR ', 'different@example.test'), ('other', ' OPERATOR@EXAMPLE.TEST '),
        (' ', 'different@example.test'), ('other', ' '),
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text("INSERT INTO app_user (user_id, tenant_id, username, fullname, email) "
                                     "VALUES (:id, :tenant, :username, 'Test', :email)"),
                                {"id": uuid4(), "tenant": tenant_a, "username": username, "email": email})
    for table, pk, left_table, left_column, right_table, right_column in (
        ('user_role', 'user_role_id', 'app_user', 'user_id', 'role', 'role_id'),
        ('role_permission', 'role_permission_id', 'role', 'role_id', 'permission', 'permission_id'),
    ):
        statement = text(f"INSERT INTO {table} ({pk}, tenant_id, {left_column}, {right_column}) "
                         "VALUES (:id, :tenant, :left, :right)")
        params = {"id": uuid4(), "tenant": tenant_a,
                  "left": ids[left_table, tenant_a], "right": ids[right_table, tenant_a]}
        await c.execute(statement, params)
        for invalid in (
            {**params, "id": uuid4()},
            {**params, "id": uuid4(), "left": ids[left_table, tenant_b]},
            {**params, "id": uuid4(), "right": ids[right_table, tenant_b]},
        ):
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, invalid)
    for table, pk in (('app_user', 'user_id'), ('role', 'role_id'), ('permission', 'permission_id')):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text(f"DELETE FROM {table} WHERE {pk}=:id"),
                                {"id": ids[table, tenant_a]})


async def verify_receiving(c, tenant_a, tenant_b, kitchen_id):
    suppliers = list((await c.execute(text("SELECT supplier_id FROM supplier WHERE tenant_id=:t ORDER BY supplier_code"),
                                      {"t": tenant_a})).scalars())
    operator = await c.scalar(text("SELECT user_id FROM app_user WHERE tenant_id=:t"), {"t": tenant_a})
    other_operator = await c.scalar(text("SELECT user_id FROM app_user WHERE tenant_id=:t"), {"t": tenant_b})
    material = await c.scalar(text("SELECT raw_material_id FROM raw_material WHERE tenant_id=:t"), {"t": tenant_a})
    other_material = await c.scalar(text("SELECT raw_material_id FROM raw_material WHERE tenant_id=:t"), {"t": tenant_b})
    receiving_id, other_receiving, batch_id, item_id = (uuid4() for _ in range(4))
    header_sql = text("INSERT INTO receiving (receiving_id, tenant_id, supplier_id, kitchen_id, operator, received_at) "
                      "VALUES (:id, :tenant, :supplier, :kitchen, :operator, now())")
    header = {"id": receiving_id, "tenant": tenant_a, "supplier": suppliers[0], "kitchen": kitchen_id, "operator": operator}
    await c.execute(header_sql, header)
    await c.execute(header_sql, {**header, "id": other_receiving})
    for invalid in ({**header, "id": uuid4(), "operator": other_operator},
                    {**header, "id": uuid4(), "tenant": tenant_b}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(header_sql, invalid)
    batch_sql = text("INSERT INTO raw_material_batch (raw_material_batch_id, tenant_id, raw_material_id, "
                     "receiving_id, supplier_id, batch_code) VALUES (:id, :tenant, :material, :receiving, :supplier, :code)")
    batch = {"id": batch_id, "tenant": tenant_a, "material": material, "receiving": receiving_id,
             "supplier": suppliers[0], "code": "BATCH01"}
    await c.execute(batch_sql, batch)
    for invalid in ({**batch, "id": uuid4()},
                    {**batch, "id": uuid4(), "code": "B2", "supplier": suppliers[1]},
                    {**batch, "id": uuid4(), "code": "B2", "material": other_material}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(batch_sql, invalid)
    item_sql = text("INSERT INTO receiving_item (receiving_item_id, tenant_id, receiving_id, "
                    "raw_material_batch_id, quantity, uom) VALUES (:id, :tenant, :receiving, :batch, 1.125, 'kg')")
    item = {"id": item_id, "tenant": tenant_a, "receiving": receiving_id, "batch": batch_id}
    # Belum ada item valid, jadi kegagalan ini benar-benar akibat header tidak cocok.
    with pytest.raises(IntegrityError):
        async with c.begin_nested():
            await c.execute(item_sql, {**item, "receiving": other_receiving})
    await c.execute(item_sql, item)
    assert await c.scalar(text("SELECT accepted FROM receiving_item WHERE receiving_item_id=:id"), {"id": item_id}) is None
    with pytest.raises(IntegrityError):
        async with c.begin_nested():
            await c.execute(item_sql, {**item, "id": uuid4()})
    for query, identifier in (
        ("UPDATE receiving_item SET quantity=0 WHERE receiving_item_id=:id", item_id),
        ("UPDATE receiving_item SET quantity='NaN' WHERE receiving_item_id=:id", item_id),
        ("UPDATE receiving_item SET uom=' ' WHERE receiving_item_id=:id", item_id),
        ("DELETE FROM receiving WHERE receiving_id=:id", receiving_id),
        ("DELETE FROM raw_material_batch WHERE raw_material_batch_id=:id", batch_id),
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text(query), {"id": identifier})


async def verify_production(c, tenant_a, tenant_b, kitchen_id):
    menu_a = await c.scalar(text("SELECT food_item_id FROM food_item WHERE tenant_id=:t"), {"t": tenant_a})
    menu_b = await c.scalar(text("SELECT food_item_id FROM food_item WHERE tenant_id=:t"), {"t": tenant_b})
    kitchen_b = await c.scalar(text("SELECT kitchen_id FROM kitchen WHERE tenant_id=:t"), {"t": tenant_b})
    type_b = await c.scalar(text("SELECT package_type_id FROM packaging_type WHERE tenant_id=:t"), {"t": tenant_b})
    raw_batch = await c.scalar(text("SELECT raw_material_batch_id FROM raw_material_batch WHERE tenant_id=:t"), {"t": tenant_a})
    production_a, production_b, item_id, package_id = (uuid4() for _ in range(4))
    production_sql = text("INSERT INTO production_batch (production_batch_id, tenant_id, batch_code, kitchen, menu) "
                          "VALUES (:id, :t, :code, :kitchen, :menu)")
    production = {"id": production_a, "t": tenant_a, "code": "PROD01", "kitchen": kitchen_id, "menu": menu_a}
    await c.execute(production_sql, production)
    await c.execute(production_sql, {**production, "id": production_b, "t": tenant_b,
                                    "kitchen": kitchen_b, "menu": menu_b})
    for invalid in ({**production, "id": uuid4()},
                    {**production, "id": uuid4(), "code": "PROD02", "menu": menu_b},
                    {**production, "id": uuid4(), "code": "PROD02", "kitchen": kitchen_b}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(production_sql, invalid)
    item_sql = text("INSERT INTO production_item (production_item_id, tenant_id, production_batch_id, "
                    "raw_material_batch_id, quantity, uom) VALUES (:id, :t, :production, :raw, 0.125, 'kg')")
    item = {"id": item_id, "t": tenant_a, "production": production_a, "raw": raw_batch}
    for invalid in ({**item, "production": production_b},
                    {**item, "t": tenant_b, "production": production_b}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(item_sql, invalid)
    await c.execute(item_sql, item)
    with pytest.raises(IntegrityError):
        async with c.begin_nested():
            await c.execute(item_sql, {**item, "id": uuid4()})
    package_sql = text("INSERT INTO package (package_id, tenant_id, package_code, production_batch_id, "
                       "package_type_id, package_number, remaining_minutes) "
                       "VALUES (:id, :t, :code, :production, :type, :number, -1)")
    package = {"id": package_id, "t": tenant_a, "code": "PKG01", "production": production_a,
               "type": None, "number": 1}
    for invalid in ({**package, "production": production_b}, {**package, "type": type_b}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(package_sql, invalid)
    await c.execute(package_sql, package)
    for invalid in ({**package, "id": uuid4(), "number": 2},
                    {**package, "id": uuid4(), "code": "PKG02"}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(package_sql, invalid)
    assert await c.scalar(text("SELECT remaining_minutes FROM package WHERE package_id=:id"), {"id": package_id}) == -1
    for query, identifier in (
        ("UPDATE production_batch SET finished_at=now() WHERE production_batch_id=:id", production_a),
        ("UPDATE production_batch SET started_at=now(), finished_at=now()-interval '1 hour' WHERE production_batch_id=:id", production_a),
        ("UPDATE production_batch SET holding_expired_at=now() WHERE production_batch_id=:id", production_a),
        ("UPDATE production_item SET quantity=0 WHERE production_item_id=:id", item_id),
        ("UPDATE production_item SET quantity='NaN' WHERE production_item_id=:id", item_id),
        ("UPDATE package SET package_number=0 WHERE package_id=:id", package_id),
        ("DELETE FROM production_batch WHERE production_batch_id=:id", production_a),
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text(query), {"id": identifier})


async def verify_delivery(c, tenant_a, tenant_b, kitchen_id):
    refs = {}
    for table, pk in (('vehicle', 'vehicle_id'), ('driver', 'driver_id')):
        for tenant in (tenant_a, tenant_b):
            refs[table, tenant] = await c.scalar(text(f"SELECT {pk} FROM {table} WHERE tenant_id=:t"), {"t": tenant})
    package = await c.scalar(text("SELECT package_id FROM package WHERE tenant_id=:t"), {"t": tenant_a})
    school = await c.scalar(text("SELECT school_id FROM school WHERE tenant_id=:t"), {"t": tenant_a})
    delivery_a, delivery_b, extra_delivery, item_id, receipt_id, other_school = (uuid4() for _ in range(6))
    header_sql = text("INSERT INTO delivery (delivery_id, tenant_id, vehicle, driver) VALUES (:id, :t, :vehicle, :driver)")
    header = {"id": delivery_a, "t": tenant_a, "vehicle": refs['vehicle', tenant_a], "driver": refs['driver', tenant_a]}
    await c.execute(header_sql, header)
    await c.execute(header_sql, {**header, "id": extra_delivery})
    await c.execute(header_sql, {"id": delivery_b, "t": tenant_b,
                               "vehicle": refs['vehicle', tenant_b], "driver": refs['driver', tenant_b]})
    for invalid in ({**header, "id": uuid4(), "vehicle": refs['vehicle', tenant_b]},
                    {**header, "id": uuid4(), "driver": refs['driver', tenant_b]}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(header_sql, invalid)
    item_sql = text("INSERT INTO delivery_item (delivery_item_id, tenant_id, delivery_id, package_id, school_id) "
                    "VALUES (:id, :t, :delivery, :package, :school)")
    item = {"id": item_id, "t": tenant_a, "delivery": delivery_a, "package": package, "school": school}
    for invalid in ({**item, "delivery": delivery_b}, {**item, "t": tenant_b, "delivery": delivery_b}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(item_sql, invalid)
    await c.execute(item_sql, item)
    with pytest.raises(IntegrityError):
        async with c.begin_nested():
            await c.execute(item_sql, {**item, "id": uuid4()})
    await c.execute(text("INSERT INTO school (school_id, tenant_id, kitchen_id, school_code, school_name) "
                         "VALUES (:id, :t, :k, 'WRONG_DEST', 'Other school')"),
                    {"id": other_school, "t": tenant_a, "k": kitchen_id})
    receipt_sql = text("INSERT INTO school_receiving (school_receiving_id, tenant_id, delivery_id, package, school, received_time) "
                       "VALUES (:id, :t, :delivery, :package, :school, now())")
    receipt = {**item, "id": receipt_id}
    for invalid in ({**receipt, "school": other_school}, {**receipt, "delivery": extra_delivery},
                    {**receipt, "t": tenant_b}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(receipt_sql, invalid)
    await c.execute(receipt_sql, receipt)
    assert await c.scalar(text("SELECT accepted FROM school_receiving WHERE school_receiving_id=:id"), {"id": receipt_id}) is None
    with pytest.raises(IntegrityError):
        async with c.begin_nested():
            await c.execute(receipt_sql, {**receipt, "id": uuid4()})
    for query, identifier in (
        ("UPDATE delivery SET arrival_time=now() WHERE delivery_id=:id", delivery_a),
        ("UPDATE delivery SET departure_time=now(), arrival_time=now()-interval '1 hour' WHERE delivery_id=:id", delivery_a),
        ("UPDATE school_receiving SET temperature='NaN' WHERE school_receiving_id=:id", receipt_id),
        ("DELETE FROM delivery_item WHERE delivery_item_id=:id", item_id),
        ("DELETE FROM delivery WHERE delivery_id=:id", delivery_a),
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text(query), {"id": identifier})
    await c.execute(text("DELETE FROM school WHERE school_id=:id"), {"id": other_school})


async def verify_consumption_recall(c, tenant_a, tenant_b):
    package = await c.scalar(text("SELECT package_id FROM package WHERE tenant_id=:t"), {"t": tenant_a})
    school = await c.scalar(text("SELECT school_id FROM school WHERE tenant_id=:t"), {"t": tenant_a})
    production = await c.scalar(text("SELECT production_batch_id FROM production_batch WHERE tenant_id=:t"), {"t": tenant_a})
    statements = {
        'consumption': text("INSERT INTO consumption (consumption_id, tenant_id, package_id, consumed_at, remaining_minutes) "
                            "VALUES (:id, :t, :package, now(), -10)"),
        'complaint': text("INSERT INTO complaint (complaint_id, tenant_id, package_id, school_id, description, reported_at) "
                         "VALUES (:id, :t, :package, :school, 'Reported issue', now())"),
        'recall': text("INSERT INTO recall (recall_id, tenant_id, production_batch_id, reason, started_at) "
                      "VALUES (:id, :t, :production, 'Investigation', now())"),
    }
    params = {'id': uuid4(), 't': tenant_a, 'package': package, 'school': school, 'production': production}
    ids = {}
    for table, statement in statements.items():
        for invalid in ({**params, 't': tenant_b},
                        {**params, 'package': uuid4(), 'production': uuid4()}):
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, invalid)
        ids[table] = uuid4()
        await c.execute(statement, {**params, 'id': ids[table]})
    assert (await c.execute(text("SELECT remaining_minutes, safe FROM consumption WHERE consumption_id=:id"),
                            {'id': ids['consumption']})).one() == (-10, None)
    with pytest.raises(IntegrityError):
        async with c.begin_nested():
            await c.execute(statements['consumption'], {**params, 'id': uuid4()})
    # Beberapa laporan/recall dapat disimpan untuk paket/batch yang sama.
    for table in ('complaint', 'recall'):
        await c.execute(statements[table], {**params, 'id': uuid4()})
    for query, identifier in (
        ("UPDATE complaint SET description=' ' WHERE complaint_id=:id", ids['complaint']),
        ("UPDATE recall SET reason=' ' WHERE recall_id=:id", ids['recall']),
        ("UPDATE recall SET completed_at=started_at-interval '1 minute' WHERE recall_id=:id", ids['recall']),
        ("UPDATE consumption SET consumed_at=NULL WHERE consumption_id=:id", ids['consumption']),
        ("UPDATE complaint SET reported_at=NULL WHERE complaint_id=:id", ids['complaint']),
        ("UPDATE recall SET started_at=NULL WHERE recall_id=:id", ids['recall']),
        ("DELETE FROM package WHERE package_id=:id", package),
        ("DELETE FROM production_batch WHERE production_batch_id=:id", production),
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text(query), {'id': identifier})


async def verify_asset_graph(c, tenant_a, tenant_b):
    package = await c.scalar(text("SELECT package_id FROM package WHERE tenant_id=:t"), {'t': tenant_a})
    school = await c.scalar(text("SELECT school_id FROM school WHERE tenant_id=:t"), {'t': tenant_a})
    operator_b = await c.scalar(text("SELECT user_id FROM app_user WHERE tenant_id=:t"), {'t': tenant_b})
    asset_a, asset_b, location, movement = (uuid4() for _ in range(4))
    asset_sql = text("INSERT INTO digital_asset (asset_uuid, tenant_id, asset_type, entity_uuid, code, name) "
                     "VALUES (:id, :t, :type, :entity, :code, 'Asset')")
    params = {'id': asset_a, 't': tenant_a, 'type': 'PACKAGE', 'entity': package, 'code': 'PKG01'}
    await c.execute(asset_sql, params)
    await c.execute(asset_sql, {**params, 'id': location, 'entity': school, 'type': 'SCHOOL', 'code': 'S01'})
    vehicle_b = await c.scalar(text("SELECT vehicle_id FROM vehicle WHERE tenant_id=:t"), {'t': tenant_b})
    await c.execute(asset_sql, {**params, 'id': asset_b, 't': tenant_b, 'entity': vehicle_b, 'type': 'VEHICLE'})
    with pytest.raises(IntegrityError):
        async with c.begin_nested():
            await c.execute(asset_sql, {**params, 'id': uuid4(), 'code': 'OTHER'})
    edge_sql = text("INSERT INTO asset_relationship (relationship_uuid, tenant_id, parent_uuid, child_uuid, relationship_type) "
                    "VALUES (:id, :t, :parent, :child, 'DELIVERED')")
    edge = {'id': uuid4(), 't': tenant_a, 'parent': asset_a, 'child': location}
    await c.execute(edge_sql, edge)
    for invalid in ({**edge, 'id': uuid4()}, {**edge, 'id': uuid4(), 'child': asset_a},
                    {**edge, 'id': uuid4(), 'child': asset_b}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(edge_sql, invalid)
    movement_sql = text("INSERT INTO asset_movement (movement_id, tenant_id, asset_type, asset_uuid, "
                        "movement_type, to_location, operator, movement_time) "
                        "VALUES (:id, :t, :type, :asset, 'DELIVERY', :location, :operator, now())")
    event = {'id': movement, 't': tenant_a, 'type': 'PACKAGE', 'asset': asset_a,
             'location': location, 'operator': None}
    for invalid in ({**event, 'type': 'VEHICLE'}, {**event, 'location': asset_b},
                    {**event, 'operator': operator_b}, {**event, 'asset': uuid4()}):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(movement_sql, invalid)
    await c.execute(movement_sql, event)
    for statement in (
        "UPDATE asset_movement SET remarks='edited'",
        "UPDATE asset_movement SET deleted_at=now()",
        "DELETE FROM asset_movement", "TRUNCATE asset_movement",
    ):
        with pytest.raises(DBAPIError) as error:
            async with c.begin_nested():
                await c.execute(text(statement))
        assert error.value.orig.sqlstate == '55000'
    assert await c.scalar(text("SELECT count(*) FROM asset_movement")) == 1


async def verify_event_log(c, tenant):
    package = await c.scalar(text("SELECT package_id FROM package WHERE tenant_id=:t"), {'t': tenant})
    statement = text("INSERT INTO event_log (event_uuid, tenant_id, event_type, entity_type, entity_uuid, payload) "
                     "VALUES (:id, :t, :event, :type, :entity, CAST(:payload AS jsonb))")
    event = {'id': uuid4(), 't': tenant, 'event': 'package.created', 'type': 'PACKAGE',
             'entity': package, 'payload': '{"status": "CREATED", "context": {"source": "test"}}'}
    await c.execute(statement, event)
    body = (await c.execute(text("SELECT payload, created_at IS NOT NULL FROM event_log WHERE event_uuid=:id"),
                           {'id': event['id']})).one()
    assert body == ({'status': 'CREATED', 'context': {'source': 'test'}}, True)
    for invalid in (
        event, {**event, 'id': uuid4(), 't': uuid4()},
        {**event, 'id': uuid4(), 'event': ' '}, {**event, 'id': uuid4(), 'type': ' '},
        {**event, 'id': uuid4(), 'payload': '[]'}, {**event, 'id': uuid4(), 'payload': 'null'},
    ):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(statement, invalid)
    for mutation in ("UPDATE event_log SET payload='{}'", "UPDATE event_log SET deleted_at=now()",
                     "DELETE FROM event_log", "TRUNCATE event_log"):
        with pytest.raises(DBAPIError) as error:
            async with c.begin_nested():
                await c.execute(text(mutation))
        assert error.value.orig.sqlstate == '55000'
    # Satu entity dapat menghasilkan beberapa event dengan UUID berbeda.
    await c.execute(statement, {**event, 'id': uuid4(), 'event': 'package.updated'})
    assert await c.scalar(text("SELECT count(*) FROM event_log")) == 2


async def verify_telemetry(c, tenant, other_tenant):
    device = await c.scalar(text("SELECT device_uuid FROM device WHERE tenant_id=:t"), {'t': tenant})
    other_device = await c.scalar(text("SELECT device_uuid FROM device WHERE tenant_id=:t"), {'t': other_tenant})
    storage = await c.scalar(text("SELECT storage_id FROM storage WHERE tenant_id=:t"), {'t': tenant})
    vehicle = await c.scalar(text("SELECT vehicle_id FROM vehicle WHERE tenant_id=:t"), {'t': tenant})
    message, other_message = uuid4(), uuid4()
    for message_id, tenant_id in ((message, tenant), (other_message, other_tenant)):
        await c.execute(text("INSERT INTO mqtt_message_log (message_uuid, tenant_id, topic, qos, payload, received_at) "
                             "VALUES (:id, :t, 'fsos/test', 1, :payload, now())"),
                        {'id': message_id, 't': tenant_id, 'payload': b'original bytes'})
    statements = {
        'temperature_log': ("temperature_log_id, device_uuid, storage_uuid, temperature, unit",
                            ":id, :device, :storage, 4.125, 'C'"),
        'humidity_log': ("humidity_log_id, device_uuid, humidity", ":id, :device, 60"),
        'gps_log': ("gps_log_id, vehicle_uuid, latitude, longitude", ":id, :vehicle, -6.2, 106.8"),
        'heartbeat_log': ("heartbeat_log_id, device_uuid, uptime", ":id, :device, 100"),
    }
    params = {'id': uuid4(), 't': tenant, 'device': device, 'storage': storage,
              'vehicle': vehicle, 'message': message, 'time': datetime.fromisoformat('2026-09-30T23:59:59+00:00')}
    for table, (columns, values) in statements.items():
        statement = text(f"INSERT INTO {table} (tenant_id, mqtt_message_id, recorded_at, {columns}) "
                         f"VALUES (:t, :message, CAST(:time AS timestamptz), {values}) RETURNING tableoid::regclass::text")
        first = {**params, 'id': uuid4()}
        assert await c.scalar(statement, first) == table + '_202609'
        assert await c.scalar(statement, {**first, 'id': uuid4(), 'time': datetime.fromisoformat('2026-10-01T00:00:00+00:00')}) == table + '_202610'
        for invalid in (first, {**first, 'id': uuid4(), 'message': other_message},
                        {**first, 'id': uuid4(), 'time': datetime.fromisoformat('2030-01-01T00:00:00+00:00')}):
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, invalid)
        if table != 'gps_log':
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, {**first, 'id': uuid4(), 'device': other_device})
        for target in (table, table + '_202609'):
            for mutation in (f"UPDATE {target} SET version=2", f"DELETE FROM {target}", f"TRUNCATE {target}"):
                with pytest.raises(DBAPIError) as error:
                    async with c.begin_nested():
                        await c.execute(text(mutation))
                assert error.value.orig.sqlstate == '55000'
    assert (await c.execute(text("SELECT ST_X(location), ST_Y(location) FROM gps_log LIMIT 1"))).one() == (106.8, -6.2)
    # Partisi tambahan dibuat idempotent, row trigger diwariskan dan truncate guard dibuat pada child.
    for _ in range(2):
        await c.execute(text("SELECT public.fsos_create_telemetry_partitions(DATE '2026-12-01', 1)"))
    assert await c.scalar(text("SELECT count(*) FROM pg_inherits i JOIN pg_class p ON p.oid=i.inhparent "
                              "WHERE p.relname IN ('temperature_log','humidity_log','gps_log','heartbeat_log')")) == 16
    await c.execute(text("INSERT INTO humidity_log (humidity_log_id, tenant_id, device_uuid, recorded_at, humidity) "
                         "VALUES (:id, :t, :device, '2026-12-01T00:00:00+00', 50)"), params)
    with pytest.raises(DBAPIError) as error:
        async with c.begin_nested():
            await c.execute(text("TRUNCATE humidity_log_202612"))
    assert error.value.orig.sqlstate == '55000'
    with pytest.raises(DBAPIError):
        async with c.begin_nested():
            await c.execute(text("SELECT public.fsos_create_telemetry_partitions(DATE '2026-12-02', 1)"))


async def verify_remaining_telemetry(c, tenant, other_tenant):
    device = await c.scalar(text("SELECT device_uuid FROM device WHERE tenant_id=:t"), {'t': tenant})
    package = await c.scalar(text("SELECT package_id FROM package WHERE tenant_id=:t"), {'t': tenant})
    actor = await c.scalar(text("SELECT user_id FROM app_user WHERE tenant_id=:t"), {'t': tenant})
    other_actor = await c.scalar(text("SELECT user_id FROM app_user WHERE tenant_id=:t"), {'t': other_tenant})
    message = await c.scalar(text("SELECT message_uuid FROM mqtt_message_log WHERE tenant_id=:t"), {'t': other_tenant})
    rows = {
        'device_health_log': ('device_health_log_id, device_uuid, health', ":id, :device, 'OK'", "health", "' '"),
        'alarm_log': ('alarm_id, device_uuid, alarm_code, severity', ":id, :device, 'TEMP_HIGH', 'HIGH'", "alarm_code", "' '"),
        'holding_log': ('holding_id, package_uuid, status, elapsed_minutes, remaining_minutes, warning_level',
                        ":id, :package, 'EXPIRED', 120, -10, 'HIGH'", "elapsed_minutes", '-1'),
        'signal_log': ('signal_log_id, device_uuid, rssi, quality', ':id, :device, -60, 80', 'quality', '101'),
        'battery_log': ('battery_log_id, device_uuid, voltage, percentage, charging', ':id, :device, 3.7, 80, false', 'voltage', "'NaN'"),
        'device_session': ('session_id, device_uuid, connected_at, ip_address', ":id, :device, now(), '::1'", 'disconnected_at', "now()-interval '1 second'"),
    }
    params = {'t': tenant, 'device': device, 'package': package, 'message': None}
    ids = {}
    for table, (columns, values, bad_column, bad_value) in rows.items():
        statement = text(f'INSERT INTO {table} (tenant_id, recorded_at, mqtt_message_id, {columns}) '
                         f'VALUES (:t, now(), :message, {values})')
        ids[table] = uuid4()
        valid = {**params, 'id': ids[table]}
        await c.execute(statement, valid)
        for invalid in (valid, {**valid, 'id': uuid4(), 't': other_tenant},
                        {**valid, 'id': uuid4(), 'message': message}):
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, invalid)
        # INSERT SELECT changes only the value under test; immutable UPDATE would hide a missing CHECK.
        key = columns.split(',')[0]
        selected = ['gen_random_uuid()' if col == key else bad_value if col == bad_column else col
                    for col in ['tenant_id', 'recorded_at', 'mqtt_message_id', *columns.split(', ')]]
        insert_columns = f'tenant_id, recorded_at, mqtt_message_id, {columns}'
        if bad_column not in columns.split(', '):
            insert_columns += ', ' + bad_column
            selected.append(bad_value)
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(text(f'INSERT INTO {table} ({insert_columns}) SELECT {", ".join(selected)} FROM {table}'))
    assert await c.scalar(text('SELECT remaining_minutes FROM holding_log')) == -10
    ack_sql = text('INSERT INTO alarm_acknowledgment (acknowledgment_id, tenant_id, alarm_id, acknowledged_by, '
                   'acknowledged_at, recorded_at) VALUES (:id, :t, :parent, :actor, :time, now())')
    end_sql = text('INSERT INTO device_session_end (session_end_id, tenant_id, session_id, disconnected_at, recorded_at) '
                   'VALUES (:id, :t, :parent, :time, now())')
    now = await c.scalar(text('SELECT now()'))
    early = datetime.fromisoformat('2000-01-01T00:00:00+00:00')
    for statement, parent_table in ((ack_sql, 'alarm_log'), (end_sql, 'device_session')):
        event = {'id': uuid4(), 't': tenant, 'parent': ids[parent_table], 'actor': actor, 'time': now}
        for invalid in ({**event, 'time': early}, {**event, 't': other_tenant}, {**event, 'parent': uuid4()}):
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, invalid)
        if parent_table == 'alarm_log':
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(statement, {**event, 'actor': other_actor})
        await c.execute(statement, event)
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(statement, {**event, 'id': uuid4()})
    assert await c.scalar(text('SELECT acknowledged FROM alarm_log')) is False
    assert await c.scalar(text('SELECT disconnected_at FROM device_session')) is None
    assert await c.scalar(text('SELECT a.acknowledged OR k.alarm_id IS NOT NULL FROM alarm_log a '
                              'LEFT JOIN alarm_acknowledgment k USING (tenant_id, alarm_id)')) is True
    assert await c.scalar(text('SELECT coalesce(s.disconnected_at, e.disconnected_at) FROM device_session s '
                              'LEFT JOIN device_session_end e USING (tenant_id, session_id)')) == now
    # Imported final snapshots cannot be finalized again.
    final_alarm, final_session = uuid4(), uuid4()
    await c.execute(text("INSERT INTO alarm_log (alarm_id, tenant_id, device_uuid, alarm_code, severity, recorded_at, acknowledged) "
                         "VALUES (:id, :t, :device, 'IMPORTED', 'HIGH', now(), true)"), {**params, 'id': final_alarm})
    await c.execute(text('INSERT INTO device_session (session_id, tenant_id, device_uuid, connected_at, disconnected_at, recorded_at) '
                         'VALUES (:id, :t, :device, now(), now(), now())'), {**params, 'id': final_session})
    for statement, parent in ((ack_sql, final_alarm), (end_sql, final_session)):
        with pytest.raises(IntegrityError):
            async with c.begin_nested():
                await c.execute(statement, {'id': uuid4(), 't': tenant, 'parent': parent, 'actor': actor, 'time': now})
    for table in (*rows, 'alarm_acknowledgment', 'device_session_end'):
        for mutation in (f'UPDATE {table} SET version=2', f'DELETE FROM {table}', f'TRUNCATE {table} CASCADE'):
            with pytest.raises(DBAPIError) as error:
                async with c.begin_nested():
                    await c.execute(text(mutation))
            assert error.value.orig.sqlstate == '55000'


async def verify_rule_history(c, tenant, other_tenant):
    for kind, assignment in (('alarm', "rule_name='New name'"), ('holding', 'maximum_minutes=110')):
        parent, history, pk = f'{kind}_rule', f'{kind}_rule_revision', f'{kind}_rule_id'
        original = await c.scalar(text(f'SELECT snapshot FROM {history} WHERE tenant_id=:t'), {'t': tenant})
        assert original['version'] == 1
        await c.execute(text(f'UPDATE {parent} SET {assignment} WHERE tenant_id=:t AND version=1'), {'t': tenant})
        snapshots = (await c.execute(text(f'SELECT snapshot FROM {history} WHERE tenant_id=:t ORDER BY version'), {'t': tenant})).scalars().all()
        assert len(snapshots) == 2 and snapshots[0] == original and snapshots[1]['version'] == 2
        # Version predicate prevents a stale writer from creating a third revision.
        result = await c.execute(text(f'UPDATE {parent} SET {assignment} WHERE tenant_id=:t AND version=1'), {'t': tenant})
        assert result.rowcount == 0
        async with c.begin_nested() as savepoint:
            await c.execute(text(f'UPDATE {parent} SET {assignment} WHERE tenant_id=:t'), {'t': tenant})
            assert await c.scalar(text(f'SELECT count(*) FROM {history} WHERE tenant_id=:t'), {'t': tenant}) == 3
            await savepoint.rollback()
        assert await c.scalar(text(f'SELECT count(*) FROM {history} WHERE tenant_id=:t'), {'t': tenant}) == 2
        for change in ('version=0', f'{pk}=gen_random_uuid()', 'tenant_id=:other'):
            with pytest.raises(IntegrityError):
                async with c.begin_nested():
                    await c.execute(text(f'UPDATE {parent} SET {change} WHERE tenant_id=:t'), {'t': tenant, 'other': other_tenant})
        for mutation in (f"UPDATE {history} SET snapshot='{{}}'", f'DELETE FROM {history}',
                         f'TRUNCATE {history}', f'DELETE FROM {parent}', f'TRUNCATE {parent} CASCADE'):
            with pytest.raises(DBAPIError) as error:
                async with c.begin_nested():
                    await c.execute(text(mutation))
            assert error.value.orig.sqlstate == '55000'
