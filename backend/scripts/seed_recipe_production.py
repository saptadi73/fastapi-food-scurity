"""Seed menu, recipe, accepted stock, and a production batch for an existing tenant.

The script is additive and idempotent. It never deletes or changes existing master
records. It is intended for development/testing or an explicitly approved seed run.
"""
import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import UUID, uuid5

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import async_sessionmaker

from app.core.config.settings import get_settings
from app.core.database.session import close_database, get_admin_engine
from app.core.events.orm import EventLog
from app.core.database.scope import ActorScope
from app.modules.authentication.infrastructure.orm import User
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem
from app.modules.master.infrastructure.orm import (Device, Driver, FoodItem, Kitchen, PackagingType, RawMaterial, Recipe,
    School, Storage, StorageZone, Supplier, SupplierMaterial, Vehicle)
from app.modules.production.infrastructure.orm import Package, ProductionBatch, ProductionItem
from app.modules.receiving.infrastructure.orm import RawMaterialBatch, Receiving, ReceivingItem, StockEntry
from app.modules.telemetry.infrastructure.orm import GPSLog, TemperatureLog
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship
from app.modules.traceability.infrastructure.registry import sync_source

NAMESPACE = UUID('f0d8dd5f-6499-4d39-8b4f-3a994d4ca7b6')


def did(tenant: UUID, name: str) -> UUID:
    return uuid5(NAMESPACE, f'{tenant}:{name}')


def audit(tenant: UUID, actor: UUID) -> dict:
    return {'tenant_id': tenant, 'created_by': actor, 'updated_by': actor, 'version': 1}


async def existing(session, model, key, identifier):
    return (await session.execute(select(model.__table__).where(getattr(model, key) == identifier))).mappings().one_or_none()


async def active_one(session, model, tenant: UUID, key: str, value=None):
    query = select(model.__table__).where(model.tenant_id == tenant, model.deleted_at.is_(None), model.status == 'ACTIVE')
    if value is not None:
        query = query.where(getattr(model, key) == value)
    return (await session.execute(query.order_by(getattr(model, key)))).mappings().first()


async def active_named(session, model, tenant: UUID, field: str, value: str | None):
    if not value:
        return await active_one(session, model, tenant, field)
    return (await session.execute(select(model.__table__).where(
        model.tenant_id == tenant, model.deleted_at.is_(None), model.status == 'ACTIVE',
        func.lower(getattr(model, field)) == value.strip().lower(),
    ))).mappings().one_or_none()


async def insert_once(session, model, pk_name: str, pk: UUID, values: dict) -> bool:
    if await existing(session, model, pk_name, pk) is not None:
        return False
    await session.execute(insert(model.__table__).values(**{pk_name: pk}, **values))
    return True


async def seed(session, tenant: UUID, actor: UUID, food_code: str, menu_name: str,
               planned_quantity: Decimal, kitchen_name: str | None = None,
               supplier_name: str | None = None, material_names: list[str] | None = None) -> dict:
    await session.execute(text('SELECT pg_advisory_xact_lock(20260921, 41)'))
    kitchen = await active_named(session, Kitchen, tenant, 'kitchen_name', kitchen_name)
    supplier = await active_named(session, Supplier, tenant, 'supplier_name', supplier_name)
    actor_row = await existing(session, User, 'user_id', actor)
    if not kitchen or not supplier or not actor_row or actor_row['tenant_id'] != tenant or actor_row['status'] != 'ACTIVE':
        raise ValueError('Tenant harus memiliki actor, kitchen, dan supplier ACTIVE yang valid')

    material_query = select(RawMaterial.__table__).where(
        RawMaterial.tenant_id == tenant, RawMaterial.deleted_at.is_(None), RawMaterial.status == 'ACTIVE'
    ).order_by(RawMaterial.material_code)
    if material_names:
        material_query = material_query.where(func.lower(RawMaterial.material_name).in_([n.strip().lower() for n in material_names]))
    else:
        material_query = material_query.limit(2)
    materials = (await session.execute(material_query)).mappings().all()
    if not materials:
        raise ValueError('Minimal satu bahan baku ACTIVE diperlukan')

    food_id = did(tenant, f'food:{food_code}')
    created = {'food': 0, 'recipes': 0, 'storage': 0, 'zone': 0, 'receiving': 0, 'batches': 0, 'stock': 0, 'production': 0}
    food = await existing(session, FoodItem, 'food_item_id', food_id)
    if food is None:
        created['food'] += await insert_once(session, FoodItem, 'food_item_id', food_id, {
            'food_code': food_code, 'food_name': menu_name, 'category': 'HOT_MEAL',
            'uom': 'portion', 'holding_limit_minutes': 120, 'status': 'ACTIVE', **audit(tenant, actor),
        })
        food = await existing(session, FoodItem, 'food_item_id', food_id)
    elif food['tenant_id'] != tenant or food['status'] != 'ACTIVE':
        raise ValueError(f'Food code {food_code} sudah dipakai record nonaktif/tenant lain')

    recipe_rows = []
    for material in materials:
        recipe_id = did(tenant, f'recipe:{food_id}:{material["raw_material_id"]}')
        recipe = await existing(session, Recipe, 'recipe_id', recipe_id)
        if recipe is None:
            created['recipes'] += await insert_once(session, Recipe, 'recipe_id', recipe_id, {
                'food_item_id': food_id, 'raw_material_id': material['raw_material_id'],
                'quantity': Decimal('0.100000'), 'uom': material['uom'], **audit(tenant, actor),
            })
            recipe = await existing(session, Recipe, 'recipe_id', recipe_id)
        recipe_rows.append(recipe)

    now = datetime.now(UTC).replace(microsecond=0)
    receiving_id = did(tenant, f'receiving:{food_code}')
    created['receiving'] += await insert_once(session, Receiving, 'receiving_id', receiving_id, {
        'supplier_id': supplier['supplier_id'], 'kitchen_id': kitchen['kitchen_id'], 'operator': actor,
        'received_at': now - timedelta(hours=1), 'status': 'COMPLETED', 'version': 2,
        'tenant_id': tenant, 'created_by': actor, 'updated_by': actor,
    })

    stock_inputs = []
    for index, (material, recipe) in enumerate(zip(materials, recipe_rows, strict=True), 1):
        storage = (await session.execute(select(Storage.__table__).where(
            Storage.tenant_id == tenant, Storage.kitchen_id == kitchen['kitchen_id'],
            Storage.deleted_at.is_(None), Storage.status == 'ACTIVE',
            Storage.storage_type == material['storage_type'],
        ).order_by(Storage.storage_code))).mappings().first()
        if storage is None:
            storage_type = material['storage_type']
            temperature = {
                'COLD_STORAGE': (Decimal('1.00'), Decimal('5.00'), 'Cold Storage Seed'),
                'DRY_STORAGE': (Decimal('20.00'), Decimal('30.00'), 'Dry Storage Seed'),
                'FREEZER': (Decimal('-25.00'), Decimal('-18.00'), 'Freezer Seed'),
            }.get(storage_type, (None, None, f'{storage_type} Seed'))
            storage_id = did(tenant, f'storage:{kitchen["kitchen_id"]}:{storage_type}')
            storage_code = f'SEED-{storage_type}'[:50]
            created['storage'] += await insert_once(session, Storage, 'storage_id', storage_id, {
                'kitchen_id': kitchen['kitchen_id'], 'storage_code': storage_code,
                'storage_name': temperature[2], 'storage_type': storage_type,
                'temperature_min': temperature[0], 'temperature_max': temperature[1],
                'location': None, 'status': 'ACTIVE', **audit(tenant, actor),
            })
            storage = await existing(session, Storage, 'storage_id', storage_id)
        if storage is None:
            raise ValueError(f"Storage ACTIVE dengan tipe {material['storage_type']} untuk {material['material_name']} tidak dapat dibuat")
        zone = (await session.execute(select(StorageZone.__table__).where(
            StorageZone.tenant_id == tenant, StorageZone.storage_id == storage['storage_id'],
            StorageZone.deleted_at.is_(None),
        ).order_by(StorageZone.zone_code))).mappings().first()
        if zone is None:
            zone_id = did(tenant, f'zone:{storage["storage_id"]}:SEED-A1')
            created['zone'] += await insert_once(session, StorageZone, 'zone_id', zone_id, {
                'storage_id': storage['storage_id'], 'zone_code': 'SEED-A1',
                'zone_name': 'Rak Seed A1', **audit(tenant, actor),
            })
            zone = await existing(session, StorageZone, 'zone_id', zone_id)
        link_id = did(tenant, f'supplier-material:{supplier["supplier_id"]}:{material["raw_material_id"]}')
        link_exists = await session.scalar(select(SupplierMaterial.supplier_material_id).where(
            SupplierMaterial.tenant_id == tenant,
            SupplierMaterial.supplier_id == supplier['supplier_id'],
            SupplierMaterial.raw_material_id == material['raw_material_id'],
            SupplierMaterial.deleted_at.is_(None),
        ))
        if link_exists is None:
            await insert_once(session, SupplierMaterial, 'supplier_material_id', link_id, {
                'supplier_id': supplier['supplier_id'], 'raw_material_id': material['raw_material_id'], **audit(tenant, actor),
            })
        batch_id = did(tenant, f'raw-batch:{food_code}:{material["raw_material_id"]}')
        item_id = did(tenant, f'receiving-item:{food_code}:{material["raw_material_id"]}')
        batch_code = f'SEED-{food_code}-{index}'[:100]
        created['batches'] += await insert_once(session, RawMaterialBatch, 'raw_material_batch_id', batch_id, {
            'raw_material_id': material['raw_material_id'], 'receiving_id': receiving_id,
            'supplier_id': supplier['supplier_id'], 'batch_code': batch_code,
            'expired_date': date.today() + timedelta(days=30), 'status': 'ACCEPTED',
            'qr_code': f'QR-{batch_code}', **audit(tenant, actor), 'version': 2,
        })
        created['batches'] += await insert_once(session, ReceivingItem, 'receiving_item_id', item_id, {
            'receiving_id': receiving_id, 'raw_material_batch_id': batch_id,
            'quantity': Decimal('20.000000'), 'uom': material['uom'], 'temperature': None,
            'condition': 'GOOD', 'photo': None, 'accepted': True, **audit(tenant, actor), 'version': 2,
        })
        stock_id = did(tenant, f'stock:{food_code}:{material["raw_material_id"]}')
        created['stock'] += await insert_once(session, StockEntry, 'stock_entry_id', stock_id, {
            'raw_material_batch_id': batch_id, 'storage_id': storage['storage_id'],
            'zone_id': zone['zone_id'] if zone else None, 'quantity': Decimal('20.000000'),
            'batch_version': 2, **audit(tenant, actor),
        })
        stock_inputs.append((material, recipe, batch_id, storage['storage_id']))

    scope = ActorScope(tenant, actor)
    supplier_asset = await sync_source(session, scope, 'SUPPLIER', supplier['supplier_id'])
    kitchen_asset = await sync_source(session, scope, 'KITCHEN', kitchen['kitchen_id'])
    receipt_asset = await sync_source(session, scope, 'RECEIVING', receiving_id)
    for material, recipe, batch_id, storage_id in stock_inputs:
        material_asset = await sync_source(session, scope, 'RAW_MATERIAL_BATCH', batch_id)
        await insert_once(session, AssetRelationship, 'relationship_uuid', did(tenant, f'rel:supplied:{batch_id}'), {
            'parent_uuid': supplier_asset['asset_uuid'], 'child_uuid': material_asset['asset_uuid'],
            'relationship_type': 'SUPPLIED', **audit(tenant, actor),
        })
        await insert_once(session, AssetRelationship, 'relationship_uuid', did(tenant, f'rel:received:{batch_id}'), {
            'parent_uuid': receipt_asset['asset_uuid'], 'child_uuid': material_asset['asset_uuid'],
            'relationship_type': 'RECEIVED', **audit(tenant, actor),
        })
        await insert_once(session, AssetMovement, 'movement_id', did(tenant, f'movement:receiving:{batch_id}'), {
            'asset_type': 'RAW_MATERIAL_BATCH', 'asset_uuid': material_asset['asset_uuid'],
            'movement_type': 'RECEIVING', 'from_location': None, 'to_location': kitchen_asset['asset_uuid'],
            'operator': actor, 'movement_time': now - timedelta(hours=1), 'remarks': None, **audit(tenant, actor),
        })

    production_id = did(tenant, f'production:{food_code}')
    production = await existing(session, ProductionBatch, 'production_batch_id', production_id)
    if production is None:
        snapshot_items = []
        for material, recipe, batch_id, storage_id in stock_inputs:
            required = (recipe['quantity'] * planned_quantity).quantize(Decimal('0.000001'))
            snapshot_items.append({'recipe_id': str(recipe['recipe_id']), 'version': recipe['version'],
                'raw_material_id': str(material['raw_material_id']), 'quantity': str(recipe['quantity']),
                'required_quantity': str(required), 'uom': recipe['uom']})
        production_code = f'MO-{food_code}-001'[:100]
        created['production'] += await insert_once(session, ProductionBatch, 'production_batch_id', production_id, {
            'batch_code': production_code, 'kitchen': kitchen['kitchen_id'], 'menu': food_id,
            'planned_quantity': planned_quantity, 'actual_quantity': None, 'initial_temperature': None,
            'holding_policy': {'maximum_minutes': food['holding_limit_minutes'] or 120},
            'recipe_snapshot': {'schema_version': 1, 'food_version': food['version'],
                'food_category': food['category'], 'holding_limit_minutes': food['holding_limit_minutes'],
                'uom': food['uom'], 'items': snapshot_items},
            'status': 'CREATED', 'started_at': None, 'finished_at': None,
            'holding_started_at': None, 'holding_expired_at': None, **audit(tenant, actor),
        })
        await sync_source(session, scope, 'PRODUCTION_BATCH', production_id)
        await session.execute(insert(EventLog.__table__).values(
            event_uuid=did(tenant, f'event:production.created:{production_id}'), event_type='production.created',
            entity_type='PRODUCTION_BATCH', entity_uuid=production_id,
            payload={'schema_version': 1, 'source': 'seed_recipe_production'}, **audit(tenant, actor)))

    return {'tenant_id': str(tenant), 'food_code': food_code, 'kitchen': kitchen['kitchen_name'],
            'supplier': supplier['supplier_name'], 'materials': [m['material_name'] for m in materials],
            'production_batch_id': str(production_id), 'status': 'CREATED', 'created': created,
            'note': 'Sekolah belum dipakai pada resep/produksi; sekolah digunakan pada delivery dan school receiving.'}


async def continue_distribution(session, tenant: UUID, actor: UUID, food_code: str, planned_quantity: Decimal) -> dict:
    """Continue the deterministic seed into production, packaging and live delivery."""
    scope = ActorScope(tenant, actor)
    production_id = did(tenant, f'production:{food_code}')
    production = await existing(session, ProductionBatch, 'production_batch_id', production_id)
    if production is None:
        raise ValueError('Batch production seed belum ada; jalankan seed tanpa --continue-distribution dahulu')
    kitchen = await existing(session, Kitchen, 'kitchen_id', production['kitchen'])
    food = await existing(session, FoodItem, 'food_item_id', production['menu'])
    if kitchen is None or food is None:
        raise ValueError('Dapur atau menu batch produksi tidak ditemukan')

    now = datetime.now(UTC).replace(microsecond=0)
    snapshot = production['recipe_snapshot'] or {}
    if production['status'] == 'CREATED':
        for line in snapshot.get('items', []):
            batch_id = did(tenant, f'raw-batch:{food_code}:{line["raw_material_id"]}')
            batch = await existing(session, RawMaterialBatch, 'raw_material_batch_id', batch_id)
            if batch is None or batch['status'] != 'ACCEPTED':
                raise ValueError(f'Batch bahan untuk {line["raw_material_id"]} belum ACCEPTED')
            stock = (await session.execute(select(StockEntry.__table__).where(
                StockEntry.tenant_id == tenant, StockEntry.raw_material_batch_id == batch_id,
                StockEntry.deleted_at.is_(None),
            ).order_by(StockEntry.batch_version.desc()))).mappings().first()
            if stock is None:
                raise ValueError('Stock entry bahan belum tersedia')
            production_item_id = did(tenant, f'production-item:{food_code}:{line["raw_material_id"]}')
            await insert_once(session, ProductionItem, 'production_item_id', production_item_id, {
                'production_batch_id': production_id, 'raw_material_batch_id': batch_id,
                'storage_id': stock['storage_id'], 'batch_version': batch['version'] + 1,
                'quantity': Decimal(str(line['required_quantity'])), 'uom': line['uom'], **audit(tenant, actor),
            })
            await session.execute(update(RawMaterialBatch.__table__).where(
                RawMaterialBatch.tenant_id == tenant, RawMaterialBatch.raw_material_batch_id == batch_id,
                RawMaterialBatch.version == batch['version'],
            ).values(version=batch['version'] + 1, updated_at=now, updated_by=actor))
        await session.execute(update(ProductionBatch.__table__).where(
            ProductionBatch.tenant_id == tenant, ProductionBatch.production_batch_id == production_id,
        ).values(status='RUNNING', started_at=now, version=production['version'] + 1,
                 updated_at=now, updated_by=actor))
        production = await existing(session, ProductionBatch, 'production_batch_id', production_id)

    if production['status'] == 'RUNNING':
        holding_policy = {'schema_version': 1, 'rule_id': None, 'rule_version': None,
                          'food_category': food['category'], 'maximum_minutes': 120,
                          'warning_minutes': 90, 'discard_minutes': 150}
        await session.execute(update(ProductionBatch.__table__).where(
            ProductionBatch.tenant_id == tenant, ProductionBatch.production_batch_id == production_id,
        ).values(status='COMPLETED', actual_quantity=planned_quantity,
                 initial_temperature=Decimal('75.00'), finished_at=now,
                 holding_policy=holding_policy, version=production['version'] + 1,
                 updated_at=now, updated_by=actor))
        production = await existing(session, ProductionBatch, 'production_batch_id', production_id)
    if production['status'] != 'COMPLETED':
        raise ValueError(f'Batch produksi harus COMPLETED, status saat ini {production["status"]}')

    package_type = (await session.execute(select(PackagingType.__table__).where(
        PackagingType.tenant_id == tenant, PackagingType.deleted_at.is_(None),
    ).order_by(PackagingType.code))).mappings().first()
    if package_type is None:
        package_type_id = did(tenant, 'packaging:seed-tray')
        await insert_once(session, PackagingType, 'package_type_id', package_type_id, {
            'code': 'SEED-TRAY-750', 'name': 'Seed Tray 750ml', 'material': 'Food grade',
            'volume': Decimal('750.000'), **audit(tenant, actor),
        })
        package_type = await existing(session, PackagingType, 'package_type_id', package_type_id)

    package_id = did(tenant, f'package:{food_code}')
    package = await existing(session, Package, 'package_id', package_id)
    expiry = production['finished_at'] + timedelta(minutes=120)
    if package is None:
        await insert_once(session, Package, 'package_id', package_id, {
            'package_code': f'PKG-{food_code}-001'[:100], 'production_batch_id': production_id,
            'package_type_id': package_type['package_type_id'], 'package_number': 1,
            'quantity': planned_quantity, 'initial_temperature': Decimal('68.00'),
            'holding_started_at': production['finished_at'], 'holding_finished_at': now,
            'remaining_minutes': max(0, int((expiry - now).total_seconds() // 60)),
            'expired_at': expiry, 'status': 'RELEASED', **audit(tenant, actor), 'version': 3,
        })
        package = await existing(session, Package, 'package_id', package_id)
    elif package['status'] not in {'RELEASED', 'ALLOCATED', 'IN_TRANSIT'}:
        await session.execute(update(Package.__table__).where(
            Package.tenant_id == tenant, Package.package_id == package_id,
        ).values(status='RELEASED', holding_finished_at=now, version=package['version'] + 1,
                 updated_at=now, updated_by=actor))
        package = await existing(session, Package, 'package_id', package_id)

    package_asset = await sync_source(session, scope, 'PACKAGE', package_id)
    production_asset = await sync_source(session, scope, 'PRODUCTION_BATCH', production_id)
    kitchen_asset = await sync_source(session, scope, 'KITCHEN', kitchen['kitchen_id'])
    await insert_once(session, AssetRelationship, 'relationship_uuid', did(tenant, f'rel:packaged:{package_id}'), {
        'parent_uuid': production_asset['asset_uuid'], 'child_uuid': package_asset['asset_uuid'],
        'relationship_type': 'PACKAGED', **audit(tenant, actor),
    })
    await insert_once(session, AssetMovement, 'movement_id', did(tenant, f'movement:packaging:{package_id}'), {
        'asset_type': 'PACKAGE', 'asset_uuid': package_asset['asset_uuid'], 'movement_type': 'PACKAGING',
        'from_location': None, 'to_location': kitchen_asset['asset_uuid'], 'operator': actor,
        'movement_time': now, 'remarks': None, **audit(tenant, actor),
    })

    school = (await session.execute(select(School.__table__).where(
        School.tenant_id == tenant, School.kitchen_id == kitchen['kitchen_id'],
        School.deleted_at.is_(None), School.status == 'ACTIVE',
    ).order_by(School.school_code))).mappings().first()
    vehicle = (await session.execute(select(Vehicle.__table__).where(
        Vehicle.tenant_id == tenant, Vehicle.deleted_at.is_(None), Vehicle.status == 'ACTIVE',
    ).order_by(Vehicle.vehicle_code))).mappings().first()
    if school is None or vehicle is None:
        raise ValueError('Minimal satu school pada dapur asal dan vehicle ACTIVE diperlukan untuk manifest')
    driver_id = vehicle['driver_id'] or await session.scalar(select(Driver.driver_id).where(
        Driver.tenant_id == tenant, Driver.deleted_at.is_(None), Driver.status == 'ACTIVE',
    ).order_by(Driver.driver_code).limit(1))
    if driver_id is None:
        raise ValueError('Driver ACTIVE diperlukan untuk manifest')

    delivery_id = did(tenant, f'delivery:{food_code}')
    delivery = await existing(session, Delivery, 'delivery_id', delivery_id)
    if delivery is None:
        await insert_once(session, Delivery, 'delivery_id', delivery_id, {
            'vehicle': vehicle['vehicle_id'], 'driver': driver_id, 'kitchen_id': kitchen['kitchen_id'],
            'estimated_arrival_time': now + timedelta(minutes=30),
            'estimated_distance_km': Decimal('4.500'), 'estimated_duration_minutes': 20,
            'departure_time': now, 'arrival_time': None, 'status': 'IN_TRANSIT',
            **audit(tenant, actor), 'version': 2,
        })
        await insert_once(session, DeliveryItem, 'delivery_item_id', did(tenant, f'delivery-item:{food_code}'), {
            'delivery_id': delivery_id, 'package_id': package_id, 'school_id': school['school_id'],
            **audit(tenant, actor),
        })
        await session.execute(update(Package.__table__).where(
            Package.tenant_id == tenant, Package.package_id == package_id,
        ).values(status='IN_TRANSIT', version=package['version'] + 1, updated_at=now, updated_by=actor))
    elif delivery['status'] not in {'IN_TRANSIT', 'COMPLETED'}:
        raise ValueError(f'Delivery seed sudah ada dengan status {delivery["status"]}; tidak diubah otomatis')

    delivery_asset = await sync_source(session, scope, 'DELIVERY', delivery_id)
    vehicle_asset = await sync_source(session, scope, 'VEHICLE', vehicle['vehicle_id'])
    await insert_once(session, AssetRelationship, 'relationship_uuid', did(tenant, f'rel:loaded:{package_id}'), {
        'parent_uuid': package_asset['asset_uuid'], 'child_uuid': delivery_asset['asset_uuid'],
        'relationship_type': 'LOADED', **audit(tenant, actor),
    })
    await insert_once(session, AssetMovement, 'movement_id', did(tenant, f'movement:loading:{package_id}'), {
        'asset_type': 'PACKAGE', 'asset_uuid': package_asset['asset_uuid'], 'movement_type': 'VEHICLE_LOADING',
        'from_location': kitchen_asset['asset_uuid'], 'to_location': vehicle_asset['asset_uuid'],
        'operator': actor, 'movement_time': now, 'remarks': str(delivery_id), **audit(tenant, actor),
    })

    gps_points = [(-6.200000, 106.800000), (-6.205000, 106.810000), (-6.210000, 106.820000)]
    for index, (latitude, longitude) in enumerate(gps_points):
        await insert_once(session, GPSLog, 'gps_log_id', did(tenant, f'gps:{food_code}:{index}'), {
            'vehicle_uuid': vehicle['vehicle_id'], 'recorded_at': now - timedelta(minutes=10 - index * 4),
            'mqtt_message_id': None, 'latitude': Decimal(str(latitude)), 'longitude': Decimal(str(longitude)),
            'speed': Decimal('28.000'), 'heading': Decimal('90.000'), 'altitude': Decimal('20.000'),
            'hdop': Decimal('0.900'), 'satellite': 12, **audit(tenant, actor),
        })
    if vehicle['gps_device'] is not None:
        device = await existing(session, Device, 'device_id', vehicle['gps_device'])
        if device is not None:
            await insert_once(session, TemperatureLog, 'temperature_log_id', did(tenant, f'temp:gps:{food_code}'), {
                'device_uuid': device['device_uuid'], 'storage_uuid': None, 'package_uuid': None,
                'production_batch_uuid': None, 'recorded_at': now, 'mqtt_message_id': None,
                'temperature': Decimal('24.500'), 'unit': 'C', **audit(tenant, actor),
            })
    return {'production_batch_id': str(production_id), 'package_id': str(package_id),
            'delivery_id': str(delivery_id), 'delivery_status': 'IN_TRANSIT',
            'school': school['school_name'], 'vehicle': vehicle['vehicle_code'],
            'tracking_endpoint': f'/api/v1/deliveries/{delivery_id}/tracking'}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--tenant-id', required=True, type=UUID)
    parser.add_argument('--actor-id', required=True, type=UUID)
    parser.add_argument('--food-code', default='SEED-MENU-001')
    parser.add_argument('--menu-name', default='Menu Produksi Demo')
    parser.add_argument('--planned-quantity', default='100', type=Decimal)
    parser.add_argument('--kitchen-name', default=None, help='Nama dapur ACTIVE; jika kosong memakai dapur pertama')
    parser.add_argument('--supplier-name', default=None, help='Nama supplier ACTIVE; jika kosong memakai supplier pertama')
    parser.add_argument('--material-name', action='append', dest='material_names',
                        help='Nama bahan ACTIVE; dapat diulang. Jika kosong memakai maksimal dua bahan pertama.')
    parser.add_argument('--continue-distribution', action='store_true',
                        help='Lanjutkan seed ke produksi selesai, paket RELEASED, manifest IN_TRANSIT dan GPS demo')
    parser.add_argument('--allow-production', action='store_true')
    args = parser.parse_args()
    settings = get_settings()
    if settings.environment not in {'development', 'testing'} and not args.allow_production:
        raise ValueError('Seed hanya boleh pada development/testing; gunakan --allow-production jika sudah disetujui')
    try:
        async with async_sessionmaker(get_admin_engine())() as session, session.begin():
            result = await seed(session, args.tenant_id, args.actor_id, args.food_code,
                                args.menu_name, args.planned_quantity, args.kitchen_name,
                                args.supplier_name, args.material_names)
            if args.continue_distribution:
                result['distribution'] = await continue_distribution(
                    session, args.tenant_id, args.actor_id, args.food_code, args.planned_quantity)
        print(json.dumps(result, default=str, indent=2))
        return 0
    finally:
        await close_database()


if __name__ == '__main__':
    raise SystemExit(asyncio.run(main()))
