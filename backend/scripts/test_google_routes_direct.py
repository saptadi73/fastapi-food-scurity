"""Read-only Google Routes fleet diagnostic using the backend database directly."""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from pathlib import Path
from typing import Any
from uuid import UUID

import httpx
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config.settings import get_settings


def arguments():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery-id', type=UUID, required=True)
    parser.add_argument('--google-api-key', default=os.getenv('GOOGLE_MAP_API_KEY'))
    parser.add_argument('--timeout', type=float, default=20.0)
    args = parser.parse_args()
    if not args.google_api_key:
        parser.error('GOOGLE_MAP_API_KEY or --google-api-key is required')
    return args


def waypoint(latitude: Any, longitude: Any):
    if latitude is None or longitude is None:
        raise RuntimeError('Kitchen, school, or GPS coordinate is incomplete')
    return {'waypoint': {'location': {'latLng': {
        'latitude': float(latitude), 'longitude': float(longitude)}}}}


async def matrix(client, key, origin, destinations):
    response = await client.post(
        'https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix',
        headers={'X-Goog-Api-Key': key,
                 'X-Goog-FieldMask': 'destinationIndex,distanceMeters,duration,status,condition'},
        json={'origins': [waypoint(origin['latitude'], origin['longitude'])],
              'destinations': [waypoint(row['latitude'], row['longitude']) for row in destinations],
              'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_AWARE'},
    )
    response.raise_for_status()
    routes = []
    for row in response.json():
        if row.get('condition') == 'ROUTE_EXISTS' and not row.get('status'):
            routes.append({'destination_index': int(row['destinationIndex']),
                           'distance_km': float(row['distanceMeters']) / 1000,
                           'duration_minutes': float(str(row['duration']).removesuffix('s')) / 60})
    if not routes:
        raise RuntimeError('Google returned no usable route')
    return routes, max(routes, key=lambda row: row['duration_minutes'])


async def main(args):
    settings = get_settings()
    engine = create_async_engine(settings.database_url.get_secret_value())
    try:
        async with engine.connect() as connection:
            delivery = (await connection.execute(text("""
                select d.delivery_id,d.status,d.vehicle,d.kitchen_id,d.estimated_distance_km,
                       d.estimated_duration_minutes,d.departure_time,d.arrival_time,
                       k.latitude,k.longitude
                from delivery d join kitchen k on k.tenant_id=d.tenant_id and k.kitchen_id=d.kitchen_id
                where d.delivery_id=:id and d.deleted_at is null
            """), {'id': args.delivery_id})).mappings().one_or_none()
            if delivery is None:
                raise RuntimeError('Delivery not found')
            schools = (await connection.execute(text("""
                select distinct s.school_id,s.school_name,s.latitude,s.longitude
                from delivery_item i join school s on s.tenant_id=i.tenant_id and s.school_id=i.school_id
                where i.delivery_id=:id and i.deleted_at is null order by s.school_id
            """), {'id': args.delivery_id})).mappings().all()
            gps = (await connection.execute(text("""
                select gps_log_id,recorded_at,latitude,longitude,speed
                from gps_log where tenant_id=(select tenant_id from delivery where delivery_id=:id)
                  and vehicle_uuid=(select vehicle from delivery where delivery_id=:id)
                order by recorded_at desc limit 1
            """), {'id': args.delivery_id})).mappings().one_or_none()

        async with httpx.AsyncClient(timeout=args.timeout) as client:
            initial_routes, initial = await matrix(client, args.google_api_key, delivery, schools)
            print(f"DELIVERY {delivery['delivery_id']} status={delivery['status']} destinations={len(schools)}")
            print(f"STORED   {delivery['estimated_distance_km']} km / {delivery['estimated_duration_minutes']} min")
            print(f"GOOGLE   {initial['distance_km']:.3f} km / {initial['duration_minutes']:.1f} min "
                  f"to {schools[initial['destination_index']]['school_name']}")
            if delivery['estimated_distance_km'] is not None:
                delta = abs(float(delivery['estimated_distance_km']) - initial['distance_km'])
                percent = 100 * delta / max(initial['distance_km'], 0.001)
                print(f'INITIAL_DELTA {delta:.3f} km ({percent:.1f}%)')
            for route in initial_routes:
                print(f"DESTINATION {schools[route['destination_index']]['school_name']}: "
                      f"{route['distance_km']:.3f} km / {route['duration_minutes']:.1f} min")
            if gps is None:
                print('REMAINING skipped: no GPS log for delivery vehicle')
                return 1
            _, remaining = await matrix(client, args.google_api_key, gps, schools)
            print(f"GPS      {gps['latitude']},{gps['longitude']} at {gps['recorded_at']}")
            print(f"REMAINING_GOOGLE {remaining['distance_km']:.3f} km / "
                  f"{remaining['duration_minutes']:.1f} min")
            return 0
    finally:
        await engine.dispose()


if __name__ == '__main__':
    try:
        raise SystemExit(asyncio.run(main(arguments())))
    except (httpx.HTTPError, RuntimeError, ValueError, KeyError) as exc:
        print(f'ERROR {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(2) from None
