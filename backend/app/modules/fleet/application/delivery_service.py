from datetime import UTC, datetime, timedelta
from decimal import Decimal, ROUND_HALF_UP
from math import asin, cos, radians, sin
from uuid import uuid4

import httpx
from sqlalchemy import insert, or_, select, update

from app.core.config.settings import get_settings
from app.core.database.scope import RecordNotFoundError, VersionConflictError
from app.core.events.orm import EventLog
from app.modules.authentication.infrastructure.authorization import require_permission
from app.modules.fleet.infrastructure.orm import Delivery, DeliveryItem
from app.modules.fleet.schemas.delivery import DeliveryDetail
from app.modules.master.infrastructure.orm import Device, Driver, Kitchen, School, Vehicle
from app.modules.packaging.application.service import PackageService, timer
from app.modules.production.infrastructure.orm import Package, ProductionBatch
from app.modules.telemetry.infrastructure.orm import GPSLog, TemperatureLog
from app.modules.traceability.infrastructure.orm import AssetMovement, AssetRelationship
from app.modules.traceability.infrastructure.registry import sync_source


class DeliveryConflictError(Exception):
    pass


class RoutingProviderError(Exception):
    pass


class DeliveryService(PackageService):
    @staticmethod
    def distance_meters(start, end):
        lat1, lon1, lat2, lon2 = map(radians, (float(start['latitude']), float(start['longitude']),
            float(end['latitude']), float(end['longitude'])))
        delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
        value = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
        return 2 * 6371008.8 * asin(min(1.0, value ** 0.5))

    @staticmethod
    def coordinates(origin, destinations):
        if origin['latitude'] is None or origin['longitude'] is None:
            return None
        if not destinations or any(item['latitude'] is None or item['longitude'] is None
                                   for item in destinations):
            return None
        return [(float(origin['latitude']), float(origin['longitude']))] + [
            (float(item['latitude']), float(item['longitude'])) for item in destinations]

    @staticmethod
    def route_result(routes, anchor):
        usable = [(distance, duration) for distance, duration in routes
                  if distance is not None and duration is not None and distance >= 0 and duration >= 0]
        if not usable:
            raise ValueError('Routing provider returned no usable route')
        distance_m, duration_s = max(usable, key=lambda route: route[1])
        minutes = max(1, int((duration_s / 60) + 0.999999))
        return {'estimated_distance_km': Decimal(str(distance_m / 1000)).quantize(
                    Decimal('0.001'), rounding=ROUND_HALF_UP),
                'estimated_duration_minutes': minutes,
                'estimated_arrival_time': anchor + timedelta(minutes=minutes)}

    async def google_routes(self, coordinates, anchor):
        settings = get_settings()
        api_key = settings.google_map_api_key.get_secret_value()
        if not api_key:
            raise ValueError('Google Maps API key is not configured')

        def waypoint(point):
            return {'waypoint': {'location': {'latLng': {
                'latitude': point[0], 'longitude': point[1]}}}}

        async with httpx.AsyncClient(timeout=settings.routing_timeout_seconds) as client:
            response = await client.post('https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix',
                headers={'X-Goog-Api-Key': api_key,
                         'X-Goog-FieldMask': 'destinationIndex,distanceMeters,duration,status,condition'},
                json={'origins': [waypoint(coordinates[0])],
                      'destinations': [waypoint(point) for point in coordinates[1:]],
                      'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_AWARE'})
            response.raise_for_status()
            rows = response.json()
        routes = []
        for row in rows:
            if row.get('condition') == 'ROUTE_EXISTS' and not row.get('status'):
                routes.append((float(row['distanceMeters']), float(str(row['duration']).removesuffix('s'))))
        return self.route_result(routes, anchor)

    async def estimate_route(self, origin, destinations, *, average_speed_kmph=None, anchor=None):
        anchor = anchor or datetime.now(UTC)
        coordinates = self.coordinates(origin, destinations)
        if coordinates is None:
            return {'estimated_distance_km': None, 'estimated_duration_minutes': None,
                    'estimated_arrival_time': None}
        try:
            return await self.google_routes(coordinates, anchor)
        except (httpx.HTTPError, KeyError, TypeError, ValueError):
            # Fallback estimate keeps tracking useful without a Google Maps key.
            earth_radius_km = 6371.0088
            distance_km = 0.0
            for start, end in zip(coordinates, coordinates[1:]):
                lat1, lon1, lat2, lon2 = map(radians, (*start, *end))
                delta_lat, delta_lon = lat2 - lat1, lon2 - lon1
                haversine = sin(delta_lat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(delta_lon / 2) ** 2
                distance_km += 2 * earth_radius_km * asin(min(1.0, haversine ** 0.5))
            speed = float(average_speed_kmph or 30)
            minutes = max(1, int((distance_km / speed) * 60 + 0.999999))
            return {'estimated_distance_km': Decimal(str(distance_km)).quantize(Decimal('0.001'), rounding=ROUND_HALF_UP),
                    'estimated_duration_minutes': minutes,
                    'estimated_arrival_time': anchor + timedelta(minutes=minutes)}

    async def parents(self, data, school_ids, active=True):
        # Driver before vehicle matches master vehicle update; then kitchen/schools.
        result = {}
        for model, key, identifier in ((Driver, 'driver_id', data['driver']),
                (Vehicle, 'vehicle_id', data['vehicle']), (Kitchen, 'kitchen_id', data['kitchen_id'])):
            try:
                row = await self.row(model, key, identifier, lock=True)
            except RecordNotFoundError:
                raise DeliveryConflictError('Delivery parents unavailable in this tenant') from None
            if active and row['status'] != 'ACTIVE':
                raise DeliveryConflictError('Active driver, vehicle, kitchen and schools required')
            result[key] = row
        schools = []
        for identifier in sorted(set(school_ids)):
            try:
                school = await self.row(School, 'school_id', identifier, lock=True)
            except RecordNotFoundError:
                raise DeliveryConflictError('Delivery parents unavailable in this tenant') from None
            if school['kitchen_id'] != data['kitchen_id']:
                raise DeliveryConflictError('Destination schools must belong to origin kitchen')
            if active and school['status'] != 'ACTIVE':
                raise DeliveryConflictError('Active driver, vehicle, kitchen and schools required')
            schools.append(school)
        assigned = result['vehicle_id']['driver_id']
        if active and assigned is not None and assigned != data['driver']:
            raise DeliveryConflictError('Selected driver differs from vehicle assigned driver')
        result['schools'] = schools
        return result

    async def manifest(self, identifier):
        return [dict(r) for r in (await self.db.execute(select(DeliveryItem.__table__).where(
            *self.visible(DeliveryItem), DeliveryItem.delivery_id == identifier)
            .order_by(DeliveryItem.package_id))).mappings()]

    async def detail(self, identifier):
        result = await self.row(Delivery, 'delivery_id', identifier)
        now = datetime.now(UTC)
        result['items'] = [dict(item, package=await self.projection(
            await self.row(Package, 'package_id', item['package_id']), now)) for item in await self.manifest(identifier)]
        return result

    async def get(self, identifier):
        await require_permission(self.db, self.scope, 'Delivery.Read')
        await self.row(Delivery, 'delivery_id', identifier, lock=True)
        return await self.detail(identifier)

    async def tracking(self, identifier):
        await require_permission(self.db, self.scope, 'Delivery.Read')
        delivery = await self.row(Delivery, 'delivery_id', identifier)
        manifest = await self.manifest(identifier)
        schools = [await self.row(School, 'school_id', item['school_id']) for item in manifest]
        gps = (await self.db.execute(select(GPSLog.__table__).where(
            *self.visible(GPSLog), GPSLog.vehicle_uuid == delivery['vehicle'])
            .order_by(GPSLog.recorded_at.desc()).limit(1))).mappings().one_or_none()
        vehicle = await self.row(Vehicle, 'vehicle_id', delivery['vehicle'])
        temperature = None
        if vehicle['gps_device'] is not None:
            device = await self.row(Device, 'device_id', vehicle['gps_device'])
            temperature = (await self.db.execute(select(TemperatureLog.__table__).where(
                *self.visible(TemperatureLog), TemperatureLog.device_uuid == device['device_uuid'])
                .order_by(TemperatureLog.recorded_at.desc()).limit(1))).mappings().one_or_none()
        now = datetime.now(UTC)
        remaining_distance = None
        remaining_minutes = None
        eta = delivery['estimated_arrival_time']
        if gps is not None:
            speed = float(gps['speed'] or 0)
            if speed <= 0 and delivery['estimated_distance_km'] and delivery['estimated_duration_minutes']:
                speed = float(delivery['estimated_distance_km']) / (delivery['estimated_duration_minutes'] / 60)
            estimate = await self.estimate_route(gps, schools,
                average_speed_kmph=speed if speed > 0 else Decimal('30'), anchor=now)
            remaining_distance = estimate['estimated_distance_km']
            remaining_minutes = estimate['estimated_duration_minutes']
            eta = estimate['estimated_arrival_time'] or eta
        return {'delivery_id': identifier, 'vehicle': delivery['vehicle'], 'status': delivery['status'],
                'destination_count': len({item['school_id'] for item in manifest}),
                'latest_gps': None if gps is None else {k: gps[k] for k in
                    ('gps_log_id', 'recorded_at', 'latitude', 'longitude', 'speed', 'heading')},
                'latest_temperature': None if temperature is None else {k: temperature[k] for k in
                    ('temperature_log_id', 'device_uuid', 'recorded_at', 'temperature', 'unit')},
                'remaining_distance_km': remaining_distance, 'remaining_duration_minutes': remaining_minutes,
                'estimated_arrival_time': eta, 'calculated_at': now}

    async def history(self, identifier, *, radius_meters=200, limit=500):
        await require_permission(self.db, self.scope, 'Delivery.Read')
        delivery = await self.row(Delivery, 'delivery_id', identifier)
        manifest = await self.manifest(identifier)
        schools = [await self.row(School, 'school_id', school_id)
                   for school_id in sorted({item['school_id'] for item in manifest})]
        located = [school for school in schools if school['latitude'] is not None and school['longitude'] is not None]
        started = delivery['departure_time'] or delivery['created_at']
        ended = delivery['arrival_time'] or datetime.now(UTC)
        rows = (await self.db.execute(select(GPSLog.__table__).where(*self.visible(GPSLog),
            GPSLog.vehicle_uuid == delivery['vehicle'], GPSLog.recorded_at >= started,
            GPSLog.recorded_at <= ended).order_by(GPSLog.recorded_at.desc(), GPSLog.gps_log_id.desc())
            .limit(limit + 1))).mappings().all()
        truncated, rows = len(rows) > limit, list(reversed(rows[:limit]))
        states = {school['school_id']: False for school in located}
        points, events = [], []
        for row in rows:
            distances = [(school, self.distance_meters(row, school)) for school in located]
            nearest = min(distances, key=lambda item: item[1]) if distances else None
            for school, distance in distances:
                inside = distance <= radius_meters
                if inside != states[school['school_id']]:
                    events.append({'event_type': 'ENTER' if inside else 'EXIT', 'school_id': school['school_id'],
                        'gps_log_id': row['gps_log_id'], 'recorded_at': row['recorded_at'],
                        'distance_meters': Decimal(str(distance)).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP)})
                    states[school['school_id']] = inside
            points.append({k: row[k] for k in ('gps_log_id', 'recorded_at', 'latitude', 'longitude', 'speed', 'heading')} | {
                'nearest_school_id': None if nearest is None else nearest[0]['school_id'],
                'distance_to_nearest_meters': None if nearest is None else Decimal(str(nearest[1])).quantize(Decimal('0.1'), rounding=ROUND_HALF_UP),
                'inside_geofence': False if nearest is None else nearest[1] <= radius_meters})
        return {'delivery_id': identifier, 'vehicle': delivery['vehicle'], 'status': delivery['status'],
                'window_started_at': started, 'window_ended_at': ended, 'geofence_radius_meters': radius_meters,
                'points': points, 'geofence_events': events, 'truncated': truncated}

    async def route_estimate(self, payload):
        await require_permission(self.db, self.scope, 'Delivery.Read')
        calculated_at = datetime.now(UTC)
        origin = (float(payload.origin_latitude), float(payload.origin_longitude))
        destination = (float(payload.destination_latitude), float(payload.destination_longitude))
        try:
            result = await self.google_routes([origin, destination], calculated_at)
        except (httpx.HTTPError, KeyError, TypeError, ValueError) as exc:
            raise RoutingProviderError('Google Routes API unavailable or returned no usable route') from exc
        return {'provider': 'GOOGLE_ROUTES',
                'origin_latitude': payload.origin_latitude,
                'origin_longitude': payload.origin_longitude,
                'destination_latitude': payload.destination_latitude,
                'destination_longitude': payload.destination_longitude,
                'distance_km': result['estimated_distance_km'],
                'duration_minutes': result['estimated_duration_minutes'],
                'estimated_arrival_time': result['estimated_arrival_time'],
                'calculated_at': calculated_at}

    async def list(self, *, offset=0, limit=20, kitchen_id=None, vehicle=None, driver=None, status=None):
        await require_permission(self.db, self.scope, 'Delivery.Read')
        query = select(Delivery.__table__).where(*self.visible(Delivery))
        for key, value in (('kitchen_id', kitchen_id), ('vehicle', vehicle), ('driver', driver), ('status', status)):
            if value is not None:
                query = query.where(getattr(Delivery, key) == value)
        rows = (await self.db.execute(query.order_by(Delivery.created_at.desc(), Delivery.delivery_id.desc())
            .offset(offset).limit(limit + 1))).mappings().all()
        return {'items': [dict(r) for r in rows[:limit]], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(rows) > limit else None}

    async def package_summary(self, *, group_by, offset=0, limit=20, vehicle=None, school_id=None, status=None):
        await require_permission(self.db, self.scope, 'Delivery.Read')
        rows = (await self.db.execute(select(Delivery.__table__, DeliveryItem.__table__, Package.__table__,
                ProductionBatch.recipe_snapshot).join(DeliveryItem,
                    (DeliveryItem.tenant_id == Delivery.tenant_id) & (DeliveryItem.delivery_id == Delivery.delivery_id))
                .join(Package, (Package.tenant_id == DeliveryItem.tenant_id) & (Package.package_id == DeliveryItem.package_id))
                .join(ProductionBatch, (ProductionBatch.tenant_id == Package.tenant_id)
                      & (ProductionBatch.production_batch_id == Package.production_batch_id))
                .where(*self.visible(Delivery), *self.visible(DeliveryItem), *self.visible(Package))
                .order_by(Delivery.created_at.desc(), Delivery.delivery_id.desc()))).mappings().all()
        groups = {}
        for row in rows:
            if vehicle is not None and row['vehicle'] != vehicle:
                continue
            if school_id is not None and row['school_id'] != school_id:
                continue
            if status is not None and row['status'] != status:
                continue
            key = row['vehicle'] if group_by == 'vehicle' else row['school_id']
            group = groups.setdefault(key, {
                group_by if group_by == 'vehicle' else 'school_id': key,
                'delivery_ids': set(), 'package_count': 0, 'total_quantity': Decimal(0), 'uoms': set(),
                'tenant_id': row['tenant_id'], 'created_at': row['created_at'], 'updated_at': row['updated_at'],
                'deleted_at': row['deleted_at'], 'created_by': row['created_by'], 'updated_by': row['updated_by'],
                'deleted_by': row['deleted_by'], 'version': 1,
            })
            group['delivery_ids'].add(row['delivery_id'])
            group['package_count'] += 1
            if row['quantity'] is not None:
                group['total_quantity'] += row['quantity']
            uom = (row['recipe_snapshot'] or {}).get('uom')
            if uom is not None:
                group['uoms'].add(uom)
        items = []
        for group in groups.values():
            uoms = group.pop('uoms')
            deliveries = group.pop('delivery_ids')
            group['delivery_count'] = len(deliveries)
            group['uom'] = next(iter(uoms)) if len(uoms) == 1 else None
            items.append(group)
        items.sort(key=lambda item: (item['package_count'], item['delivery_count']), reverse=True)
        return {'items': items[offset:offset + limit], 'offset': offset, 'limit': limit,
                'next_offset': offset + limit if len(items) > offset + limit else None}

    async def available_resources(self, data, excluding=None):
        query = select(Delivery.delivery_id).where(*self.visible(Delivery),
            Delivery.status.in_(['CREATED', 'IN_TRANSIT']),
            or_(Delivery.vehicle == data['vehicle'], Delivery.driver == data['driver']))
        if excluding is not None:
            query = query.where(Delivery.delivery_id != excluding)
        if await self.db.scalar(query.limit(1)) is not None:
            raise DeliveryConflictError('Vehicle or driver already reserved by an active delivery')

    async def usable(self, package, kitchen_id, now, expected_status, eta=None):
        production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
        if production['kitchen'] != kitchen_id or production['status'] != 'COMPLETED' or package['quantity'] is None:
            raise DeliveryConflictError('Package must originate from completed production in origin kitchen')
        state = timer(production, package, now)
        if package['status'] != expected_status or state['timer_status'] not in ('SAFE', 'WARNING') or package['holding_finished_at'] is None:
            raise DeliveryConflictError('Package must be released and unexpired for dispatch')
        if eta is not None and (package['expired_at'] is None or eta >= package['expired_at']):
            raise DeliveryConflictError('Estimated arrival must precede every package holding deadline')
        return production

    async def package_status(self, package, status, now):
        await self.db.execute(update(Package).where(*self.visible(Package), Package.package_id == package['package_id'])
            .values(status=status, version=package['version'] + 1, updated_at=now, updated_by=self.scope.actor_id))
        return await sync_source(self.db, self.scope, 'PACKAGE', package['package_id'])

    async def create(self, payload):
        await require_permission(self.db, self.scope, 'Delivery.Write')
        data = payload.model_dump(exclude={'items'})
        average_speed = data.pop('average_speed_kmph')
        parents = await self.parents(data, [i.school_id for i in payload.items])
        await self.available_resources(data)
        now, checked = datetime.now(UTC), []
        estimates = await self.estimate_route(parents['kitchen_id'], parents['schools'],
                                              average_speed_kmph=average_speed, anchor=now)
        for item in sorted(payload.items, key=lambda i: i.package_id):
            try:
                package = await self.row(Package, 'package_id', item.package_id, lock=True)
            except RecordNotFoundError:
                raise DeliveryConflictError('Package unavailable in this tenant') from None
            if package['version'] != item.expected_version:
                raise VersionConflictError()
            await self.usable(package, payload.kitchen_id, now, 'RELEASED')
            used = await self.db.scalar(select(DeliveryItem.delivery_id).join(Delivery,
                (Delivery.tenant_id == DeliveryItem.tenant_id) & (Delivery.delivery_id == DeliveryItem.delivery_id)).where(
                *self.visible(DeliveryItem), *self.visible(Delivery), DeliveryItem.package_id == item.package_id,
                Delivery.status != 'CANCELLED').limit(1))
            if used is not None:
                raise DeliveryConflictError('Package already assigned to a noncancelled delivery')
            checked.append((item, package))
        identifier = uuid4()
        await self.db.execute(insert(Delivery).values(delivery_id=identifier, **data, **estimates,
            status='CREATED', **self.audit))
        for item, package in checked:
            await self.db.execute(insert(DeliveryItem).values(delivery_item_id=uuid4(), delivery_id=identifier,
                package_id=item.package_id, school_id=item.school_id, **self.audit))
            await self.package_status(package, 'ALLOCATED', now)
        await sync_source(self.db, self.scope, 'DELIVERY', identifier)
        result = await self.detail(identifier)
        await self.event('delivery.created', result)
        return result

    async def transition(self, identifier, payload, action):
        await require_permission(self.db, self.scope, {'depart': 'Delivery.Depart', 'complete': 'Delivery.Complete', 'cancel': 'Delivery.Cancel'}[action])
        initial = await self.row(Delivery, 'delivery_id', identifier)
        if initial['kitchen_id'] is None:
            raise DeliveryConflictError('Legacy delivery has no executable origin kitchen')
        items = await self.manifest(identifier)
        if not items:
            raise DeliveryConflictError('Delivery manifest cannot be empty')
        parents = await self.parents(initial, [i['school_id'] for i in items], active=action == 'depart')
        current = await self.row(Delivery, 'delivery_id', identifier, lock=True)
        if current['version'] != payload.expected_version:
            raise VersionConflictError()
        required = 'IN_TRANSIT' if action == 'complete' else 'CREATED'
        if current['status'] != required:
            raise DeliveryConflictError(f'Delivery must be {required}')
        if action == 'depart':
            await self.available_resources(current, excluding=identifier)
        now = datetime.now(UTC)
        eta = payload.estimated_arrival_time if action == 'depart' else None
        if action == 'depart' and eta is None:
            eta = (await self.estimate_route(parents['kitchen_id'], parents['schools'],
                                             anchor=now))['estimated_arrival_time']
        if action == 'depart' and eta is None:
            raise DeliveryConflictError('Estimated arrival required when route coordinates are incomplete')
        if action == 'depart' and eta <= now:
            raise DeliveryConflictError('Estimated arrival must be in the future at departure')
        packages = []
        for item in items:
            package = await self.row(Package, 'package_id', item['package_id'], lock=True)
            if action == 'depart':
                await self.usable(package, current['kitchen_id'], now, 'ALLOCATED', eta)
            elif package['status'] != ('IN_TRANSIT' if action == 'complete' else 'ALLOCATED'):
                raise DeliveryConflictError('Package state differs from delivery state')
            packages.append((item, package))
        changes = {'status': {'depart': 'IN_TRANSIT', 'complete': 'COMPLETED', 'cancel': 'CANCELLED'}[action],
                   'version': current['version'] + 1, 'updated_at': now, 'updated_by': self.scope.actor_id}
        if action == 'depart':
            changes.update(departure_time=now, estimated_arrival_time=eta)
        if action == 'complete':
            changes.update(arrival_time=now)
        await self.db.execute(update(Delivery).where(*self.visible(Delivery), Delivery.delivery_id == identifier).values(**changes))
        delivery_asset = await sync_source(self.db, self.scope, 'DELIVERY', identifier)
        vehicle = await sync_source(self.db, self.scope, 'VEHICLE', current['vehicle']) if action != 'cancel' else None
        origin = await sync_source(self.db, self.scope, 'KITCHEN', current['kitchen_id']) if action == 'depart' else None
        schools = {}
        if action == 'complete':
            for school_id in sorted({i['school_id'] for i in items}):
                schools[school_id] = await sync_source(self.db, self.scope, 'SCHOOL', school_id)
        for item, package in packages:
            if action == 'cancel':
                production = await self.row(ProductionBatch, 'production_batch_id', package['production_batch_id'])
                state = timer(production, package, now)
                status = 'RELEASED' if state['timer_status'] in ('SAFE', 'WARNING') else 'EXPIRED'
            else:
                status = 'IN_TRANSIT' if action == 'depart' else 'DELIVERED'
            asset = await self.package_status(package, status, now)
            if action == 'cancel':
                continue
            await self.db.execute(insert(AssetRelationship).values(relationship_uuid=uuid4(),
                parent_uuid=asset['asset_uuid'], child_uuid=delivery_asset['asset_uuid'] if action == 'depart' else schools[item['school_id']]['asset_uuid'],
                relationship_type='LOADED' if action == 'depart' else 'DELIVERED', **self.audit))
            await self.db.execute(insert(AssetMovement).values(movement_id=uuid4(), asset_type='PACKAGE',
                asset_uuid=asset['asset_uuid'], movement_type='VEHICLE_LOADING' if action == 'depart' else 'DELIVERY',
                from_location=origin['asset_uuid'] if action == 'depart' else vehicle['asset_uuid'],
                to_location=vehicle['asset_uuid'] if action == 'depart' else schools[item['school_id']]['asset_uuid'],
                operator=self.scope.actor_id, movement_time=now, remarks=str(item['delivery_item_id']), **self.audit))
        result = await self.detail(identifier)
        await self.event({'depart': 'delivery.departed', 'complete': 'delivery.completed', 'cancel': 'delivery.cancelled'}[action], result)
        return result

    async def event(self, name, detail):
        await self.db.execute(insert(EventLog).values(event_uuid=uuid4(), event_type=name, entity_type='DELIVERY',
            entity_uuid=detail['delivery_id'], payload={'schema_version': 1, 'actor_id': str(self.scope.actor_id),
                'delivery': DeliveryDetail.model_validate(detail).model_dump(mode='json')}, **self.audit))
