"""Diagnose fleet routing and geofence against Google Routes API.

This script is read-only. It does not create or transition deliveries.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
from math import asin, cos, radians, sin
from typing import Any

import httpx


def arguments() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--delivery-id', required=True)
    parser.add_argument('--api-base', default=os.getenv('FSOS_API_BASE_URL', 'http://localhost:8000/api/v1'))
    parser.add_argument('--access-token', default=os.getenv('FSOS_ACCESS_TOKEN'))
    parser.add_argument('--google-api-key', default=os.getenv('GOOGLE_MAP_API_KEY'))
    parser.add_argument('--radius-meters', type=int, default=200)
    parser.add_argument('--history-limit', type=int, default=500)
    parser.add_argument('--distance-tolerance-percent', type=float, default=10.0)
    parser.add_argument('--duration-tolerance-minutes', type=float, default=5.0)
    parser.add_argument('--timeout', type=float, default=20.0)
    args = parser.parse_args()
    if not args.access_token:
        parser.error('--access-token or FSOS_ACCESS_TOKEN is required')
    if not args.google_api_key:
        parser.error('--google-api-key or GOOGLE_MAP_API_KEY is required')
    if not 10 <= args.radius_meters <= 5000:
        parser.error('--radius-meters must be 10..5000')
    if not 1 <= args.history_limit <= 1000:
        parser.error('--history-limit must be 1..1000')
    return args


def data(response: httpx.Response) -> Any:
    response.raise_for_status()
    body = response.json()
    if not body.get('success'):
        raise RuntimeError(f"FSOS API failed: code={body.get('code')} message={body.get('message')}")
    return body['data']


def coordinate(row: dict[str, Any]) -> tuple[float, float]:
    latitude, longitude = row.get('latitude'), row.get('longitude')
    if latitude is None or longitude is None:
        raise RuntimeError('Kitchen, school, or GPS coordinate is incomplete')
    return float(latitude), float(longitude)


def haversine_meters(start: tuple[float, float], end: tuple[float, float]) -> float:
    lat1, lon1, lat2, lon2 = map(radians, (*start, *end))
    dlat, dlon = lat2 - lat1, lon2 - lon1
    value = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    return 2 * 6371008.8 * asin(min(1.0, value ** 0.5))


def waypoint(point: tuple[float, float]) -> dict[str, Any]:
    return {'waypoint': {'location': {'latLng': {'latitude': point[0], 'longitude': point[1]}}}}


async def google_matrix(client: httpx.AsyncClient, key: str, origin: tuple[float, float],
                        destinations: list[tuple[float, float]]) -> dict[str, float]:
    response = await client.post(
        'https://routes.googleapis.com/distanceMatrix/v2:computeRouteMatrix',
        headers={'X-Goog-Api-Key': key,
                 'X-Goog-FieldMask': 'destinationIndex,distanceMeters,duration,status,condition'},
        json={'origins': [waypoint(origin)], 'destinations': [waypoint(item) for item in destinations],
              'travelMode': 'DRIVE', 'routingPreference': 'TRAFFIC_AWARE'},
    )
    response.raise_for_status()
    routes = []
    for row in response.json():
        if row.get('condition') == 'ROUTE_EXISTS' and not row.get('status'):
            routes.append((float(row['distanceMeters']) / 1000,
                           float(str(row['duration']).removesuffix('s')) / 60,
                           int(row['destinationIndex'])))
    if not routes:
        raise RuntimeError('Google returned no usable route')
    distance, duration, index = max(routes, key=lambda route: route[1])
    return {'distance_km': distance, 'duration_minutes': duration, 'destination_index': index}


def compare(label: str, backend_distance: Any, backend_duration: Any, google: dict[str, float],
            distance_tolerance: float, duration_tolerance: float) -> bool:
    if backend_distance is None or backend_duration is None:
        print(f'FAIL {label}: backend distance/duration is null')
        return False
    backend_km, backend_min = float(backend_distance), float(backend_duration)
    distance_delta = abs(backend_km - google['distance_km'])
    distance_percent = 100 * distance_delta / max(google['distance_km'], 0.001)
    duration_delta = abs(backend_min - google['duration_minutes'])
    passed = distance_percent <= distance_tolerance and duration_delta <= duration_tolerance
    print(f"{'PASS' if passed else 'FAIL'} {label}: backend={backend_km:.3f} km/{backend_min:.1f} min; "
          f"google={google['distance_km']:.3f} km/{google['duration_minutes']:.1f} min; "
          f'delta={distance_percent:.1f}%/{duration_delta:.1f} min')
    return passed


async def main(args: argparse.Namespace) -> int:
    headers = {'Authorization': f'Bearer {args.access_token}'}
    async with httpx.AsyncClient(timeout=args.timeout, headers=headers) as fsos, \
            httpx.AsyncClient(timeout=args.timeout) as google:
        base = args.api_base.rstrip('/')
        detail = data(await fsos.get(f'{base}/deliveries/{args.delivery_id}'))
        tracking = data(await fsos.get(f'{base}/deliveries/{args.delivery_id}/tracking'))
        history = data(await fsos.get(f'{base}/deliveries/{args.delivery_id}/history', params={
            'radius_meters': args.radius_meters, 'limit': args.history_limit}))
        kitchen = data(await fsos.get(f"{base}/kitchens/{detail['kitchen_id']}"))
        school_ids = sorted({item['school_id'] for item in detail['items']})
        schools = [data(await fsos.get(f'{base}/schools/{school_id}')) for school_id in school_ids]
        destinations = [coordinate(school) for school in schools]

        checks = []
        initial_google = await google_matrix(google, args.google_api_key, coordinate(kitchen), destinations)
        checks.append(compare('initial route', detail['estimated_distance_km'],
            detail['estimated_duration_minutes'], initial_google,
            args.distance_tolerance_percent, args.duration_tolerance_minutes))

        latest = tracking.get('latest_gps')
        if latest:
            remaining_google = await google_matrix(google, args.google_api_key, coordinate(latest), destinations)
            checks.append(compare('remaining route', tracking['remaining_distance_km'],
                tracking['remaining_duration_minutes'], remaining_google,
                args.distance_tolerance_percent, args.duration_tolerance_minutes))
        else:
            print('FAIL remaining route: delivery has no GPS sample')
            checks.append(False)

        geofence_failures = 0
        school_coordinates = dict(zip(school_ids, destinations))
        for point in history['points']:
            distances = [(school_id, haversine_meters(coordinate(point), location))
                         for school_id, location in school_coordinates.items()]
            nearest = min(distances, key=lambda item: item[1]) if distances else None
            expected_inside = bool(nearest and nearest[1] <= args.radius_meters)
            if expected_inside != point['inside_geofence']:
                geofence_failures += 1
            if nearest and (point['nearest_school_id'] != nearest[0] or
                            abs(float(point['distance_to_nearest_meters']) - nearest[1]) > 0.2):
                geofence_failures += 1
        geofence_ok = geofence_failures == 0
        checks.append(geofence_ok)
        print(f"{'PASS' if geofence_ok else 'FAIL'} geofence: {len(history['points'])} points, "
              f"{len(history['geofence_events'])} transitions, {geofence_failures} mismatches")
        print(f"INFO Google destination selected by longest duration: {school_ids[initial_google['destination_index']]}")
        print('INFO Backend and this script use route-matrix origin-to-each-destination, not an optimized multi-stop route.')
        return 0 if all(checks) else 1


if __name__ == '__main__':
    try:
        raise SystemExit(asyncio.run(main(arguments())))
    except (httpx.HTTPError, RuntimeError, KeyError, ValueError) as exc:
        print(f'ERROR {type(exc).__name__}: {exc}', file=sys.stderr)
        raise SystemExit(2) from None
