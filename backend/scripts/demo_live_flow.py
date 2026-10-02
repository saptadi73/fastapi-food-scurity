"""Live exhibition demo: real HTTP end-to-end flow through the running API.

Drives receiving (with QR batch) -> production -> packaging/holding -> delivery
-> school receiving -> consumption, using the actual REST endpoints so every
business rule (QR persistence, "package not delivered yet", holding time
expiry) is exercised exactly as a real operator would trigger it.

Use --stop-after-depart to prepare persistent demo data and stop while the
delivery is IN_TRANSIT. The frontend can then demonstrate active delivery and
live tracking before an operator completes the remaining flow.

This script does NOT delete anything; it is safe to run repeatedly against the
same demo tenant (run_in_terminal a fresh --run-tag each time to avoid unique
code collisions). To reset the tenant between rehearsals, use
`demo_cleanup.py` before rerunning.

Prerequisites:
  1. Backend running (uvicorn) and reachable at --base-url.
  2. `seed_exhibition_masters.py` already applied once (kitchen, suppliers,
     materials, schools, vehicle/driver, packaging types, menu + recipe).

Usage:
    python backend/scripts/demo_live_flow.py --base-url http://localhost:8000/api/v1 \
        --tenant FSOS_EXPO --username expo-admin --password ExpoDemo123!
"""
import argparse
import asyncio
import json
import sys
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import httpx

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))


def banner(title: str) -> None:
    print(f'\n{"=" * 8} {title} {"=" * 8}')


def show(label: str, payload) -> None:
    print(f'  {label}: {json.dumps(payload, default=str)}')


class ApiError(Exception):
    pass


class Api:
    def __init__(self, base_url: str, timeout: float):
        self.client = httpx.AsyncClient(base_url=base_url, timeout=timeout)
        self.token: str | None = None

    async def close(self):
        await self.client.aclose()

    def _headers(self):
        return {'Authorization': f'Bearer {self.token}'} if self.token else {}

    async def call(self, method: str, path: str, *, json_body=None, params=None, expect=None):
        response = await self.client.request(method, path, json=json_body, params=params, headers=self._headers())
        try:
            body = response.json()
        except ValueError:
            body = {'message': response.text}
        if expect is not None and response.status_code != expect:
            raise ApiError(f'{method} {path} -> {response.status_code} {body.get("message")} '
                            f'{body.get("errors")}')
        return response.status_code, body.get('data'), body.get('message')

    async def get(self, path: str, **params):
        _, data, _ = await self.call('GET', path, params=params, expect=200)
        return data

    async def post(self, path: str, json_body: dict, expect: int = 201):
        _, data, _ = await self.call('POST', path, json_body=json_body, expect=expect)
        return data

    async def try_post(self, path: str, json_body: dict):
        """Attempt a POST that is expected to fail; returns (status, message) without raising."""
        status, _, message = await self.call('POST', path, json_body=json_body)
        return status, message


async def find_by_code(api: Api, path: str, code_field: str, code_value: str):
    data = await api.get(path, limit=100)
    for item in data['items']:
        if item[code_field] == code_value:
            return item
    raise ApiError(f'{code_value} not found under {path}; run seed_exhibition_masters.py first')


async def login(api: Api, tenant: str, username: str, password: str):
    data = await api.post('/auth/login', {'tenant': tenant, 'username': username, 'password': password}, expect=200)
    api.token = data['access_token']
    print(f'Login OK sebagai {username} pada tenant {tenant}')


async def run(args):
    api = Api(args.base_url, args.timeout)
    tag = args.run_tag or uuid4().hex[:8]
    try:
        banner('LOGIN')
        await login(api, args.tenant, args.username, args.password)

        banner('MUAT MASTER TERDAFTAR (kitchen, supplier, bahan, sekolah, armada, menu)')
        kitchen = await find_by_code(api, '/kitchens', 'kitchen_code', args.kitchen_code)
        storages = (await api.get('/storages', kitchen_id=kitchen['kitchen_id'], limit=100))['items']
        storage_by_type = {s['storage_type']: s for s in storages}
        supplier_rice = await find_by_code(api, '/suppliers', 'supplier_code', args.supplier_codes[0])
        supplier_chicken = await find_by_code(api, '/suppliers', 'supplier_code', args.supplier_codes[1])
        material_rice = await find_by_code(api, '/raw-materials', 'material_code', args.material_codes[0])
        material_chicken = await find_by_code(api, '/raw-materials', 'material_code', args.material_codes[1])
        menu = await find_by_code(api, '/food-items', 'food_code', args.menu_code)
        vehicle = await find_by_code(api, '/vehicles', 'vehicle_code', args.vehicle_code)
        school = await find_by_code(api, '/schools', 'school_code', args.school_code)
        show('kitchen', kitchen['kitchen_id'])
        show('vehicle/driver', {'vehicle': vehicle['vehicle_id'], 'driver': vehicle['driver_id']})
        show('school', school['school_id'])

        banner('TAHAP 1: Penerimaan bahan baku (QR batch dari dua sumber pemasok)')
        received_at = datetime.now(UTC) - timedelta(minutes=1)
        receiving = await api.post('/receivings', {
            'kitchen_id': kitchen['kitchen_id'], 'supplier_id': supplier_rice['supplier_id'],
            'received_at': received_at.isoformat(), 'items': [
                {'raw_material_id': material_rice['raw_material_id'], 'batch_code': f'EXPO-{tag}-BERAS',
                 'quantity': '100.000000', 'temperature': '27.00', 'condition': 'GOOD',
                 'expired_date': str(date.today() + timedelta(days=60))},
            ]})
        show('receiving (beras)', {'id': receiving['receiving_id'], 'status': receiving['status']})
        receiving_chicken = await api.post('/receivings', {
            'kitchen_id': kitchen['kitchen_id'], 'supplier_id': supplier_chicken['supplier_id'],
            'received_at': received_at.isoformat(), 'items': [
                {'raw_material_id': material_chicken['raw_material_id'], 'batch_code': f'EXPO-{tag}-AYAM',
                 'quantity': '50.000000', 'temperature': '3.50', 'condition': 'GOOD',
                 'expired_date': str(date.today() + timedelta(days=3))},
            ]})
        show('receiving (ayam)', {'id': receiving_chicken['receiving_id'], 'status': receiving_chicken['status']})

        batches = {}
        for label, receiving_data in [('rice', receiving), ('chicken', receiving_chicken)]:
            item = receiving_data['items'][0]
            completed = await api.post(f'/receivings/{receiving_data["receiving_id"]}/complete', {
                'expected_version': receiving_data['version'],
                'items': [{'receiving_item_id': item['receiving_item_id'], 'accepted': True}],
            }, expect=200)
            batch = completed['items'][0]['batch']
            print(f'  QR batch {label}: {batch["qr_code"]}  (scan simulasi di stasiun penerimaan)')
            resolved = await api.get('/raw-material-batches/resolve', qr_code=batch['qr_code'])
            assert resolved['raw_material_batch_id'] == batch['raw_material_batch_id']
            batches[label] = {'batch_id': batch['raw_material_batch_id'], 'version': batch['version'],
                               'raw_material_id': batch['raw_material_id']}

        banner('TAHAP 1b: Putaway ke storage sesuai tipe bahan')
        storage_map = {'rice': storage_by_type['DRY_STORAGE'], 'chicken': storage_by_type['COLD_STORAGE']}
        quantities = {'rice': '100.000000', 'chicken': '50.000000'}
        for label, batch in batches.items():
            entry = await api.post(f'/raw-material-batches/{batch["batch_id"]}/putaway', {
                'expected_version': batch['version'], 'storage_id': storage_map[label]['storage_id'],
                'quantity': quantities[label],
            })
            batch['version'] = entry['batch_version']
            batch['storage_id'] = storage_map[label]['storage_id']
        show('stok siap dipakai produksi', {k: v['batch_id'] for k, v in batches.items()})

        banner('TAHAP 2: Batch produksi (scan QR batch bahan sebagai sumber)')
        production = await api.post('/production-batches', {
            'batch_code': f'MO-EXPO-{tag}', 'kitchen': kitchen['kitchen_id'], 'menu': menu['food_item_id'],
            'planned_quantity': str(args.planned_quantity),
        })
        production_id = production['production_batch_id']
        show('production batch', {'id': production_id, 'status': production['status']})
        by_material = {line['raw_material_id']: batches[label]
                       for label in ('rice', 'chicken') for line in production['recipe_snapshot']['items']
                       if line['raw_material_id'] == batches[label]['raw_material_id']}
        start_items = []
        for line in production['recipe_snapshot']['items']:
            source = by_material.get(line['raw_material_id'])
            if source is None:
                raise ApiError(f'Menu {args.menu_code} butuh bahan yang belum diterima pada demo ini')
            start_items.append({'raw_material_batch_id': source['batch_id'], 'storage_id': source['storage_id'],
                                 'expected_version': source['version'], 'quantity': line['required_quantity']})
        production = await api.post(f'/production-batches/{production_id}/start', {
            'expected_version': production['version'], 'items': start_items,
        }, expect=200)
        show('produksi dimulai (stok terpakai)', {'status': production['status']})
        production = await api.post(f'/production-batches/{production_id}/complete', {
            'expected_version': production['version'], 'actual_quantity': str(args.planned_quantity),
            'initial_temperature': '75.00',
        }, expect=200)
        show('produksi selesai', {'status': production['status'], 'actual_quantity': production['actual_quantity']})

        banner('TAHAP 3: Pengemasan + mulai holding time')
        package_type_id = args.package_type_id
        if package_type_id is None:
            package_type = await find_by_code(api, '/packaging-types', 'code', args.package_type_code)
            package_type_id = package_type['package_type_id']
        package = await api.post('/packages', {
            'production_batch_id': production_id, 'package_type_id': package_type_id,
            'package_code': f'PKG-EXPO-{tag}-01', 'package_number': 1,
            'quantity': str(args.planned_quantity), 'initial_temperature': '68.00',
            'expected_version': production['version'],
        })
        package = await api.post(f'/packages/{package["package_id"]}/holding/start', {
            'expected_version': package['version'],
        }, expect=200)
        print(f'  QR kemasan: {package["qr_payload"]}  (scan di titik distribusi/sekolah)')
        show('holding aktif', {'status': package['status'], 'remaining_minutes': package['remaining_minutes'],
                                'timer_status': package['timer_status']})

        banner('TAHAP 4: Manifest pengiriman ke sekolah terdaftar')
        delivery = await api.post('/deliveries', {
            'kitchen_id': kitchen['kitchen_id'], 'vehicle': vehicle['vehicle_id'], 'driver': vehicle['driver_id'],
            'items': [{'package_id': package['package_id'], 'school_id': school['school_id'],
                       'expected_version': package['version']}],
        })
        show('delivery dibuat', {'id': delivery['delivery_id'], 'status': delivery['status']})
        package = await api.get(f'/packages/{package["package_id"]}')

        banner('CEK: penerimaan sekolah SEBELUM kendaraan berangkat (harus DITOLAK)')
        status, message = await api.try_post('/school-receivings', {
            'expected_version': package['version'], 'delivery_id': delivery['delivery_id'],
            'package': package['package_id'], 'school': school['school_id'],
            'received_quantity': package['quantity'], 'condition': 'GOOD', 'accepted': True,
        })
        print(f'  Hasil: HTTP {status} - {message}  (benar; paket belum berangkat/DELIVERED)')

        banner('TAHAP 5: Keberangkatan armada')
        delivery = await api.post(f'/deliveries/{delivery["delivery_id"]}/depart', {
            'expected_version': delivery['version'],
        }, expect=200)
        show('armada berangkat', {'status': delivery['status']})
        package = await api.get(f'/packages/{package["package_id"]}')

        banner('CEK: penerimaan sekolah SAAT MASIH DI PERJALANAN (harus DITOLAK)')
        status, message = await api.try_post('/school-receivings', {
            'expected_version': package['version'], 'delivery_id': delivery['delivery_id'],
            'package': package['package_id'], 'school': school['school_id'],
            'received_quantity': package['quantity'], 'condition': 'GOOD', 'accepted': True,
        })
        print(f'  Hasil: HTTP {status} - {message}  (benar; paket masih IN_TRANSIT, belum sampai)')

        if args.stop_after_depart:
            banner('RINGKASAN DATA DEMO SIAP LIVE TRACKING')
            show('summary', {
                'run_tag': tag,
                'production_batch': production['batch_code'],
                'package_id': package['package_id'],
                'package_code': f'PKG-EXPO-{tag}-01',
                'package_qr': package.get('qr_payload'),
                'delivery_id': delivery['delivery_id'],
                'delivery_status': delivery['status'],
                'school': school['school_name'],
            })
            print('\nPersiapan selesai pada status IN_TRANSIT. Lanjutkan arrival dan penerimaan dari frontend.')
            return

        banner('TAHAP 6: Armada tiba di sekolah')
        delivery = await api.post(f'/deliveries/{delivery["delivery_id"]}/complete', {
            'expected_version': delivery['version'],
        }, expect=200)
        package = await api.get(f'/packages/{package["package_id"]}')
        show('paket tiba', {'status': package['status'], 'remaining_minutes': package['remaining_minutes'],
                             'timer_status': package['timer_status']})

        banner('CEK HOLDING TIME saat serah-terima kemasan di sekolah')
        print(f'  Sisa waktu aman (remaining_minutes): {package["remaining_minutes"]}')
        print(f'  Status timer holding: {package["timer_status"]}  (SAFE/WARNING/EXPIRED)')

        banner('TAHAP 7: Penerimaan sekolah (scan QR kemasan)')
        receipt = await api.post('/school-receivings', {
            'expected_version': package['version'], 'delivery_id': delivery['delivery_id'],
            'package': package['package_id'], 'school': school['school_id'],
            'received_quantity': package['quantity'], 'condition': 'GOOD', 'accepted': True,
            'temperature': '58.00', 'notes': 'Diterima lengkap saat demo live',
        })
        show('penerimaan sekolah tercatat', {'id': receipt['school_receiving_id'], 'timer_status': receipt['timer_status']})
        package = await api.get(f'/packages/{package["package_id"]}')

        banner('TAHAP 8: Konsumsi (opsional, menutup siklus paket)')
        consumption = await api.post('/consumptions', {
            'expected_version': package['version'], 'package_id': package['package_id'],
            'consumed_quantity': package['quantity'], 'discarded_quantity': '0.000000',
            'notes': 'Dikonsumsi penuh saat demo live',
        })
        show('konsumsi tercatat', {'id': consumption['consumption_id'], 'safe': consumption['safe']})

        banner('RINGKASAN DEMO')
        summary = {
            'run_tag': tag, 'production_batch': production['batch_code'],
            'package_code': f'PKG-EXPO-{tag}-01', 'package_qr': package.get('qr_payload'),
            'school': school['school_name'], 'final_package_status': package['status'],
            'asset_uuid': package.get('asset_uuid'),
        }
        show('summary', summary)
        if package.get('asset_uuid'):
            passport = await api.get(f'/traceability/assets/{package["asset_uuid"]}/passport')
            show('traceability passport (ringkas)', {
                'asset': passport['asset']['name'], 'parents': len(passport.get('parents', [])),
                'children': len(passport.get('children', [])), 'movements': len(passport.get('movements', [])),
            })
        print('\nDemo selesai. Jalankan lagi dengan --run-tag berbeda, atau reset dengan demo_cleanup.py.')
    finally:
        await api.close()


def parse_args():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('--base-url', default='http://localhost:8000/api/v1')
    parser.add_argument('--tenant', default='FSOS_EXPO')
    parser.add_argument('--username', default='expo-admin')
    parser.add_argument('--password', default='ExpoDemo123!')
    parser.add_argument('--kitchen-code', default='DKP-EXPO')
    parser.add_argument('--supplier-codes', nargs=2, default=['SUP-EXPO-01', 'SUP-EXPO-02'],
                        metavar=('RICE_SUPPLIER', 'CHICKEN_SUPPLIER'))
    parser.add_argument('--material-codes', nargs=2, default=['RM-EXPO-BERAS', 'RM-EXPO-AYAM'],
                        metavar=('RICE_MATERIAL', 'CHICKEN_MATERIAL'))
    parser.add_argument('--menu-code', default='MENU-EXPO-UTAMA')
    parser.add_argument('--vehicle-code', default='VH-EXPO-01')
    parser.add_argument('--school-code', default='SCH-EXPO-01')
    parser.add_argument('--package-type-code', default='PKG-EXPO-LB')
    parser.add_argument('--package-type-id', default=None)
    parser.add_argument('--planned-quantity', default=Decimal('50'), type=Decimal)
    parser.add_argument('--run-tag', default=None, help='Suffix for codes; random if omitted so reruns do not collide')
    parser.add_argument('--stop-after-depart', action='store_true',
                        help='Stop with delivery IN_TRANSIT so live tracking and arrival continue from frontend')
    parser.add_argument('--timeout', default=20.0, type=float)
    return parser.parse_args()


if __name__ == '__main__':
    try:
        asyncio.run(run(parse_args()))
    except ApiError as exc:
        print(f'\nGAGAL: {exc}')
        sys.exit(1)
