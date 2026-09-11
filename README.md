# Food Safety Operating System — Backend

Fondasi FastAPI berdasarkan dokumen desain di [docs](docs). Python development
menggunakan **3.11** dan virtual environment `venv` di root proyek.
Pelacakan pekerjaan ada di [TODO.md](TODO.md).

## Menjalankan di Windows PowerShell

Dari `C:\projek\fastapi-Food-Security`:

```powershell
.\venv\Scripts\Activate.ps1
python -m uvicorn main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

Tanpa aktivasi, gunakan perintah berikut:

```powershell
.\venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload --host 127.0.0.1 --port 8000
```

- Swagger: http://127.0.0.1:8000/docs
- ReDoc: http://127.0.0.1:8000/redoc
- OpenAPI: http://127.0.0.1:8000/openapi.json
- Liveness: http://127.0.0.1:8000/api/v1/health

Health hanya membuktikan proses API aktif, bukan kesiapan database atau broker.
Health dan dokumentasi adalah endpoint publik untuk development/monitoring.
Endpoint login/refresh/logout dan /auth/me sudah tersedia. Endpoint holding/alarm rule serta daftar/detail/acknowledgment alarm telemetry tersedia; setiap operasi bisnis tetap wajib memeriksa permission dan tenant.
[Kontrak autentikasi frontend](backend/docs/frontend-api.md#kontrak-autentikasi-http)
memuat payload, respons, header, error dan contoh. Akun manusia perlu diprovisioning;
actor dev-maintenance tetap tanpa password. Gunakan [bootstrap manusia development](backend/docs/human-bootstrap.md)
untuk membuat akun baru dengan password pilihan sendiri.

## Instalasi ulang

Venv yang ada sudah dapat dipakai, tidak perlu dibuat ulang. Untuk checkout baru:

```powershell
python -m venv venv
.\venv\Scripts\python.exe -m pip install -r backend\requirements\dev.txt
Copy-Item backend\.env.example backend\.env
```

Jangan menimpa `.env` yang sudah berisi konfigurasi sendiri. File
`backend/requirements/lock-windows-py311.txt` mencatat versi paket hasil instalasi
dan pengujian Windows Python 3.11. Untuk mengulang versi tersebut:

```powershell
.\venv\Scripts\python.exe -m pip install -r backend\requirements\lock-windows-py311.txt
```

## Konfigurasi dan layanan pendukung

`backend/.env` dibaca berdasarkan lokasi file, sehingga tetap bekerja dari root
atau folder `backend`. `.env` dan `venv` diabaikan Git.

| Kebutuhan | Dependensi Python | Status awal |
| --- | --- | --- |
| REST, validasi, WebSocket | FastAPI, Uvicorn, Pydantic v2 | Fondasi API tersedia |
| PostgreSQL 18 | SQLAlchemy 2 async, asyncpg, Alembic | Schema hingga revisi 0017, termasuk telemetry, history aturan dan sesi autentikasi |
| PostGIS | GeoAlchemy2 | Extension aktif; lokasi kitchen berupa Point SRID 4326 |
| Redis | redis | Client tersedia; koneksi dan cache belum diimplementasikan |
| Mosquitto MQTT | aiomqtt | Client tersedia; worker dan broker belum diimplementasikan |
| JWT dan password | PyJWT crypto, bcrypt | Endpoint login/refresh/logout/me, sesi dan RBAC aktif; bootstrap akun manusia development melalui CLI tersedia |
| Integrasi REST | httpx | Client tersedia; integrasi ERP/Maps/AI belum diimplementasikan |

PostgreSQL, PostGIS, Redis, dan Mosquitto adalah layanan tersendiri; memasang
paket Python tidak memasang server tersebut. PostgreSQL 18 ditemukan sebagai
layanan Windows dan database lokal `fsos` sudah dikonfigurasi. Redis/Mosquitto
ditunda ke tahap integrasi/deployment. Contoh URL untuk instalasi baru:
`postgresql+asyncpg://fsos:PASSWORD@localhost:5432/fsos` (encode
karakter khusus password sebagai URL). Jangan menyimpan secret di source code.

## Migrasi database

Dari root proyek dengan venv aktif, konfigurasi `alembic.ini` di root mendukung:

```powershell
python -m alembic upgrade head
python -m alembic current
```

Konfigurasi `backend/alembic.ini` tetap dapat dipakai dari folder backend atau
melalui opsi `-c`. Keduanya menunjuk direktori migrasi dan `.env` yang sama.
Jangan menambahkan `backend` setelah `upgrade head`; path konfigurasi diberikan
melalui `-c backend/alembic.ini` sebelum `upgrade`.

Alembic menggunakan `ADMIN_DATABASE_URL`; aplikasi memakai `DATABASE_URL`.
Lihat [panduan koneksi](backend/docs/database-connections.md). Revisi pertama
`20260911_0001` membuat tenant dan kitchen; `20260911_0002` menambahkan storage,
storage zone, dan device; `20260911_0003` menambahkan vehicle, driver, dan school.
`20260911_0004` menambahkan supplier, raw material, food item, recipe, dan relasi
supplier–material. `20260911_0005` menambahkan packaging type, alarm rule, dan
holding rule. `20260911_0006` menambahkan user, role, permission dan relasi RBAC
di modul authentication. `20260911_0007` menambahkan header penerimaan, batch bahan,
dan item penerimaan. `20260911_0008` menambahkan batch produksi, pemakaian bahan,
dan paket. `20260911_0009` menambahkan delivery, item pengiriman, dan penerimaan
sekolah. `20260911_0010` menambahkan consumption, complaint, dan recall.
`20260911_0011` menambahkan registry digital asset, relationship, dan movement
dengan trigger perlindungan riwayat. `20260911_0012` melengkapi operational
event_log beserta index timeline dan perlindungan riwayat. `20260911_0013`
menambahkan empat sensor log berpartisi bulanan dan pesan MQTT. Partisi awal
September–November 2026; panduan menambah bulan ada di dokumentasi database.
Model terdaftar di
`backend/alembic/env.py`. Untuk menerapkan revisi yang sudah tersedia:

```powershell
.\venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
.\venv\Scripts\python.exe backend\scripts\check_database.py
```

Untuk perubahan model berikutnya:

```powershell
Set-Location backend
..\venv\Scripts\python.exe -m alembic revision --autogenerate -m "next schema change"
# Review revisi yang dihasilkan sebelum diterapkan.
..\venv\Scripts\python.exe -m alembic upgrade head
```

DDL harus melalui migrasi sesuai docs/03. Jangan memakai `create_all()` saat
startup. Panduan provisioning dan pengujian ada di
[backend/docs/database.md](backend/docs/database.md).

Schema telemetry docs/08 kini lengkap melalui migrasi `20260911_0014`, termasuk
health, alarm, holding, signal, battery, dan device session. Acknowledgment alarm
dan penutupan sesi memakai tabel bukti tambahan yang append-only. Detail satuan
dan cara membaca status efektif tersedia di [panduan database](backend/docs/database.md).
Ingestion MQTT dan API bisnis lainnya masih dalam TODO. Holding rule memiliki
[endpoint manajemen dan history](backend/docs/frontend-api.md#kontrak-holding-rule-http).
Alarm rule memiliki [enam endpoint konfigurasi termasuk aktivasi](backend/docs/frontend-api.md#kontrak-alarm-rule-http); engine dan executor masih TODO.

## Pemeriksaan

Dari root proyek:

```powershell
.\venv\Scripts\python.exe -m pip check
.\venv\Scripts\python.exe -m pytest -c backend\pyproject.toml backend\tests -q
.\venv\Scripts\python.exe -m ruff check backend
```

Pengujian awal mencakup health, Swagger/OpenAPI, envelope 404, validasi 400,
dan penanganan error 500 tanpa membocorkan detail ke respons. Tes integrasi migrasi
PostgreSQL/PostGIS juga sudah lulus pada database uji terpisah. Secara default
tes integrasi dilewati bila `FSOS_TEST_DATABASE_URL` belum diisi; lihat panduan database.
Redis dan MQTT belum diuji.

## Struktur dan keputusan awal

`backend/main.py` adalah entrypoint. Konfigurasi, respons, dan sesi database ada
di `backend/app/core/`. `common`, `shared`, `resources`, dan `modules` disediakan
untuk pengembangan berikutnya. Modul bisnis harus mengikuti struktur
`api/application/domain/infrastructure/schemas/tests` di docs/17.

Envelope mengikuti docs/16 yang lebih khusus untuk API: metadata memakai
`request_id`, `correlation_id`, `timestamp`, dan `execution_time_ms`. Validasi input
menghasilkan HTTP 400. Request ID dan JSON logging ke console sudah tersedia;
rotasi file, audit log, dan event bus masih TODO.

Development Windows memakai Uvicorn. Deployment Linux mengikuti docs/18:
Gunicorn, empat worker, Nginx, dan HTTPS. Dependensi Linux ada di
`backend/requirements/production.txt`. Contoh dari folder `backend`:

```bash
python -m pip install -r requirements/production.txt
gunicorn main:app -w 4 -k uvicorn_worker.UvicornWorker -b 127.0.0.1:8000
```

Konfigurasi production tersebut belum diuji atau dideploy. Gunakan paket
`uvicorn-worker` karena modul `uvicorn.workers` sudah deprecated menurut
[dokumentasi Uvicorn](https://www.uvicorn.org/deployment/).
Referensi instalasi: [FastAPI](https://fastapi.tiangolo.com/tutorial/),
[SQLAlchemy async](https://docs.sqlalchemy.org/en/20/orm/extensions/asyncio.html).
#   f a s t a p i - f o o d - s c u r i t y 
 
 

API kejadian alarm: [kontrak frontend](backend/docs/frontend-api.md#kontrak-alarm-telemetry-http). Empat permission telemetry sudah diprovision ke DEV_MAINTENANCE lokal. [API sesi perangkat](backend/docs/frontend-api.md#kontrak-sesi-perangkat-http) dan [runbook provisioning](backend/docs/telemetry-permissions.md) tersedia.

Master operasional kitchen/storage/zone: [15 operasi API dan kontrak frontend](backend/docs/frontend-api.md#kontrak-master-kitchen-storage-zone). Supplier/bahan/relasi juga tersedia; berikutnya transaksi receiving.

[Kontrak supplier dan bahan baku](backend/docs/frontend-api.md#kontrak-supplier-bahan-dan-relasi): 15 operasi termasuk soft delete untuk persiapan receiving.

CRUD keenam master kini mencakup [DELETE soft delete](backend/docs/frontend-api.md#soft-delete-master-operasional), dengan permission Delete, version dan proteksi referensi.

[Cakupan CRUD per modul](backend/docs/frontend-api.md#cakupan-crud-dan-status-modul): CRUD lengkap saat ini sembilan master termasuk sekolah, kendaraan dan driver. Menu/resep, jenis kemasan dan master device masih belum memiliki CRUD HTTP.

[CRUD master sekolah](backend/docs/frontend-api.md#kontrak-crud-sekolah) tersedia: list/detail/create/replace/soft delete. Transaksi penerimaan sekolah masih TODO.

[CRUD kendaraan dan driver](backend/docs/frontend-api.md#kontrak-kendaraan-dan-driver) tersedia; transaksi delivery dan GPS ingestion tetap TODO.
