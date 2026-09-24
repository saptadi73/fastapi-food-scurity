# Uji Google Routes untuk fleet

Skrip `backend/scripts/test_google_routes_fleet.py` bersifat read-only dan menguji
delivery nyata terhadap Google Routes API. Skrip tidak membuat delivery, mengubah
status, atau mencetak API key/token.

Siapkan access token akun yang memiliki `Delivery.Read`, Google Routes API key
backend, dan UUID delivery yang memiliki koordinat dapur/sekolah serta GPS armada.

```powershell
$env:FSOS_API_BASE_URL='https://api.example.invalid/api/v1'
$env:FSOS_ACCESS_TOKEN='<access-token-sementara>'
$env:GOOGLE_MAP_API_KEY='<server-key>'
python backend/scripts/test_google_routes_fleet.py --delivery-id '<uuid-delivery>'
```

Opsi penting:

- `--distance-tolerance-percent 10`: toleransi jarak backend versus Google.
- `--duration-tolerance-minutes 5`: toleransi durasi untuk perubahan traffic.
- `--radius-meters 200`: radius pemeriksaan geofence.
- `--history-limit 500`: jumlah titik GPS yang diperiksa.

Exit code `0` berarti semua pemeriksaan lulus, `1` berarti ada mismatch, dan `2`
berarti konfigurasi/request gagal. Backend memilih tujuan dengan durasi terlama dari
matrix origin-ke-masing-tujuan. Ini bukan rute multi-stop teroptimasi; perbedaan
dengan garis Directions frontend dapat berasal dari perbedaan model tersebut.
