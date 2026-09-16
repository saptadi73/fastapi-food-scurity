# Panduan integrasi frontend FSOS

Terakhir diperbarui: 2026-09-15. Versi aplikasi: 0.1.0.
Status: **165 operasi HTTP aktif**, termasuk CRUD empat belas master, autentikasi,
konfigurasi rule, bukti alarm/sesi perangkat, penerimaan bahan/stok, produksi,
pengemasan/holding, pengiriman, penerimaan sekolah, konsumsi dan complaint intake/report.
Recall start/execute/withdrawal/close, notification outbox, traceability passport/impact dan dashboard read aktif;
notifikasi dan pendukung lain masih bertahap.

Dokumen ini menjelaskan implementasi yang dapat dipanggil sekarang.
[Desain API](../../docs/16_API_design.md) adalah roadmap draft, bukan daftar
endpoint aktif. Tabel database yang sudah ada belum menyediakan API CRUD.

Untuk implementasi frontend development, seed demo end-to-end tersedia melalui
`backend/scripts/seed_demo_ready.py`. Script membuat tenant `FSOS_DEMO`, user
`frontend-admin`, workflow 14 tahap, sampel IoT, complaint report, recall dan
notification outbox. Detail login/kode demo ada di
[Seed development](development-seed.md#seed-demo-frontend-end-to-end).

Tautan: [Event catalog](event-catalog.md), [perubahan kontrak](frontend-changelog.md),
[database](database.md), [TODO](../../TODO.md).

## Koneksi dan dokumentasi interaktif

| Pengaturan | Nilai development default |
| --- | --- |
| Origin backend | `http://localhost:8000` |
| Prefix API | `/api/v1` (konfigurasi backend `API_PREFIX`) |
| Swagger | `GET /docs` â€” HTML interaktif |
| ReDoc | `GET /redoc` â€” HTML dokumentasi |
| OpenAPI | `GET /openapi.json` â€” dokumen JSON OpenAPI, tanpa envelope |
| Swagger OAuth redirect | `GET /docs/oauth2-redirect` â€” HTML internal Swagger; bukan login aplikasi |

Route dokumentasi berada di origin backend, di luar prefix API. Seluruh route
dokumentasi saat ini publik dan tanpa payload/path/query parameter aplikasi.
OpenAPI mencantumkan endpoint dan envelope. Data respons autentikasi memiliki
schema terstruktur; data endpoint sistem masih bertipe bebas di OpenAPI.

Origin frontend harus tercantum di `CORS_ORIGINS` backend; contoh konfigurasi
development adalah `["http://localhost:5173"]`. Default kode adalah daftar kosong.
Perbedaan host atau port berarti origin berbeda. CORS bukan autentikasi.

## Header dan autentikasi

| Header | Arah | Keterangan |
| --- | --- | --- |
| `Accept: application/json` | Request | Disarankan untuk API |
| `X-Correlation-ID` | Request opsional | Menghubungkan request satu aktivitas; dipotong maksimal 128 karakter |
| `X-Request-ID` | Response | UUID baru setiap request; tersedia untuk JavaScript melalui CORS |
| `Content-Type: application/json` | Response API | Format envelope |
| `Cache-Control: no-store` | Response `/ready`, `/health/database`, `/auth/*`, `/holding-rules*`, `/alarm-rules*`, `/alarms*`, `/device-sessions*`, `/devices*`, `/device-bindings*`, `/telemetry*`, `/dashboard*`, `/notifications*`, `/kitchens*`, `/storages*`, `/storage-zones*`, `/suppliers*`, `/raw-materials*`, `/supplier-materials*`, `/schools*`, `/vehicles*`, `/drivers*`, `/receivings*`, `/raw-material-batches*`, `/food-items*`, `/recipes*`, `/production-batches*`, `/packages*`, `/packaging-types*`, `/deliveries*`, `/complaints*`, `/recalls*`, `/traceability*`, `/school-receivings*`, `/consumptions*` | Respons tidak boleh disimpan cache |
| `Content-Type: application/json` | Request POST autentikasi | Body JSON wajib; bukan form OAuth |
| `Authorization: Bearer <access_token>` | Request `/auth/me` | Access JWT dengan sesi aktif |
| `Retry-After` | Response 429 autentikasi | Detik sebelum mencoba lagi; diekspos lewat CORS |
| `WWW-Authenticate: Bearer` | Response 401 autentikasi | Challenge bearer |

Kedua endpoint sistem tidak membutuhkan token, API key, tenant ID, atau permission
khusus. Login JWT, refresh, logout dan /auth/me sudah aktif. API key device
masih TODO. Permission bisnis tetap harus diperiksa per operasi dari database. Jangan memasukkan kredensial PostgreSQL/MQTT ke frontend.

## Envelope API

| Field | Tipe | Makna |
| --- | --- | --- |
| `success` | boolean | `true` jika code < 400 |
| `code` | integer | Status HTTP |
| `message` | string | Penjelasan singkat; percabangan frontend gunakan HTTP/code dan field status |
| `data` | object atau null | Data endpoint; null untuk error generik |
| `errors` | array object | Kosong bila tidak ada detail validasi |
| `meta.request_id` | string UUID | Sama dengan header `X-Request-ID` |
| `meta.correlation_id` | string | Header request yang dipotong, atau request_id bila header tidak dikirim |
| `meta.timestamp` | string ISO 8601 UTC | Waktu pembuatan respons; contoh `2026-09-11T09:00:00Z` |
| `meta.execution_time_ms` | number | Durasi hingga envelope dibentuk dalam milidetik; bukan latency jaringan |

Semua field envelope di atas selalu dikirim oleh handler API. Nilai UUID,
timestamp, dan durasi pada contoh hanya ilustrasi. Respons CORS preflight atau
error dari proxy/jaringan dapat berada di luar envelope aplikasi.

## Cakupan CRUD dan status modul

Status berikut diperiksa dari router yang terdaftar dan OpenAPI aplikasi: **165
operasi HTTP aktif**, termasuk 70 operasi CRUD untuk empat belas master. Angka ini adalah
kombinasi method/path, bukan jumlah modul. Schema database, fixture development,
service internal atau adapter registry tidak berarti endpoint sudah tersedia.

| Modul | Create | Read daftar/detail | Update | Delete | Kontrak/status |
| --- | --- | --- | --- | --- | --- |
| Kitchen | Ada | Ada | Ada | Soft delete | [Master lokasi](#kontrak-master-kitchen-storage-zone) |
| Storage | Ada | Ada | Ada | Soft delete | [Master lokasi](#kontrak-master-kitchen-storage-zone) |
| Storage zone | Ada | Ada | Ada | Soft delete | [Master lokasi](#kontrak-master-kitchen-storage-zone) |
| Supplier | Ada | Ada | Ada | Soft delete | [Pemasok/bahan](#kontrak-supplier-bahan-dan-relasi) |
| Bahan baku | Ada | Ada | Ada | Soft delete | [Pemasok/bahan](#kontrak-supplier-bahan-dan-relasi) |
| Relasi supplier-material | Ada | Ada | Ada | Soft delete/unlink | [Pemasok/bahan](#kontrak-supplier-bahan-dan-relasi) |
| Sekolah (school) | Ada | Ada | Ada | Soft delete | [Kontrak sekolah](#kontrak-crud-sekolah) |
| Kendaraan (vehicle) | Ada | Ada | Ada | Soft delete | [Kontrak kendaraan/driver](#kontrak-kendaraan-dan-driver) |
| Driver | Ada | Ada | Ada | Soft delete | [Kontrak kendaraan/driver](#kontrak-kendaraan-dan-driver) |
| Menu/food item | Ada | Ada | Ada | Soft delete | [Menu/resep](#kontrak-menu-dan-resep) |
| Resep (recipe) | Ada | Ada | Ada | Soft delete | [Menu/resep](#kontrak-menu-dan-resep) |
| Jenis kemasan (packaging type) | Ada | Ada | Ada | Soft delete | [Kemasan/paket/holding](#kontrak-kemasan-paket-dan-holding) |
| Master device | Ada | Ada | Ada | Soft delete | [Master device dan binding](#kontrak-master-device-dan-binding) |
| Binding device/vehicle | Ada | Ada | Ada | Soft delete | [Master device dan binding](#kontrak-master-device-dan-binding) |
| Tenant/user/role/permission | Belum | Belum | Belum | Belum | Schema dan CLI administratif tertentu tersedia; bukan API CRUD |
| Holding rule | Ada | Ada | Ada | Belum | [Konfigurasi + history](#kontrak-holding-rule-http); timer paket melalui kontrak holding |
| Alarm rule | Ada | Ada | Ada | Belum | [Konfigurasi + aktivasi/history](#kontrak-alarm-rule-http); executor belum tersedia |

Read pada matriks berarti endpoint master, bukan pembacaan database internal.
CRUD empat belas master menggunakan permission Read/Write/Delete terpisah. Delete adalah
soft delete dengan expected_version dan proteksi referensi; bukan cascade atau
hard delete. Lihat [kontrak DELETE](#soft-delete-master-operasional).

Modul lain yang memiliki HTTP hanya untuk operasi tertentu:

| Modul | Operasi HTTP tersedia | Batas |
| --- | --- | --- |
| Autentikasi | Login, refresh, logout, identitas /auth/me | Tidak menyediakan CRUD user/role/permission |
| Kejadian alarm | Daftar/detail dan acknowledgment | Tidak menyediakan create/update/delete bukti alarm |
| Sesi perangkat | Daftar/detail dan akhir sesi | Berbeda dari CRUD device; tidak menyediakan create/delete sesi atau reconnect |
| Sistem | Health dan readiness | Bukan indikator seluruh modul bisnis telah selesai |

Receiving/item/batch bahan tersedia melalui [kontrak receiving](#kontrak-receiving-dan-batch-bahan).
Putaway, ledger dan saldo tersedia melalui [kontrak stok](#stok-batch-bahan-dan-putaway).
Produksi kini tersedia melalui [kontrak produksi](#kontrak-transaksi-produksi).
Paket dan holding tersedia melalui [kontrak pengemasan](#kontrak-kemasan-paket-dan-holding).
Pengiriman tersedia melalui [kontrak manifest/perjalanan](#kontrak-pengiriman).
Penerimaan sekolah dan konsumsi tersedia melalui [kontrak sekolah/konsumsi](#kontrak-penerimaan-sekolah-dan-konsumsi).
Complaint intake/report tersedia melalui [kontrak complaint](#kontrak-complaint-intake).
Recall dasar tersedia melalui [kontrak recall](#kontrak-recall-dasar).
Notification outbox tersedia melalui [kontrak notification](#kontrak-notification-outbox).
Traceability read tersedia melalui [kontrak traceability](#kontrak-traceability-read).
Dashboard read tersedia melalui [kontrak dashboard](#kontrak-dashboard-read).
Subscription realtime belum tersedia. Penghapusan
kitchen tetap diblokir bila sekolah nondeleted masih merujuknya.

Frontend hanya boleh mengintegrasikan method/path pada daftar endpoint aktif di
bawah. Jangan menebak path, payload atau permission untuk modul berstatus Belum;
kontrak akan ditambahkan bersamaan dengan implementasinya.

## Daftar endpoint aktif

| Method | Path | Tujuan | Payload | Respons normal |
| --- | --- | --- | --- | --- |
| POST | `/api/v1/school-receivings` | Keputusan inspeksi manifest | ReceiptInput | 201 ReceiptData |
| GET | `/api/v1/school-receivings` | Daftar penerimaan | Tanpa body; filter/pagination | 200 ReceiptPage |
| GET | `/api/v1/school-receivings/{identifier}` | Bukti penerimaan | Tanpa body | 200 ReceiptData |
| POST | `/api/v1/consumptions` | Finalisasi konsumsi/pembuangan | ConsumptionInput | 201 ConsumptionData |
| GET | `/api/v1/consumptions` | Daftar konsumsi | Tanpa body; filter/pagination | 200 ConsumptionPage |
| GET | `/api/v1/consumptions/{identifier}` | Bukti konsumsi | Tanpa body | 200 ConsumptionData |
| GET | `/api/v1/health` | Liveness proses API | Tidak ada | 200 |
| GET | /api/v1/ready | Kesiapan database aplikasi | Tidak ada | 200 atau 503 |
| GET | /api/v1/health/database | Test koneksi database eksplisit | Tidak ada | 200 atau 503 |
| POST | `/api/v1/auth/login` | Autentikasi akun dalam tenant | tenant atau tenant_id, username, password | 200 |
| POST | `/api/v1/auth/refresh` | Rotasi token sesi | refresh_token | 200 |
| POST | `/api/v1/auth/logout` | Cabut satu sesi | refresh_token | 200 |
| GET | `/api/v1/auth/me` | Identitas dan RBAC aktif | Tidak ada; bearer header | 200 |
| GET | `/api/v1/holding-rules` | Daftar aturan holding | Tidak ada; offset/limit | 200 |
| POST | `/api/v1/holding-rules` | Buat aturan holding | Definisi empat field | 201 |
| GET | `/api/v1/holding-rules/{rule_id}` | Detail aturan | Tidak ada | 200 |
| PUT | `/api/v1/holding-rules/{rule_id}` | Ganti definisi aturan | Definisi + expected_version | 200 |
| GET | `/api/v1/holding-rules/{rule_id}/history` | Revisi aturan | Tidak ada; offset/limit | 200 |
| GET | `/api/v1/alarm-rules` | Daftar aturan alarm | Tidak ada; offset/limit | 200 |
| POST | `/api/v1/alarm-rules` | Buat aturan alarm nonaktif | Definisi lengkap | 201 |
| GET | `/api/v1/alarm-rules/{rule_id}` | Detail aturan alarm | Tidak ada | 200 |
| PUT | `/api/v1/alarm-rules/{rule_id}` | Ganti definisi alarm nonaktif | Definisi + expected_version | 200 |
| PUT | `/api/v1/alarm-rules/{rule_id}/enabled` | Aktifkan/nonaktifkan konfigurasi | enabled + expected_version | 200 |
| GET | `/api/v1/alarm-rules/{rule_id}/history` | Riwayat aturan alarm | Tidak ada; offset/limit | 200 |
| GET | `/api/v1/alarms` | Daftar kejadian alarm | Tidak ada; filter/pagination | 200 |
| GET | `/api/v1/alarms/{alarm_id}` | Detail kejadian alarm | Tidak ada | 200 |
| POST | `/api/v1/alarms/{alarm_id}/acknowledgment` | Catat acknowledgment | Tidak ada | 200 |
| GET | `/api/v1/device-sessions` | Daftar sesi perangkat | Tidak ada; filter/pagination | 200 |
| GET | `/api/v1/device-sessions/{session_id}` | Detail sesi perangkat | Tidak ada | 200 |
| POST | `/api/v1/device-sessions/{session_id}/end` | Catat akhir sesi | disconnected_at | 200 |
| GET | `/api/v1/devices` | Daftar perangkat | Tidak ada; filter/pagination/zone | 200 |
| POST | `/api/v1/devices` | Buat perangkat | DeviceInput | 201 |
| GET | `/api/v1/devices/{identifier}` | Detail perangkat | Tidak ada | 200 |
| PUT | `/api/v1/devices/{identifier}` | Ganti perangkat | DeviceInput + expected_version | 200 |
| DELETE | `/api/v1/devices/{identifier}` | Soft delete master | Tidak ada; expected_version query wajib | 200 |
| GET | `/api/v1/device-bindings` | Daftar binding perangkat-kendaraan | Tidak ada; filter/pagination | 200 |
| POST | `/api/v1/device-bindings` | Buat binding perangkat-kendaraan | DeviceBindingInput | 201 |
| GET | `/api/v1/device-bindings/{identifier}` | Detail binding | Tidak ada | 200 |
| PUT | `/api/v1/device-bindings/{identifier}` | Ganti binding | DeviceBindingInput + expected_version | 200 |
| DELETE | `/api/v1/device-bindings/{identifier}` | Putuskan hubungan perangkat-kendaraan | Tidak ada; expected_version query wajib | 200 |
| POST | `/api/v1/complaints` | Catat keluhan paket | ComplaintInput | 201 |
| GET | `/api/v1/complaints` | Daftar keluhan | Tidak ada; filter/pagination | 200 |
| GET | `/api/v1/complaints/reports` | Daftar laporan insiden lengkap | Tidak ada; filter/pagination | 200 |
| GET | `/api/v1/complaints/{identifier}` | Detail keluhan | Tidak ada | 200 |
| GET | `/api/v1/complaints/{identifier}/report` | Analisa laporan insiden | Tidak ada | 200 |
| POST | `/api/v1/recalls` | Mulai recall batch produksi | RecallInput | 201 |
| GET | `/api/v1/recalls` | Daftar recall | Tidak ada; filter/pagination | 200 |
| GET | `/api/v1/recalls/{identifier}` | Detail recall | Tidak ada | 200 |
| POST | `/api/v1/recalls/{identifier}/execute` | Eksekusi recall paket terdampak | RecallExecuteInput | 200 |
| POST | `/api/v1/recalls/{identifier}/withdrawals` | Catat bukti penarikan fisik recall | RecallWithdrawalInput | 201 |
| GET | `/api/v1/recalls/{identifier}/withdrawals` | Daftar bukti penarikan recall | Tidak ada; offset/limit/package_id | 200 |
| POST | `/api/v1/recalls/{identifier}/close` | Selesaikan recall | RecallCloseInput | 200 |
| GET | `/api/v1/notifications` | Daftar notification outbox | Tidak ada; filter/pagination | 200 |
| POST | `/api/v1/notifications/{identifier}/mark-sent` | Tandai notifikasi terkirim | NotificationMarkSentInput | 200 |
| POST | `/api/v1/notifications/{identifier}/mark-failed` | Tandai notifikasi gagal | NotificationMarkFailedInput | 200 |
| GET | `/api/v1/traceability/assets/{asset_uuid}` | Detail registry asset | Tidak ada | 200 |
| GET | `/api/v1/traceability/assets/{asset_uuid}/relationships` | Edge parent/child langsung | Tidak ada; direction/pagination | 200 |
| GET | `/api/v1/traceability/assets/{asset_uuid}/movements` | Timeline movement asset | Tidak ada; pagination | 200 |
| GET | `/api/v1/traceability/assets/{asset_uuid}/passport` | Passport asset | Tidak ada | 200 |
| GET | `/api/v1/traceability/assets/{asset_uuid}/impact` | Impact downstream | Tidak ada; depth/limit | 200 |
| GET | `/api/v1/traceability/assets/{asset_uuid}/traverse` | Traversal graph terbatas | Tidak ada; direction/depth/limit | 200 |
| GET | `/api/v1/dashboard/home` | Ringkasan operasional home | Tidak ada | 200 |
| GET | `/api/v1/dashboard/storage` | Ringkasan storage | Tidak ada | 200 |
| GET | `/api/v1/dashboard/storage-temperatures` | Monitor suhu terbaru per storage | Tidak ada; offset/limit | 200 |
| GET | `/api/v1/dashboard/fleet` | Ringkasan fleet | Tidak ada | 200 |
| GET | `/api/v1/dashboard/holding` | Ringkasan holding | Tidak ada | 200 |
| GET | `/api/v1/dashboard/recall` | Ringkasan recall | Tidak ada | 200 |
| GET | `/api/v1/dashboard/notifications` | Ringkasan notification outbox | Tidak ada | 200 |
| GET | `/api/v1/kitchens` | Daftar Kitchen | Tidak ada; pagination/filter induk | 200 |
| POST | `/api/v1/kitchens` | Buat Kitchen | Definisi | 201 |
| GET | `/api/v1/kitchens/{identifier}` | Detail Kitchen | Tidak ada | 200 |
| PUT | `/api/v1/kitchens/{identifier}` | Ganti Kitchen | Definisi + expected_version | 200 |
| DELETE | `/api/v1/kitchens/{identifier}` | Soft delete master | Tidak ada; expected_version query wajib | 200 |
| GET | `/api/v1/storages` | Daftar Storage | Tidak ada; pagination/filter induk | 200 |
| POST | `/api/v1/storages` | Buat Storage | Definisi | 201 |
| GET | `/api/v1/storages/{identifier}` | Detail Storage | Tidak ada | 200 |
| PUT | `/api/v1/storages/{identifier}` | Ganti Storage | Definisi + expected_version | 200 |
| DELETE | `/api/v1/storages/{identifier}` | Soft delete master | Tidak ada; expected_version query wajib | 200 |
| GET | `/api/v1/storage-zones` | Daftar Storage zone | Tidak ada; pagination/filter induk | 200 |
| POST | `/api/v1/storage-zones` | Buat Storage zone | Definisi | 201 |
| GET | `/api/v1/storage-zones/{identifier}` | Detail Storage zone | Tidak ada | 200 |
| PUT | `/api/v1/storage-zones/{identifier}` | Ganti Storage zone | Definisi + expected_version | 200 |
| DELETE | `/api/v1/storage-zones/{identifier}` | Soft delete master | Tidak ada; expected_version query wajib | 200 |
| GET | `/api/v1/suppliers` | Daftar Supplier | Tidak ada; pagination/filter relasi | 200 |
| POST | `/api/v1/suppliers` | Buat Supplier | Definisi | 201 |
| GET | `/api/v1/suppliers/{identifier}` | Detail Supplier | Tidak ada | 200 |
| PUT | `/api/v1/suppliers/{identifier}` | Ganti Supplier | Definisi + expected_version | 200 |
| DELETE | `/api/v1/suppliers/{identifier}` | Soft delete master | Tidak ada; expected_version query wajib | 200 |
| GET | `/api/v1/raw-materials` | Daftar Bahan baku | Tidak ada; pagination/filter relasi | 200 |
| POST | `/api/v1/raw-materials` | Buat Bahan baku | Definisi | 201 |
| GET | `/api/v1/raw-materials/{identifier}` | Detail Bahan baku | Tidak ada | 200 |
| PUT | `/api/v1/raw-materials/{identifier}` | Ganti Bahan baku | Definisi + expected_version | 200 |
| DELETE | `/api/v1/raw-materials/{identifier}` | Soft delete master | Tidak ada; expected_version query wajib | 200 |
| GET | `/api/v1/supplier-materials` | Daftar Relasi pemasok-bahan | Tidak ada; pagination/filter relasi | 200 |
| POST | `/api/v1/supplier-materials` | Buat Relasi pemasok-bahan | Definisi | 201 |
| GET | `/api/v1/supplier-materials/{identifier}` | Detail Relasi pemasok-bahan | Tidak ada | 200 |
| PUT | `/api/v1/supplier-materials/{identifier}` | Ganti Relasi pemasok-bahan | Definisi + expected_version | 200 |
| DELETE | `/api/v1/supplier-materials/{identifier}` | Soft delete master | Tidak ada; expected_version query wajib | 200 |
| GET | `/api/v1/schools` | Daftar sekolah | Tidak ada; kitchen_id/offset/limit | 200 |
| POST | `/api/v1/schools` | Buat sekolah | Definisi sekolah | 201 |
| GET | `/api/v1/schools/{identifier}` | Detail sekolah | Tidak ada | 200 |
| PUT | `/api/v1/schools/{identifier}` | Ganti definisi sekolah | Definisi + expected_version | 200 |
| DELETE | `/api/v1/schools/{identifier}` | Soft delete sekolah | Tidak ada; expected_version query | 200 |
| GET | `/api/v1/drivers` | Daftar driver | Tidak ada; pagination | 200 |
| POST | `/api/v1/drivers` | Buat driver | Definisi | 201 |
| GET | `/api/v1/drivers/{identifier}` | Detail driver | Tidak ada | 200 |
| PUT | `/api/v1/drivers/{identifier}` | Ganti driver | Definisi + expected_version | 200 |
| DELETE | `/api/v1/drivers/{identifier}` | Soft delete driver | Tidak ada; expected_version query | 200 |
| GET | `/api/v1/vehicles` | Daftar kendaraan | Tidak ada; pagination | 200 |
| POST | `/api/v1/vehicles` | Buat kendaraan | Definisi | 201 |
| GET | `/api/v1/vehicles/{identifier}` | Detail kendaraan | Tidak ada | 200 |
| PUT | `/api/v1/vehicles/{identifier}` | Ganti kendaraan | Definisi + expected_version | 200 |
| DELETE | `/api/v1/vehicles/{identifier}` | Soft delete kendaraan | Tidak ada; expected_version query | 200 |
| POST | `/api/v1/raw-material-batches/{identifier}/putaway` | Alokasi stok ke storage/zone | expected_version, storage_id, zone_id opsional, quantity | 201 |
| GET | `/api/v1/raw-material-batches/{identifier}/stock` | Saldo dan ketersediaan | Tidak ada | 200 |
| GET | `/api/v1/raw-material-batches/{identifier}/stock-entries` | Ledger alokasi | Tidak ada; offset/limit | 200 |
| POST | `/api/v1/raw-material-batches/{identifier}/manual-stock-issues` | Pengeluaran manual/scan dari storage | expected_version, storage_id, zone_id opsional, quantity, issued_at opsional, reason | 201 |
| GET | `/api/v1/raw-material-batches/{identifier}/manual-stock-issues` | Ledger pengeluaran manual/scan | Tidak ada; offset/limit | 200 |
| GET | `/api/v1/food-items` | Daftar menu | Tidak ada; pagination/filter | 200 |
| GET | `/api/v1/food-items/{identifier}` | Detail menu | Tidak ada | 200 |
| POST | `/api/v1/food-items` | Buat menu | Payload lengkap | 201 |
| PUT | `/api/v1/food-items/{identifier}` | Ganti menu | Payload lengkap + expected_version | 200 |
| DELETE | `/api/v1/food-items/{identifier}` | Soft delete menu | Tidak ada; expected_version query | 200 |
| GET | `/api/v1/recipes` | Daftar baris resep | Tidak ada; pagination/filter | 200 |
| GET | `/api/v1/recipes/{identifier}` | Detail baris resep | Tidak ada | 200 |
| POST | `/api/v1/recipes` | Buat baris resep | Payload lengkap | 201 |
| PUT | `/api/v1/recipes/{identifier}` | Ganti baris resep | Payload lengkap + expected_version | 200 |
| DELETE | `/api/v1/recipes/{identifier}` | Soft delete baris resep | Tidak ada; expected_version query | 200 |
| POST | `/api/v1/production-batches` | Buat rencana produksi | kitchen/menu/batch_code/planned_quantity | 201 |
| GET | `/api/v1/production-batches` | Daftar produksi | Tidak ada; pagination/filter | 200 |
| GET | `/api/v1/production-batches/{identifier}` | Detail produksi | Tidak ada | 200 |
| POST | `/api/v1/production-batches/{identifier}/start` | Mulai/pakai bahan | expected_version + items sumber stok | 200 |
| POST | `/api/v1/production-batches/{identifier}/complete` | Catat hasil dan suhu awal | expected_version + actual_quantity + initial_temperature opsional | 200 |
| POST | `/api/v1/production-batches/{identifier}/cancel` | Batalkan CREATED | expected_version | 200 |
| GET | `/api/v1/raw-material-batches/{identifier}/stock-issues` | Riwayat pemakaian produksi | Tidak ada; offset/limit | 200 |
| GET | `/api/v1/packaging-types` | Daftar jenis kemasan | Tanpa body; offset/limit | 200 |
| GET | `/api/v1/packaging-types/{identifier}` | Detail jenis kemasan | Tanpa body | 200 |
| POST | `/api/v1/packaging-types` | Buat jenis kemasan | code/name/material/volume | 201 |
| PUT | `/api/v1/packaging-types/{identifier}` | Replace jenis kemasan | Payload + expected_version | 200 |
| DELETE | `/api/v1/packaging-types/{identifier}` | Soft delete jenis kemasan | Tanpa body; expected_version query | 200 |
| POST | `/api/v1/packages` | Alokasi paket | Production version/type/code/number/quantity | 201 |
| GET | `/api/v1/packages` | Daftar paket + timer | Tanpa body; filter/pagination | 200 |
| GET | `/api/v1/packages/resolve` | Resolve QR | Tanpa body; qr_payload query | 200 |
| GET | `/api/v1/packages/{identifier}` | Detail paket + timer | Tanpa body | 200 |
| GET | `/api/v1/production-batches/{identifier}/packaging` | Sisa alokasi hasil | Tanpa body | 200 |
| POST | `/api/v1/packages/{identifier}/holding/start` | Mulai holding paket | expected_version | 200 |
| POST | `/api/v1/packages/{identifier}/holding/update` | Refresh/materialisasi expiry | expected_version | 200 |
| POST | `/api/v1/packages/{identifier}/holding/finish` | Release/discard | expected_version + outcome | 200 |
| POST | `/api/v1/deliveries` | Buat manifest | kitchen_id/vehicle/driver/items | 201 |
| GET | `/api/v1/deliveries` | Daftar pengiriman | Tanpa body; filter/pagination | 200 |
| GET | `/api/v1/deliveries/packages/by-vehicle` | Ringkasan kemasan per armada | Tanpa body; filter/pagination | 200 |
| GET | `/api/v1/deliveries/packages/by-destination` | Ringkasan kemasan per tujuan | Tanpa body; filter/pagination | 200 |
| GET | `/api/v1/deliveries/{identifier}` | Detail manifest/perjalanan | Tanpa body | 200 |
| GET | `/api/v1/deliveries/{identifier}/tracking` | Tracking GPS/suhu terakhir dan sisa jarak/waktu | Tanpa body | 200 |
| POST | `/api/v1/telemetry/gps` | Ingest GPS armada HTTP | vehicle_uuid, lat/lon, speed opsional | 201 |
| POST | `/api/v1/telemetry/temperatures` | Ingest suhu device/storage HTTP | device_uuid, storage_uuid opsional, temperature/unit | 201 |
| POST | `/api/v1/deliveries/{identifier}/depart` | Berangkat | expected_version/estimated_arrival_time | 200 |
| POST | `/api/v1/deliveries/{identifier}/complete` | Konfirmasi perjalanan selesai | expected_version | 200 |
| POST | `/api/v1/deliveries/{identifier}/cancel` | Batalkan CREATED | expected_version | 200 |
| POST | `/api/v1/receivings` | Buat penerimaan + item/batch | Header + items | 201 |
| GET | `/api/v1/receivings` | Daftar header penerimaan | Tidak ada; filter/pagination | 200 |
| GET | `/api/v1/receivings/{identifier}` | Detail penerimaan + item/batch | Tidak ada | 200 |
| POST | `/api/v1/receivings/{identifier}/complete` | Selesaikan inspeksi | expected_version + seluruh keputusan item | 200 |
| POST | `/api/v1/receivings/{identifier}/cancel` | Batalkan CREATED | expected_version | 200 |
| GET | `/api/v1/raw-material-batches` | Daftar batch bahan | Tidak ada; filter/pagination | 200 |
| GET | `/api/v1/raw-material-batches/{identifier}` | Detail batch bahan | Tidak ada | 200 |

### GET /api/v1/health

Memastikan proses API dapat merespons. Tidak memeriksa PostgreSQL, Redis, MQTT,
atau kelengkapan modul bisnis. Tidak mengubah data dan tidak menerbitkan event.

- Auth/permission: publik.
- Path parameter: tidak ada.
- Query parameter: tidak ada yang didefinisikan; pagination/filter/sort tidak berlaku.
- Request body/payload: **tidak ada**; jangan mengirim `{}` sebagai body GET.
- Header wajib: tidak ada header aplikasi khusus.

Contoh request:

```http
GET /api/v1/health HTTP/1.1
Host: localhost:8000
Accept: application/json
X-Correlation-ID: frontend-startup-001
```

Respons **200 OK**:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {"status": "ok", "service": "Food Safety Operating System"},
  "errors": [],
  "meta": {
    "request_id": "bf074e8f-91a1-456c-ae8d-f46f2bbd19d8",
    "correlation_id": "frontend-startup-001",
    "timestamp": "2026-09-11T09:00:00Z",
    "execution_time_ms": 0.4
  }
}
```

`data.status` selalu string `ok`; `data.service` adalah string dari konfigurasi
`APP_NAME` dan dapat berbeda antarlingkungan. Keduanya wajib, bukan nullable.
Error internal tak terduga memakai 500 sebagaimana bagian error bersama.

### GET /api/v1/health/database

Endpoint publik untuk test koneksi database secara eksplisit dari frontend/devops. Pemeriksaan sama dengan `/ready`: PostgreSQL 18, extension PostGIS/pgcrypto, dan Alembic heads. Tidak mengekspos URL, nama database, credential, exception SQL, atau menjalankan migrasi. Respons 200 memakai message `Database Ready`; respons 503 memakai message `Database Not Ready`; bentuk `data.status` dan `data.checks` sama dengan `/ready`.

```http
GET /api/v1/health/database HTTP/1.1
Accept: application/json
X-Correlation-ID: frontend-db-check-001
```

Gunakan endpoint ini bila UI ingin tombol "Test Database Connection" terpisah dari readiness aplikasi. Untuk startup gate/load balancer, `/ready` tetap cukup.

### GET /api/v1/ready

Memeriksa PostgreSQL major 18, extension `postgis` dan `pgcrypto`, serta kesamaan
revisi database dengan seluruh Alembic heads kode aplikasi. Pemeriksaan read-only;
tidak menjalankan migrasi dan tidak menerbitkan event.

- Auth/permission: publik.
- Path/query parameter: tidak ada yang didefinisikan.
- Request body/payload: **tidak ada**.
- Header wajib: tidak ada header aplikasi khusus.
- Batas probe: `READINESS_TIMEOUT_SECONDS`, default 3 detik, konfigurasi > 0 hingga 30.
  Ini batas probe backend, bukan jaminan durasi total request di jaringan.
- HTTP 200 hanya bila semua checks bernilai `ok`; lainnya HTTP 503.

Contoh request:

```http
GET /api/v1/ready HTTP/1.1
Host: localhost:8000
Accept: application/json
X-Correlation-ID: frontend-startup-001
```

Respons **200 OK**:

```json
{
  "success": true,
  "code": 200,
  "message": "Ready",
  "data": {
    "status": "ready",
    "checks": {"postgresql": "ok", "extensions": "ok", "schema": "ok"}
  },
  "errors": [],
  "meta": {
    "request_id": "bf074e8f-91a1-456c-ae8d-f46f2bbd19d8",
    "correlation_id": "frontend-startup-001",
    "timestamp": "2026-09-11T09:00:00Z",
    "execution_time_ms": 20.5
  }
}
```

Contoh respons **503 Service Unavailable** saat koneksi tidak tersedia:

```json
{
  "success": false,
  "code": 503,
  "message": "Not Ready",
  "data": {
    "status": "not_ready",
    "checks": {"postgresql": "unavailable", "extensions": "unchecked", "schema": "unchecked"}
  },
  "errors": [],
  "meta": {
    "request_id": "bf074e8f-91a1-456c-ae8d-f46f2bbd19d8",
    "correlation_id": "frontend-startup-001",
    "timestamp": "2026-09-11T09:00:00Z",
    "execution_time_ms": 30.1
  }
}
```

Semua field `data` di kedua respons wajib dan tidak nullable:

| Field | Nilai string | Makna |
| --- | --- | --- |
| `status` | `ready`, `not_ready` | Kesimpulan seluruh pemeriksaan |
| `checks.postgresql` | `ok`, `unsupported`, `unavailable`, `timeout` | Versi sesuai, versi selain 18, kegagalan probe, atau probe melewati batas |
| `checks.extensions` | `ok`, `missing`, `unchecked` | Dua extension tersedia, ada yang hilang, atau belum berhasil diperiksa |
| `checks.schema` | `ok`, `mismatch`, `unchecked` | Revisi sesuai, berbeda/belum migrasi, atau belum berhasil diperiksa |

Jika kegagalan terjadi setelah sebagian pemeriksaan, hasil sebelumnya tetap ada;
`postgresql` berubah menjadi `unavailable`/`timeout`. Jadi jangan menganggap hanya
satu kombinasi checks yang mungkin. `unavailable` tidak selalu berarti server mati.
Detail koneksi/exception tidak dikirim kepada frontend. Redis/MQTT, hak tulis,
kelengkapan tabel/constraint, serta partisi bulan mendatang belum diperiksa.

Frontend dapat menampilkan status layanan sementara tidak tersedia pada 503.
Gunakan retry terbatas dengan jeda, bukan loop langsung; hentikan polling saat
komponen dilepas. Jangan mengalihkan 503 ke halaman login.

## Error bersama

| HTTP | Message | Kondisi saat ini |
| --- | --- | --- |
| 400 | `Validation Error` | Handler validasi request tersedia; kedua GET saat ini tidak memiliki input tervalidasi |
| 404 | `Not Found` | Route tidak ditemukan, termasuk route bisnis yang belum dibuat |
| 405 | `Method Not Allowed` | Contoh POST ke `/api/v1/health` |
| 500 | `Internal Server Error` | Exception internal tak terduga |
| 503 | `Not Ready` | Khusus hasil pemeriksaan `/ready`, dengan data checks |

Contoh **404** untuk `GET /api/v1/missing`:

```json
{
  "success": false,
  "code": 404,
  "message": "Not Found",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "bf074e8f-91a1-456c-ae8d-f46f2bbd19d8",
    "correlation_id": "frontend-startup-001",
    "timestamp": "2026-09-11T09:00:00Z",
    "execution_time_ms": 0.4
  }
}
```

405 dan 500 memiliki bentuk yang sama, dengan `code`/`message` sesuai tabel.
400 memiliki `data: null` dan `errors: [{"field": "body.count", "message": "..."}]`;
`field` adalah lokasi input dipisahkan titik dan `message` menjelaskan validasi.
Contoh field ini hanya ilustrasi handler, bukan payload endpoint bisnis aktif.
Detail input sensitif tidak disalin ke daftar errors. 401/403/409/422 bisnis dalam
bisnis belum menjadi kontrak aktif; 401 autentikasi dijelaskan di bawah.

## Contoh pemanggilan frontend

Contoh JavaScript memakai Fetch, menangani HTTP gagal maupun error jaringan.
Browser Fetch tidak otomatis melempar exception untuk HTTP 503.

```javascript
export async function readReadiness(apiOrigin = "http://localhost:8000") {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 5000); // sesuaikan timeout server
  try {
    const response = await fetch(`${apiOrigin}/api/v1/ready`, {
      method: "GET",
      headers: { Accept: "application/json", "X-Correlation-ID": crypto.randomUUID() },
      cache: "no-store",
      signal: controller.signal,
    });
    const body = await response.json(); // proxy dapat mengirim HTML, masuk catch
    if (!response.ok) {
      return { ready: false, checks: body.data?.checks ?? null,
        requestId: response.headers.get("X-Request-ID"), httpStatus: response.status };
    }
    return { ready: body.data?.status === "ready", checks: body.data?.checks ?? null,
      requestId: response.headers.get("X-Request-ID"), httpStatus: response.status };
  } catch {
    return { ready: false, checks: null, requestId: null, httpStatus: null };
  } finally {
    clearTimeout(timer);
  }
}
```

Sesuaikan origin/prefix melalui konfigurasi frontend untuk deployment. Error
jaringan/CORS/timeout tidak memiliki envelope yang dapat diandalkan. Jangan
menganggap `ready: true` sebagai autentikasi atau kesiapan semua fitur bisnis.

## API bisnis dan realtime

[Sesi dan refresh token](refresh-sessions.md) terhubung ke endpoint autentikasi di
atas. Browser memakai JSON dan bearer; tidak ada cookie refresh otomatis. Lihat
bagian kontrak autentikasi di bawah untuk payload, respons dan error lengkap.

[Daftar alarm/sesi](telemetry-lifecycle.md#daftar-alarm-dan-sesi-service-internal)
tersedia pada service internal. Daftar/detail/acknowledgment alarm kini juga memiliki
[kontrak HTTP](#kontrak-alarm-telemetry-http); operasi sesi perangkat juga memiliki [kontrak HTTP](#kontrak-sesi-perangkat-http).
Tidak ada subscription realtime.

[Rekonsiliasi digital asset](asset-registry.md#rekonsiliasi-registry-laporan-tanpa-mutasi)
tersedia sebagai service internal/CLI dengan hasil IN_SYNC, SOURCE_MISSING, atau
PROJECTION_MISMATCH dan pagination UUID registry. Hasil tersebut bukan response
HTTP aktif: belum ada endpoint untuk dashboard, payload browser, atau subscription.
Scan tidak mengubah data maupun menghasilkan event; kontrak health/ready tetap.


[Pemisahan koneksi database](database-connections.md) memakai DATABASE_URL runtime
dan ADMIN_DATABASE_URL administratif. fsos_app adalah login PostgreSQL backend,
bukan akun frontend. Perubahan ini tidak menambah endpoint atau mengubah envelope.

[Role PostgreSQL runtime](runtime-database-role.md) kini dipisahkan sebagai profil
privilege NOLOGIN. Ini konfigurasi backend, bukan role login frontend. Tidak ada
payload/response HTTP baru dan credential database tetap tidak boleh dikirim ke browser.

[Maintenance partisi](telemetry-maintenance.md) kini tersedia melalui CLI dan tugas
Windows development. Tidak ada endpoint laporan maintenance baru. Respons ready
tetap tidak menyatakan cakupan partisi bulan mendatang atau ketersediaan arsip.

[Service status alarm/sesi](telemetry-lifecycle.md) sekarang menghitung status efektif
dan mencatat acknowledgment/akhir sesi secara append-only. HTTP alarm sudah tersedia;
API akhir sesi juga tersedia. Snapshot awal bisa berbeda dari status efektif setelah finalisasi.

[Fixture development](development-seed.md) kini tersedia di database lokal:
tenant FSOS_DEV dan data master contoh. dev-maintenance adalah actor internal
tanpa password login, bukan credential frontend. Data fixture belum bisa diambil
lewat API bisnis karena endpointnya belum tersedia. Jangan menaruh DATABASE_URL
di frontend atau memperlakukan UUID actor sebagai token.

Adapter dan [service registry digital asset](asset-registry.md) kini tersedia,
termasuk backfill dan sinkronisasi kitchen dalam transaksi yang sama. Tidak ada
endpoint registry baru. asset_uuid registry berbeda dari entity_uuid sumber;
frontend belum boleh mengasumsikan keduanya dapat saling menggantikan.

Holding dan alarm rule memiliki endpoint daftar/detail/create/update/history yang
dijelaskan di bawah. Alarm juga memiliki endpoint aktivasi/nonaktif konfigurasi.
DSL v1 menjadi kontrak input alarm; evaluator, simulasi dan executor masih TODO.

API kitchen, storage dan storage zone kini tersedia dengan tenant/actor dari bearer,
permission Read/Write dan expected_version. Lihat [kontrak master lokasi](#kontrak-master-kitchen-storage-zone).

Master data selain kitchen/storage/zone/sekolah/kendaraan/driver/supplier/bahan/relasi pemasok/menu/resep/jenis kemasan/holding/alarm rule, telemetry selain alarm/sesi, stok lanjutan, holding dinamis berbasis telemetry,
traceability traversal, GPS/geofence fleet, complaint, recall, dashboard, analytics, dan cetak QR
belum memiliki endpoint aktif. Filter dan pagination tersedia untuk aturan/alarm/sesi
sesuai kontrak masing-masing; sort kustom dan upload belum tersedia melalui HTTP. Payloadnya belum menjadi
kontrak; akan ditambahkan saat endpoint dibuat.

Tidak ada route WebSocket atau SSE aktif. Frontend belum dapat berlangganan
event. Lihat [event catalog](event-catalog.md) untuk status rencana.

## Pemeliharaan

Perubahan API wajib memperbarui halaman ini, OpenAPI/schema, contoh respons,
tes perilaku yang relevan, dan [changelog](frontend-changelog.md) dalam pekerjaan
yang sama. Jika ada event, perbarui catalog juga. Aturan proyek disimpan di
[AGENTS.md](../../AGENTS.md) agar berlaku pada pengembangan berikutnya.

## Kontrak autentikasi HTTP

Seluruh path berikut memakai prefix API yang dapat dikonfigurasi. Tidak ada path
parameter atau query parameter. Semua POST menerima JSON, bukan form-urlencoded.
Field tambahan body ditolak. Tidak ada cookie yang dipasang/dibaca untuk auth.
Request dan response membawa secret hanya pada body/header yang disebutkan;
jangan masukkan token/password ke URL, correlation ID atau log frontend.

Persiapan: JWT_SECRET backend minimal 32 byte (gunakan secret acak), lifetime
konfigurasi harus 15 menit/7 hari dan schema 0017 beserta grant runtime tersedia.
Secret acak lokal telah disiapkan di .env yang diabaikan Git. Akun manusia perlu
password bcrypt yang sah; dev-maintenance tetap tanpa password dan tidak bisa
login. [Bootstrap akun manusia development](human-bootstrap.md) tersedia melalui CLI
administratif, bukan endpoint signup; pengguna memilih profil/password di terminal. Health/ready tidak memeriksa secret
JWT, rate limiter atau kelengkapan akun, sehingga readiness 200 tidak menjamin login.

### POST /api/v1/auth/login

Tujuan: memverifikasi username/password pada tenant dan membuat sesi baru.
Auth: publik, tanpa Authorization dan tanpa permission bisnis prasyarat.
User dan tenant harus ACTIVE serta belum soft-deleted. Username dicocokkan tanpa
membedakan case dan mengabaikan spasi ASCII tepi; email login belum didukung.
Password tidak di-trim/dinormalisasi. Sesi dan hash refresh di-commit sebelum token
dikirim. Request login baru membuat keluarga sesi baru, bukan memakai sesi lama.

| Body field | Tipe | Required / nullable | Validasi |
| --- | --- | --- | --- |
| tenant | string | Kondisional / ya | Tenant code seperti `FSOS_DEMO` atau UUID tenant; kirim salah satu dari tenant atau tenant_id |
| tenant_id | string UUID | Kondisional / ya | Legacy UUID tenant; kirim salah satu dari tenant atau tenant_id |
| username | string | Ya / tidak | 1..100 karakter; angka/field tambahan ditolak |
| password | string secret | Ya / tidak | 1..72 karakter pada schema; kredensial harus memenuhi kebijakan 12 karakter sampai 72 byte UTF-8, tanpa NUL |

Password terlalu pendek menurut kebijakan, terlalu panjang dalam byte UTF-8,
username blank/NUL, akun tanpa hash, user tidak aktif, tenant salah dan password
salah menghasilkan 401 seragam. Panjang/tipenya melanggar schema, tenant dan
tenant_id kosong semua atau dikirim bersamaan, UUID tidak valid pada tenant_id,
atau JSON rusak menghasilkan 400. Tidak ada password default aplikasi.

Contoh request (nilai ilustratif, bukan akun yang sudah dibuat):

```http
POST /api/v1/auth/login HTTP/1.1
Content-Type: application/json
Accept: application/json

{
  "tenant": "FSOS_DEMO",
  "username": "operator",
  "password": "contoh passphrase pengguna"
}
```

Respons sukses 200 lengkap (token placeholder harus diganti hasil server):

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "access_token": "<ACCESS_JWT>",
    "refresh_token": "<OPAQUE_REFRESH_TOKEN>",
    "refresh_expires_at": "2026-09-18T10:00:00Z",
    "token_type": "Bearer",
    "expires_in": 900
  },
  "errors": [],
  "meta": {
    "request_id": "22222222-2222-4222-8222-222222222222",
    "correlation_id": "22222222-2222-4222-8222-222222222222",
    "timestamp": "2026-09-11T10:00:00Z",
    "execution_time_ms": 310.2
  }
}
```

| Data field | Tipe / nullable | Makna |
| --- | --- | --- |
| access_token | string / tidak | JWT access bertanda tangan; membawa sid sesi, berlaku 15 menit |
| refresh_token | string / tidak | Token opaque sekali pakai; simpan sebagai secret, bukan JWT |
| refresh_expires_at | ISO 8601 UTC / tidak | Batas absolut keluarga sesi tujuh hari sejak login |
| token_type | string / tidak | Selalu Bearer |
| expires_in | integer / tidak | Selalu 900 detik; access dapat ditolak lebih awal jika sesi dicabut/expired |

Error: 400, 401, 429, 503, 500 sebagaimana tabel bersama. Tidak ada event bus,
WebSocket, notifikasi atau event catalog baru akibat login. Log operasional hanya
mencatat action/outcome/request ID; audit keamanan persisten belum tersedia.

### POST /api/v1/auth/refresh

Tujuan: mengganti refresh token dan menerbitkan access token baru pada sesi sama.
Auth: kepemilikan refresh token pada body; Authorization tidak diperlukan dan tidak
dipakai. Akun/tenant serta sesi harus aktif. Role/permission snapshot dibaca ulang.

| Body field | Tipe | Required / nullable | Validasi |
| --- | --- | --- | --- |
| refresh_token | string secret | Ya / tidak | 1..101 karakter; token sah berbentuk UUID + titik + 64 karakter acak |

```json
{"refresh_token": "<OPAQUE_REFRESH_TOKEN>"}
```

200 memakai envelope dan kelima field data yang sama persis dengan login. Kedua
token berubah; refresh_expires_at tetap dan tidak diperpanjang. Token lama ditandai
terpakai. Token benar yang dipakai ulang mencabut seluruh keluarga termasuk access
dan refresh hasil rotasi sebelumnya. Pencabutan di-commit sebelum 401 dikirim.

401 untuk format/hash salah, sesi habis/dicabut, akun/tenant nonaktif atau reuse;
responsnya tidak membedakan penyebab. Error lain: 400, 429, 503, 500.
Tidak ada event yang diterbitkan; perubahan berupa bukti token dan status sesi.

**Wajib satu refresh berjalan per sesi pada frontend.** Dua refresh bersamaan bisa
menghasilkan satu 200 dan satu 401; sesudah reuse, token dari 200 juga ditolak.
Jika respons refresh hilang/timeout, jangan otomatis mencoba token lama berulang:
rotasi mungkin sudah commit. Minta login kembali bila tidak memiliki pasangan token
baru. Tidak ada grace period atau idempotency key refresh saat ini.

### POST /api/v1/auth/logout

Tujuan: mencabut satu keluarga sesi. Auth: kepemilikan refresh token di body;
bearer tidak diperlukan. Payload dan validasi sama dengan refresh:

```json
{"refresh_token": "<OPAQUE_REFRESH_TOKEN>"}
```

200 selalu memakai data {"logged_out": true} untuk payload lolos schema, termasuk
token tidak dikenal atau sesi sudah dicabut. Ini tidak mengungkap validitas token.
Token lama yang masih dapat diverifikasi juga boleh mencabut keluarga sesi.
revoked_at pertama dipertahankan pada pengulangan. Tidak ada logout semua perangkat.

Contoh respons lengkap:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {"logged_out": true},
  "errors": [],
  "meta": {
    "request_id": "22222222-2222-4222-8222-222222222222",
    "correlation_id": "22222222-2222-4222-8222-222222222222",
    "timestamp": "2026-09-11T10:00:00Z",
    "execution_time_ms": 5.3
  }
}
```

logged_out adalah boolean nonnullable. Bersihkan token client setelah logout.
Kesalahan request/config/database tetap dapat menghasilkan 400/429/503/500;
logout token invalid tidak menghasilkan 401. Tidak ada cookie yang perlu dihapus
server atau event yang diterbitkan. Access lama ditolak pada pemeriksaan sesi
berikutnya; transaksi yang sudah mendapat izin tidak dibatalkan secara retroaktif.

### GET /api/v1/auth/me

Tujuan: membaca identitas dan daftar izin terkini. Auth: header wajib
Authorization: Bearer <access_token>. Tidak ada body/path/query parameter atau
permission bisnis khusus; user/tenant dan sesi harus aktif. Token tanpa sid,
refresh token pada bearer, JWT rusak/expired, akun/sesi nonaktif ditolak 401.
Jangan gunakan claim permission yang di-decode frontend sebagai otorisasi server.

```http
GET /api/v1/auth/me HTTP/1.1
Authorization: Bearer <ACCESS_JWT>
Accept: application/json
```

Contoh 200:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "user_id": "33333333-3333-4333-8333-333333333333",
    "tenant_id": "11111111-1111-4111-8111-111111111111",
    "roles": ["Viewer"],
    "permissions": ["Alarm.Read"]
  },
  "errors": [],
  "meta": {
    "request_id": "22222222-2222-4222-8222-222222222222",
    "correlation_id": "22222222-2222-4222-8222-222222222222",
    "timestamp": "2026-09-11T10:00:00Z",
    "execution_time_ms": 4.1
  }
}
```

| Data field | Tipe / nullable | Makna |
| --- | --- | --- |
| user_id / tenant_id | string UUID / tidak | Identitas terverifikasi |
| roles | array string / tidak | Kode role aktif terurut tanpa duplikasi; boleh kosong |
| permissions | array string / tidak | Permission RBAC aktif terurut tanpa duplikasi; boleh kosong |

Tidak mengubah data dan tidak menerbitkan event. Error: 401, 429, 503, 500.
Pencabutan grant tercermin pada request berikut, meskipun token belum expired.

### Error dan header autentikasi

Semua respons auth, termasuk error, memakai Cache-Control: no-store dan
Pragma: no-cache. X-Request-ID tetap ada. 401 menyertakan WWW-Authenticate: Bearer.
429 menyertakan Retry-After dalam detik dan dapat dibaca melalui CORS.

| HTTP | message | Penanganan |
| --- | --- | --- |
| 400 | Validation Error | Perbaiki JSON/field; errors berisi field dan message, tanpa nilai password/token |
| 401 | Invalid credentials or session | Login: periksa kredensial; refresh/revoked session: login ulang |
| 429 | Too many authentication requests | Tunggu Retry-After; jangan mengulang rapat |
| 503 | Authentication unavailable | Secret/lifetime tidak sesuai atau database/commit gagal; jangan menganggap token sudah diterbitkan |
| 500 | Internal Server Error | Kegagalan tak terduga; catat request_id tanpa secret |

Contoh 401 lengkap untuk login, refresh atau me:

```json
{
  "success": false,
  "code": 401,
  "message": "Invalid credentials or session",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "22222222-2222-4222-8222-222222222222",
    "correlation_id": "22222222-2222-4222-8222-222222222222",
    "timestamp": "2026-09-11T10:00:00Z",
    "execution_time_ms": 300.1
  }
}
```

400/429/503/500 mengikuti envelope yang sama dengan code/message sesuai tabel.
400 mengisi errors, misalnya [{"field":"body.tenant_id","message":"Input should be a valid UUID, invalid length: expected length 32 for simple format, found 3"}];
teks validasi dapat berubah mengikuti library, gunakan field/code untuk UI.
FastAPI 422 otomatis dihapus dari OpenAPI auth karena handler aktual memakai 400.

Limiter sementara: maksimal 100 permintaan gabungan /auth/* per 60 detik per
request.client.host dalam satu proses; login sukses/gagal dan /me ikut dihitung.
OPTIONS tidak dihitung. Aplikasi tidak membaca X-Forwarded-For sendiri; konfigurasi
trusted proxy ASGI server menentukan nilai request.client yang diterima aplikasi.
Limiter menyimpan maksimal 4096 IP; IP baru ditolak sementara jika kapasitas penuh.
Window reset saat habis; restart proses menghapus hitungan. Ini bukan limiter
terdistribusi dan belum menggantikan Redis/proxy untuk deployment multiworker.

### Contoh pemanggilan frontend

```javascript
const response = await fetch(`${apiBase}/auth/login`, {
  method: "POST",
  headers: { "Content-Type": "application/json", Accept: "application/json" },
  credentials: "omit",
  body: JSON.stringify({ tenant: tenantCode, username, password }),
});
const body = await response.json();
if (!response.ok) throw new Error(`${body.code}: ${body.message}`);
const tokens = body.data; // kelola di memori; jangan console.log token/password
const profileResponse = await fetch(`${apiBase}/auth/me`, {
  headers: { Authorization: `Bearer ${tokens.access_token}` },
  credentials: "omit",
});
const profile = await profileResponse.json();
```

Contoh apiBase adalah http://localhost:8000/api/v1. Jangan hardcode credential nyata
ke source frontend atau membagikan token di log/screenshot. Penyimpanan token yang
bertahan setelah reload, BFF/cookie HttpOnly/CSRF, reset password, bootstrap admin production,
audit persisten serta limiter Redis masih perlu ditentukan/diimplementasikan.

Verifikasi: suite 103 tes lulus; setelah perbaikan urutan middleware CORS, 20 tes
API/auth/readiness diulang dan lulus. OpenAPI serta payload/respons diuji melalui
HTTP. Local readiness=200; dev-maintenance tanpa password tetap ditolak 401.
Restart backend yang sudah berjalan untuk memuat route dan konfigurasi baru.

Bootstrap development kini dapat membuat akun manusia baru dengan membership role
terpilih. [Panduan bootstrap](human-bootstrap.md) memuat perintah, mode --check,
validasi, output dan efek samping. Tidak ada endpoint, payload atau respons baru;
login/me yang sudah didokumentasikan dipakai setelah akun berhasil dibuat.
Actor dev-maintenance tetap tanpa password; script tidak mengubahnya.

## Kontrak holding rule HTTP

Holding rule adalah konfigurasi batas waktu per kategori makanan. Endpoint ini
menyimpan definisi dan revisinya; perubahan rule tidak otomatis mengubah timer atau
status paket yang sudah dibuat, mengirim alarm, atau menerbitkan event. Timer paket
menggunakan snapshot policy saat pengemasan pertama (lihat kontrak holding). Angka contoh di bawah hanya
ilustrasi kontrak API, bukan rekomendasi batas keamanan pangan.

Semua endpoint wajib Authorization: Bearer <access_token> dari login dengan sid
aktif. Tenant dan actor berasal dari sesi, tidak diterima dari body/header tenant.
Header Accept: application/json disarankan, Content-Type: application/json wajib
untuk POST/PUT, X-Correlation-ID opsional. Respons menggunakan envelope standar,
X-Request-ID, Cache-Control: no-store dan Pragma: no-cache, termasuk error.
Tidak ada cookie, API key, upload atau subscription. Limiter sementara /auth/*
belum mencakup endpoint holding rule; limiter bisnis lintas worker tetap TODO.

| Method/path | Tujuan | Permission | Body | Path/query |
| --- | --- | --- | --- | --- |
| GET /api/v1/holding-rules | Daftar aturan aktif tenant | HoldingRule.Read | Tidak ada | offset/limit opsional |
| POST /api/v1/holding-rules | Buat aturan dan revisi awal | HoldingRule.Write | Definisi lengkap | Tidak ada |
| GET /api/v1/holding-rules/{rule_id} | Detail satu aturan | HoldingRule.Read | Tidak ada | rule_id UUID wajib |
| PUT /api/v1/holding-rules/{rule_id} | Ganti seluruh definisi | HoldingRule.Write | Definisi + expected_version | rule_id UUID wajib |
| GET /api/v1/holding-rules/{rule_id}/history | Revisi immutable | HoldingRule.Read | Tidak ada | rule_id UUID; offset/limit opsional |

Permission diperiksa dari database setiap operasi; claim JWT tidak menggantikan
pemeriksaan ini. Read tidak memberi Write. Write boleh mengembalikan hasil mutasinya
tanpa Read terpisah. Actor/user/tenant atau sesi tidak aktif ditolak 401. Jika
permission tidak ada, 403 diberikan sebelum mencari rule. Dengan Read/Write sah,
UUID rule tidak ada, soft-deleted atau milik tenant lain menghasilkan 404 yang sama.
Role DEV_MAINTENANCE sudah memuat HoldingRule.Read/Write; login manusia yang
memakai role ini dapat mengakses endpoint sesuai grant yang belum dicabut.

### Payload POST dan PUT

| Field | Tipe | Required / nullable | Validasi |
| --- | --- | --- | --- |
| food_category | string | Ya / tidak | Trim whitespace, 1..100 karakter, UTF-8 valid tanpa NUL; unik per tenant, case-sensitive |
| warning_minutes | integer | Ya / tidak | 0..2147483647 |
| maximum_minutes | integer | Ya / tidak | 1..2147483647 |
| discard_minutes | integer | Ya / tidak | 1..2147483647 |
| expected_version | integer | PUT saja / tidak | 1..2147483647, harus sama dengan version terakhir yang dibaca |

Semua nilai waktu dalam menit dan harus memenuhi warning <= maximum <= discard.
Boolean, angka dalam string, nilai pecahan dan field tambahan ditolak. Audit,
tenant_id, created_by, updated_by, deleted_at, version atau enabled tidak boleh
masuk body. POST tidak menerima expected_version. PUT bukan PATCH: empat field
definisi wajib dikirim kembali, termasuk bila hanya satu nilai yang diubah.

Contoh POST /api/v1/holding-rules:

```json
{"food_category":"EXAMPLE_ONLY","warning_minutes":60,"maximum_minutes":90,"discard_minutes":120}
```

Contoh PUT /api/v1/holding-rules/11111111-1111-4111-8111-111111111111:

```json
{"food_category":"EXAMPLE_ONLY","warning_minutes":60,"maximum_minutes":100,"discard_minutes":120,"expected_version":1}
```

POST menghasilkan 201 dengan version=1 dan snapshot pertama. PUT menghasilkan
200 dengan version bertambah satu; trigger mengisi updated_at dan history atomik,
updated_by diambil dari sesi. Tidak ada commit jika write/history gagal. PUT identik
dengan version terbaru tetap menambah revisi; mengulang expected_version lama
menghasilkan 409. Setelah konflik, fetch ulang detail dan minta pengguna meninjau
perubahan sebelum mencoba lagi. Tidak ada dukungan If-Match/ETag/idempotency key.
Kategori yang sama setelah trim berbenturan 409; akun tenant lain boleh memakai
kategori sama. Kategori lama soft-deleted tetap tercakup constraint unik.

### Bentuk data detail dan hasil mutasi

GET detail (200), POST (201) dan PUT (200) mengembalikan data dengan field berikut.
Semua field selalu hadir; nullable hanya seperti ditandai.

| Field | Tipe / nullable | Penjelasan |
| --- | --- | --- |
| holding_rule_id | UUID / tidak | Identitas aturan |
| tenant_id | UUID / tidak | Tenant terverifikasi |
| food_category | string / tidak | Kategori yang sudah di-trim |
| warning_minutes / maximum_minutes / discard_minutes | integer / tidak | Batas menit tersimpan |
| version | integer / tidak | Versi untuk expected_version pada PUT |
| created_at / updated_at | ISO 8601 UTC / tidak | Audit waktu database |
| created_by / updated_by | UUID atau null | Actor audit; record legacy mungkin null |
| deleted_at | ISO 8601 UTC atau null | Null pada record yang dapat dibaca endpoint |
| deleted_by | UUID atau null | Null pada record aktif; tidak dapat diubah melalui endpoint |

Contoh response POST 201 lengkap:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "holding_rule_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "22222222-2222-4222-8222-222222222222",
    "food_category": "EXAMPLE_ONLY",
    "warning_minutes": 60,
    "maximum_minutes": 90,
    "discard_minutes": 120,
    "version": 1,
    "created_at": "2026-09-11T10:00:00Z",
    "updated_at": "2026-09-11T10:00:00Z",
    "created_by": "33333333-3333-4333-8333-333333333333",
    "updated_by": "33333333-3333-4333-8333-333333333333",
    "deleted_at": null,
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T10:00:00Z",
    "execution_time_ms": 8.4
  }
}
```

GET detail memakai bentuk yang sama dengan code/status 200. PUT memakai code 200,
version berikutnya, waktu updated_at baru dan definisi yang dikirim.

### Pagination daftar dan history

Query offset default 0, minimum 0, maksimum 2147483647. Query limit default 20,
rentang 1..100. Tidak ada total_count, cursor, filter/sort bebas atau pencarian.
Daftar hanya tenant sendiri dan nondeleted, urut created_at DESC lalu holding_rule_id
DESC. History urut version DESC dan hanya tersedia jika parent rule terlihat.

GET /api/v1/holding-rules?offset=0&limit=20 menghasilkan 200 dengan data
{items: [record detail], offset: 0, limit: 20}. Halaman kosong:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [],
    "offset": 20,
    "limit": 20
  },
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T10:00:00Z",
    "execution_time_ms": 8.4
  }
}
```

Naikkan offset sebesar limit untuk halaman berikutnya; berhenti jika jumlah items
kurang dari limit. Jika halaman terakhir tepat penuh, request berikutnya kosong.
Pagination offset bukan snapshot lintas request: insert baru dapat menggeser daftar.

GET /api/v1/holding-rules/{rule_id}/history?offset=0&limit=20 mengembalikan data
{items: [revision], offset, limit}. Tiap revision memiliki revision_id UUID,
tenant_id UUID, rule_id UUID, version integer, captured_at timestamp, dan snapshot
berisi seluruh field data detail di atas. Semua field revisi nonnullable; field
nullable di dalam snapshot mengikuti data detail. Contoh response history:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [
      {
        "revision_id": "55555555-5555-4555-8555-555555555555",
        "tenant_id": "22222222-2222-4222-8222-222222222222",
        "rule_id": "11111111-1111-4111-8111-111111111111",
        "version": 1,
        "captured_at": "2026-09-11T10:00:00Z",
        "snapshot": {
          "holding_rule_id": "11111111-1111-4111-8111-111111111111",
          "tenant_id": "22222222-2222-4222-8222-222222222222",
          "food_category": "EXAMPLE_ONLY",
          "warning_minutes": 60,
          "maximum_minutes": 90,
          "discard_minutes": 120,
          "version": 1,
          "created_at": "2026-09-11T10:00:00Z",
          "updated_at": "2026-09-11T10:00:00Z",
          "created_by": "33333333-3333-4333-8333-333333333333",
          "updated_by": "33333333-3333-4333-8333-333333333333",
          "deleted_at": null,
          "deleted_by": null
        }
      }
    ],
    "offset": 0,
    "limit": 20
  },
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T10:00:00Z",
    "execution_time_ms": 8.4
  }
}
```

History tidak memiliki endpoint edit/delete; endpoint ini tidak menghapus snapshot.
Tidak ada DELETE, PATCH atau endpoint aktivasi holding rule. Tidak ada automatic
re-evaluation paket atau pemilihan threshold produksi ketika definisi diubah.

### Error holding rule

| HTTP | message | Penyebab |
| --- | --- | --- |
| 400 | Validation Error | JSON/body/path/query tidak valid; errors berisi field/message tanpa raw input |
| 400 | Invalid holding rule input | Validasi ulang service gagal |
| 401 | Invalid credentials or session | Bearer hilang/invalid, akun/tenant atau sesi tidak aktif; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted | HoldingRule.Read atau Write belum diberikan/dicabut |
| 404 | Rule not found | Tidak ditemukan, soft-deleted atau tenant lain |
| 409 | Food category already exists in this tenant | Konflik kategori unik |
| 409 | Rule changed; reload before retrying | expected_version tertinggal |
| 503 | Authentication unavailable | Koneksi DB/konfigurasi auth tidak tersedia |
| 500 | Internal Server Error | Kegagalan tak terduga |

Contoh error konflik versi lengkap:

```json
{
  "success": false,
  "code": 409,
  "message": "Rule changed; reload before retrying",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T10:00:00Z",
    "execution_time_ms": 8.4
  }
}
```

Error lainnya memakai envelope sama dengan code/message sesuai tabel; 400 validasi
mengisi errors, misalnya field body.maximum_minutes. OpenAPI mendokumentasikan 400
bukan 422 otomatis. Rincian database/SQL tidak dikirim ke browser.

Tindakan frontend: gunakan version hasil GET/POST/PUT untuk edit berikutnya, jangan
mengirim field audit, gunakan izin dari /auth/me untuk tampilan dan tetap tangani
403 jika grant berubah. Setelah create/update berhasil, muat ulang daftar/history
sesuai kebutuhan; tidak ada event realtime untuk refresh otomatis.

Verifikasi holding rule: 37 tes API/service/DSL/autentikasi terkait lulus, termasuk
history yang konsisten dengan detail setelah normalisasi UTC, error versi/kategori,
permission terpisah dan lintas tenant. Tidak ada migrasi baru atau fixture aturan
pada database aplikasi. Restart proses backend lama untuk memuat route baru.


## Kontrak alarm rule HTTP

Status: enam operasi berikut sudah tersedia. Semua memakai bearer access token dengan
session aktif, tenant/actor dari sesi dan permission database yang diperiksa setiap
operasi. Header wajib `Authorization: Bearer <access_token>`; untuk POST/PUT gunakan
`Content-Type: application/json`. `X-Correlation-ID` opsional (maksimal 128 karakter
diteruskan). Respons JSON envelope, `X-Request-ID`, `Cache-Control: no-store` dan
`Pragma: no-cache`. Tidak ada cookie atau header tenant yang mengganti scope sesi.
Limiter auth sementara tidak mencakup endpoint alarm rule; limiter bisnis masih TODO.

| Method/path | Tujuan | Permission | Payload | Path/query |
| --- | --- | --- | --- | --- |
| GET /api/v1/alarm-rules | Daftar konfigurasi nondeleted, enabled true maupun false | AlarmRule.Read | Tidak ada | offset/limit opsional |
| POST /api/v1/alarm-rules | Buat konfigurasi disabled dan revisi awal | AlarmRule.Write | Definisi lengkap | Tidak ada |
| GET /api/v1/alarm-rules/{rule_id} | Detail aturan tenant | AlarmRule.Read | Tidak ada | rule_id UUID wajib |
| PUT /api/v1/alarm-rules/{rule_id} | Ganti seluruh definisi aturan disabled | AlarmRule.Write | Definisi + expected_version | rule_id UUID wajib |
| PUT /api/v1/alarm-rules/{rule_id}/enabled | Aktifkan/nonaktifkan konfigurasi | AlarmRule.Activate | enabled + expected_version | rule_id UUID wajib |
| GET /api/v1/alarm-rules/{rule_id}/history | Snapshot revisi immutable | AlarmRule.Read | Tidak ada | rule_id UUID wajib; offset/limit opsional |

Read, Write, Activate independen. Write saja dapat membuat/mengedit dan menerima
snapshot respons, tetapi tidak membaca daftar/detail/history. Activate saja dapat
mengubah enabled dan menerima snapshot tanpa Read/Write. Seed DEV_MAINTENANCE
memiliki ketiga grant; akun manusia harus dibuat melalui bootstrap development.
Tidak ada DELETE, PATCH, restore, bulk, simulasi atau endpoint execution log.

### Payload dan validasi alarm

Semua field tabel berikut wajib dan tidak nullable. POST menerima enam field definisi;
PUT definisi menerima enam field tersebut ditambah expected_version. Field tambahan
(termasuk tenant_id, audit, version dan enabled) ditolak. String metadata di-trim;
setelah trim panjang minimum 1; NUL dan Unicode tidak valid ditolak.

| Field | Tipe / batas | Makna |
| --- | --- | --- |
| rule_code | string 1..50 | Unik case-sensitive per tenant; kode milik record soft-deleted tetap terpakai |
| rule_name | string 1..200 | Nama tampilan |
| rule_category | string 1..100 | Kategori konfigurasi |
| priority | string enum CRITICAL/HIGH/MEDIUM/LOW/INFO | Prioritas konfigurasi |
| condition | object | Pohon kondisi DSL v1 |
| action | object | DSL v1 dengan dsl_version dan steps |
| expected_version | integer 1..2147483647; hanya PUT | Versi terakhir dari server; bool/string angka ditolak |

Grammar condition/action lengkap ada di [DSL v1](rule-versioning.md#kontrak-validator-internal)
dan merupakan bagian kontrak endpoint ini. Leaf tepat field/op/value atau group tepat
all/any (1..20 anak); maksimum 100 node dan kedalaman 8. Field numerik temperature,
duration_minutes, humidity, remaining_minutes, speed menerima eq/ne/gt/gte/lt/lte,
angka finite -1e12..1e12 (bukan bool/string). Field storage_type/status menerima eq/ne
dan string nonblank 1..200. Action tepat dsl_version integer 1 dan steps 1..10 object;
tipe dan field wajib dijabarkan di tabel DSL. Semua nilai teks DSL harus valid UTF-8,
tanpa NUL, nonblank dan maksimal 200 karakter; teks DSL tidak di-trim oleh validator.
Key tambahan dan null ditolak. Template/target/transisi belum divalidasi semantik.

Contoh POST /api/v1/alarm-rules (angka hanya ilustrasi, bukan ambang keamanan pangan):

```json
{
  "rule_code": "TEMP_EXAMPLE",
  "rule_name": "Contoh suhu",
  "rule_category": "STORAGE",
  "priority": "HIGH",
  "condition": {
    "field": "temperature",
    "op": "gt",
    "value": 10
  },
  "action": {
    "dsl_version": 1,
    "steps": [
      {
        "type": "alarm",
        "code": "TEMP_EXAMPLE",
        "severity": "HIGH"
      }
    ]
  }
}
```

Contoh PUT /api/v1/alarm-rules/11111111-1111-4111-8111-111111111111:

```json
{
  "rule_code": "TEMP_EXAMPLE",
  "rule_name": "Contoh suhu diperbarui",
  "rule_category": "STORAGE",
  "priority": "HIGH",
  "condition": {
    "field": "temperature",
    "op": "gt",
    "value": 10
  },
  "action": {
    "dsl_version": 1,
    "steps": [
      {
        "type": "alarm",
        "code": "TEMP_EXAMPLE",
        "severity": "HIGH"
      }
    ]
  },
  "expected_version": 1
}
```

Endpoint enabled hanya menerima dua field wajib, tidak nullable:
`enabled` boolean JSON true/false (bukan 0/1 atau string), dan `expected_version`
integer 1..2147483647. Contoh PUT /api/v1/alarm-rules/{rule_id}/enabled setelah edit:

```json
{
  "enabled": true,
  "expected_version": 2
}
```

POST selalu enabled=false, version=1. Edit definisi mensyaratkan disabled; perubahan
berhasil menaikkan version dan mencatat snapshot atomik. Bahkan definisi identik
menghasilkan revisi baru. Ubah enabled juga menaikkan version jika status berubah.
Status identik dengan expected_version terkini menghasilkan 200 tanpa revisi baru;
versi lama tetap 409. Enable selalu memvalidasi ulang DSL tersimpan, termasuk jika
sudah enabled. Disable tetap bisa untuk DSL legacy invalid. Untuk edit aturan aktif,
nonaktifkan dahulu lalu gunakan version dari respons disable untuk PUT definisi.
Konflik 409 harus diikuti reload dan peninjauan perubahan sebelum mencoba ulang.
POST tidak memiliki idempotency key; retry kode yang sudah tersimpan menghasilkan 409.

### Respons alarm dan pagination

POST mengembalikan 201; GET dan kedua PUT 200. Semua field data berikut selalu hadir:

| Field data | Tipe / nullable | Penjelasan |
| --- | --- | --- |
| alarm_rule_id, tenant_id | UUID / tidak | Identitas aturan dan tenant sesi |
| rule_code, rule_name, rule_category, priority | string / tidak | Metadata konfigurasi |
| condition, action | object / tidak | Definisi tersimpan; legacy bisa belum memenuhi DSL |
| enabled | boolean / tidak | Status konfigurasi; bukan bukti engine berjalan |
| version | integer / tidak | Versi untuk expected_version berikutnya |
| created_at, updated_at | ISO 8601 UTC / tidak | Waktu audit server |
| created_by, updated_by | UUID / ya | Actor audit; null dimungkinkan pada data lama |
| deleted_at | ISO 8601 UTC / ya | Null pada record yang tersedia melalui API |
| deleted_by | UUID / ya | Actor penghapusan; API ini tidak menyediakan delete |

Contoh respons lengkap POST 201. GET detail dan PUT memakai bentuk data sama dengan
nilai tersimpan terbaru serta code 200; metadata request dibuat server untuk setiap request.

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "alarm_rule_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "22222222-2222-4222-8222-222222222222",
    "rule_code": "TEMP_EXAMPLE",
    "rule_name": "Contoh suhu",
    "rule_category": "STORAGE",
    "priority": "HIGH",
    "condition": {
      "field": "temperature",
      "op": "gt",
      "value": 10
    },
    "action": {
      "dsl_version": 1,
      "steps": [
        {
          "type": "alarm",
          "code": "TEMP_EXAMPLE",
          "severity": "HIGH"
        }
      ]
    },
    "enabled": false,
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "created_by": "33333333-3333-4333-8333-333333333333",
    "updated_by": "33333333-3333-4333-8333-333333333333",
    "deleted_at": null,
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

GET /api/v1/alarm-rules?offset=0&limit=20 mengembalikan 200, data berbentuk:

```json
{
  "items": [
    {
      "alarm_rule_id": "11111111-1111-4111-8111-111111111111",
      "tenant_id": "22222222-2222-4222-8222-222222222222",
      "rule_code": "TEMP_EXAMPLE",
      "rule_name": "Contoh suhu",
      "rule_category": "STORAGE",
      "priority": "HIGH",
      "condition": {
        "field": "temperature",
        "op": "gt",
        "value": 10
      },
      "action": {
        "dsl_version": 1,
        "steps": [
          {
            "type": "alarm",
            "code": "TEMP_EXAMPLE",
            "severity": "HIGH"
          }
        ]
      },
      "enabled": false,
      "version": 1,
      "created_at": "2026-09-11T03:00:00Z",
      "updated_at": "2026-09-11T03:00:00Z",
      "created_by": "33333333-3333-4333-8333-333333333333",
      "updated_by": "33333333-3333-4333-8333-333333333333",
      "deleted_at": null,
      "deleted_by": null
    }
  ],
  "offset": 0,
  "limit": 20
}
```

Bungkus data tersebut dengan envelope sukses di atas (code 200). GET list dan history
menerima offset integer 0..2147483647, default 0, serta limit integer 1..100, default 20;
keduanya opsional, tidak menerima null. Parameter lain tidak menyediakan filter/sort.
List urut created_at DESC lalu alarm_rule_id DESC; history version DESC. Tidak ada
total/cursor/has_more. Halaman habis mengembalikan items=[] dengan offset/limit diminta.
Pagination offset tidak menjamin snapshot stabil saat data berubah bersamaan.

GET /api/v1/alarm-rules/11111111-1111-4111-8111-111111111111/history?offset=0&limit=20
mengembalikan 200 dengan data berikut (contoh tepat setelah create):

```json
{
  "items": [
    {
      "revision_id": "55555555-5555-4555-8555-555555555555",
      "tenant_id": "22222222-2222-4222-8222-222222222222",
      "rule_id": "11111111-1111-4111-8111-111111111111",
      "version": 1,
      "captured_at": "2026-09-11T03:00:00Z",
      "snapshot": {
        "alarm_rule_id": "11111111-1111-4111-8111-111111111111",
        "tenant_id": "22222222-2222-4222-8222-222222222222",
        "rule_code": "TEMP_EXAMPLE",
        "rule_name": "Contoh suhu",
        "rule_category": "STORAGE",
        "priority": "HIGH",
        "condition": {
          "field": "temperature",
          "op": "gt",
          "value": 10
        },
        "action": {
          "dsl_version": 1,
          "steps": [
            {
              "type": "alarm",
              "code": "TEMP_EXAMPLE",
              "severity": "HIGH"
            }
          ]
        },
        "enabled": false,
        "version": 1,
        "created_at": "2026-09-11T03:00:00Z",
        "updated_at": "2026-09-11T03:00:00Z",
        "created_by": "33333333-3333-4333-8333-333333333333",
        "updated_by": "33333333-3333-4333-8333-333333333333",
        "deleted_at": null,
        "deleted_by": null
      }
    }
  ],
  "offset": 0,
  "limit": 20
}
```

Item history memiliki revision_id/tenant_id/rule_id UUID, version integer,
captured_at ISO 8601 UTC dan snapshot lengkap dengan schema AlarmRuleData di atas;
semua field item wajib dan tidak nullable. Nullable di dalam snapshot mengikuti
schema data. History hanya dapat dibaca jika aturan masih nondeleted dalam tenant.
Snapshot lama dipertahankan; bukan event untuk subscribe/replay.

### Error dan efek samping alarm

| HTTP | message | Kondisi / tindakan frontend |
| --- | --- | --- |
| 400 | Validation Error | Body, DSL, UUID atau query invalid; lihat errors field/message |
| 400 | Invalid alarm rule input | Validasi ulang service/DSL legacy gagal; perbaiki definisi sebelum enable |
| 401 | Invalid credentials or session | Bearer hilang, invalid atau sesi tidak aktif; alur autentikasi ulang |
| 403 | Required permission is not granted | Permission operasi tidak tersedia/dicabut |
| 404 | Rule not found | ID tidak ada, soft-deleted atau tenant lain; respons sama |
| 409 | Rule code already exists in this tenant | Kode sudah terpakai |
| 409 | Rule changed; reload before retrying | expected_version kedaluwarsa |
| 409 | Disable alarm rule before changing its definition | PUT definisi saat enabled |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database tidak tersedia |
| 500 | Internal Server Error | Kegagalan tak terduga |

Contoh konflik versi (bentuk error generik juga dipakai status lain):

```json
{
  "success": false,
  "code": 409,
  "message": "Rule changed; reload before retrying",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Pada 400 Validation Error, errors berisi object field/message seperti
`{"field":"body.expected_version","message":"Field required"}`; data null.
401 menyertakan WWW-Authenticate: Bearer. Validasi request dan autentikasi dapat
terjadi sebelum pengecekan permission/record; jangan bergantung pada urutan error
ketika satu request melanggar beberapa syarat sekaligus.

Mutasi dan pencatatan revisi dalam satu transaksi, tenant dan actor berasal dari
sesi; tidak menerima identitas audit dari browser. Tidak ada publikasi event,
alarm_log baru, evaluasi telemetry, notifikasi, perubahan paket ataupun recall.
`enabled=true` hanya konfigurasi yang disimpan. Engine, executor, validasi target/
template/transisi dan distribusi event masih TODO. Lihat [event catalog](event-catalog.md).


## Kontrak alarm telemetry HTTP

Status: tiga operasi tersedia. Ini kejadian alarm (`alarm_log`), berbeda dari
konfigurasi `/alarm-rules`. Tidak ada endpoint untuk membuat alarm, ingestion MQTT,
evaluator, menghapus/mengedit bukti, atau subscription realtime.

| Method/path | Tujuan | Permission | Body | Parameter |
| --- | --- | --- | --- | --- |
| GET /api/v1/alarms | Daftar kejadian berdasarkan status efektif | Alarm.Read | Tidak ada | Filter dan pagination opsional |
| GET /api/v1/alarms/{alarm_id} | Detail snapshot dan status efektif | Alarm.Read | Tidak ada | alarm_id UUID wajib |
| POST /api/v1/alarms/{alarm_id}/acknowledgment | Akui alarm dengan actor/waktu server | Alarm.Acknowledge | Wajib kosong; bahkan {} atau null ditolak | alarm_id UUID wajib; tanpa query |

Semua memakai `Authorization: Bearer <access_token>` dengan sid aktif; tenant/actor
berasal dari sesi, bukan parameter browser. `X-Correlation-ID` opsional (128 karakter
pertama diteruskan). Tidak memerlukan Content-Type karena tidak ada request body.
Respons JSON envelope 200, X-Request-ID, Cache-Control: no-store dan Pragma: no-cache.
Auth limiter sementara belum mencakup endpoint bisnis ini.

Alarm.Read dan Alarm.Acknowledge independen; izin mutasi dapat menerima snapshot
respons tanpa Read. Permission Alarm.Read, Alarm.Acknowledge, DeviceSession.Read dan DeviceSession.Close
sudah diprovision secara eksplisit ke role DEV_MAINTENANCE di tenant FSOS_DEV lokal.
Seed generik tetap tidak memperluas grant secara otomatis. Akun pada role lain perlu
provisioning terpilih; AlarmRule.* sendiri tidak memberikan izin Alarm.*. Lihat
[runbook provisioning](telemetry-permissions.md). User harus memiliki membership
aktif; tidak ada akun/password baru yang dibuat oleh provisioning ini.

### Query GET daftar

Semua opsional, tidak menerima literal null; kosong bukan pengganti parameter yang
dihilangkan. Tidak ada body, pencarian bebas atau sort kustom.

| Parameter | Tipe / default | Validasi / makna |
| --- | --- | --- |
| device_uuid | UUID / tidak ada | Identitas publik perangkat; perangkat tenant lain menghasilkan halaman kosong |
| acknowledged | string true atau false / tidak ada | Tepat huruf kecil; 1/0/yes ditolak; filter effective_acknowledged |
| since | datetime bertimezone / tidak ada | recorded_at >= since; ISO 8601 dengan Z/offset direkomendasikan |
| until | datetime bertimezone / tidak ada | recorded_at < until; jika keduanya ada harus since < until |
| offset | integer / 0 | 0..2147483647 |
| limit | integer / 20 | 1..100 |

Datetime diparsing Pydantic AwareDatetime; timestamp Unix yang dikenali parser juga
bisa diterima. Gunakan ISO 8601 untuk integrasi frontend; encode '+' pada offset
menjadi %2B. Timestamp tanpa timezone ditolak. Urutan recorded_at DESC lalu alarm_id
DESC. Parameter yang tidak didefinisikan tidak menyediakan filter tambahan.

Contoh request (Bearer header wajib untuk setiap operasi):

```http
GET /api/v1/alarms?acknowledged=false&since=2026-09-11T00:00:00Z&until=2026-09-12T00:00:00Z&offset=0&limit=20
Authorization: Bearer <access_token>
```

```http
GET /api/v1/alarms/11111111-1111-4111-8111-111111111111
Authorization: Bearer <access_token>
```

```http
POST /api/v1/alarms/11111111-1111-4111-8111-111111111111/acknowledgment
Authorization: Bearer <access_token>
```

### Respons dan status efektif

Semua field data berikut selalu hadir. Field nullable menggunakan JSON null.

| Field | Tipe / nullable | Makna |
| --- | --- | --- |
| alarm_id, tenant_id, device_uuid | UUID / tidak | Identitas alarm, tenant dan perangkat |
| alarm_code | string / tidak | Kode kejadian tersimpan |
| severity | string / tidak | Severity tersimpan; bukan enum tertutup karena bukti legacy |
| description | string / ya | Keterangan alarm |
| acknowledged | boolean / tidak | Snapshot awal immutable |
| recorded_at | ISO 8601 UTC / tidak | Waktu kejadian; dasar filter dan urutan |
| mqtt_message_id | UUID / ya | Referensi pesan sumber bila tersedia |
| created_at, updated_at | ISO 8601 UTC / tidak | Audit snapshot awal |
| created_by, updated_by, deleted_by | UUID / ya | Actor audit snapshot |
| deleted_at | ISO 8601 UTC / ya | Null; bukti tidak menyediakan soft delete |
| version | integer / tidak | Versi snapshot awal, tidak berubah saat acknowledge |
| effective_acknowledged | boolean / tidak | acknowledged OR bukti acknowledgment tersedia |
| acknowledgment_id | UUID / ya | Identitas bukti tambahan |
| acknowledged_at | ISO 8601 UTC / ya | Waktu acknowledgment tambahan |
| acknowledged_by | UUID / ya | Actor yang pertama mencatat bukti tambahan |

Contoh GET detail 200 sebelum acknowledgment:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "alarm_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "22222222-2222-4222-8222-222222222222",
    "device_uuid": "44444444-4444-4444-8444-444444444444",
    "alarm_code": "TEMP_EXAMPLE",
    "severity": "HIGH",
    "description": null,
    "acknowledged": false,
    "recorded_at": "2026-09-11T01:00:00Z",
    "mqtt_message_id": null,
    "created_at": "2026-09-11T01:00:00Z",
    "updated_at": "2026-09-11T01:00:00Z",
    "deleted_at": null,
    "created_by": null,
    "updated_by": null,
    "deleted_by": null,
    "version": 1,
    "effective_acknowledged": false,
    "acknowledgment_id": null,
    "acknowledged_at": null,
    "acknowledged_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

GET daftar memakai envelope sama dengan data `{items, offset, limit, next_offset}`.
items adalah array AlarmData lengkap di atas, offset/limit integer nonnull,
next_offset integer atau null (null bila tidak ada halaman berikutnya). Tidak ada
total/cursor. Contoh data halaman kosong untuk GET /api/v1/alarms?offset=100&limit=20:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [],
    "offset": 100,
    "limit": 20,
    "next_offset": null
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

POST acknowledgment 200 memakai schema detail yang sama. Contoh hasil:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "alarm_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "22222222-2222-4222-8222-222222222222",
    "device_uuid": "44444444-4444-4444-8444-444444444444",
    "alarm_code": "TEMP_EXAMPLE",
    "severity": "HIGH",
    "description": null,
    "acknowledged": false,
    "recorded_at": "2026-09-11T01:00:00Z",
    "mqtt_message_id": null,
    "created_at": "2026-09-11T01:00:00Z",
    "updated_at": "2026-09-11T01:00:00Z",
    "deleted_at": null,
    "created_by": null,
    "updated_by": null,
    "deleted_by": null,
    "version": 1,
    "effective_acknowledged": true,
    "acknowledgment_id": "66666666-6666-4666-8666-666666666666",
    "acknowledged_at": "2026-09-11T03:00:00Z",
    "acknowledged_by": "33333333-3333-4333-8333-333333333333"
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Frontend harus menggunakan effective_acknowledged untuk badge/filter. acknowledged,
version dan updated_at snapshot awal tetap sama. Snapshot impor acknowledged=true
bisa menghasilkan effective_acknowledged=true dengan tiga field acknowledgment null;
UI jangan mengarang actor/waktu yang tidak diketahui.

Retry POST mengembalikan bukti pertama, tanpa mengganti actor/waktu atau menambah
row; tidak membutuhkan expected_version/idempotency key. Alarm yang sudah diakui
pada snapshot impor tidak dibuatkan bukti baru. Parent dikunci dan insert bukti
committed sebelum respons; gagal berarti transaksi rollback. Untuk insert baru,
recorded_at masa depan ditolak. Perangkat yang kemudian nonaktif tidak menyembunyikan
bukti historis; actor/tenant pemanggil tetap harus aktif. Pagination bukan snapshot
stabil lintas halaman; acknowledgment baru dapat menggeser hasil filter.

### Error dan efek samping

| HTTP | message | Penyebab |
| --- | --- | --- |
| 400 | Validation Error | UUID/filter/pagination tidak valid; errors berisi field/message |
| 400 | Request body must be empty | POST membawa body, termasuk {} atau null |
| 400 | Invalid alarm filters or observation time | Rentang since/until terbalik/sama atau alarm masa depan saat insert acknowledgment |
| 401 | Invalid credentials or session | Token hilang/invalid atau sesi tidak aktif; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted | Permission operasi tidak tersedia/dicabut |
| 404 | Telemetry record not found | Detail/POST untuk ID hilang atau tenant lain, pesan sama |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database tidak tersedia |
| 500 | Internal Server Error | Kegagalan tak terduga |

Contoh error permission:

```json
{
  "success": false,
  "code": 403,
  "message": "Required permission is not granted",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Error validasi memiliki data null dan errors seperti
`[{"field":"query.limit","message":"Input should be less than or equal to 100"}]`.
Urutan validasi/auth/permission tidak dijamin ketika beberapa syarat dilanggar.

GET tidak memutasi data. POST hanya menambah alarm_acknowledgment secara atomik;
tidak menulis ulang alarm_log, menonaktifkan alarm rule, menjalankan aksi perangkat,
atau menerbitkan event/notifikasi. Browser dapat memuat ulang daftar setelah POST;
WebSocket, event acknowledgment dan ingestion masih rencana. Lihat
[event catalog](event-catalog.md) dan [service lifecycle](telemetry-lifecycle.md).


## Kontrak sesi perangkat HTTP

Status: tiga operasi tersedia. Ini sesi koneksi perangkat, berbeda dari sesi login
`/auth/*`. Semua membutuhkan bearer access token dengan sid aktif; actor dan tenant
dari sesi login. Tidak ada create/delete sesi, ingestion atau reconnect otomatis.

| Method/path | Tujuan | Permission | Body | Path/query |
| --- | --- | --- | --- | --- |
| GET /api/v1/device-sessions | Daftar sesi berdasarkan status efektif | DeviceSession.Read | Tidak ada | Filter/pagination opsional |
| GET /api/v1/device-sessions/{session_id} | Detail snapshot dan status akhir efektif | DeviceSession.Read | Tidak ada | session_id UUID wajib |
| POST /api/v1/device-sessions/{session_id}/end | Catat akhir sesi immutable | DeviceSession.Close | disconnected_at wajib | session_id UUID wajib; tanpa query |

Header wajib `Authorization: Bearer <access_token>`; POST memakai
`Content-Type: application/json`. `X-Correlation-ID` opsional, 128 karakter pertama
diteruskan. Respons JSON envelope, X-Request-ID, Cache-Control: no-store,
Pragma: no-cache. Limiter auth sementara tidak mencakup endpoint ini.
Read dan Close independen: Close saja boleh menerima snapshot hasil mutasi tanpa
Read. Role DEV_MAINTENANCE lokal kini mempunyai keduanya melalui provisioning
administratif eksplisit; role lain tidak otomatis berubah.

### Query dan payload

GET list: semua parameter opsional; literal null/kosong bukan pengganti parameter
yang dihilangkan. Parameter lain tidak menyediakan filter/sort tambahan.

| Parameter | Tipe / default | Validasi / arti |
| --- | --- | --- |
| device_uuid | UUID / tidak ada | UUID publik perangkat; tenant lain menghasilkan items kosong |
| is_open | string true/false / tidak ada | Tepat huruf kecil; filter status efektif; 1/0/yes ditolak |
| since | datetime bertimezone / tidak ada | connected_at >= since |
| until | datetime bertimezone / tidak ada | connected_at < until; since < until jika keduanya ada |
| offset | integer / 0 | 0..2147483647 |
| limit | integer / 20 | 1..100 |

Datetime query mengikuti AwareDatetime Pydantic (termasuk timestamp Unix yang
parser kenali); gunakan ISO 8601 dengan Z/offset dan encode '+' menjadi %2B.
Tanpa timezone ditolak. Urutan connected_at DESC lalu session_id DESC. Filter
waktu berdasarkan waktu mulai sesi, bukan recorded_at atau disconnected_at.

POST hanya menerima field `disconnected_at`: string ISO 8601 bertimezone dengan
pemisah T, wajib dan tidak nullable. Timestamp angka, body kosong, field tambahan
(tenant/actor/expected_version) dan timestamp tanpa timezone ditolak.
Waktu dinormalisasi ke UTC, harus >= connected_at. Penutupan baru tidak boleh di
masa depan. Tidak membutuhkan expected_version karena parent immutable.

Contoh request:

```http
GET /api/v1/device-sessions?is_open=true&since=2026-09-11T00:00:00Z&until=2026-09-12T00:00:00Z&offset=0&limit=20
Authorization: Bearer <access_token>
```

```http
GET /api/v1/device-sessions/11111111-1111-4111-8111-111111111111
Authorization: Bearer <access_token>
```

POST /api/v1/device-sessions/11111111-1111-4111-8111-111111111111/end
(dengan kedua header wajib di atas):

```json
{
  "disconnected_at": "2026-09-11T02:00:00Z"
}
```

### Respons dan perilaku finalisasi

Ketiga operasi sukses mengembalikan 200. Semua field data berikut selalu hadir;
nullable berarti JSON null diizinkan.

| Field | Tipe / nullable | Penjelasan |
| --- | --- | --- |
| session_id, tenant_id, device_uuid | UUID / tidak | Identitas sesi, tenant dan perangkat |
| connected_at | ISO 8601 UTC / tidak | Awal sesi, dasar filter waktu |
| disconnected_at | ISO 8601 UTC / ya | Snapshot akhir sesi asli, tidak berubah oleh POST |
| ip_address | string / ya | Alamat INET snapshot perangkat, termasuk prefix bila tersimpan |
| firmware | string / ya | Versi firmware snapshot |
| recorded_at | ISO 8601 UTC / tidak | Waktu pencatatan bukti sumber |
| mqtt_message_id | UUID / ya | Referensi pesan sumber |
| created_at, updated_at | ISO 8601 UTC / tidak | Waktu audit snapshot awal |
| created_by, updated_by, deleted_by | UUID / ya | Actor audit snapshot |
| deleted_at | ISO 8601 UTC / ya | Null, tidak ada soft delete bukti |
| version | integer / tidak | Versi snapshot awal, tidak naik karena finalisasi |
| effective_disconnected_at | ISO 8601 UTC / ya | Akhir snapshot asli atau bukti device_session_end |
| is_open | boolean / tidak | true jika effective_disconnected_at null |
| session_end_id | UUID / ya | ID bukti tambahan; null pada sesi terbuka atau snapshot impor lengkap |

Contoh GET detail sebelum penutupan:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "session_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "22222222-2222-4222-8222-222222222222",
    "device_uuid": "33333333-3333-4333-8333-333333333333",
    "connected_at": "2026-09-11T01:00:00Z",
    "disconnected_at": null,
    "ip_address": "192.0.2.1",
    "firmware": "example-v1",
    "recorded_at": "2026-09-11T01:00:00Z",
    "mqtt_message_id": null,
    "created_at": "2026-09-11T01:00:00Z",
    "updated_at": "2026-09-11T01:00:00Z",
    "deleted_at": null,
    "created_by": null,
    "updated_by": null,
    "deleted_by": null,
    "version": 1,
    "effective_disconnected_at": null,
    "is_open": true,
    "session_end_id": null
  },
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh POST 200 setelah penutupan; GET detail berikutnya memakai data sama:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "session_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "22222222-2222-4222-8222-222222222222",
    "device_uuid": "33333333-3333-4333-8333-333333333333",
    "connected_at": "2026-09-11T01:00:00Z",
    "disconnected_at": null,
    "ip_address": "192.0.2.1",
    "firmware": "example-v1",
    "recorded_at": "2026-09-11T01:00:00Z",
    "mqtt_message_id": null,
    "created_at": "2026-09-11T01:00:00Z",
    "updated_at": "2026-09-11T01:00:00Z",
    "deleted_at": null,
    "created_by": null,
    "updated_by": null,
    "deleted_by": null,
    "version": 1,
    "effective_disconnected_at": "2026-09-11T02:00:00Z",
    "is_open": false,
    "session_end_id": "55555555-5555-4555-8555-555555555555"
  },
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

GET list memakai envelope sama dengan data `{items, offset, limit, next_offset}`.
items array DeviceSessionData lengkap di atas; offset/limit integer nonnull,
next_offset integer atau null bila halaman berikutnya tidak ada. Tidak ada total
atau cursor. Contoh halaman kosong:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [],
    "offset": 0,
    "limit": 20,
    "next_offset": null
  },
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Frontend memakai is_open/effective_disconnected_at; snapshot disconnected_at bisa
tetap null meskipun sesi sudah ditutup. Snapshot impor lengkap memiliki is_open=false
namun session_end_id null. Jangan menganggap null ID bukti berarti sesi terbuka.
POST ulang dengan waktu instant yang sama (meski offset berbeda) mengembalikan
bukti yang sama; waktu berbeda menghasilkan 409. Ini juga berlaku untuk snapshot
impor lengkap. Timestamp/actor audit bukti pertama tidak ditimpa.

Perangkat nonaktif tetap dapat memiliki bukti historis yang terbaca. Penutupan
satu sesi tidak menetapkan perangkat offline secara global karena bisa ada sesi
lain. Reconnect harus membuka session_id baru melalui ingestion yang masih TODO.
Pagination offset tidak stabil terhadap perubahan data/status di antara halaman.

### Error dan efek samping

| HTTP | message | Kondisi |
| --- | --- | --- |
| 400 | Validation Error | Body, UUID, timezone atau query tidak valid; errors field/message |
| 400 | Invalid session filters or disconnection time | Rentang since/until invalid, akhir sebelum awal atau penutupan baru di masa depan |
| 401 | Invalid credentials or session | Bearer hilang/invalid atau sesi login tidak aktif; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted | Permission operasi hilang/dicabut |
| 404 | Telemetry record not found | ID hilang atau tenant lain; respons sama |
| 409 | Session already ended at a different time | Sesi sudah ditutup dengan instant berbeda |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database tidak tersedia |
| 500 | Internal Server Error | Kegagalan tak terduga |

Contoh konflik:

```json
{
  "success": false,
  "code": 409,
  "message": "Session already ended at a different time",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "44444444-4444-4444-8444-444444444444",
    "correlation_id": "44444444-4444-4444-8444-444444444444",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

400 Validation Error memiliki data null dan errors seperti
`[{"field":"body.disconnected_at","message":"Field required"}]`.
Urutan validasi/auth/permission tidak dijamin bila beberapa syarat dilanggar.

GET tidak memutasi. POST mengunci parent dan menambah satu device_session_end
beserta actor audit dari sesi login dalam transaksi yang selesai sebelum respons.
Rollback membatalkan bukti bila gagal. Tidak mengubah device_session, tidak
mengirim device.disconnected atau notifikasi, dan tidak membuka koneksi/reconnect.
Lihat [event catalog](event-catalog.md) dan [lifecycle](telemetry-lifecycle.md).


## Kontrak master device dan binding

Status: sepuluh operasi aktif: lima operasi CRUD perangkat dengan sinkronisasi
asset `DEVICE`, dan lima operasi binding perangkat GPS aktif ke kendaraan aktif.
Binding adalah data administratif untuk mengaitkan perangkat telemetry kendaraan;
belum menerbitkan event runtime atau GPS log.

| Method/path | Tujuan | Permission | Body | Path/query |
| --- | --- | --- | --- | --- |
| GET /api/v1/devices | Daftar perangkat | Device.Read | Tidak ada | offset/limit/zone_id |
| POST /api/v1/devices | Buat perangkat | Device.Write | DeviceInput | Tidak ada |
| GET /api/v1/devices/{identifier} | Detail perangkat | Device.Read | Tidak ada | identifier UUID perangkat wajib |
| PUT /api/v1/devices/{identifier} | Ganti definisi perangkat | Device.Write | DeviceInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/devices/{identifier} | Soft delete perangkat | Device.Delete | Tidak ada | identifier UUID; expected_version query wajib |
| GET /api/v1/device-bindings | Daftar binding perangkat-kendaraan | Device.Read | Tidak ada | offset/limit/device_id/vehicle_id |
| POST /api/v1/device-bindings | Buat binding | Device.Write | DeviceBindingInput | Tidak ada |
| GET /api/v1/device-bindings/{identifier} | Detail binding | Device.Read | Tidak ada | identifier UUID binding wajib |
| PUT /api/v1/device-bindings/{identifier} | Ganti binding | Device.Write | DeviceBindingInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/device-bindings/{identifier} | Soft delete binding | Device.Delete | Tidak ada | identifier UUID; expected_version query wajib |

Semua endpoint membutuhkan `Authorization: Bearer <access_token>`; tenant/operator dari sesi.
POST/PUT wajib `Content-Type: application/json`; DELETE menolak body.
Respons memakai `JSON envelope`, `X-Request-ID`, `Cache-Control: no-store`, `Pragma: no-cache`.

### Payload

| Field | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| zone_id | UUID / tidak / ya | Opsi storage zone aktif, tenant dan nondeleted; default null |
| device_uuid | UUID / tidak / ya | Dipakai sebagai identitas publik; bila kosong akan digenerate |
| device_name | string / ya / tidak | 1..200 |
| device_type | string / ya / tidak | 1..50 |
| firmware | string / tidak / ya | Maksimal 100 |
| hardware | string / tidak / ya | Maksimal 100 |
| mqtt_topic | string / tidak / ya | Maksimal 512 |
| status | string enum / tidak / tidak | REGISTERED/ACTIVE/INACTIVE; default REGISTERED |
| last_online | datetime UTC / tidak / ya | ISO 8601 UTC |

Semua field input tambahan ditolak. PUT mengganti penuh definisi sehingga field optional
yang tidak dikirim akan memakai default sesuai skema, bukan mempertahankan nilai lama.

| Field tambahan respons | Tipe / nullable | Makna |
| --- | --- | --- |
| device_id | UUID / tidak | ID internal |
| tenant_id | UUID / tidak | Tenant sesi |
| version | integer / tidak | Create 1; naik 1 pada PUT/DELETE |
| created_at, updated_at | ISO 8601 UTC / tidak | Audit server |
| created_by, updated_by | UUID / ya | Actor audit; null pada data lama |
| deleted_at | ISO 8601 UTC / ya | Null pada GET biasa; terisi saat DELETE sukses |
| deleted_by | UUID / ya | Actor penghapusan, nonnull saat DELETE |

Query list: `offset` 0..2147483647 (default 0), `limit` 1..100 (default 20),
`zone_id` opsional. Omit parameter tidak dipakai; null literal tidak selalu setara
dengan dihapus. Urutan `created_at DESC, device_id DESC`; query tidak snapshot.

### Payload binding

| Field | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| device_id | UUID / ya / tidak | Device aktif, tenant sama, nondeleted, `status=ACTIVE`, dan `device_type=GPS` |
| vehicle_id | UUID / ya / tidak | Vehicle aktif, tenant sama, nondeleted, dan `status=ACTIVE` |
| expected_version | integer / hanya PUT / tidak | 1..2147483647; wajib pada PUT body |

Field tambahan ditolak. Create menghasilkan `binding_id` baru, `tenant_id` dari
sesi, audit server dan `version=1`. Respons binding berisi `binding_id`,
`tenant_id`, `device_id`, `vehicle_id`, `version`, `created_at`, `updated_at`,
`created_by`, `updated_by`, `deleted_at` dan `deleted_by`.

Query list binding: `offset` 0..2147483647 (default 0), `limit` 1..100
(default 20), `device_id` opsional, `vehicle_id` opsional. Urutan
`created_at DESC, binding_id DESC`; query tidak snapshot.

### Contoh request

POST `/api/v1/devices`:

```json
{
  "device_name": "THERMAL_GATE_A1",
  "device_type": "TEMPERATURE_GATEWAY",
  "firmware": "fw-1.0.0",
  "hardware": "rev-b",
  "mqtt_topic": "fsos/site/gw/a1",
  "status": "ACTIVE",
  "last_online": "2026-09-11T08:00:00Z"
}
```

PUT `/api/v1/devices/22222222-2222-4222-8222-222222222222`:

```json
{
  "device_name": "THERMAL_GATE_A1",
  "device_type": "TEMPERATURE_GATEWAY",
  "status": "ACTIVE",
  "expected_version": 1
}
```

GET `/api/v1/devices?zone_id=33333333-3333-4333-8333-333333333333&offset=0&limit=20`

DELETE `/api/v1/devices/22222222-2222-4222-8222-222222222222?expected_version=2`

POST `/api/v1/device-bindings`:

```json
{
  "device_id": "22222222-2222-4222-8222-222222222222",
  "vehicle_id": "55555555-5555-4555-8555-555555555555"
}
```

PUT `/api/v1/device-bindings/66666666-6666-4666-8666-666666666666`:

```json
{
  "device_id": "22222222-2222-4222-8222-222222222222",
  "vehicle_id": "55555555-5555-4555-8555-555555555555",
  "expected_version": 1
}
```

GET `/api/v1/device-bindings?vehicle_id=55555555-5555-4555-8555-555555555555&offset=0&limit=20`

DELETE `/api/v1/device-bindings/66666666-6666-4666-8666-666666666666?expected_version=2`

### Error dan efek samping

| HTTP | message | Kondisi |
| --- | --- | --- |
| 400 | Validation Error | UUID/body/query invalid |
| 400 | Invalid location input | Validasi service gagal |
| 400 | Request body must be empty | DELETE membawa body |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi mati |
| 403 | Required permission is not granted | Permission device belum tersedia/dicabut |
| 404 | Location not found | ID hilang, deleted atau tenant lain |
| 404 | Device binding not found | Binding hilang, deleted atau tenant lain |
| 409 | Active parent storage zone in this tenant required | zone_id inaktif/tipe/tenant lain |
| 409 | Active GPS device in this tenant required | Binding memakai device nonaktif, bukan GPS, deleted atau tenant lain |
| 409 | Active vehicle in this tenant required | Binding memakai vehicle nonaktif, deleted atau tenant lain |
| 409 | Device already bound to this vehicle in this tenant | Pair device-vehicle aktif sudah ada |
| 409 | Parent location cannot be changed | PUT mencoba mengganti zone_id |
| 409 | Location changed; reload before retrying | expected_version kedaluwarsa |
| 409 | Record changed; reload before retrying | DELETE dengan expected_version lama |
| 409 | Device binding changed; reload before retrying | expected_version binding kedaluwarsa |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database tidak tersedia |
| 500 | Internal Server Error | Kegagalan tak terduga |

Soft delete device tidak cascade dan tidak menghapus bukti lain. Row fisik tetap ada,
nilai `device_code` tidak tercadangkan khusus pada perangkat karena identitas berbasis
`device_uuid` dan UUID internal. Soft delete device atau vehicle ditolak bila masih
direferensikan binding aktif. Soft delete binding hanya memutus relasi administratif;
tidak menghapus device, vehicle, gps_log, delivery, movement, event_log atau asset
registry. Write/delete binding tidak menulis event runtime.


## Kontrak master kitchen storage zone

Status: 15 operasi aktif untuk data operasional dasar docs/06. Alur frontend:
buat/pilih kitchen, buat storage pada kitchen tersebut, lalu buat zone pada storage.
Ini belum menyediakan receiving/stok, movement atau hard delete.

Semua operasi wajib `Authorization: Bearer <access_token>` dengan sesi aktif dan
tenant/actor dari sesi. POST/PUT wajib `Content-Type: application/json`.
`X-Correlation-ID` opsional (128 karakter pertama diteruskan). Respons JSON envelope,
X-Request-ID, Cache-Control: no-store, Pragma: no-cache. Limiter auth sementara belum
mencakup endpoint bisnis ini. Tenant/audit/ID/version tidak boleh ditulis oleh browser.

| Method/path | Tujuan | Permission | Body | Path/query |
| --- | --- | --- | --- | --- |
| GET /api/v1/kitchens | Daftar kitchen | Kitchen.Read | Tidak ada | offset/limit |
| POST /api/v1/kitchens | Buat kitchen dan registry | Kitchen.Write | KitchenInput | Tidak ada |
| GET /api/v1/kitchens/{identifier} | Detail kitchen | Kitchen.Read | Tidak ada | identifier UUID kitchen wajib |
| PUT /api/v1/kitchens/{identifier} | Ganti definisi kitchen | Kitchen.Write | KitchenInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/kitchens/{identifier} | Hapus secara administratif | Kitchen.Delete | Tidak ada | identifier UUID; expected_version query wajib |
| GET /api/v1/storages | Daftar storage | Storage.Read | Tidak ada | kitchen_id opsional; offset/limit |
| POST /api/v1/storages | Buat storage dan registry | Storage.Write | StorageInput | Tidak ada |
| GET /api/v1/storages/{identifier} | Detail storage | Storage.Read | Tidak ada | identifier UUID storage wajib |
| PUT /api/v1/storages/{identifier} | Ganti definisi storage | Storage.Write | StorageInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/storages/{identifier} | Hapus secara administratif | Storage.Delete | Tidak ada | identifier UUID; expected_version query wajib |
| GET /api/v1/storage-zones | Daftar zone | StorageZone.Read | Tidak ada | storage_id opsional; offset/limit |
| POST /api/v1/storage-zones | Buat zone | StorageZone.Write | ZoneInput | Tidak ada |
| GET /api/v1/storage-zones/{identifier} | Detail zone | StorageZone.Read | Tidak ada | identifier UUID zone wajib |
| PUT /api/v1/storage-zones/{identifier} | Ganti definisi zone | StorageZone.Write | ZoneInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/storage-zones/{identifier} | Hapus secara administratif | StorageZone.Delete | Tidak ada | identifier UUID; expected_version query wajib |

Read/Write/Delete setiap modul independen. Write saja dapat menerima snapshot hasil mutasi;
pengecekan induk tidak memerlukan Read induk. Sembilan permission telah diberikan secara
eksplisit ke role DEV_MAINTENANCE lokal sebagai kebutuhan minimum API ini. Role lain
tidak otomatis mendapat akses. AssetRegistry.Sync tidak diperlukan untuk sinkronisasi
internal saat menulis kitchen/storage. DELETE soft delete tersedia sesuai kontrak di bawah; PATCH, restore dan pemindahan induk belum tersedia.

### Payload input

Semua field tambahan ditolak. String di-trim, NUL/Unicode invalid ditolak; boolean
tidak dikonversi menjadi angka. Decimal menerima angka JSON atau string numerik finite;
frontend sebaiknya mengirim string untuk mempertahankan presisi. Null hanya pada
field bertanda nullable. Default di bawah berlaku juga pada PUT: PUT mengganti seluruh
definisi, jadi field opsional yang dihilangkan direset ke default, bukan dipertahankan.

| KitchenInput | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| kitchen_code | string / ya / tidak | 1..50 karakter; unik case-sensitive per tenant termasuk kode record soft-deleted |
| kitchen_name | string / ya / tidak | 1..200 karakter |
| latitude | decimal / tidak / ya | -90..90, maksimal 6 desimal; default null |
| longitude | decimal / tidak / ya | -180..180, maksimal 6 desimal; default null |
| address | string / tidak / ya | Default null; tidak ada batas panjang aplikasi |
| capacity | integer / tidak / ya | 0..2147483647; string angka/bool ditolak; default null |
| status | string enum / tidak / tidak | ACTIVE atau INACTIVE; default ACTIVE |

Latitude/longitude harus keduanya bernilai atau keduanya null. Lokasi PostGIS
kitchen dihitung dari pasangan tersebut; field location tidak diterima/tidak dikirim.

| StorageInput | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| kitchen_id | UUID / ya / tidak | Induk nondeleted ACTIVE dalam tenant; tidak bisa diganti lewat PUT |
| storage_code | string / ya / tidak | 1..50; unik case-sensitive per kitchen termasuk soft-deleted |
| storage_name | string / ya / tidak | 1..200 |
| storage_type | string enum / ya / tidak | COLD_STORAGE, FREEZER, DRY_STORAGE |
| temperature_min | decimal / tidak / ya | -9999.99..9999.99, maksimal 2 desimal; default null |
| temperature_max | decimal / tidak / ya | Batas sama; default null; jika keduanya terisi min <= max |
| latitude, longitude | decimal / tidak / ya | Rentang/pasangan/presisi seperti kitchen; default null |
| status | string enum / tidak / tidak | ACTIVE/INACTIVE, default ACTIVE |

Satu batas suhu boleh null. Angka suhu contoh di bawah hanya ilustrasi konfigurasi,
bukan rekomendasi keamanan pangan. Lokasi storage disimpan sebagai Point SRID 4326,
direspons sebagai latitude/longitude (maksimal 6 desimal), bukan WKB internal.

| ZoneInput | Tipe / required / nullable | Validasi |
| --- | --- | --- |
| storage_id | UUID / ya / tidak | Storage dan kitchen induknya nondeleted ACTIVE dalam tenant; tidak bisa diganti lewat PUT |
| zone_code | string / ya / tidak | 1..50; unik case-sensitive per storage termasuk soft-deleted |
| zone_name | string / ya / tidak | 1..200 |

Semua PUT menambahkan expected_version integer wajib, tidak nullable, 1..2147483647;
string angka dan boolean ditolak. POST tidak menerima expected_version.

### Contoh request per modul

Contoh POST /api/v1/kitchens:

```json
{
  "kitchen_code": "KITCHEN_EXAMPLE",
  "kitchen_name": "Dapur contoh",
  "latitude": "-6.200000",
  "longitude": "106.800000",
  "address": null,
  "capacity": 200,
  "status": "ACTIVE"
}
```

Contoh PUT /api/v1/kitchens/11111111-1111-4111-8111-111111111111:

```json
{
  "kitchen_code": "KITCHEN_EXAMPLE",
  "kitchen_name": "Dapur diperbarui",
  "latitude": "-6.200000",
  "longitude": "106.800000",
  "address": null,
  "capacity": 200,
  "status": "ACTIVE",
  "expected_version": 1
}
```

Contoh POST /api/v1/storages:

```json
{
  "kitchen_id": "11111111-1111-4111-8111-111111111111",
  "storage_code": "COLD_EXAMPLE",
  "storage_name": "Penyimpanan contoh",
  "storage_type": "COLD_STORAGE",
  "temperature_min": "1.50",
  "temperature_max": "5.00",
  "latitude": null,
  "longitude": null,
  "status": "ACTIVE"
}
```

Contoh PUT /api/v1/storages/22222222-2222-4222-8222-222222222222:

```json
{
  "kitchen_id": "11111111-1111-4111-8111-111111111111",
  "storage_code": "COLD_EXAMPLE",
  "storage_name": "Penyimpanan diperbarui",
  "storage_type": "COLD_STORAGE",
  "temperature_min": "1.50",
  "temperature_max": "5.00",
  "latitude": null,
  "longitude": null,
  "status": "ACTIVE",
  "expected_version": 1
}
```

Contoh POST /api/v1/storage-zones:

```json
{
  "storage_id": "22222222-2222-4222-8222-222222222222",
  "zone_code": "RACK_A",
  "zone_name": "Rak A"
}
```

Contoh PUT /api/v1/storage-zones/33333333-3333-4333-8333-333333333333:

```json
{
  "storage_id": "22222222-2222-4222-8222-222222222222",
  "zone_code": "RACK_A",
  "zone_name": "Rak diperbarui",
  "expected_version": 1
}
```

Contoh GET tanpa body (semuanya memakai header Bearer di atas):

```http
GET /api/v1/kitchens?offset=0&limit=20
GET /api/v1/kitchens/11111111-1111-4111-8111-111111111111
GET /api/v1/storages?kitchen_id=11111111-1111-4111-8111-111111111111&offset=0&limit=20
GET /api/v1/storages/22222222-2222-4222-8222-222222222222
GET /api/v1/storage-zones?storage_id=22222222-2222-4222-8222-222222222222&offset=0&limit=20
GET /api/v1/storage-zones/33333333-3333-4333-8333-333333333333
```

### Respons sukses

POST 201, GET/PUT 200. data detail/mutasi berisi seluruh field definisi di atas,
termasuk opsional yang null, ditambah field berikut (semuanya selalu hadir):

| Field tambahan | Tipe / nullable | Makna |
| --- | --- | --- |
| kitchen_id / storage_id / zone_id | UUID / tidak | ID sumber sesuai modul, bukan asset_uuid registry |
| tenant_id | UUID / tidak | Tenant sesi |
| version | integer / tidak | 1 pada create; naik satu setiap PUT, termasuk definisi identik |
| created_at, updated_at | ISO 8601 UTC / tidak | Waktu audit server |
| created_by, updated_by | UUID / ya | Actor audit; null mungkin pada data lama |
| deleted_at | ISO 8601 UTC / ya | Null pada hasil biasa; timestamp terisi pada respons DELETE |
| deleted_by | UUID / ya | Actor penghapusan; terisi pada respons DELETE |

Tipe respons mengikuti input kecuali decimal dikirim sebagai **string** dan
status/storage_type berupa string terbuka agar record legacy tetap dapat dibaca.
Record legacy belum tentu lolos validasi saat ditulis kembali. Latitude/longitude
storage diproyeksikan sampai enam desimal; tidak ada field location mentah.

Contoh respons POST kitchen 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "kitchen_code": "KITCHEN_EXAMPLE",
    "kitchen_name": "Dapur contoh",
    "latitude": "-6.200000",
    "longitude": "106.800000",
    "address": null,
    "capacity": 200,
    "status": "ACTIVE",
    "kitchen_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "deleted_at": null,
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh respons POST storage 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "kitchen_id": "11111111-1111-4111-8111-111111111111",
    "storage_code": "COLD_EXAMPLE",
    "storage_name": "Penyimpanan contoh",
    "storage_type": "COLD_STORAGE",
    "temperature_min": "1.50",
    "temperature_max": "5.00",
    "latitude": null,
    "longitude": null,
    "status": "ACTIVE",
    "storage_id": "22222222-2222-4222-8222-222222222222",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "deleted_at": null,
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh respons POST zone 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "storage_id": "22222222-2222-4222-8222-222222222222",
    "zone_code": "RACK_A",
    "zone_name": "Rak A",
    "zone_id": "33333333-3333-4333-8333-333333333333",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "deleted_at": null,
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

GET detail dan PUT memakai envelope/data sesuai modul yang sama dengan code 200;
PUT mengembalikan version dan audit terbaru. Simpan version respons sebelum edit berikutnya.

### Pagination, status dan induk

GET list menerima offset integer 0..2147483647 default 0, limit integer 1..100 default
20. Filter induk kitchen_id/storage_id berupa UUID opsional. Hilangkan parameter
jika tidak digunakan, bukan string null. Filter ID induk tenant lain/missing memberi
items kosong. Tidak ada filter status/search/sort kustom. Hanya nondeleted dalam
tenant; kitchen/storage ACTIVE dan INACTIVE sama-sama dapat dibaca. Urutan
created_at DESC lalu ID DESC. Data list: items array snapshot modul, offset/limit
integer, next_offset integer atau null bila tidak ada halaman berikutnya. Tidak ada
total/cursor; perpindahan halaman tidak menjamin snapshot stabil saat ada mutasi.

Contoh list kosong (berlaku pada ketiga collection):

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [],
    "offset": 0,
    "limit": 20,
    "next_offset": null
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Mengubah status kitchen/storage menjadi INACTIVE tidak menghapus atau mengubah status
anak. Pembacaan anak tetap tersedia; create/update storage memerlukan kitchen aktif,
dan create/update zone memerlukan storage serta kitchen aktif. Aktifkan kembali induk
jika perlu memperbarui anak. Referensi induk ditolak dengan pesan sama jika tidak ada,
lintas tenant, deleted atau inactive. Kode tetap dimiliki record lama walaupun inactive.
Pemindahan induk tidak disediakan: PUT storage/zone wajib mempertahankan ID induk.

### Error, transaksi dan efek samping

| HTTP | message | Penyebab/tindakan |
| --- | --- | --- |
| 400 | Validation Error | Body, UUID, query, tipe, koordinat atau suhu invalid; errors field/message |
| 400 | Invalid location input | Validasi ulang input service gagal |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi tidak aktif; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted | Permission modul/operasi hilang atau dicabut |
| 404 | Location not found | Detail/update record tidak ada, deleted atau tenant lain |
| 409 | Location code already exists in this scope | Kode sudah terpakai pada tenant/induk |
| 409 | Location changed; reload before retrying | expected_version kedaluwarsa; reload dan tinjau perubahan |
| 409 | Active parent location in this tenant required | Induk tidak tersedia/aktif dalam tenant |
| 409 | Parent location cannot be changed | PUT mencoba memindahkan induk |
| 409 | Parent location unavailable | Constraint referensi database gagal |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database gagal |
| 500 | Internal Server Error | Kegagalan tak terduga |

Pengecekan parent pada write dapat mendahului lookup record; jika beberapa syarat
invalid jangan bergantung pada urutan error. Contoh konflik version:

```json
{
  "success": false,
  "code": 409,
  "message": "Location changed; reload before retrying",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Pada 400 Validation Error, data null dan errors seperti
`[{"field":"body.kitchen_name","message":"Field required"}]`.

Kitchen/storage disimpan bersama proyeksi digital_asset dalam satu transaksi;
rollback membatalkan keduanya. ID registry tetap terpisah dari ID sumber. Zone tidak
membuat digital_asset karena belum menjadi tipe registry. Tidak membuat relationship,
movement, event_log, notifikasi, alarm atau data receiving. Tidak ada publisher/event
baru. Audit/version sumber dicatat, tetapi history revisi khusus master ini belum ada.
POST tidak memiliki idempotency key; retry kode yang sudah berhasil disimpan memberi
409. Gunakan daftar/detail untuk meninjau hasil bila respons sebelumnya terputus.

Akses runtime storage/zone diperluas hanya untuk insert dan kolom update definisi/audit
minimum, tanpa hard delete/DDL atau perubahan induk. Lihat
[runbook akses lokasi](location-permissions.md) dan [event catalog](event-catalog.md).


## Kontrak supplier bahan dan relasi

Status: 15 operasi tersedia untuk persiapan receiving. Buat/pilih supplier dan
bahan baku, lalu daftarkan pasangan supplier-material. Satu bahan dapat memiliki
beberapa supplier dan satu supplier dapat memasok beberapa bahan. Relasi ini
adalah daftar pemasok bahan, bukan saldo stok atau bukti penerimaan.

Semua endpoint wajib `Authorization: Bearer <access_token>` dengan sesi aktif.
POST/PUT wajib `Content-Type: application/json`; `X-Correlation-ID` opsional,
128 karakter pertama diteruskan. Tenant/actor dari sesi, bukan body/header bebas.
Respons JSON envelope, X-Request-ID, Cache-Control: no-store dan Pragma: no-cache.
Limiter auth sementara tidak mencakup endpoint bisnis ini.

| Method/path | Tujuan | Permission | Body | Parameter |
| --- | --- | --- | --- | --- |
| GET /api/v1/suppliers | Daftar pemasok | Supplier.Read | Tidak ada | offset/limit |
| POST /api/v1/suppliers | Buat pemasok | Supplier.Write | SupplierInput | Tidak ada |
| GET /api/v1/suppliers/{identifier} | Detail pemasok | Supplier.Read | Tidak ada | identifier UUID supplier wajib |
| PUT /api/v1/suppliers/{identifier} | Ganti definisi pemasok | Supplier.Write | SupplierInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/suppliers/{identifier} | Hapus secara administratif | Supplier.Delete | Tidak ada | identifier UUID; expected_version query wajib |
| GET /api/v1/raw-materials | Daftar bahan baku | RawMaterial.Read | Tidak ada | offset/limit |
| POST /api/v1/raw-materials | Buat bahan baku | RawMaterial.Write | RawMaterialInput | Tidak ada |
| GET /api/v1/raw-materials/{identifier} | Detail bahan | RawMaterial.Read | Tidak ada | identifier UUID bahan wajib |
| PUT /api/v1/raw-materials/{identifier} | Ganti definisi bahan | RawMaterial.Write | RawMaterialInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/raw-materials/{identifier} | Hapus secara administratif | RawMaterial.Delete | Tidak ada | identifier UUID; expected_version query wajib |
| GET /api/v1/supplier-materials | Daftar pasangan pemasok-bahan | SupplierMaterial.Read | Tidak ada | supplier_id/raw_material_id opsional; offset/limit |
| POST /api/v1/supplier-materials | Daftarkan pasangan | SupplierMaterial.Write | SupplierMaterialInput | Tidak ada |
| GET /api/v1/supplier-materials/{identifier} | Detail pasangan | SupplierMaterial.Read | Tidak ada | identifier UUID relasi wajib |
| PUT /api/v1/supplier-materials/{identifier} | Koreksi pasangan | SupplierMaterial.Write | SupplierMaterialInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/supplier-materials/{identifier} | Hapus secara administratif | SupplierMaterial.Delete | Tidak ada | identifier UUID; expected_version query wajib |

Read/Write/Delete tiap modul independen; Write boleh mengembalikan snapshot hasil tanpa
Read. Validasi relasi tidak memerlukan Read supplier/bahan. Sembilan permission ini
sudah diberikan ke DEV_MAINTENANCE lokal; role lain tetap memerlukan grant terpilih.
AssetRegistry.Sync tidak diperlukan untuk sinkronisasi internal. Tidak ada endpoint
PATCH/restore, harga pemasok, stok, penerimaan atau konversi satuan. DELETE relasi menyediakan unlink secara soft delete.

### Payload dan validasi

String di-trim, NUL dan Unicode invalid ditolak. Boolean tidak dikonversi ke angka.
Field tambahan termasuk tenant_id, ID/audit/version ditolak. Semua PUT wajib
expected_version integer 1..2147483647, tidak nullable, bukan string/bool.
POST tidak menerima expected_version. PUT mengganti seluruh definisi: field
opsional yang dihilangkan kembali ke default, bukan mempertahankan nilai lama.

| SupplierInput | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| supplier_code | string / ya / tidak | 1..50; unik case-sensitive per tenant termasuk kode soft-deleted |
| supplier_name | string / ya / tidak | 1..200 |
| phone | string / tidak / ya | Maksimal 30; default null, tidak divalidasi sebagai nomor negara tertentu |
| email | string email / tidak / ya | EmailStr valid, maksimal 254 setelah normalisasi; default null; string kosong ditolak |
| status | enum string / tidak / tidak | ACTIVE/INACTIVE; default ACTIVE |

| RawMaterialInput | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| material_code | string / ya / tidak | 1..50; unik case-sensitive per tenant termasuk soft-deleted |
| material_name | string / ya / tidak | 1..200 |
| category | string / tidak / ya | Maksimal 100; default null |
| uom | string / ya / tidak | 1..30, nonblank; bebas seperti kg/g/liter; tidak dapat diubah setelah create |
| storage_type | enum string / tidak / ya | COLD_STORAGE/FREEZER/DRY_STORAGE; default null |
| recommended_temperature_min | decimal / tidak / ya | -9999.99..9999.99, maksimal 2 desimal; default null |
| recommended_temperature_max | decimal / tidak / ya | Batas sama; jika kedua suhu terisi min <= max; default null |
| maximum_storage_hours | decimal / tidak / ya | 0..99999999.99, maksimal 2 desimal; default null |
| status | enum string / tidak / tidak | ACTIVE/INACTIVE; default ACTIVE |

Decimal menerima angka JSON atau string numerik finite; gunakan string untuk
presisi. Satu batas suhu boleh null. Nilai contoh hanya ilustrasi konfigurasi,
bukan rekomendasi keamanan pangan. Uom dipertahankan setelah dibuat untuk menjaga
makna kuantitas transaksi; konversi satuan belum tersedia.

| SupplierMaterialInput | Tipe / required / nullable | Validasi |
| --- | --- | --- |
| supplier_id | UUID / ya / tidak | Supplier ACTIVE, nondeleted dalam tenant |
| raw_material_id | UUID / ya / tidak | Bahan ACTIVE, nondeleted dalam tenant |

Pasangan unik per tenant, termasuk pasangan soft-deleted. PUT boleh mengubah
supplier_id/raw_material_id ke pasangan lain yang valid dan belum terpakai dengan
expected_version terbaru. Ini koreksi daftar pemasok; tidak mengubah supplier/batch
pada transaksi lama. Tidak ada tabel history khusus untuk perubahan relasi.

### Contoh request

POST /api/v1/suppliers:

```json
{
  "supplier_code": "SUPPLIER_EXAMPLE",
  "supplier_name": "Pemasok contoh",
  "phone": null,
  "email": "supplier@example.com",
  "status": "ACTIVE"
}
```

PUT /api/v1/suppliers/11111111-1111-4111-8111-111111111111:

```json
{
  "supplier_code": "SUPPLIER_EXAMPLE",
  "supplier_name": "Pemasok diperbarui",
  "phone": null,
  "email": "supplier@example.com",
  "status": "ACTIVE",
  "expected_version": 1
}
```

POST /api/v1/raw-materials:

```json
{
  "material_code": "MATERIAL_EXAMPLE",
  "material_name": "Bahan contoh",
  "category": null,
  "uom": "kg",
  "storage_type": "COLD_STORAGE",
  "recommended_temperature_min": "1.50",
  "recommended_temperature_max": "5.00",
  "maximum_storage_hours": "12.50",
  "status": "ACTIVE"
}
```

PUT /api/v1/raw-materials/22222222-2222-4222-8222-222222222222:

```json
{
  "material_code": "MATERIAL_EXAMPLE",
  "material_name": "Bahan diperbarui",
  "category": null,
  "uom": "kg",
  "storage_type": "COLD_STORAGE",
  "recommended_temperature_min": "1.50",
  "recommended_temperature_max": "5.00",
  "maximum_storage_hours": "12.50",
  "status": "ACTIVE",
  "expected_version": 1
}
```

POST /api/v1/supplier-materials:

```json
{
  "supplier_id": "11111111-1111-4111-8111-111111111111",
  "raw_material_id": "22222222-2222-4222-8222-222222222222"
}
```

PUT /api/v1/supplier-materials/33333333-3333-4333-8333-333333333333 (contoh pasangan sama; version tetap naik):

```json
{
  "supplier_id": "11111111-1111-4111-8111-111111111111",
  "raw_material_id": "22222222-2222-4222-8222-222222222222",
  "expected_version": 1
}
```

Contoh GET tanpa body; setiap request memakai header Bearer:

```http
GET /api/v1/suppliers?offset=0&limit=20
GET /api/v1/suppliers/11111111-1111-4111-8111-111111111111
GET /api/v1/raw-materials?offset=0&limit=20
GET /api/v1/raw-materials/22222222-2222-4222-8222-222222222222
GET /api/v1/supplier-materials?supplier_id=11111111-1111-4111-8111-111111111111&raw_material_id=22222222-2222-4222-8222-222222222222&offset=0&limit=20
GET /api/v1/supplier-materials/33333333-3333-4333-8333-333333333333
```

### Respons sukses dan pagination

POST 201, GET/PUT 200. Snapshot berisi seluruh field input (opsional tetap hadir
meskipun null) ditambah audit berikut. Semua field respons selalu hadir.

| Field tambahan | Tipe / nullable | Makna |
| --- | --- | --- |
| supplier_id / raw_material_id / supplier_material_id | UUID / tidak | ID sumber sesuai modul, bukan asset_uuid registry |
| tenant_id | UUID / tidak | Tenant sesi |
| version | integer / tidak | Create 1; setiap PUT naik satu termasuk nilai identik |
| created_at, updated_at | ISO 8601 UTC / tidak | Waktu audit |
| created_by, updated_by | UUID / ya | Actor audit; null mungkin pada data lama |
| deleted_at | ISO 8601 UTC / ya | Null pada hasil biasa; timestamp terisi pada respons DELETE |
| deleted_by | UUID / ya | Actor penghapusan; terisi pada respons DELETE |

Decimal respons adalah string, misalnya "12.50". Status/storage_type/email respons
berupa string terbuka agar snapshot legacy tetap terbaca; input baru tetap mengikuti
validasi di atas. PUT mengembalikan audit/version terbaru. Tidak ada nested objek
supplier/bahan dalam respons relasi; ambil detail dengan permission Read terkait.

Contoh POST supplier 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "supplier_code": "SUPPLIER_EXAMPLE",
    "supplier_name": "Pemasok contoh",
    "phone": null,
    "email": "supplier@example.com",
    "status": "ACTIVE",
    "supplier_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "deleted_at": null,
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh POST bahan 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "material_code": "MATERIAL_EXAMPLE",
    "material_name": "Bahan contoh",
    "category": null,
    "uom": "kg",
    "storage_type": "COLD_STORAGE",
    "recommended_temperature_min": "1.50",
    "recommended_temperature_max": "5.00",
    "maximum_storage_hours": "12.50",
    "status": "ACTIVE",
    "raw_material_id": "22222222-2222-4222-8222-222222222222",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "deleted_at": null,
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh POST relasi 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "supplier_id": "11111111-1111-4111-8111-111111111111",
    "raw_material_id": "22222222-2222-4222-8222-222222222222",
    "supplier_material_id": "33333333-3333-4333-8333-333333333333",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "deleted_at": null,
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

GET detail/PUT memakai schema snapshot yang sama dengan code 200 dan nilai terbaru.
GET list memakai data `{items, offset, limit, next_offset}`: items array snapshot
modul terkait; offset/limit integer nonnull; next_offset integer atau null bila
halaman berikutnya tidak ada. Tidak ada total/cursor. Contoh list kosong:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [],
    "offset": 0,
    "limit": 20,
    "next_offset": null
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Query offset integer 0..2147483647 default 0 dan limit integer 1..100 default 20;
keduanya opsional, tidak nullable. Filter supplier_id/raw_material_id hanya di
collection relasi, UUID opsional; bila keduanya diberikan berlaku AND. ID tenant
lain/tidak ada memberi items kosong. Hilangkan parameter yang tidak dipakai,
bukan string null. Tidak ada search, filter status atau sort kustom.

Hasil hanya tenant sendiri dan nondeleted, urut created_at DESC lalu ID DESC.
Supplier/bahan INACTIVE tetap terbaca. Relasi lama tetap terbaca ketika induknya
INACTIVE; status parent tidak menghapus atau mengubah relasi secara cascade.
Create/update relasi memerlukan kedua induk aktif. Pagination offset tidak menjamin
snapshot stabil antarhalaman saat data berubah. Frontend jangan menyamakan adanya
relasi dengan bukti supplier/bahan saat ini aktif.

### Error dan efek samping

| HTTP | message | Kondisi |
| --- | --- | --- |
| 400 | Validation Error | UUID, query, payload, email, decimal atau suhu tidak valid |
| 400 | Invalid supply input | Validasi ulang service gagal |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi tidak aktif; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted | Permission operasi tidak ada/dicabut |
| 404 | Supply not found | Record hilang, deleted atau tenant lain |
| 409 | Supply code or pair already exists in this tenant | Kode/pasangan sudah terpakai |
| 409 | Supply changed; reload before retrying | expected_version kedaluwarsa |
| 409 | Active supplier and material in this tenant required | Parent hilang/deleted/INACTIVE/lintas tenant |
| 409 | Material unit cannot be changed | PUT mengubah uom bahan |
| 409 | Supplier or material unavailable | Constraint referensi database gagal |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database gagal |
| 500 | Internal Server Error | Kegagalan tak terduga |

Contoh konflik:

```json
{
  "success": false,
  "code": 409,
  "message": "Supply changed; reload before retrying",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

400 Validation Error memakai data null dan errors field/message, misalnya
`[{"field":"body.uom","message":"Field required"}]`. Pengecekan parent dapat
mendahului lookup relasi; jangan bergantung pada urutan error saat beberapa syarat
invalid. Konflik versi memerlukan reload dan peninjauan sebelum retry.

Mutasi supplier/bahan dan digital_asset atomik; relasi hanya menulis supplier_material.
Tidak membuat stok, batch receiving, asset_relationship, movement atau event_log,
dan tidak mengirim event/notifikasi. Audit/version sumber dicatat, history khusus
master belum tersedia. POST tidak memiliki idempotency key; duplicate retry 409.
Perubahan relasi tidak mengubah bukti transaksi yang sudah tercatat.
Lihat [event catalog](event-catalog.md) dan [akses minimum](supply-permissions.md).


## Soft delete master operasional

Status: keenam modul kitchen, storage, zone, supplier, bahan baku dan relasi
pemasok-bahan kini memiliki Create, Read, Update dan Delete. Delete adalah **soft
delete**, bukan DELETE SQL: row fisik tetap ada dan menjadi nonaktif secara
administratif melalui deleted_at/deleted_by. Field status asli tidak diganti.
Tidak ada cascade, restore, reuse kode/pasangan terhapus atau daftar recycle bin.

| Method/path | Permission | Path | Query | Payload |
| --- | --- | --- | --- | --- |
| DELETE /api/v1/kitchens/{identifier} | Kitchen.Delete | UUID kitchen wajib | expected_version wajib | Tidak ada |
| DELETE /api/v1/storages/{identifier} | Storage.Delete | UUID storage wajib | expected_version wajib | Tidak ada |
| DELETE /api/v1/storage-zones/{identifier} | StorageZone.Delete | UUID zone wajib | expected_version wajib | Tidak ada |
| DELETE /api/v1/suppliers/{identifier} | Supplier.Delete | UUID supplier wajib | expected_version wajib | Tidak ada |
| DELETE /api/v1/raw-materials/{identifier} | RawMaterial.Delete | UUID bahan wajib | expected_version wajib | Tidak ada |
| DELETE /api/v1/supplier-materials/{identifier} | SupplierMaterial.Delete | UUID relasi wajib | expected_version wajib | Tidak ada |

Authorization: Bearer <access_token> wajib dengan sid aktif. Tidak membutuhkan
Content-Type karena body wajib kosong (termasuk {} dan null ditolak).
X-Correlation-ID opsional (128 karakter pertama diteruskan). expected_version adalah
integer query 1..2147483647, required/nonnullable; string true/null/angka pecahan ditolak.
Gunakan version terakhir dari GET/list atau respons mutasi. Path UUID invalid 400.

Read/Write/Delete independen: pemilik Delete boleh menerima snapshot hasil tanpa
Read/Write. Write tidak memberi hak Delete. Enam permission Delete sudah ditambahkan
secara eksplisit ke role DEV_MAINTENANCE lokal; role lain tidak otomatis berubah.
Frontend muat ulang /auth/me dan tampilkan aksi hapus berdasarkan permission Delete.

### Perlindungan referensi

Penghapusan menolak referensi dari record yang deleted_at-nya masih null, termasuk
record INACTIVE dan transaksi selesai. Tidak mencoba menghapus anak otomatis.

| Target | Referensi yang menghalangi (409) |
| --- | --- |
| Packaging type | Package nondeleted, termasuk DISCARDED |
| Food item | Recipe, production_batch (menu) |
| Recipe | Tidak ada tabel anak saat ini; pasangan tetap dicadangkan |
| Kitchen | Storage, school, receiving, production_batch, delivery |
| Storage | Storage zone, temperature_log, stock_entry, production_item |
| Storage zone | Device yang masih menunjuk zone |
| Supplier | Supplier-material, receiving |
| Raw material | Supplier-material, recipe, raw_material_batch |
| Supplier-material | Tidak memiliki tabel anak; penghapusan melepaskan pasangan dari daftar aktif |

Field status INACTIVE bukan soft delete dan tetap menghalangi penghapusan induk.
Bukti telemetry/transaksi tidak dihapus oleh API ini. Gunakan INACTIVE bila ingin
menghentikan pemakaian master yang memiliki riwayat dan tidak bisa dihapus.
Untuk hierarki baru tanpa referensi lain, hapus zone sebelum storage sebelum kitchen;
untuk pemasok/bahan, hapus relasi terlebih dahulu. Jangan memaksa penghapusan bukti
untuk meloloskan validasi. Delete zone/relasi tidak memerlukan induk ACTIVE, sehingga
pembersihan relasi masih bisa dilakukan setelah induk dinonaktifkan.

Service mengunci record sebelum memeriksa versi/referensi. Jalur tulis anak yang
tersedia memeriksa dan mengunci induk. Pemeriksaan soft-delete adalah aturan service,
bukan pengganti FK untuk SQL administratif; writer baru wajib mengikuti aturan ini.

### Request dan respons lengkap

Semua contoh berikut memakai Authorization: Bearer <access_token>, tanpa body.
Contoh sukses diasumsikan tidak memiliki referensi penghalang. HTTP 200 dengan
schema snapshot detail modul yang sama; berikut contoh lengkap untuk setiap DELETE.

DELETE /api/v1/kitchens/11111111-1111-4111-8111-111111111111?expected_version=1

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "kitchen_code": "KITCHEN_EXAMPLE",
    "kitchen_name": "Dapur contoh",
    "latitude": "-6.200000",
    "longitude": "106.800000",
    "address": null,
    "capacity": 200,
    "status": "ACTIVE",
    "kitchen_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 2,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "deleted_at": "2026-09-11T04:00:00Z",
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": "55555555-5555-4555-8555-555555555555"
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T04:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

DELETE /api/v1/storages/22222222-2222-4222-8222-222222222222?expected_version=1

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "kitchen_id": "11111111-1111-4111-8111-111111111111",
    "storage_code": "COLD_EXAMPLE",
    "storage_name": "Penyimpanan contoh",
    "storage_type": "COLD_STORAGE",
    "temperature_min": "1.50",
    "temperature_max": "5.00",
    "latitude": null,
    "longitude": null,
    "status": "ACTIVE",
    "storage_id": "22222222-2222-4222-8222-222222222222",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 2,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "deleted_at": "2026-09-11T04:00:00Z",
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": "55555555-5555-4555-8555-555555555555"
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T04:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

DELETE /api/v1/storage-zones/33333333-3333-4333-8333-333333333333?expected_version=1

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "storage_id": "22222222-2222-4222-8222-222222222222",
    "zone_code": "RACK_A",
    "zone_name": "Rak A",
    "zone_id": "33333333-3333-4333-8333-333333333333",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 2,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "deleted_at": "2026-09-11T04:00:00Z",
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": "55555555-5555-4555-8555-555555555555"
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T04:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

DELETE /api/v1/suppliers/11111111-1111-4111-8111-111111111111?expected_version=1

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "supplier_code": "SUPPLIER_EXAMPLE",
    "supplier_name": "Pemasok contoh",
    "phone": null,
    "email": "supplier@example.com",
    "status": "ACTIVE",
    "supplier_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 2,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "deleted_at": "2026-09-11T04:00:00Z",
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": "55555555-5555-4555-8555-555555555555"
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T04:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

DELETE /api/v1/raw-materials/22222222-2222-4222-8222-222222222222?expected_version=1

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "material_code": "MATERIAL_EXAMPLE",
    "material_name": "Bahan contoh",
    "category": null,
    "uom": "kg",
    "storage_type": "COLD_STORAGE",
    "recommended_temperature_min": "1.50",
    "recommended_temperature_max": "5.00",
    "maximum_storage_hours": "12.50",
    "status": "ACTIVE",
    "raw_material_id": "22222222-2222-4222-8222-222222222222",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 2,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "deleted_at": "2026-09-11T04:00:00Z",
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": "55555555-5555-4555-8555-555555555555"
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T04:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

DELETE /api/v1/supplier-materials/33333333-3333-4333-8333-333333333333?expected_version=1

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "supplier_id": "11111111-1111-4111-8111-111111111111",
    "raw_material_id": "22222222-2222-4222-8222-222222222222",
    "supplier_material_id": "33333333-3333-4333-8333-333333333333",
    "tenant_id": "44444444-4444-4444-8444-444444444444",
    "version": 2,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "deleted_at": "2026-09-11T04:00:00Z",
    "created_by": "55555555-5555-4555-8555-555555555555",
    "updated_by": "55555555-5555-4555-8555-555555555555",
    "deleted_by": "55555555-5555-4555-8555-555555555555"
  },
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T04:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Seluruh field snapshot tetap hadir dengan tipe/nullable sesuai kontrak modul.
Pada DELETE sukses, version naik satu, deleted_at/updated_at ISO 8601 UTC nonnull,
deleted_by/updated_by UUID actor nonnull. created_at/created_by dan definisi tetap.
Tidak ada field removed_count atau respons 204. Respons mengirim X-Request-ID,
Cache-Control: no-store, Pragma: no-cache; meta tetap envelope umum.

Setelah commit, GET detail/PUT/DELETE ulang mengembalikan 404 bila caller memiliki
permission operasi; list menyembunyikan record. Pengulangan DELETE tidak menambah
version/bukti dan tetap 404 meski mengirim version terbaru. POST dengan kode atau
pasangan yang pernah dihapus tetap konflik; tidak ada restore otomatis.

### Error dan efek samping

| HTTP | message | Arti/tindakan |
| --- | --- | --- |
| 400 | Validation Error | UUID/query required/batas version invalid; errors field/message |
| 400 | Request body must be empty | DELETE membawa body |
| 400 | Invalid location input / Invalid supply input | Validasi ulang service gagal |
| 401 | Invalid credentials or session | Bearer invalid/hilang/sesi mati; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted | Permission Delete tidak tersedia/dicabut |
| 404 | Location not found / Supply not found | Missing, tenant lain atau sudah soft-deleted |
| 409 | Location changed; reload before retrying / Supply changed; reload before retrying | Version kedaluwarsa; reload/tinjau sebelum retry |
| 409 | Master record is still referenced | Referensi pada tabel di atas masih ada; jangan mencoba cascade |
| 503 | Authentication unavailable | Konfigurasi autentikasi/database gagal |
| 500 | Internal Server Error | Kegagalan tak terduga |

Contoh 409 referensi (berlaku keenam route):

```json
{
  "success": false,
  "code": 409,
  "message": "Master record is still referenced",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "66666666-6666-4666-8666-666666666666",
    "correlation_id": "66666666-6666-4666-8666-666666666666",
    "timestamp": "2026-09-11T04:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

400 validasi mengisi errors, misalnya
`[{"field":"query.expected_version","message":"Field required"}]`.
Jika beberapa syarat dilanggar, jangan bergantung pada urutan validasi/auth/error.

Mutasi sumber dan proyeksi digital_asset untuk kitchen/storage/supplier/raw-material
berada dalam transaksi yang sama; registry mendapat deleted_at/deleted_by yang sama.
Zone/relasi bukan digital_asset. Gagal berarti rollback; FK/bukti lama tetap utuh.
Tidak menerbitkan event/notifikasi, tidak menghapus graph/movement/telemetry dan tidak
mengubah transaksi sebelumnya. Tidak ada history revisi khusus master baru; audit
tersimpan pada record. HTTP handler menyelesaikan transaksi sebelum respons.


## Kontrak CRUD sekolah

Status: lima operasi aktif untuk master school, terpisah dari transaksi penerimaan
sekolah yang masih TODO. Sekolah harus dimiliki kitchen aktif dalam tenant yang sama.
Tidak ada pemindahan kitchen, PATCH, restore, hard delete atau data siswa individual.

| Method/path | Tujuan | Permission | Body | Path/query |
| --- | --- | --- | --- | --- |
| GET /api/v1/schools | Daftar sekolah tenant | School.Read | Tidak ada | kitchen_id opsional, offset/limit |
| POST /api/v1/schools | Buat sekolah dan registry | School.Write | SchoolInput | Tidak ada |
| GET /api/v1/schools/{identifier} | Detail sekolah | School.Read | Tidak ada | identifier UUID sekolah wajib |
| PUT /api/v1/schools/{identifier} | Ganti definisi sekolah | School.Write | SchoolInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/schools/{identifier} | Soft delete sekolah | School.Delete | Wajib kosong | identifier UUID; expected_version query wajib |

Semua memakai Authorization: Bearer <access_token> dengan sid aktif, tenant/actor
berasal dari sesi. POST/PUT memakai Content-Type: application/json. DELETE tidak
memerlukan Content-Type dan menolak body, termasuk {} atau null. X-Correlation-ID
opsional, 128 karakter pertama diteruskan. Respons JSON envelope, X-Request-ID,
Cache-Control: no-store dan Pragma: no-cache. Limiter auth sementara belum mencakup API ini.

School.Read/Write/Delete independen. Write/Delete boleh menerima hasil mutasi tanpa
Read; pengecekan kitchen tidak membutuhkan Kitchen.Read. Tiga permission School
sudah diprovision ke DEV_MAINTENANCE lokal; role lain tidak otomatis berubah.
AssetRegistry.Sync tidak diperlukan untuk sinkronisasi internal. Muat ulang /auth/me
untuk snapshot permission terbaru, bukan menganggap Kitchen.* memberikan School.*.

### Payload SchoolInput

| Field | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| kitchen_id | UUID / ya / tidak | Kitchen nondeleted ACTIVE dalam tenant; tidak dapat diganti melalui PUT |
| school_code | string / ya / tidak | 1..50, unik case-sensitive per tenant termasuk kode soft-deleted |
| school_name | string / ya / tidak | 1..200 |
| latitude | decimal / tidak / ya | -90..90, maksimal 6 desimal, default null |
| longitude | decimal / tidak / ya | -180..180, maksimal 6 desimal, default null |
| address | string / tidak / ya | Default null, tanpa batas panjang aplikasi |
| student_count | integer / tidak / ya | 0..2147483647; default null; string angka/bool ditolak |
| status | string enum / tidak / tidak | ACTIVE/INACTIVE, default ACTIVE |

String di-trim, NUL/Unicode invalid ditolak. Koordinat harus keduanya berisi atau
keduanya null, menerima angka JSON/string decimal finite; gunakan string agar presisi
terjaga. Lokasi PostGIS dihitung dari koordinat; field location tidak diterima.
Field tambahan tenant_id/audit/ID/version ditolak. Status INACTIVE tidak mengubah
transaksi/registry anak atau menghapus sekolah.

PUT wajib menambahkan expected_version integer 1..2147483647, tidak nullable, bukan
bool/string. PUT mengganti seluruh definisi; optional yang tidak dikirim direset ke
default. Kitchen induk harus aktif pada create/update; delete dan pembacaan tetap
boleh saat kitchen INACTIVE. Perubahan kitchen_id ditolak 409.

### Contoh request

POST /api/v1/schools:

```json
{
  "kitchen_id": "11111111-1111-4111-8111-111111111111",
  "school_code": "SCHOOL_EXAMPLE",
  "school_name": "Sekolah contoh",
  "latitude": "-6.200000",
  "longitude": "106.800000",
  "address": null,
  "student_count": 100,
  "status": "ACTIVE"
}
```

PUT /api/v1/schools/22222222-2222-4222-8222-222222222222:

```json
{
  "kitchen_id": "11111111-1111-4111-8111-111111111111",
  "school_code": "SCHOOL_EXAMPLE",
  "school_name": "Sekolah diperbarui",
  "latitude": "-6.200000",
  "longitude": "106.800000",
  "address": null,
  "student_count": 100,
  "status": "ACTIVE",
  "expected_version": 1
}
```

GET/DELETE tanpa body; setiap request tetap wajib header Bearer:

```http
GET /api/v1/schools?kitchen_id=11111111-1111-4111-8111-111111111111&offset=0&limit=20
GET /api/v1/schools/22222222-2222-4222-8222-222222222222
DELETE /api/v1/schools/22222222-2222-4222-8222-222222222222?expected_version=2
```

Query list: kitchen_id UUID opsional; offset integer 0..2147483647 default 0, limit
integer 1..100 default 20. Hilangkan parameter yang tidak dipakai, bukan literal
null. Filter kitchen tenant lain/missing memberi items kosong. Tidak ada search,
filter status atau sort kustom. Urutan created_at DESC lalu school_id DESC, hanya
nondeleted tenant sendiri; ACTIVE/INACTIVE sama-sama terbaca. Pagination offset
tidak menjamin snapshot stabil antarhalaman saat ada mutasi.

DELETE query expected_version integer wajib, tidak nullable, 1..2147483647. Jika
record masih dirujuk delivery_item, school_receiving atau complaint nondeleted,
termasuk transaksi selesai, operasi ditolak 409. Tidak ada cascade; gunakan status
INACTIVE jika master memiliki riwayat yang perlu dipertahankan.

### Respons sukses

POST 201; GET/PUT/DELETE 200. data snapshot berisi semua field definisi SchoolInput
yang selalu hadir (termasuk optional null) dengan decimal sebagai string dan status
string terbuka untuk data legacy, ditambah field berikut:

| Field | Tipe / nullable | Makna |
| --- | --- | --- |
| school_id, tenant_id | UUID / tidak | Identitas sumber sekolah dan tenant, bukan asset_uuid registry |
| version | integer / tidak | Awal 1; setiap PUT/DELETE naik satu, termasuk PUT identik |
| created_at, updated_at | ISO 8601 UTC / tidak | Audit waktu server |
| created_by, updated_by | UUID / ya | Audit actor; null mungkin pada data lama |
| deleted_at | ISO 8601 UTC / ya | Null pada hasil biasa; terisi setelah DELETE |
| deleted_by | UUID / ya | Actor penghapusan; nonnull pada DELETE sukses |

Contoh POST 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "kitchen_id": "11111111-1111-4111-8111-111111111111",
    "school_code": "SCHOOL_EXAMPLE",
    "school_name": "Sekolah contoh",
    "latitude": "-6.200000",
    "longitude": "106.800000",
    "address": null,
    "student_count": 100,
    "status": "ACTIVE",
    "school_id": "22222222-2222-4222-8222-222222222222",
    "tenant_id": "33333333-3333-4333-8333-333333333333",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "created_by": "44444444-4444-4444-8444-444444444444",
    "updated_by": "44444444-4444-4444-8444-444444444444",
    "deleted_at": null,
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

GET detail/PUT memakai schema sama dengan code 200 dan snapshot terbaru; PUT
mengembalikan version yang harus dipakai operasi berikutnya. GET list memakai
items array snapshot SchoolData, offset/limit integer dan next_offset integer
atau null bila halaman berikutnya tidak ada. Tidak ada total/cursor. Contoh kosong:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [],
    "offset": 0,
    "limit": 20,
    "next_offset": null
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh DELETE 200 setelah PUT contoh di atas:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "kitchen_id": "11111111-1111-4111-8111-111111111111",
    "school_code": "SCHOOL_EXAMPLE",
    "school_name": "Sekolah diperbarui",
    "latitude": "-6.200000",
    "longitude": "106.800000",
    "address": null,
    "student_count": 100,
    "status": "ACTIVE",
    "school_id": "22222222-2222-4222-8222-222222222222",
    "tenant_id": "33333333-3333-4333-8333-333333333333",
    "version": 3,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "created_by": "44444444-4444-4444-8444-444444444444",
    "updated_by": "44444444-4444-4444-8444-444444444444",
    "deleted_at": "2026-09-11T04:00:00Z",
    "deleted_by": "44444444-4444-4444-8444-444444444444"
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

DELETE hanya mengisi deleted_at/deleted_by dan updated_at/updated_by serta version;
field status/definisi tetap. Row fisik dipertahankan. Setelah sukses list menyembunyikan
record; GET/PUT/DELETE ulang memberi 404 jika permission tersedia. Kode tetap
tercadangkan; POST kode lama 409 dan tidak mengembalikan record terhapus otomatis.

### Error dan efek samping

| HTTP | message | Kondisi |
| --- | --- | --- |
| 400 | Validation Error | Field wajib, UUID, query, koordinat atau jumlah siswa invalid |
| 400 | Invalid location input | Validasi ulang service gagal |
| 400 | Request body must be empty | DELETE membawa body |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi nonaktif; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted | School.Read/Write/Delete sesuai operasi belum diberikan/dicabut |
| 404 | Location not found | ID hilang, deleted atau tenant lain |
| 409 | Location code already exists in this scope | Kode sekolah tenant sudah terpakai |
| 409 | Location changed; reload before retrying | expected_version kedaluwarsa |
| 409 | Active parent location in this tenant required | Kitchen hilang, deleted, INACTIVE atau tenant lain |
| 409 | Parent location cannot be changed | PUT mencoba mengganti kitchen_id |
| 409 | Parent location unavailable | Constraint referensi gagal |
| 409 | Master record is still referenced | Pengiriman/penerimaan/complaint masih merujuk sekolah |
| 503 | Authentication unavailable | Konfigurasi autentikasi/database gagal |
| 500 | Internal Server Error | Kegagalan tak terduga |

Contoh konflik penghapusan:

```json
{
  "success": false,
  "code": 409,
  "message": "Master record is still referenced",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

400 Validation Error mengisi errors seperti
`[{"field":"body.school_name","message":"Field required"}]`; data null. Jika
beberapa syarat dilanggar, urutan error tidak dijamin. Konflik versi memerlukan
reload dan peninjauan, bukan retry dengan versi baru tanpa pemeriksaan.

Create/update/soft delete school dan proyeksi digital_asset SCHOOL atomik; rollback
membatalkan keduanya. Registry memakai UUID terpisah, tidak dikembalikan sebagai
school_id. Tidak membuat delivery, school_receiving, complaint, event_log, movement,
relationship atau notifikasi. POST belum memiliki idempotency key, duplicate retry
409. Tidak ada history revisi khusus school baru. Hak runtime dibatasi insert dan
update definisi/audit/version; kitchen_id/tenant tidak dapat diganti.


## Kontrak kendaraan dan driver

Status: sepuluh operasi CRUD aktif. Manifest/perjalanan kini tersedia melalui
kontrak pengiriman. GPS ingestion dan penjadwalan driver otomatis masih TODO.

| Method/path | Tujuan | Permission | Body | Path/query |
| --- | --- | --- | --- | --- |
| GET /api/v1/drivers | Daftar driver | Driver.Read | Tidak ada | offset/limit |
| POST /api/v1/drivers | Buat driver | Driver.Write | DriverInput | Tidak ada |
| GET /api/v1/drivers/{identifier} | Detail driver | Driver.Read | Tidak ada | identifier UUID driver wajib |
| PUT /api/v1/drivers/{identifier} | Ganti definisi driver | Driver.Write | DriverInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/drivers/{identifier} | Soft delete driver | Driver.Delete | Kosong | identifier UUID; expected_version query |
| GET /api/v1/vehicles | Daftar kendaraan | Vehicle.Read | Tidak ada | driver_id opsional; offset/limit |
| POST /api/v1/vehicles | Buat kendaraan | Vehicle.Write | VehicleInput | Tidak ada |
| GET /api/v1/vehicles/{identifier} | Detail kendaraan | Vehicle.Read | Tidak ada | identifier UUID kendaraan wajib |
| PUT /api/v1/vehicles/{identifier} | Ganti definisi/tautan kendaraan | Vehicle.Write | VehicleInput + expected_version | identifier UUID wajib |
| DELETE /api/v1/vehicles/{identifier} | Soft delete kendaraan | Vehicle.Delete | Kosong | identifier UUID; expected_version query |

Semua wajib Authorization: Bearer <access_token> dengan sid aktif; tenant/actor dari
sesi. POST/PUT memakai Content-Type: application/json. DELETE tidak memerlukan
Content-Type dan menolak seluruh body termasuk {} atau null. X-Correlation-ID opsional
(128 karakter pertama diteruskan). Respons JSON envelope, X-Request-ID,
Cache-Control: no-store, Pragma: no-cache. Limiter auth sementara tidak mencakup API ini.

Read/Write/Delete setiap modul independen. Write/Delete mengembalikan snapshot tanpa
memerlukan Read. Enam permission sudah diberikan ke DEV_MAINTENANCE lokal; role lain
perlu grant terpilih. Validasi driver/GPS tidak mensyaratkan Read parent tambahan;
AssetRegistry.Sync tidak diperlukan untuk sinkronisasi vehicle internal.

### Payload

String di-trim, NUL/Unicode invalid ditolak. Field tambahan termasuk tenant_id,
ID/audit/version ditolak. Optional yang dihilangkan pada PUT direset ke default
karena PUT mengganti seluruh definisi, bukan PATCH. Semua PUT wajib expected_version
integer 1..2147483647, nonnullable, bukan bool/string; POST tidak menerimanya.

| DriverInput | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| driver_code | string / ya / tidak | 1..50, unik case-sensitive per tenant termasuk soft-deleted |
| driver_name | string / ya / tidak | 1..200 |
| phone | string / tidak / ya | Maksimal 30, default null; bukan validasi nomor negara tertentu |
| status | enum string / tidak / tidak | ACTIVE/INACTIVE, default ACTIVE |

| VehicleInput | Tipe / required / nullable | Validasi/default |
| --- | --- | --- |
| vehicle_code | string / ya / tidak | 1..50, unik case-sensitive per tenant termasuk soft-deleted |
| plate_number | string / ya / tidak | 1..30, unik case-sensitive per tenant termasuk soft-deleted; tidak dinormalisasi ke uppercase |
| vehicle_type | string / ya / tidak | 1..50; tidak ada enum tertutup |
| capacity | decimal / tidak / ya | 0..9999999999.99, maksimal 2 desimal, default null |
| driver_id | UUID / tidak / ya | Driver nondeleted ACTIVE dalam tenant, default null |
| gps_device | UUID / tidak / ya | device.device_id internal, bukan device_uuid publik; device nondeleted ACTIVE dan device_type=GPS dalam tenant; default null |
| latitude | decimal / tidak / ya | -90..90, maksimal 6 desimal, default null |
| longitude | decimal / tidak / ya | -180..180, maksimal 6 desimal, default null |
| status | enum string / tidak / tidak | ACTIVE/INACTIVE, default ACTIVE |

Decimal menerima angka JSON/string numerik finite, boolean ditolak. Gunakan string
untuk presisi. Latitude/longitude harus berpasangan atau keduanya null. API menyimpan
Point SRID 4326 dan mengembalikannya sebagai koordinat, bukan WKB/location mentah.
Capacity hanya nilai kapasitas numerik sesuai schema saat ini; satuan/konversi kapasitas
belum didefinisikan, jangan menafsirkannya otomatis sebagai kg, liter atau jumlah paket.
Koordinat master bukan bukti GPS realtime dan tidak membuat gps_log.

Driver/GPS boleh dipasang, diganti atau dilepas dengan null melalui PUT. Driver tidak
harus unik pada satu kendaraan dan GPS tidak memiliki validasi eksklusivitas binding
Pada versi ini. INACTIVE driver/device tidak otomatis melepaskan tautan lama. Baca
kendaraan tetap boleh; update yang masih mengirim parent nonaktif ditolak. Kirim null
untuk melepas tautan bila dibutuhkan. Perubahan ini tidak mengubah driver/vehicle pada
delivery lama. Untuk memilih perangkat GPS aktif, gunakan `/api/v1/devices`.

### Contoh request

POST /api/v1/drivers:

```json
{
  "driver_code": "DRIVER_EXAMPLE",
  "driver_name": "Driver contoh",
  "phone": null,
  "status": "ACTIVE"
}
```

PUT /api/v1/drivers/11111111-1111-4111-8111-111111111111:

```json
{
  "driver_code": "DRIVER_EXAMPLE",
  "driver_name": "Driver diperbarui",
  "phone": null,
  "status": "ACTIVE",
  "expected_version": 1
}
```

POST /api/v1/vehicles:

```json
{
  "vehicle_code": "VEHICLE_EXAMPLE",
  "plate_number": "EXAMPLE-001",
  "vehicle_type": "VAN",
  "capacity": "100.50",
  "gps_device": null,
  "driver_id": "11111111-1111-4111-8111-111111111111",
  "latitude": "-6.200000",
  "longitude": "106.800000",
  "status": "ACTIVE"
}
```

PUT /api/v1/vehicles/22222222-2222-4222-8222-222222222222 (contoh melepas driver/GPS):

```json
{
  "vehicle_code": "VEHICLE_EXAMPLE",
  "plate_number": "EXAMPLE-001",
  "vehicle_type": "VAN",
  "capacity": "100.50",
  "gps_device": null,
  "driver_id": null,
  "latitude": "-6.200000",
  "longitude": "106.800000",
  "status": "ACTIVE",
  "expected_version": 1
}
```

GET/DELETE tanpa body, semuanya memakai header Bearer:

```http
GET /api/v1/drivers?offset=0&limit=20
GET /api/v1/drivers/11111111-1111-4111-8111-111111111111
GET /api/v1/vehicles?driver_id=11111111-1111-4111-8111-111111111111&offset=0&limit=20
GET /api/v1/vehicles/22222222-2222-4222-8222-222222222222
DELETE /api/v1/vehicles/22222222-2222-4222-8222-222222222222?expected_version=2
DELETE /api/v1/drivers/11111111-1111-4111-8111-111111111111?expected_version=2
```

Query list: offset integer 0..2147483647 default 0, limit integer 1..100 default 20;
semuanya opsional nonnullable. driver_id hanya di /vehicles, UUID opsional; ID tenant
lain/missing memberi items kosong. Omit parameter yang tidak dipakai, bukan literal
null. Tidak ada search/filter status atau sort kustom. Hanya nondeleted tenant sendiri,
ACTIVE/INACTIVE sama-sama terbaca, created_at DESC lalu ID DESC. Tidak menjamin snapshot
stabil antarhalaman. Query DELETE expected_version wajib integer 1..2147483647;
body/missing/invalid query ditolak 400. Delete vehicle tidak memerlukan parent aktif.

### Respons

POST 201; GET/PUT/DELETE 200. Snapshot data memuat semua field input (termasuk optional
null) ditambah field berikut. Decimal respons berupa string dan status string terbuka
untuk kompatibilitas legacy. Seluruh field selalu hadir.

| Field tambahan | Tipe / nullable | Makna |
| --- | --- | --- |
| driver_id / vehicle_id | UUID / tidak | ID sumber modul, bukan asset_uuid registry |
| tenant_id | UUID / tidak | Tenant sesi |
| version | integer / tidak | Create 1; setiap PUT/DELETE naik satu termasuk PUT identik |
| created_at, updated_at | ISO 8601 UTC / tidak | Waktu audit server |
| created_by, updated_by | UUID / ya | Actor audit, null mungkin pada data lama |
| deleted_at | ISO 8601 UTC / ya | Null pada read biasa, terisi pada DELETE sukses |
| deleted_by | UUID / ya | Actor penghapusan, nonnull pada DELETE sukses |

Contoh POST driver 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "driver_code": "DRIVER_EXAMPLE",
    "driver_name": "Driver contoh",
    "phone": null,
    "status": "ACTIVE",
    "driver_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "33333333-3333-4333-8333-333333333333",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "created_by": "44444444-4444-4444-8444-444444444444",
    "updated_by": "44444444-4444-4444-8444-444444444444",
    "deleted_at": null,
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh POST vehicle 201:

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "vehicle_code": "VEHICLE_EXAMPLE",
    "plate_number": "EXAMPLE-001",
    "vehicle_type": "VAN",
    "capacity": "100.50",
    "gps_device": null,
    "driver_id": "11111111-1111-4111-8111-111111111111",
    "latitude": "-6.200000",
    "longitude": "106.800000",
    "status": "ACTIVE",
    "vehicle_id": "22222222-2222-4222-8222-222222222222",
    "tenant_id": "33333333-3333-4333-8333-333333333333",
    "version": 1,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T03:00:00Z",
    "created_by": "44444444-4444-4444-8444-444444444444",
    "updated_by": "44444444-4444-4444-8444-444444444444",
    "deleted_at": null,
    "deleted_by": null
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

GET detail dan PUT memakai snapshot schema sama dengan code 200; PUT memberi audit/
version terbaru. GET list data berisi items array snapshot modul, offset/limit integer,
next_offset integer atau null (habis). Tidak ada total/cursor. Contoh list kosong:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "items": [],
    "offset": 0,
    "limit": 20,
    "next_offset": null
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh DELETE vehicle 200 setelah PUT melepas tautan:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "vehicle_code": "VEHICLE_EXAMPLE",
    "plate_number": "EXAMPLE-001",
    "vehicle_type": "VAN",
    "capacity": "100.50",
    "gps_device": null,
    "driver_id": null,
    "latitude": "-6.200000",
    "longitude": "106.800000",
    "status": "ACTIVE",
    "vehicle_id": "22222222-2222-4222-8222-222222222222",
    "tenant_id": "33333333-3333-4333-8333-333333333333",
    "version": 3,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "created_by": "44444444-4444-4444-8444-444444444444",
    "updated_by": "44444444-4444-4444-8444-444444444444",
    "deleted_at": "2026-09-11T04:00:00Z",
    "deleted_by": "44444444-4444-4444-8444-444444444444"
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Contoh DELETE driver 200 setelah PUT:

```json
{
  "success": true,
  "code": 200,
  "message": "Success",
  "data": {
    "driver_code": "DRIVER_EXAMPLE",
    "driver_name": "Driver diperbarui",
    "phone": null,
    "status": "ACTIVE",
    "driver_id": "11111111-1111-4111-8111-111111111111",
    "tenant_id": "33333333-3333-4333-8333-333333333333",
    "version": 3,
    "created_at": "2026-09-11T03:00:00Z",
    "updated_at": "2026-09-11T04:00:00Z",
    "created_by": "44444444-4444-4444-8444-444444444444",
    "updated_by": "44444444-4444-4444-8444-444444444444",
    "deleted_at": "2026-09-11T04:00:00Z",
    "deleted_by": "44444444-4444-4444-8444-444444444444"
  },
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

Delete driver diblokir bila dirujuk vehicle/ delivery nondeleted. Delete vehicle
diblokir delivery/gps_log nondeleted, termasuk perjalanan selesai dan bukti historis.
Tidak ada cascade. Driver yang masih dipasang pada kendaraan harus dilepas lebih dahulu;
riwayat pengiriman tetap menjadi penghalang. Gunakan INACTIVE bila master bersejarah
perlu dihentikan pemakaiannya. Setelah DELETE, row fisik/status/definisi tetap; list
menyembunyikannya dan GET/PUT/DELETE ulang 404. Kode/plat tetap tercadangkan; tidak ada
restore atau reuse otomatis. Tidak ada history revisi khusus master baru.

### Error dan efek samping

| HTTP | message | Kondisi |
| --- | --- | --- |
| 400 | Validation Error | UUID/body/query/decimal/koordinat invalid |
| 400 | Invalid location input | Validasi ulang service gagal |
| 400 | Request body must be empty | DELETE membawa body |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi mati; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted | Permission operasi belum tersedia/dicabut |
| 404 | Location not found | Missing/deleted/tenant lain |
| 409 | Location code already exists in this scope | Kode driver/kendaraan atau plat sudah terpakai |
| 409 | Location changed; reload before retrying | expected_version kedaluwarsa |
| 409 | Active driver in this tenant required | Driver hilang/deleted/INACTIVE/tenant lain |
| 409 | Active GPS device in this tenant required | ID internal perangkat hilang/deleted/nonaktif/tipe bukan GPS/tenant lain |
| 409 | Parent location unavailable | Constraint referensi gagal |
| 409 | Master record is still referenced | Delete masih memiliki referensi di atas |
| 503 | Authentication unavailable | Konfigurasi autentikasi/database gagal |
| 500 | Internal Server Error | Kegagalan tak terduga |

Contoh konflik:

```json
{
  "success": false,
  "code": 409,
  "message": "Active GPS device in this tenant required",
  "data": null,
  "errors": [],
  "meta": {
    "request_id": "55555555-5555-4555-8555-555555555555",
    "correlation_id": "55555555-5555-4555-8555-555555555555",
    "timestamp": "2026-09-11T03:00:00Z",
    "execution_time_ms": 12.0
  }
}
```

400 validasi menggunakan data null dan errors field/message, misalnya
`[{"field":"body.plate_number","message":"Field required"}]`. Pengecekan parent
bisa mendahului lookup record; jangan bergantung pada urutan error untuk request
dengan beberapa pelanggaran. Konflik versi memerlukan reload dan peninjauan.

Vehicle serta proyeksi digital_asset VEHICLE disinkronkan atomik, termasuk soft delete;
label registry berasal dari plate_number. Driver bukan tipe registry dan tidak membuat
digital_asset. Rollback membatalkan mutasi; tidak membuat delivery, gps_log, movement,
relationship, event_log atau notifikasi. Tidak ada realtime/event runtime baru.
POST tanpa idempotency key: retry kode/plat yang sudah disimpan memberi 409.


## Kontrak receiving dan batch bahan

Status: **7 operasi aktif**, bagian penerimaan bahan. Prefix semua path `/api/v1`.
Tidak tersedia PUT/PATCH/DELETE receiving/item/batch. Item dan batch dibuat atomik
melalui receiving; kesalahan draft diselesaikan dengan cancel lalu create baru
menggunakan kode batch/QR baru. Kode lama tetap dicadangkan, termasuk yang dibatalkan.

| Method/path | Tujuan dan permission independen | Payload | Sukses |
| --- | --- | --- | --- |
| POST `/receivings` | Mulai penerimaan, `Receiving.Write` | ReceivingInput wajib | 201, ReceivingDetail |
| GET `/receivings` | Daftar header, `Receiving.Read` | Tidak ada | 200, ReceivingPage |
| GET `/receivings/{identifier}` | Detail dengan item/batch, `Receiving.Read` | Tidak ada | 200, ReceivingDetail |
| POST `/receivings/{identifier}/complete` | Simpan seluruh keputusan inspeksi, `Receiving.Complete` | CompleteInput wajib | 200, ReceivingDetail |
| POST `/receivings/{identifier}/cancel` | Batalkan CREATED, `Receiving.Cancel` | CancelInput wajib | 200, ReceivingDetail |
| GET `/raw-material-batches` | Daftar/search batch, `RawMaterialBatch.Read` | Tidak ada | 200, BatchPage |
| GET `/raw-material-batches/{identifier}` | Detail batch, `RawMaterialBatch.Read` | Tidak ada | 200, BatchData |

Seluruh endpoint memakai `Authorization: Bearer <access_token>` dari sesi aktif.
POST wajib `Content-Type: application/json`; `Accept: application/json` dianjurkan.
`X-Correlation-ID` opsional, maksimum yang dicatat 128 karakter. Respons memakai
JSON envelope umum, `X-Request-ID`, `Cache-Control: no-store`, `Pragma: no-cache`.
Tenant/operator/audit diturunkan dari sesi, tidak boleh dikirim sebagai payload.
Receiving.Read mengizinkan nested batch pada detail tanpa RawMaterialBatch.Read;
permission batch terpisah diperlukan untuk endpoint batch. Write/Complete/Cancel
mengembalikan hasil mutasi tanpa otomatis memberikan akses GET.

### Parameter dan pagination

`identifier` wajib UUID pada setiap path detail/aksi. Tidak ada query untuk POST
atau GET detail. Parameter GET daftar berikut opsional dan tidak nullable bila
dikirim: UUID berbentuk string; status peka huruf besar/kecil; string kosong invalid.

| Endpoint daftar | Query | Tipe/default/validasi |
| --- | --- | --- |
| Keduanya | offset | integer 0..2147483647, default 0 |
| Keduanya | limit | integer 1..100, default 20 |
| Keduanya | supplier_id | UUID, default tidak difilter |
| Receivings | kitchen_id | UUID, default tidak difilter |
| Receivings | status | CREATED, COMPLETED, CANCELLED; default semua |
| Batches | receiving_id, raw_material_id | UUID, default tidak difilter |
| Batches | search | string 1..200, cari material_code/material_name/batch_code secara case-insensitive |
| Batches | material_category | string 1..100, filter kategori bahan |
| Batches | status | CREATED, ACCEPTED, REJECTED, CANCELLED; default semua |
| Batches | sort | CREATED_DESC default, FIFO, FEFO |

Filter digabung AND dalam tenant sesi. UUID filter milik tenant lain/tidak ada
menghasilkan daftar kosong. Urutan receiving tetap `created_at DESC, primary UUID DESC`.
Urutan batch default juga `created_at DESC, raw_material_batch_id DESC`; `FIFO`
mengurutkan `received_at ASC`, lalu created_at/UUID; `FEFO` mengurutkan
expired_date paling dekat lebih dulu, expired_date null terakhir, lalu received_at.
Pagination bukan snapshot stabil jika transaksi baru masuk. `next_offset` integer
atau null bila tidak ada halaman selanjutnya, tanpa total. Detail receiving
mengembalikan semua item urut `receiving_item_id ASC`; daftar receiving tidak
menyertakan items.

### Payload create

| Field | Tipe | Required / nullable / default | Validasi dan makna |
| --- | --- | --- | --- |
| supplier_id | UUID | Ya / tidak | Supplier aktif, nondeleted, tenant sesi |
| kitchen_id | UUID | Ya / tidak | Kitchen aktif, nondeleted, tenant sesi |
| received_at | ISO datetime timezone | Ya / tidak | Tidak di masa depan; disimpan/dikirim UTC |
| items | array ItemInput | Ya / tidak | 1..100 elemen |
| items[].raw_material_id | UUID | Ya / tidak | Bahan aktif, nondeleted, tenant sesi; relasi supplier-material nondeleted wajib |
| items[].batch_code | string | Ya / tidak | Trim, 1..100; unik per tenant dan dalam request |
| items[].quantity | decimal number/string | Ya / tidak | >0; maksimum 14 digit total, 6 desimal (maksimum 99999999.999999); bukan NaN/infinity/bool |
| items[].temperature | decimal number/string | Tidak / ya / null | -9999.99..9999.99, maksimal 2 desimal; suhu inspeksi dalam Celsius |
| items[].condition | string | Tidak / ya / null | 1..100 karakter; kondisi visual/manual bahan saat diterima, misalnya `GOOD`, `DAMAGED`, atau catatan singkat |
| items[].photo | string | Tidak / ya / null | 1..1024 karakter; referensi foto kondisi bahan, tidak di-fetch/upload/diverifikasi backend |
| items[].expired_date | date YYYY-MM-DD | Tidak / ya / null | Batch kedaluwarsa boleh dicatat agar bisa ditolak |
| items[].qr_code | string | Tidak / ya / null | Trim, 1..255; unik per tenant dan dalam request jika bukan null |

Field ekstra ditolak pada seluruh object payload. String harus UTF-8 valid, tanpa
NUL. Bool tidak diterima sebagai angka. `uom` diambil dari master bahan dan disimpan
sebagai snapshot item; jumlah tidak dikonversi. Beberapa batch bahan yang sama boleh
berada dalam satu receiving selama kode/QR berbeda. API tidak membuat gambar QR.

Contoh request (ganti UUID master dengan hasil GET master milik tenant sendiri):

```http
POST /api/v1/receivings
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{"supplier_id":"11111111-1111-4111-8111-111111111111","kitchen_id":"22222222-2222-4222-8222-222222222222","received_at":"2026-01-01T08:00:00+07:00","items":[{"raw_material_id":"33333333-3333-4333-8333-333333333333","batch_code":"BATCH-EXAMPLE-001","quantity":"2.500000","temperature":"3.20","condition":"GOOD","photo":"example/raw-receiving/batch-001.jpg","expired_date":null,"qr_code":null}]}
```

### Penyelesaian dan pembatalan

CompleteInput memiliki `expected_version` integer strict wajib 1..2147483647 serta
`items` array wajib 1..100 elemen. Setiap object hanya `receiving_item_id` UUID wajib
dan `accepted` boolean wajib, bukan string/angka/null. Seluruh item dari detail
harus dikirim tepat sekali; duplicate ID adalah 400, set ID tidak cocok adalah 409.
CancelInput hanya `expected_version` dengan validasi yang sama.

```http
POST /api/v1/receivings/44444444-4444-4444-8444-444444444444/complete
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{"expected_version":1,"items":[{"receiving_item_id":"55555555-5555-4555-8555-555555555555","accepted":true}]}
```

Alternatif untuk membatalkan draft lain:

```http
POST /api/v1/receivings/44444444-4444-4444-8444-444444444444/cancel
Authorization: Bearer <access_token>
Content-Type: application/json
```

```json
{"expected_version":1}
```

Alur status yang berlaku:

- Create: receiving dan batch CREATED, item.accepted null, version masing-masing 1.
- Complete: receiving COMPLETED meskipun seluruh item ditolak. Batch masing-masing
  ACCEPTED/REJECTED sesuai keputusan, accepted true/false. Header, setiap item,
  setiap batch naik version satu dan updated_by menjadi actor penyelesaian.
- Cancel: hanya CREATED menjadi CANCELLED; semua batch CANCELLED, accepted tetap
  null; version header/item/batch naik satu. Tidak ada penghapusan atau movement.
- COMPLETED/CANCELLED final. Tidak ada reopen, koreksi parsial, return atau reversal.
  expected_version lama atau mencoba finalisasi ulang menghasilkan 409; fetch ulang.

Batch dengan expired_date sebelum **tanggal UTC saat complete** tidak boleh
accepted=true, termasuk penerimaan yang dibackdate. Tanggal sama dengan hari UTC
ini masih boleh diterima; null berarti tanggal belum diketahui. Penerimaan suhu
adalah keputusan inspeksi manusia, belum evaluator ambang suhu otomatis. Parent
aktif/divalidasi saat create; complete memakai snapshot transaksi dan tidak mengubah
pemasok, kitchen, item atau kuantitas meski definisi master kemudian dinonaktifkan.
Operator pada header tetap pembuat penerimaan; operator movement adalah penyelesai.

### Bentuk response dan contoh GET

Semua field tabel respons selalu dikirim; nullable berarti nilai boleh null.
UUID/date/datetime berupa JSON string, Decimal berupa JSON **string**, version integer.
Setiap header, item, batch memiliki AuditData berikut:

| Field audit | Tipe / nullable | Makna |
| --- | --- | --- |
| tenant_id | UUID / tidak | Tenant sesi |
| version | integer / tidak | Versi optimistic locking record |
| created_at, updated_at | datetime UTC / tidak | Timestamp audit |
| created_by, updated_by | UUID / ya | Actor, diisi pada write API ini |
| deleted_at, deleted_by | datetime UTC, UUID / ya | Null pada API receiving ini |

| Object | Field selain audit (semua required pada response) |
| --- | --- |
| ReceivingData | receiving_id, supplier_id, kitchen_id, operator: UUID nonnull; received_at: datetime UTC nonnull; status: string nonnull |
| ReceivingDetail | Semua ReceivingData + items: array ItemData nonnull |
| ItemData | receiving_item_id, receiving_id, raw_material_batch_id: UUID nonnull; quantity: decimal string nonnull; uom: string nonnull; temperature: decimal string nullable; condition/photo: string nullable; accepted: bool nullable; batch: BatchData nonnull |
| BatchData | raw_material_batch_id, raw_material_id, receiving_id, supplier_id: UUID nonnull; batch_code, status: string nonnull; expired_date: date nullable; qr_code: string nullable |
| ReceivingPage | items: array ReceivingData; offset, limit: integer; next_offset: integer nullable |
| BatchPage | items: array BatchData; offset, limit: integer; next_offset: integer nullable |

Contoh panggilan GET tanpa body:

```http
GET /api/v1/receivings?status=CREATED&limit=20&offset=0
Authorization: Bearer <access_token>
```

```http
GET /api/v1/receivings/44444444-4444-4444-8444-444444444444
Authorization: Bearer <access_token>
```

```http
GET /api/v1/raw-material-batches?receiving_id=44444444-4444-4444-8444-444444444444&status=ACCEPTED
Authorization: Bearer <access_token>
```

```http
GET /api/v1/raw-material-batches?status=ACCEPTED&search=ayam&material_category=PROTEIN&sort=FEFO
Authorization: Bearer <access_token>
```

```http
GET /api/v1/raw-material-batches/66666666-6666-4666-8666-666666666666
Authorization: Bearer <access_token>
```

Contoh lengkap respons create 201 berikut juga merupakan struktur respons detail
GET 200 (code 200), complete 200 dan cancel 200. Untuk complete contoh keputusan
true di atas: status header COMPLETED, batch ACCEPTED, accepted true, ketiga version
menjadi 2 dan updated_at/by mengikuti finalisasi. Untuk cancel: header/batch
CANCELLED, accepted null, version ketiganya 2. Semua field lain tetap.

```json
{
  "success": true,
  "code": 201,
  "message": "Success",
  "data": {
    "tenant_id": "77777777-7777-4777-8777-777777777777",
    "version": 1,
    "created_at": "2026-09-11T09:00:00Z",
    "updated_at": "2026-09-11T09:00:00Z",
    "deleted_at": null,
    "created_by": "88888888-8888-4888-8888-888888888888",
    "updated_by": "88888888-8888-4888-8888-888888888888",
    "deleted_by": null,
    "receiving_id": "44444444-4444-4444-8444-444444444444",
    "supplier_id": "11111111-1111-4111-8111-111111111111",
    "kitchen_id": "22222222-2222-4222-8222-222222222222",
    "operator": "88888888-8888-4888-8888-888888888888",
    "received_at": "2026-01-01T01:00:00Z",
    "status": "CREATED",
    "items": [
      {
        "tenant_id": "77777777-7777-4777-8777-777777777777",
        "version": 1,
        "created_at": "2026-09-11T09:00:00Z",
        "updated_at": "2026-09-11T09:00:00Z",
        "deleted_at": null,
        "created_by": "88888888-8888-4888-8888-888888888888",
        "updated_by": "88888888-8888-4888-8888-888888888888",
        "deleted_by": null,
        "receiving_item_id": "55555555-5555-4555-8555-555555555555",
        "receiving_id": "44444444-4444-4444-8444-444444444444",
        "raw_material_batch_id": "66666666-6666-4666-8666-666666666666",
        "quantity": "2.500000",
        "uom": "kg",
        "temperature": "3.20",
        "condition": "GOOD",
        "photo": "example/raw-receiving/batch-001.jpg",
        "accepted": null,
        "batch": {
          "tenant_id": "77777777-7777-4777-8777-777777777777",
          "version": 1,
          "created_at": "2026-09-11T09:00:00Z",
          "updated_at": "2026-09-11T09:00:00Z",
          "deleted_at": null,
          "created_by": "88888888-8888-4888-8888-888888888888",
          "updated_by": "88888888-8888-4888-8888-888888888888",
          "deleted_by": null,
          "raw_material_batch_id": "66666666-6666-4666-8666-666666666666",
          "raw_material_id": "33333333-3333-4333-8333-333333333333",
          "receiving_id": "44444444-4444-4444-8444-444444444444",
          "supplier_id": "11111111-1111-4111-8111-111111111111",
          "batch_code": "BATCH-EXAMPLE-001",
          "expired_date": null,
          "status": "CREATED",
          "qr_code": null
        }
      }
    ]
  },
  "errors": [],
  "meta": {
    "request_id": "99999999-9999-4999-8999-999999999999",
    "correlation_id": "99999999-9999-4999-8999-999999999999",
    "timestamp": "2026-09-11T09:00:00Z",
    "execution_time_ms": 18.4
  }
}
```

Respons GET batch memakai envelope yang sama (code 200) dengan `data` tepat object
`batch` pada contoh di atas. Respons list memakai `data.items` berisi object header
(tanpa items) atau BatchData; misalnya halaman kosong untuk kedua list:

```json
{"success":true,"code":200,"message":"Success","data":{"items":[],"offset":0,"limit":20,"next_offset":null},"errors":[],"meta":{"request_id":"99999999-9999-4999-8999-999999999999","correlation_id":"99999999-9999-4999-8999-999999999999","timestamp":"2026-09-11T09:00:00Z","execution_time_ms":2.1}}
```

### Error dan efek samping receiving

| HTTP | message / kondisi |
| --- | --- |
| 400 | Validation Error: field ekstra/hilang, UUID, datetime, enum, angka, bool inspeksi, batas item/pagination, search/category/sort batch, kode/QR duplicate dalam payload, item keputusan duplicate |
| 401 | Invalid credentials or session; token hilang, invalid, expired, revoked; WWW-Authenticate: Bearer |
| 403 | Required permission is not granted |
| 404 | Receiving or batch not found; tenant lain/deleted/tidak ada sama |
| 409 | Active supplier, kitchen and material in this tenant required |
| 409 | Supplier-material link required |
| 409 | Batch code or QR already exists in this tenant; transaksi seluruhnya rollback |
| 409 | Receiving changed; reload before retrying |
| 409 | Only CREATED receiving can be completed or cancelled |
| 409 | Decisions must include every receiving item exactly once |
| 409 | Expired batch cannot be accepted (UTC date) |
| 409 | Receiving must contain items / Receiving items are already finalized / Receiving source registry is incomplete: data lama yang tidak memenuhi prasyarat lifecycle |
| 409 | Receiving reference unavailable; konflik FK |
| 503 | Authentication unavailable; database/auth belum siap |
| 500 | Internal Server Error; kesalahan tak terduga, tidak menampilkan SQL |

Contoh stale version, berlaku untuk complete/cancel:

```json
{"success":false,"code":409,"message":"Receiving changed; reload before retrying","data":null,"errors":[],"meta":{"request_id":"99999999-9999-4999-8999-999999999999","correlation_id":"99999999-9999-4999-8999-999999999999","timestamp":"2026-09-11T09:00:00Z","execution_time_ms":2.1}}
```

Error lain menggunakan envelope sama dengan code/message tabel. Error validasi
menyertakan `errors: [{"field":"body.items.0.quantity","message":"Input should be greater than 0"}]`.
Tidak memakai HTTP 422. Frontend perlu menyimpan receiving_id dan version hasil
create, fetch detail sebelum inspeksi, lalu mengganti state dari respons aksi.

Seluruh create/finalisasi satu transaksi PostgreSQL: header, item, batch, registry,
relationship/movement dan event commit bersama atau semuanya rollback. Create sync
SUPPLIER/KITCHEN/RECEIVING/RAW_MATERIAL_BATCH; finalisasi sync receiving/batch.
Untuk setiap batch accepted, complete menambah SUPPLIED (supplier -> batch),
RECEIVED (receiving -> batch) dan satu movement RECEIVING menuju digital_asset
kitchen, from_location null, waktu received_at, operator actor penyelesaian.
UUID lokasi/edge adalah asset_uuid registry, bukan kitchen_id/receiving_id.
Batch rejected/cancelled tidak menghasilkan edge/movement penerimaan.

`receiving.created`, `receiving.completed`, `receiving.cancelled` disimpan di event_log
internal dengan snapshot; lihat [catalog](event-catalog.md#event-receiving-tersimpan).
Belum ada publisher/subscription/event HTTP. GET tidak menambah event. Tidak ada
idempotency key create: retry kode sama menghasilkan 409, bukan receiving baru;
setelah timeout periksa daftar/detail sebelum mengulang. Finalisasi diserialkan
per receiving dan versi/status mencegah event/movement ganda pada retry sukses.

**Batas fitur:** ACCEPTED berarti keputusan penerimaan, bukan saldo stok siap pakai
atau jaminan keamanan otomatis. Putaway storage dan ledger/saldo tersedia pada kontrak stok di bawah. Belum ada
return/reversal, lampiran foto, nomor dokumen supplier, inspeksi
parsial, engine suhu, atau endpoint graph/timeline. Receiving/item tetap historis;
master kitchen/supplier/material yang dirujuk tidak boleh dihapus, termasuk setelah
receiving cancelled. Lengkapi relasi pemasok-bahan melalui API master sebelum create.


## Stok batch bahan dan putaway

Status **aktif** setelah migrasi `20260911_0018` dan grant runtime. Semua path
berawalan `/api/v1`; bearer session dan tenant account wajib, `Cache-Control: no-store`.
Header request: `Authorization: Bearer <access_token>`, `Content-Type: application/json`
untuk POST; GET tidak memakai body. `identifier` wajib UUID batch, tenant/deleted
terfilter server. Tenant, actor, UOM, audit dan waktu tidak boleh dikirim di payload.

| Method/path | Tujuan | Permission | Sukses |
|---|---|---|---|
| POST `/raw-material-batches/{identifier}/putaway` | Alokasi parsial ke storage/zone | `Stock.Putaway` | 201 entry |
| GET `/raw-material-batches/{identifier}/stock` | Saldo batch dan per storage | `Stock.Read` | 200 balance |
| GET `/raw-material-batches/{identifier}/stock-entries` | Ledger putaway immutable | `Stock.Read` | 200 page |
| POST `/raw-material-batches/{identifier}/manual-stock-issues` | Pengeluaran bahan manual/scan dari storage | `Stock.Issue` | 201 issue |
| GET `/raw-material-batches/{identifier}/manual-stock-issues` | Ledger pengeluaran manual/scan | `Stock.Read` | 200 page |

POST tidak memiliki query. Payload:
`expected_version` integer strict >=1 (version **batch**, bukan header receiving),
`storage_id` UUID wajib nonnull, `zone_id` UUID opsional nullable, dan `quantity`
decimal positif maksimal 14 digit dengan 6 desimal. Decimal dapat dikirim sebagai
string; bool, NaN/infinity, field tambahan dan nilai melebihi presisi ditolak 400.
GET stock tidak memiliki query. GET stock-entries dan GET manual-stock-issues
menerima `offset` integer 0..2147483647 default 0 dan `limit` integer 1..100 default 20;
urutan batch_version menurun, `next_offset` integer atau null. Tidak ada total count.

Syarat putaway: receiving COMPLETED, item accepted=true dan batch ACCEPTED;
batch belum expired sebelum tanggal UTC saat ini (tanggal hari ini masih boleh).
Kitchen, storage, material harus aktif/nondeleted satu tenant; storage wajib di
kitchen receiving dan storage_type sesuai material jika material menetapkannya.
Jika `zone_id` dikirim, zone/rak harus nondeleted, satu tenant dan milik storage
yang dipilih. Quantity <= quantity accepted dikurangi jumlah seluruh entry batch.
Putaway dapat berulang, dibagi ke beberapa storage/zone, tetapi tidak dapat melebihi
jumlah diterima.

Batch dikunci selama pengecekan saldo dan write; setiap sukses menaikkan version
batch satu kali. Dua request memakai version yang sama hanya dapat menghasilkan
satu sukses. Retry sukses memakai version lama menghasilkan 409, bukan entry baru.
Ambil ulang stock/version dan ledger sebelum mencoba ulang. Tidak ada idempotency key.

Contoh request (UUID fiktif harus diganti dengan hasil API):

```http
POST /api/v1/raw-material-batches/66666666-6666-4666-8666-666666666666/putaway
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":2,"storage_id":"99999999-9999-4999-8999-999999999999","zone_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","quantity":"1.500000"}
```

Respons menggunakan envelope standar (`success`, `code`, `message`, `data`, `errors`, `meta`) yang sama
seperti receiving. Contoh **data** pada sukses 201:

```json
{
  "stock_entry_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "tenant_id":"77777777-7777-4777-8777-777777777777",
  "raw_material_batch_id":"66666666-6666-4666-8666-666666666666",
  "storage_id":"99999999-9999-4999-8999-999999999999",
  "zone_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "quantity":"1.500000",
  "batch_version":3,
  "version":1,
  "created_at":"2026-09-11T09:00:00Z",
  "updated_at":"2026-09-11T09:00:00Z",
  "created_by":"88888888-8888-4888-8888-888888888888",
  "updated_by":"88888888-8888-4888-8888-888888888888",
  "deleted_at":null,
  "deleted_by":null
}
```

Entry fields: tiga ID resource dan tenant UUID nonnull, `zone_id` UUID nullable
untuk slot/rak; quantity decimal string nonnull; batch_version/version integer nonnull
(version entry tetap 1); timestamp
UTC nonnull; created_by/updated_by UUID nullable dalam schema audit umum (diisi actor
oleh endpoint); deleted_at timestamp nullable dan deleted_by UUID nullable, selalu
null pada ledger. Field entry tidak menyimpan UOM; baca `uom` pada saldo batch.

```http
GET /api/v1/raw-material-batches/66666666-6666-4666-8666-666666666666/stock
Authorization: Bearer <access_token>
```

Contoh data 200 setelah putaway 1.5 dari penerimaan 2.5 kg:

```json
{
  "raw_material_batch_id":"66666666-6666-4666-8666-666666666666",
  "version":3,
  "uom":"kg",
  "accepted_quantity":"2.500000",
  "putaway_quantity":"1.500000",
  "unallocated_quantity":"1.000000",
  "issued_quantity":"0",
  "available_quantity":"1.500000",
  "storages":[{"storage_id":"99999999-9999-4999-8999-999999999999","quantity":"1.500000","issued_quantity":"0","available_quantity":"1.500000"}]
}
```

Semua field balance required/nonnull; ID UUID, version integer, uom string,
quantity decimal string, storages array (boleh kosong) terurut storage_id menaik.
Saldo masih diagregasi per storage karena pemakaian produksi saat ini memilih storage,
belum memilih zone; detail slot/rak tersedia pada GET stock-entries.
`accepted_quantity` nol untuk item belum diterima/ditolak; `putaway_quantity`
adalah jumlah ledger; `unallocated_quantity = accepted_quantity - putaway_quantity`.
`issued_quantity` jumlah pemakaian produksi; `available_quantity` adalah alokasi
dikurangi pemakaian, hanya untuk batch diterima yang belum expired dengan
kitchen/material/storage aktif dan tipe storage cocok. Expiry/perubahan status
mengubah ketersediaan saat pembacaan, tidak mengubah quantity historis.
Angka nol dapat berupa `"0"` atau `"0.000000"`; jangan membandingkan string decimal.

```http
GET /api/v1/raw-material-batches/66666666-6666-4666-8666-666666666666/stock-entries?offset=0&limit=20
Authorization: Bearer <access_token>
```

Data page: `{"items":[],"offset":0,"limit":20,"next_offset":null}` bila belum
putaway; setiap item menggunakan schema entry di atas. offset/limit required integer,
next_offset required nullable integer, items required array. Pembacaan tidak mencatat event.

| Error | Kondisi dan message |
|---|---|
| 400 | Payload/path/query invalid; envelope validasi standar, tidak memakai 422 |
| 401 | Bearer/session invalid; `Invalid credentials or session` |
| 403 | `Required permission is not granted`; izin baca dan putaway terpisah |
| 404 | `Receiving or batch not found`; ID batch hilang, deleted atau tenant lain |
| 409 | `Receiving changed; reload before retrying` untuk version batch stale |
| 409 | `Active kitchen, storage and material in this tenant required` untuk referensi unavailable |
| 409 | `Active kitchen, storage, zone and material in this tenant required` untuk zone/storage/material unavailable |
| 409 | `Active kitchen, storage and material required` untuk status inactive |
| 409 | `Storage must belong to receiving kitchen` |
| 409 | `Storage zone must belong to selected storage` |
| 409 | `Storage type does not match material requirement` |
| 409 | `Completed receiving and ACCEPTED batch required` |
| 409 | `Expired batch cannot be put away (UTC date)` |
| 409 | `Quantity exceeds accepted unallocated stock` |
| 500/503 | Envelope error server/database/auth standar; transaksi tidak parsial |

Contoh error memakai envelope standar dengan `code:409`, `data:null`,
`message:"Quantity exceeds accepted unallocated stock"` dan meta request aktual.

Ledger append-only dilindungi trigger UPDATE/DELETE/TRUNCATE. Satu transaksi
mencatat entry, audit/version batch, sync registry, movement `STORAGE` dari registry
kitchen ke registry storage (remarks = stock_entry_id), dan event `stock.putaway`.
Movement parsial bukan perpindahan seluruh batch; baca ledger untuk quantity/lokasi
storage dan zone/rak.
Storage yang memiliki entry terlindungi dari soft delete, termasuk histori lama.
Tidak ada endpoint edit/delete/transfer/reversal/adjustment ledger, reservation,
reservasi; pengurangan bahan tersedia melalui start produksi.
Stock availability tidak mengevaluasi keamanan sensor atau recall; timer holding
paket adalah alur terpisah dari stok bahan.
Grant development melalui CLI `provision_receiving_permissions.py`, pilih eksplisit
`Stock.Read`, `Stock.Putaway` dan `Stock.Issue`; grant runtime `stock_entry` dan
`stock_issue` hanya SELECT/INSERT.

### Pengeluaran manual/scan bahan dari penyimpanan

Manual stock issue mencatat bahan keluar dari storage tanpa mengaitkannya ke batch
produksi. Gunakan endpoint ini untuk scan bahan/QR di frontend ketika perlu mencatat
pengeluaran operasional terpisah; untuk pemakaian bahan ke manufacturing order,
tetap gunakan start produksi.

Payload POST: `expected_version` version batch dari GET stock, `storage_id` wajib,
`zone_id` opsional nullable, `quantity` decimal positif, `issued_at` opsional
datetime timezone dan tidak boleh masa depan, `reason` wajib 1..200, serta
`reference_code` opsional 1..100. Jika `issued_at` tidak dikirim, server memakai
waktu UTC saat request diproses. Issue time tidak boleh sebelum received_at.

```http
POST /api/v1/raw-material-batches/66666666-6666-4666-8666-666666666666/manual-stock-issues
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":3,"storage_id":"99999999-9999-4999-8999-999999999999","zone_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","quantity":"0.500000","issued_at":"2026-09-15T09:30:00+07:00","reason":"SCAN_OUT","reference_code":"OUT-001"}
```

Contoh data 201:

```json
{
  "stock_issue_id":"cccccccc-cccc-4ccc-8ccc-cccccccccccc",
  "tenant_id":"77777777-7777-4777-8777-777777777777",
  "raw_material_batch_id":"66666666-6666-4666-8666-666666666666",
  "storage_id":"99999999-9999-4999-8999-999999999999",
  "zone_id":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "quantity":"0.500000",
  "batch_version":4,
  "issued_at":"2026-09-15T02:30:00Z",
  "reason":"SCAN_OUT",
  "reference_code":"OUT-001",
  "version":1,
  "created_at":"2026-09-15T02:30:01Z",
  "updated_at":"2026-09-15T02:30:01Z",
  "created_by":"88888888-8888-4888-8888-888888888888",
  "updated_by":"88888888-8888-4888-8888-888888888888",
  "deleted_at":null,
  "deleted_by":null
}
```

Syarat sama seperti putaway: receiving completed, batch accepted, belum expired,
storage aktif milik kitchen penerimaan, zone bila dikirim milik storage tersebut,
dan tipe storage cocok. Quantity tidak boleh melebihi putaway dikurangi issue
produksi dan issue manual pada storage itu. Sukses menaikkan version batch,
mencatat movement `ISSUE`, event `stock.manual_issued`, dan menurunkan
`available_quantity` pada GET stock.

```http
GET /api/v1/raw-material-batches/66666666-6666-4666-8666-666666666666/manual-stock-issues?offset=0&limit=20
Authorization: Bearer <access_token>
```

Data page memakai `items` berisi object issue seperti contoh di atas. Ledger
append-only; tidak ada edit/delete/reversal untuk issue manual saat ini.


## Kontrak menu dan resep

Status: **10 operasi aktif**, menggunakan schema existing food_item/recipe, tanpa
migrasi baru. Resep adalah satu baris komposisi menu?bahan, bukan header resep atau
snapshot produksi. `quantity` berarti jumlah bahan dalam `uom` bahan untuk **satu
unit hasil** pada `food_item.uom`. Contoh 0.125 kg per portion berarti 100 portion
memerlukan 12.5 kg; endpoint ini belum menjalankan kalkulasi/pemakaian produksi.

Semua path berawalan `/api/v1`. Header wajib `Authorization: Bearer <access_token>`;
POST/PUT memakai `Content-Type: application/json`. Tenant dan actor berasal dari
session. Respons menggunakan envelope standar success/code/message/data/errors/meta,
`X-Request-ID`, `Cache-Control: no-store`, `Pragma: no-cache`. Tidak ada public read.

| Method/path | Tujuan | Permission | Payload/query | Sukses |
|---|---|---|---|---|
| GET `/food-items` | Daftar menu | FoodItem.Read | Tanpa body; offset/limit/status | 200 FoodItemPage |
| GET `/food-items/{identifier}` | Detail menu | FoodItem.Read | UUID path; tanpa body/query | 200 FoodItemData |
| POST `/food-items` | Buat menu | FoodItem.Write | FoodItemInput; tanpa query | 201 FoodItemData |
| PUT `/food-items/{identifier}` | Ganti definisi | FoodItem.Write | FoodItemInput + expected_version; UUID path | 200 FoodItemData |
| DELETE `/food-items/{identifier}` | Soft delete | FoodItem.Delete | UUID path; expected_version query, body kosong | 200 snapshot terhapus |
| GET `/recipes` | Daftar komposisi | Recipe.Read | Tanpa body; offset/limit/food_item_id/raw_material_id | 200 RecipePage |
| GET `/recipes/{identifier}` | Detail komposisi | Recipe.Read | UUID path; tanpa body/query | 200 RecipeData |
| POST `/recipes` | Tambah komposisi | Recipe.Write | RecipeInput; tanpa query | 201 RecipeData |
| PUT `/recipes/{identifier}` | Ganti quantity/UOM | Recipe.Write | RecipeInput + expected_version; UUID path | 200 RecipeData |
| DELETE `/recipes/{identifier}` | Soft delete komposisi | Recipe.Delete | UUID path; expected_version query, body kosong | 200 snapshot terhapus |

List: offset integer 0..2147483647 default 0; limit integer 1..100 default 20;
status optional ACTIVE/INACTIVE hanya menu, food_item_id/raw_material_id optional
UUID hanya resep. Filter digabung AND; referensi filter tenant lain menghasilkan
list kosong. Urutan created_at lalu primary ID menurun, hanya nondeleted tenant.
Page: items array record, offset/limit integer, next_offset integer nullable;
semua field page selalu hadir, tidak ada total count. Contoh data page kosong:
`{"items":[],"offset":0,"limit":20,"next_offset":null}`.

### Payload dan aturan menu/resep

| FoodItemInput field | Tipe | Required | Nullable/default | Validasi |
|---|---|---|---|---|
| food_code | string | Ya | Tidak | 1..50; unik per tenant termasuk terhapus |
| food_name | string | Ya | Tidak | 1..200 |
| category | string | Tidak | Ya/null | Maksimal 100 |
| uom | string | Ya | Tidak | 1..30; tidak dapat berubah setelah create |
| holding_limit_minutes | integer strict | Tidak | Ya/null | 0..2147483647; bool/float ditolak |
| status | enum string | Tidak | Tidak/ACTIVE | ACTIVE atau INACTIVE |

| RecipeInput field | Tipe | Required | Nullable | Validasi |
|---|---|---|---|---|
| food_item_id | UUID | Ya | Tidak | Menu aktif/nondeleted satu tenant; immutable |
| raw_material_id | UUID | Ya | Tidak | Bahan aktif/nondeleted satu tenant; immutable |
| quantity | decimal | Ya | Tidak | >0; maksimal 14 digit dan 6 desimal; bukan NaN/infinity/bool |
| uom | string | Ya | Tidak | 1..30; harus sama persis dengan uom bahan |

PUT menambahkan `expected_version` integer strict 1..2147483647 wajib nonnull;
DELETE memakainya di query integer 1..2147483647 wajib. PUT adalah replace,
field optional yang tidak dikirim kembali ke default (termasuk status ACTIVE).
String ditrim; field tambahan, NUL dan UTF-8 invalid ditolak. Jangan kirim tenant,
ID primary, audit atau version selain expected_version. Decimal request boleh string;
respons quantity selalu string decimal.

Recipe create/PUT mengunci parent menu lalu bahan sebelum write; validasi parent
aktif mencegah perubahan serentak dengan deactivation/delete. Recipe food/material
pair tidak dapat dipindah; quantity dapat diperbarui. Pair unik per tenant, termasuk
soft-deleted, tidak ada restore/recreate pair. Menu/bahan inactive tetap dapat
memiliki resep historis yang terbaca; perubahan resep menunggu parent aktif kembali.
DELETE resep diizinkan saat parent inactive. Menu tidak dapat dihapus selama ada
resep nondeleted atau batch produksi yang menunjuknya (termasuk transaksi selesai).
Bahan juga terlindungi dari delete oleh resep nondeleted. Tidak ada cascade.

Write/delete menaikkan version satu kali, memelihara audit dan commit atomik.
Stale version 409; deleted/foreign/missing detail 404. Delete mengembalikan snapshot
beserta deleted_at/deleted_by; detail dan pengulangan delete berikutnya 404.
Kode menu/pasangan resep tetap dicadangkan, termasuk setelah soft delete.

### Contoh menu/resep

UUID dan identitas berikut fiktif; ganti dengan hasil API. Contoh request create:

```http
POST /api/v1/food-items
Authorization: Bearer <access_token>
Content-Type: application/json

{"food_code":"MENU-001","food_name":"Nasi contoh","uom":"portion","holding_limit_minutes":60}
```

Contoh **data** respons 201/menu detail 200 (di dalam envelope standar):

```json
{
  "food_item_id":"11111111-1111-4111-8111-111111111111",
  "food_code":"MENU-001",
  "food_name":"Nasi contoh",
  "category":null,
  "uom":"portion",
  "holding_limit_minutes":60,
  "status":"ACTIVE",
  "tenant_id":"77777777-7777-4777-8777-777777777777",
  "version":1,
  "created_at":"2026-09-11T09:00:00Z",
  "updated_at":"2026-09-11T09:00:00Z",
  "deleted_at":null,
  "created_by":"88888888-8888-4888-8888-888888888888",
  "updated_by":"88888888-8888-4888-8888-888888888888",
  "deleted_by":null
}
```

```http
POST /api/v1/recipes
Authorization: Bearer <access_token>
Content-Type: application/json

{"food_item_id":"11111111-1111-4111-8111-111111111111","raw_material_id":"33333333-3333-4333-8333-333333333333","quantity":"0.125000","uom":"kg"}
```

Contoh **data** respons 201/resep detail 200:

```json
{
  "recipe_id":"22222222-2222-4222-8222-222222222222",
  "food_item_id":"11111111-1111-4111-8111-111111111111",
  "raw_material_id":"33333333-3333-4333-8333-333333333333",
  "quantity":"0.125000",
  "uom":"kg",
  "tenant_id":"77777777-7777-4777-8777-777777777777",
  "version":1,
  "created_at":"2026-09-11T09:00:00Z",
  "updated_at":"2026-09-11T09:00:00Z",
  "deleted_at":null,
  "created_by":"88888888-8888-4888-8888-888888888888",
  "updated_by":"88888888-8888-4888-8888-888888888888",
  "deleted_by":null
}
```

Seluruh field respons selalu hadir. Field domain sama dengan tipe payload;
quantity respons decimal string, ID/tenant UUID string, version integer,
created_at/updated_at timestamp UTC nonnull, deleted_at timestamp UTC nullable;
created_by/updated_by/deleted_by UUID nullable sesuai schema audit (write HTTP
mengisi actor). Field domain nullable hanya category/holding_limit_minutes menu.
Resep tidak memiliki status; tidak menyertakan objek nested menu/bahan.

Contoh operasi selanjutnya, dengan header bearer yang sama; GET/DELETE tanpa body:

```http
GET /api/v1/food-items?status=ACTIVE&offset=0&limit=20
GET /api/v1/food-items/11111111-1111-4111-8111-111111111111
GET /api/v1/recipes?food_item_id=11111111-1111-4111-8111-111111111111&raw_material_id=33333333-3333-4333-8333-333333333333
GET /api/v1/recipes/22222222-2222-4222-8222-222222222222
```

```http
PUT /api/v1/recipes/22222222-2222-4222-8222-222222222222
Authorization: Bearer <access_token>
Content-Type: application/json

{"food_item_id":"11111111-1111-4111-8111-111111111111","raw_material_id":"33333333-3333-4333-8333-333333333333","quantity":"0.200000","uom":"kg","expected_version":1}
```

Sukses 200 memakai schema resep di atas dengan quantity `"0.200000"`, version 2,
updated_at/updated_by diperbarui; ID dan created_at/created_by tetap.

```http
PUT /api/v1/food-items/11111111-1111-4111-8111-111111111111
Authorization: Bearer <access_token>
Content-Type: application/json

{"food_code":"MENU-001","food_name":"Nasi contoh","uom":"portion","status":"INACTIVE","expected_version":1}
```

Sukses 200 memakai schema menu di atas, status INACTIVE, version 2 dan
holding_limit_minutes null karena optional dihilangkan. Resep tetap terbaca.

```http
DELETE /api/v1/recipes/22222222-2222-4222-8222-222222222222?expected_version=2
DELETE /api/v1/food-items/11111111-1111-4111-8111-111111111111?expected_version=2
```

Keduanya 200 jika tidak ada referensi penghalang lainnya: snapshot version 3,
deleted_at/updated_at waktu penghapusan dan deleted_by/updated_by actor. Hapus
resep dahulu sebelum menu. PUT/DELETE tidak mengembalikan 204.

### Error dan efek samping menu/resep

| Status | Message/kondisi |
|---|---|
| 400 | Validation Error; payload/path/query invalid; tidak memakai 422 |
| 400 | Request body must be empty; DELETE membawa body |
| 401 | Invalid credentials or session; bearer invalid/tidak ada |
| 403 | Required permission is not granted; Read/Write/Delete independen |
| 404 | Food not found; record missing/deleted/tenant lain |
| 409 | Food changed; reload before retrying; version stale |
| 409 | Food code or pair already exists in this tenant; termasuk soft-deleted |
| 409 | Active food item and material in this tenant required |
| 409 | Recipe unit must match material unit |
| 409 | Recipe food item and material cannot be changed |
| 409 | Food item unit cannot be changed |
| 409 | Master record is still referenced |
| 409 | Food item or material unavailable; FK unavailable |
| 500/503 | Error server/database/auth standar, tidak ada hasil write parsial |

Contoh error 409 lengkap:

```json
{"success":false,"code":409,"message":"Recipe unit must match material unit","data":null,"errors":[],"meta":{"request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","correlation_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","timestamp":"2026-09-11T09:00:00Z","execution_time_ms":1.2}}
```

Master menu/resep tidak membuat event_log, movement, stok, batch produksi atau
registry asset: tipe FOOD_ITEM/RECIPE belum didukung registry saat ini. Relasi
menu?bahan adalah FK recipe, bukan edge graph. Holding limit adalah konfigurasi,
dipakai oleh timer paket saat pengemasan; sensor/rule-action dinamis belum berjalan. Snapshot resep, hasil produksi, pemakaian stok dan
edge USED bahan ke hasil tersedia melalui transaksi produksi di bawah.
Enam permission development dapat diprovision melalui CLI
`provision_supply_permissions.py` dengan pilihan eksplisit FoodItem.Read/Write/Delete
dan Recipe.Read/Write/Delete; runtime diberi INSERT/SELECT dan UPDATE kolom terbatas.


## Kontrak transaksi produksi

Status: **6 endpoint produksi dan 1 endpoint riwayat pengeluaran stok aktif**
setelah migrasi `20260911_0019` dan grant runtime. Semua path di bawah memiliki
prefix `/api/v1`; bearer session wajib, tenant/actor berasal dari akun. Header:
`Authorization: Bearer <access_token>`; POST `Content-Type: application/json`.
Respons memakai envelope standar success/code/message/data/errors/meta serta
Cache-Control no-store, Pragma no-cache dan X-Request-ID.

| Method/path | Tujuan | Permission | Payload/query | Sukses |
|---|---|---|---|---|
| POST `/production-batches` | Rencana dan snapshot resep | Production.Write | ProductionInput; tanpa query | 201 detail |
| GET `/production-batches` | Daftar header + snapshot | Production.Read | Tanpa body; offset/limit/kitchen/menu/status | 200 page |
| GET `/production-batches/{identifier}` | Detail + bahan terpakai | Production.Read | UUID path; tanpa body/query | 200 detail |
| POST `/production-batches/{identifier}/start` | Mulai dan kurangi stok | Production.Start | UUID path; StartInput; tanpa query | 200 detail |
| POST `/production-batches/{identifier}/complete` | Catat hasil aktual | Production.Complete | UUID path; FinishInput; tanpa query | 200 detail |
| POST `/production-batches/{identifier}/cancel` | Batalkan rencana | Production.Cancel | UUID path; expected_version; tanpa query | 200 detail |
| GET `/raw-material-batches/{identifier}/stock-issues` | Ledger pengeluaran bahan | Stock.Read | UUID batch bahan; tanpa body; offset/limit | 200 page item |

Read/Write/Start/Complete/Cancel independen; start tidak memerlukan Stock.Putaway,
Stock.Read, Recipe.Read atau permission registry. Semua validasi tenant/parent tetap
dijalankan di service. Action mengembalikan snapshot walaupun aktor tidak punya Read.

### Payload, snapshot dan aturan produksi

ProductionInput: `batch_code` string wajib nonnull 1..100, unik per tenant termasuk
kode historis; `kitchen` UUID wajib nonnull kitchen aktif; `menu` UUID wajib nonnull
food item aktif; `planned_quantity` decimal wajib nonnull >0, maksimal 14 digit dan
6 desimal, dalam food_item.uom. String ditrim; bool, NaN/infinity, field tambahan,
NUL dan presisi berlebih ditolak. Tenant/actor/status/timestamp tidak boleh dikirim.

Create membutuhkan 1..100 baris resep nondeleted dengan bahan aktif satu tenant
serta uom sesuai bahan. Snapshot menyimpan food_version, uom hasil, recipe_id/version,
raw_material_id, quantity per unit, uom bahan dan required_quantity. Kebutuhan =
quantity resep * planned_quantity, dibulatkan HALF_UP ke enam desimal; setiap hasil
harus >0 dan <=99999999.999999. Nilai snapshot tetap walaupun master resep berubah.
Create tidak memesan atau mengurangi stok, sehingga start kelak masih bisa gagal.

StartInput: `expected_version` integer strict 1..2147483647 wajib untuk produksi;
`items` array wajib berisi 1..100 objek, setiap field objek wajib nonnull:

| Field item start | Tipe | Aturan |
|---|---|---|
| raw_material_batch_id | UUID | Batch bahan ACCEPTED dari receiving COMPLETED |
| storage_id | UUID | Storage aktif di kitchen produksi, sesuai tipe penyimpanan bahan |
| expected_version | integer strict | 1..2147483647; version batch bahan dari GET stock |
| quantity | decimal | >0, maksimal 14 digit/6 desimal, dalam uom snapshot bahan |

Setiap batch bahan hanya boleh muncul sekali (satu storage per batch per produksi).
Satu bahan resep boleh dipenuhi beberapa batch. Total per raw_material_id harus
**persis** required_quantity snapshot, tidak boleh ada bahan tambahan atau kurang.
Parent kitchen/menu/material/storage harus aktif nondeleted satu tenant. Receiving
berasal dari kitchen yang sama, item accepted=true, expiry tidak sebelum tanggal UTC
saat start (hari ini masih boleh). UOM material/receiving harus sama dengan snapshot.
Jumlah sumber <= putaway historis dikurangi seluruh issue pada batch/storage tersebut.

Start mengunci kitchen/storage/parent dan batch bahan dalam urutan tetap, memeriksa
version, kebutuhan dan saldo sebelum write. Seluruh issue, version batch bahan,
production RUNNING/version, registry, edge USED, movement ISSUE dan event dicatat
satu transaksi. Konflik tidak menyisakan pengurangan stok parsial. Dua request
version sama hanya dapat menghasilkan satu sukses; retry stale 409. Tidak ada
idempotency key; baca ulang detail/stock sebelum retry ketika respons tidak diketahui.

FinishInput: expected_version wajib seperti di atas dan `actual_quantity` decimal
wajib nonnull >=0, maksimal 14 digit/6 desimal, <= planned_quantity. `initial_temperature`
opsional nullable, -9999.99..9999.99, maksimal 2 desimal; ini suhu makanan awal
manual saat selesai masak dalam Celsius dan belum dievaluasi rule otomatis. Hanya
RUNNING bisa COMPLETED; hasil dalam snapshot.uom. Nol mewakili tidak ada hasil layak
dicatat, selisih terhadap rencana tidak mengembalikan stok. Timestamp started_at/
finished_at berasal dari server UTC. Cancel hanya CREATED dengan expected_version,
menjadi CANCELLED tanpa stok terpakai; tidak ada cancel RUNNING/reversal/edit/delete
produksi.

List produksi: offset integer 0..2147483647 default 0; limit 1..100 default 20;
kitchen/menu optional UUID; status optional CREATED/RUNNING/COMPLETED/CANCELLED.
Filter AND, hanya tenant nondeleted; urutan created_at lalu ID menurun.
Page: items array header (tanpa items pemakaian), offset/limit integer dan
next_offset integer nullable, semuanya required. Tidak ada total count.
Stock-issues memakai pagination sama, urutan batch_version menurun. Hanya issue yang
memiliki storage (bukan production_item legacy tanpa alokasi); item page memakai
schema production item di bawah. ID tenant lain untuk detail/stock-issues 404,
filter tenant lain menghasilkan list kosong. Detail items terurut UUID item menaik.

### Contoh request dan respons produksi

Contoh fiktif, ganti UUID dengan data hasil API:

```http
POST /api/v1/production-batches
Authorization: Bearer <access_token>
Content-Type: application/json

{"batch_code":"PROD-001","kitchen":"99999999-9999-4999-8999-999999999999","menu":"11111111-1111-4111-8111-111111111111","planned_quantity":"4"}
```

Contoh **data** sukses 201 (resep contoh membutuhkan 0.25 kg per portion):

```json
{
  "tenant_id": "77777777-7777-4777-8777-777777777777",
  "version": 1,
  "created_at": "2026-09-11T09:00:00Z",
  "updated_at": "2026-09-11T09:00:00Z",
  "deleted_at": null,
  "created_by": "88888888-8888-4888-8888-888888888888",
  "updated_by": "88888888-8888-4888-8888-888888888888",
  "deleted_by": null,
  "production_batch_id": "44444444-4444-4444-8444-444444444444",
  "batch_code": "PROD-001",
  "kitchen": "99999999-9999-4999-8999-999999999999",
  "menu": "11111111-1111-4111-8111-111111111111",
  "planned_quantity": "4.000000",
  "actual_quantity": null,
  "initial_temperature": null,
  "recipe_snapshot": {
    "schema_version": 1,
    "food_version": 1,
    "uom": "portion",
    "items": [
      {
        "recipe_id": "22222222-2222-4222-8222-222222222222",
        "version": 1,
        "raw_material_id": "33333333-3333-4333-8333-333333333333",
        "quantity": "0.250000",
        "required_quantity": "1.000000",
        "uom": "kg"
      }
    ],
    "food_category": null,
    "holding_limit_minutes": 60
  },
  "status": "CREATED",
  "started_at": null,
  "finished_at": null,
  "holding_started_at": null,
  "holding_expired_at": null,
  "items": []
}
```

Semua field respons hadir. ID/tenant/kitchen/menu string UUID nonnull; batch_code/status
string; planned_quantity/actual_quantity decimal string nullable (planned null hanya
legacy); initial_temperature decimal string nullable; recipe_snapshot object nullable
(null hanya legacy); timestamps UTC nullable kecuali audit created_at/updated_at.
Audit UUID nullable seperti kontrak master; version integer. Snapshot:
schema_version/food_version integer, uom string, items
array RecipeLine; RecipeLine ID UUID, version integer, quantity/required_quantity
string decimal, uom string, seluruh field nonnull. Detail `items` array selalu hadir,
kosong sebelum start; list header tidak menyertakannya. Holding fields tetap null
saat complete; alokasi paket kemudian membekukan holding policy dan mengisi
holding_started_at dari finished_at serta holding_expired_at.

```http
GET /api/v1/production-batches?status=CREATED&offset=0&limit=20
GET /api/v1/production-batches/44444444-4444-4444-8444-444444444444
```

GET memakai header bearer, tanpa body. Detail sama dengan contoh data di atas.
Contoh page kosong: `{"items":[],"offset":0,"limit":20,"next_offset":null}`.

```http
POST /api/v1/production-batches/44444444-4444-4444-8444-444444444444/start
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":1,"items":[{"raw_material_batch_id":"66666666-6666-4666-8666-666666666666","storage_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","expected_version":4,"quantity":"1"}]}
```

Sukses 200 detail sama, status RUNNING/version 2, started_at/updated_at waktu start,
snapshot tetap, items berisi objek berikut (contoh timestamp start sama dengan create):

```json
{
  "tenant_id": "77777777-7777-4777-8777-777777777777",
  "version": 1,
  "created_at": "2026-09-11T09:00:00Z",
  "updated_at": "2026-09-11T09:00:00Z",
  "deleted_at": null,
  "created_by": "88888888-8888-4888-8888-888888888888",
  "updated_by": "88888888-8888-4888-8888-888888888888",
  "deleted_by": null,
  "production_item_id": "55555555-5555-4555-8555-555555555555",
  "production_batch_id": "44444444-4444-4444-8444-444444444444",
  "raw_material_batch_id": "66666666-6666-4666-8666-666666666666",
  "storage_id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "batch_version": 5,
  "quantity": "1.000000",
  "uom": "kg"
}
```

Item: seluruh field required; primary/production/material ID UUID nonnull, quantity
string decimal nonnull, uom string nonnull; storage_id UUID dan batch_version integer
nullable hanya untuk legacy. API start mengisi keduanya. Audit seperti header,
version item 1, deleted_at/deleted_by null; trigger menolak UPDATE/DELETE/TRUNCATE.
`batch_version` adalah version bahan **setelah** pengeluaran, berbeda dari version
production dan version item. Item menjadi ledger issue stok, bukan alokasi rencana.

```http
POST /api/v1/production-batches/44444444-4444-4444-8444-444444444444/complete
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":2,"actual_quantity":"3","initial_temperature":"74.50"}
```

Sukses 200 detail status COMPLETED/version 3, actual_quantity `"3.000000"`,
initial_temperature `"74.50"`, finished_at/updated_at waktu server, snapshot dan
item pemakaian tetap. Registry, movement PRODUCTION di kitchen, dan event completed
atomik. Hasil tidak langsung menjadi package; zero yield tetap COMPLETED dengan
actual_quantity nol.

Contoh cancel untuk batch **lain** yang masih CREATED:

```http
POST /api/v1/production-batches/bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb/cancel
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":1}
```

Sukses 200 snapshot header batch itu dengan status CANCELLED/version 2, items kosong,
started_at/finished_at/actual_quantity/initial_temperature tetap null. Tidak ada
efek stok/movement.

```http
GET /api/v1/raw-material-batches/66666666-6666-4666-8666-666666666666/stock-issues?offset=0&limit=20
Authorization: Bearer <access_token>
```

Data 200 `{items:[item_di_atas],offset:0,limit:20,next_offset:null}`. Tidak membuat event.
GET stock kini menambah `issued_quantity` decimal string nonnull pada total dan
setiap storage; contoh accepted/putaway 2.5, issue 1 menghasilkan available 1.5 dan
unallocated 0. `storages[].quantity` tetap putaway historis, bukan saldo neto;
available_quantity menghitung quantity-issued ketika seluruh syarat eligibility
terpenuhi. Saat expired/inactive available menjadi nol, issue tetap historis.
GET stock-entries tetap hanya putaway; version dapat melompat karena issue juga
menaikkan version bahan. Pengeluaran tidak memungkinkan menerima/putaway ulang
bahan yang sama. Production item legacy tanpa storage tidak dianggap stok terpakai
oleh ledger baru; tidak ada backfill/reservasi otomatis.

### Error produksi dan efek samping

| Status | Message/kondisi |
|---|---|
| 400 | Validation Error; payload/path/query, duplikasi batch sumber, angka/bool/presisi invalid; tanpa 422 |
| 401 | Invalid credentials or session |
| 403 | Required permission is not granted |
| 404 | Production batch not found; record produksi missing/deleted/foreign |
| 409 | Production or material batch changed; reload before retrying |
| 409 | Production batch code already exists in this tenant |
| 409 | Active production references in this tenant required |
| 409 | Production requires 1..100 recipe lines |
| 409 | Recipe quantity and material unit must be valid |
| 409 | Recipe requirement outside supported quantity precision |
| 409 | Production must be CREATED / Production must be RUNNING |
| 409 | Legacy production has no executable recipe snapshot |
| 409 | Stock storage must belong to production kitchen |
| 409 | Material batch unavailable in this tenant |
| 409 | Material is not in recipe snapshot |
| 409 | Accepted stock from production kitchen required |
| 409 | Expired stock cannot be used (UTC date) |
| 409 | Storage type does not match material requirement |
| 409 | Stock unit does not match recipe snapshot |
| 409 | Insufficient available stock in selected storage |
| 409 | Material quantities must exactly match recipe snapshot requirements |
| 409 | Actual quantity cannot exceed planned quantity |
| 409 | Production reference unavailable / Production kitchen registry unavailable |
| 500/503 | Error server/database/auth standar; tidak ada write parsial |

Error stock-issues sama seperti GET stock: missing/deleted/foreign batch bahan 404
`Receiving or batch not found`; permission Stock.Read tetap independen.
Contoh error 409 lengkap:

```json
{"success":false,"code":409,"message":"Insufficient available stock in selected storage","data":null,"errors":[],"meta":{"request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","correlation_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","timestamp":"2026-09-11T09:00:00Z","execution_time_ms":1.2}}
```

Event internal `production.created/started/completed/cancelled` disimpan atomik,
bukan publish realtime. Start membangun edge USED dari registry batch bahan ke
registry batch produksi dan movement ISSUE dari storage ke kitchen; remarks UUID
production_item sehingga quantity dapat dilacak. Complete mencatat movement PRODUCTION
untuk batch hasil di kitchen. Create/cancel tidak menulis movement. Produksi tidak
otomatis membuat package; alokasi/holding menggunakan endpoint terpisah di bawah.
Tidak membuat FOOD_ITEM registry, notifikasi atau traversal API.
Legacy batch tanpa snapshot hanya dibaca, action ditolak. Tidak ada auto seed bisnis.
Lima permission development dapat dipilih eksplisit melalui CLI
`provision_receiving_permissions.py`; runtime hanya dapat INSERT production_item
serta memperbarui status/waktu/hasil/version produksi (snapshot tidak dapat diubah).


## Kontrak kemasan, paket dan holding

Status: **13 operasi aktif** setelah migrasi `20260911_0020`. Seluruh path memiliki
prefix `/api/v1`; bearer session dan tenant account wajib. Header request
Authorization: Bearer <access_token>, Content-Type: application/json pada POST/PUT.
Respons memakai envelope standar success/code/message/data/errors/meta, X-Request-ID,
Cache-Control no-store dan Pragma no-cache. Tidak ada endpoint QR publik.

### Master jenis kemasan

| Method/path | Permission | Body/query | Sukses |
|---|---|---|---|
| GET `/packaging-types` | PackagingType.Read | Tanpa body; offset/limit | 200 page |
| GET `/packaging-types/{identifier}` | PackagingType.Read | UUID path; tanpa body/query | 200 record |
| POST `/packaging-types` | PackagingType.Write | PackagingTypeInput; tanpa query | 201 record |
| PUT `/packaging-types/{identifier}` | PackagingType.Write | Input + expected_version; UUID path | 200 record |
| DELETE `/packaging-types/{identifier}` | PackagingType.Delete | UUID path; expected_version query wajib; body kosong | 200 snapshot terhapus |

| Field input | Tipe | Required | Nullable/default | Validasi |
|---|---|---|---|---|
| code | string | Ya | Tidak | Trim 1..50; unik per tenant termasuk soft-deleted |
| name | string | Ya | Tidak | Trim 1..200 |
| material | string | Tidak | Ya/null | Maksimal 100 |
| volume | decimal | Tidak | Ya/null | >0, 12 digit/3 desimal; milliliter |

Tidak ada status field. PUT replace, optional yang hilang menjadi null;
expected_version integer strict 1..2147483647 wajib di body PUT, integer dengan
rentang sama wajib di query DELETE. Field tambahan/bool/NUL/NaN/infinity ditolak.
List offset 0..2147483647 default 0, limit 1..100 default 20, created_at/ID menurun,
nondeleted tenant; page items/offset/limit/next_offset(nullable), tanpa total.
Read/Write/Delete independen. Semua write atomik dengan audit/version. DELETE tidak
cascade; package nondeleted termasuk discarded melindungi jenis kemasan (409).
Sesudah delete, detail/retry 404; code tetap dicadangkan. Tidak ada restore.
Volume bukan kapasitas dalam portion dan tidak otomatis dikonversi ke quantity paket.

```http
POST /api/v1/packaging-types
Authorization: Bearer <access_token>
Content-Type: application/json

{"code":"BOX-001","name":"Kotak contoh","material":"Paper","volume":"750.000"}
```

Contoh data respons 201/detail 200:

```json
{
  "tenant_id": "77777777-7777-4777-8777-777777777777",
  "version": 1,
  "created_at": "2026-09-11T09:05:00Z",
  "updated_at": "2026-09-11T09:05:00Z",
  "deleted_at": null,
  "created_by": "88888888-8888-4888-8888-888888888888",
  "updated_by": "88888888-8888-4888-8888-888888888888",
  "deleted_by": null,
  "package_type_id": "11111111-1111-4111-8111-111111111111",
  "code": "BOX-001",
  "name": "Kotak contoh",
  "material": "Paper",
  "volume": "750.000"
}
```

Semua field respons hadir: primary ID/tenant UUID nonnull, code/name string,
material string nullable, volume string decimal nullable, version integer,
created_at/updated_at UTC nonnull, deleted_at UTC nullable; created_by/updated_by/
deleted_by UUID nullable (write HTTP mengisi actor).

```http
GET /api/v1/packaging-types?offset=0&limit=20
GET /api/v1/packaging-types/11111111-1111-4111-8111-111111111111
```

Gunakan bearer, tanpa body. Data page kosong:
`{"items":[],"offset":0,"limit":20,"next_offset":null}`; item memakai schema di atas.

```http
PUT /api/v1/packaging-types/11111111-1111-4111-8111-111111111111
Authorization: Bearer <access_token>
Content-Type: application/json

{"code":"BOX-001","name":"Kotak baru","expected_version":1}
```

200 schema sama, name baru, material/volume null, version 2, audit update baru.
DELETE contoh berikut (tanpa body) 200 snapshot version 3 dengan deleted_at/deleted_by
serta updated_at/updated_by terisi, bila belum dirujuk package:

```http
DELETE /api/v1/packaging-types/11111111-1111-4111-8111-111111111111?expected_version=2
Authorization: Bearer <access_token>
```

### Alokasi paket dan QR

| Method/path | Permission | Body/query | Sukses |
|---|---|---|---|
| POST `/packages` | Package.Write | PackageInput; tanpa query | 201 PackageData |
| GET `/packages` | Package.Read | Tanpa body; production_batch_id UUID optional, offset/limit | 200 page PackageData |
| GET `/packages/{identifier}` | Package.Read | UUID path; tanpa body/query | 200 PackageData |
| GET `/packages/resolve` | Package.Read | Tanpa body; qr_payload string 1..100 wajib | 200 PackageData |
| GET `/production-batches/{identifier}/packaging` | Package.Read | UUID produksi; tanpa body/query | 200 AllocationData |

PackageInput seluruh field required/nonnull:

| Field | Tipe/validasi |
|---|---|
| production_batch_id | UUID produksi COMPLETED dengan actual_quantity/finished_at |
| expected_version | Integer strict 1..2147483647; **version produksi**, dari allocation/detail |
| package_type_id | UUID jenis kemasan nondeleted satu tenant |
| package_code | String trim 1..100; unik per tenant |
| package_number | Integer strict 1..2147483647; unik per produksi |
| quantity | Decimal >0, maksimal 14 digit/6 desimal; dalam output UOM snapshot produksi |
| initial_temperature | Decimal/null opsional; -9999.99..9999.99, maksimal 2 desimal; suhu awal pengemasan manual dalam Celsius |

Kitchen produksi aktif, quantity <= hasil aktual dikurangi seluruh paket, termasuk
DISCARDED. Tidak ada refund/reallocation/edit/delete paket. Package lama dengan
quantity null memblokir alokasi berikutnya hingga rekonsiliasi. Unallocated quantity
pada GET allocation menjadi null jika hasil/quantity legacy belum diketahui;
allocated_quantity tetap jumlah quantity yang diketahui. Tidak ada konversi volume.

Create mengunci parent dan produksi, memvalidasi expected_version, lalu mencatat
paket termasuk suhu awal pengemasan manual bila dikirim, menaikkan version produksi,
sync registry, edge PACKAGED, movement PACKAGING dan event package.created dalam
satu transaksi. Code/number duplikat menggagalkan
seluruh transaksi termasuk perubahan version/alokasi. Retry stale 409; tidak ada
idempotency key. Baca allocation kembali untuk memperoleh version berikutnya.

Saat alokasi pertama, holding policy dibekukan di produksi. Snapshot menu pada create
produksi kini menambah food_category dan holding_limit_minutes (nullable/default null
untuk legacy). Rule kategori yang cocok dibaca saat alokasi pertama. Effective maximum
adalah minimum menu limit dan rule maximum jika keduanya tersedia; jika hanya satu,
pakai nilai tersebut. Maximum harus positif. Warning = min(rule.warning, maximum),
atau 0 tanpa rule. Discard = min(rule.discard, menu limit) bila keduanya tersedia,
atau nilai sumber tunggal. Menu limit nol menolak pengemasan. Policy menyimpan rule
ID/version dan kategori; perubahan rule/menu berikutnya tidak memperpanjang waktu.

Deadline **selalu production.finished_at + maximum_minutes**, termasuk ketika
paket/holding baru dibuat belakangan. Create setelah deadline ditolak. Kolom produksi
holding_started_at/holding_expired_at terisi saat alokasi pertama; holding_started_at
bernilai finished_at. Package creation tidak langsung menandai proses holding started.

List paket: offset/limit dan page seperti master, filter production_batch_id AND tenant,
created_at/ID menurun. Filter produksi asing memberi list kosong. QR payload kanonik
`fsos:package:<package_id>` non-secret, unik berdasarkan UUID. Frontend dapat merender
payload ini sebagai QR; **belum ada endpoint gambar/label cetak QR**. Resolve memerlukan
bearer; payload bukan hak akses atau token. UUID paket tenant lain/tidak ada/deleted 404.

```http
POST /api/v1/packages
Authorization: Bearer <access_token>
Content-Type: application/json

{"production_batch_id":"44444444-4444-4444-8444-444444444444","expected_version":3,"package_type_id":"11111111-1111-4111-8111-111111111111","package_code":"PKG-001","package_number":1,"quantity":"2","initial_temperature":"65.25"}
```

Contoh data 201, produksi selesai 09:00, evaluasi 09:05, rule maximum 60/warning 30/
discard 90 dan tanpa menu cap:

```json
{
  "tenant_id": "77777777-7777-4777-8777-777777777777",
  "version": 1,
  "created_at": "2026-09-11T09:05:00Z",
  "updated_at": "2026-09-11T09:05:00Z",
  "deleted_at": null,
  "created_by": "88888888-8888-4888-8888-888888888888",
  "updated_by": "88888888-8888-4888-8888-888888888888",
  "deleted_by": null,
  "package_id": "22222222-2222-4222-8222-222222222222",
  "package_code": "PKG-001",
  "production_batch_id": "44444444-4444-4444-8444-444444444444",
  "package_type_id": "11111111-1111-4111-8111-111111111111",
  "package_number": 1,
  "quantity": "2.000000",
  "initial_temperature": "65.25",
  "uom": "portion",
  "status": "CREATED",
  "effective_status": "CREATED",
  "qr_payload": "fsos:package:22222222-2222-4222-8222-222222222222",
  "holding_started_at": null,
  "holding_finished_at": null,
  "expired_at": "2026-09-11T10:00:00Z",
  "remaining_minutes": 55,
  "remaining_seconds": 3300,
  "timer_status": "SAFE",
  "holding_eligible": false,
  "calculated_at": "2026-09-11T09:05:00Z",
  "holding_policy": {
    "schema_version": 1,
    "rule_id": "33333333-3333-4333-8333-333333333333",
    "rule_version": 1,
    "food_category": "EXAMPLE_ONLY",
    "maximum_minutes": 60,
    "warning_minutes": 30,
    "discard_minutes": 90
  }
}
```

PackageData seluruh field required kecuali field nullable. `asset_uuid` berisi UUID registry traceability untuk membuka `/traceability/assets/{asset_uuid}`; nilainya nullable untuk paket legacy yang belum tersinkron. ID/package_code/production_id/number/status dan
QR nonnull; quantity decimal string, initial_temperature decimal string nullable,
uom string, package_type_id UUID nullable untuk legacy. Policy object nullable untuk
legacy; policy schema_version/maximum/warning/discard integer nonnull, food_category
string nullable, rule_id UUID/rule_version integer nullable jika memakai menu limit
saja. Timestamp holding_start/finish/expired nullable UTC; calculated_at UTC nonnull;
remaining_seconds/minutes integer nullable untuk UNKNOWN. Audit sama dengan master.
holding_eligible boolean nonnull.

```http
GET /api/v1/packages?production_batch_id=44444444-4444-4444-8444-444444444444&offset=0&limit=20
GET /api/v1/packages/22222222-2222-4222-8222-222222222222
GET /api/v1/packages/resolve?qr_payload=fsos%3Apackage%3A22222222-2222-4222-8222-222222222222
GET /api/v1/production-batches/44444444-4444-4444-8444-444444444444/packaging
```

Gunakan bearer, tanpa body. Get/resolve mengembalikan PackageData termasuk `asset_uuid` registry package bila tersedia, dengan timer dihitung
ulang pada calculated_at; page memakai items array PackageData. AllocationData contoh
setelah mengalokasi 2 dari hasil 3:

```json
{
  "production_batch_id": "44444444-4444-4444-8444-444444444444",
  "version": 4,
  "actual_quantity": "3.000000",
  "allocated_quantity": "2.000000",
  "unallocated_quantity": "1.000000",
  "uom": "portion",
  "holding_policy": {
    "schema_version": 1,
    "rule_id": "33333333-3333-4333-8333-333333333333",
    "rule_version": 1,
    "food_category": "EXAMPLE_ONLY",
    "maximum_minutes": 60,
    "warning_minutes": 30,
    "discard_minutes": 90
  }
}
```

Allocation field required: ID UUID/version integer, actual_quantity decimal string
nullable, allocated_quantity decimal string nonnull, unallocated_quantity decimal
string nullable untuk legacy, uom string nullable, holding_policy object nullable.

### Lifecycle holding paket

| Method/path | Permission | Body wajib | Sukses |
|---|---|---|---|
| POST `/packages/{identifier}/holding/start` | Holding.Start | expected_version | 200 PackageData |
| POST `/packages/{identifier}/holding/update` | Holding.Update | expected_version | 200 PackageData |
| POST `/packages/{identifier}/holding/finish` | Holding.Finish | expected_version, outcome RELEASED atau DISCARDED | 200 PackageData |

Path UUID paket; tanpa query. expected_version integer strict 1..2147483647 wajib
nonnull adalah **version paket**. Semua payload menolak field tambahan; client tidak
boleh mengirim waktu, batas holding atau remaining time. Permission aksi terpisah dari
Package.Read/Write dan HoldingRule.Read/Write. Tidak perlu permission registry/log.

Start: CREATED belum dimulai dan belum expired menjadi PACKAGED, holding_started_at
mengikuti waktu cooking finished. Update: menghitung ulang dan menyimpan EXPIRED bila
terlewati, tanpa memperpanjang deadline. Finish RELEASED: hanya PACKAGED belum expired,
menandai keluar dari proses holding station dan mencatat holding_finished_at. Finish
DISCARDED: paket CREATED/PACKAGED/EXPIRED/RELEASED dapat dibuang; paket yang dikelola delivery
(ALLOCATED/IN_TRANSIT/DELIVERED) ditolak pada seluruh aksi holding (409);
DISCARDED final, tidak dapat diubah lagi. Discard tidak membebaskan hasil produksi.

`status` adalah status tersimpan (CREATED/PACKAGED/RELEASED/ALLOCATED/IN_TRANSIT/DELIVERED/EXPIRED/DISCARDED; legacy
bisa lain). `effective_status` adalah hasil evaluasi waktu: EXPIRED jika deadline habis,
tetapi DISCARDED tetap terminal. `timer_status` SAFE/WARNING/EXPIRED/DISCARD_RECOMMENDED,
atau UNKNOWN jika policy/deadline legacy tidak tersedia. Tidak ada CRITICAL karena
schema holding_rule belum memiliki ambang critical. Aturan evaluasi:

- remaining_seconds = floor(expired_at - now dalam detik), dapat negatif;
  remaining_minutes = floor(remaining_seconds/60), termasuk nilai negatif.
- Jika elapsed sejak produksi selesai >= discard_minutes: DISCARD_RECOMMENDED.
- Jika remaining_seconds <=0: EXPIRED. Pembulatan konservatif dapat menolak saat
  sisa kurang dari satu detik; tidak ada perpanjangan setelah release.
- Jika remaining_seconds <= warning_minutes*60: WARNING; sisanya SAFE.

holding_eligible true hanya effective_status RELEASED dengan timer SAFE/WARNING.
Ini keputusan timer/proses holding, bukan verifikasi sensor, recall, manifest atau
jaminan kelayakan makanan keseluruhan. Status RELEASED tidak berarti CONSUMED atau
sudah dikirim. Endpoint pengiriman memvalidasi ulang kondisi paket dan ETA saat
berangkat. ALLOCATED/IN_TRANSIT/DELIVERED dikelola alur delivery, bukan aksi holding.

GET selalu menghitung ulang tanpa update DB/event; frontend memakai effective_status,
holding_eligible dan calculated_at, bukan menganggap status tersimpan masih berlaku.
Update materialisasi expiry menulis holding.expired hanya saat pertama menjadi
EXPIRED; update berikutnya holding.updated. Tiap aksi sukses menaikkan version,
sync registry dan menulis holding_log immutable serta event dalam satu transaksi.
Stale/retry version lama 409. Tidak ada scheduler/background alarm/telemetry adjustment
atau notifikasi otomatis pada tahap ini; polling GET menampilkan expiry, POST update
mencatat perubahan. Tidak ada auto discard, meskipun timer merekomendasikannya.

```http
POST /api/v1/packages/22222222-2222-4222-8222-222222222222/holding/start
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":1}
```

200 PackageData: status/effective_status PACKAGED, version 2, holding_started_at
09:00 (waktu produksi), expired_at tetap 10:00. Log/event started dicatat.

```http
POST /api/v1/packages/22222222-2222-4222-8222-222222222222/holding/update
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":2}
```

Jika pukul 09:40, 200 status PACKAGED/version 3, timer WARNING, remaining_seconds
1200/remaining_minutes 20; jika sesudah 10:00, status EXPIRED dan release tidak boleh.

```http
POST /api/v1/packages/22222222-2222-4222-8222-222222222222/holding/finish
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":3,"outcome":"RELEASED"}
```

Sebelum expired, 200 status RELEASED/version 4, holding_finished_at waktu aksi,
holding_eligible true; setelah deadline GET tetap menghasilkan effective EXPIRED
meskipun status tersimpan RELEASED. Untuk membuang, gunakan outcome DISCARDED dengan
version terkini; respons 200 status DISCARDED, holding_eligible false, version naik.

### Error dan batas pengemasan

| Status | Message/kondisi |
|---|---|
| 400 | Validation Error; payload/path/query/presisi/bool invalid; tanpa 422 |
| 400 | Request body must be empty pada DELETE master |
| 401 | Invalid credentials or session |
| 403 | Required permission is not granted |
| 404 | Packaging type not found (master); Package or production not found (paket/alokasi), termasuk tenant lain |
| 409 | Packaging type changed; reload before retrying / Package or production changed; reload before retrying |
| 409 | Packaging type code already exists in this tenant / Package code or number already exists in this tenant |
| 409 | Master record is still referenced |
| 409 | Kitchen and packaging type in this tenant required / Active kitchen required |
| 409 | Completed production with actual yield required |
| 409 | Legacy packages require quantity reconciliation |
| 409 | Package quantity exceeds unallocated production yield |
| 409 | Positive holding policy from production snapshot or category rule required |
| 409 | Production holding time has expired |
| 409 | Invalid package QR payload |
| 409 | Legacy package has no executable holding policy |
| 409 | Discarded package is final |
| 409 | Package is managed by delivery or downstream workflow |
| 409 | Only unexpired CREATED package can start holding |
| 409 | Only unexpired PACKAGED package can be released |
| 409 | Packaging type unavailable / Packaging reference unavailable (FK) |
| 500/503 | Error server/database/auth standar; write tidak parsial |

Contoh error:

```json
{"success":false,"code":409,"message":"Package quantity exceeds unallocated production yield","data":null,"errors":[],"meta":{"request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","correlation_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","timestamp":"2026-09-11T09:05:00Z","execution_time_ms":1.2}}
```

QR hanya identitas, tidak menyertakan credential. Registry PACKAGE disinkron pada
create dan aksi holding, edge PACKAGED menghubungkan batch produksi ke paket,
movement PACKAGING menuju kitchen. Master jenis kemasan tidak menulis event/registry.
Holding log dan package/holding events internal, belum dipublikasikan realtime.
Tidak ada endpoint edit/delete/void paket, cetak QR atau history
holding HTTP khusus. Production snapshot legacy tanpa kategori/limit tidak dapat dipaketkan oleh API ini;
migrasi tidak mengisi atau mengubah snapshot historis.
Grant development minimum melalui CLI supply untuk PackagingType.Read/Write/Delete
dan CLI receiving untuk Package.Read/Write, Holding.Start/Update/Finish.


## Kontrak pengiriman

Status **6 endpoint aktif**, migrasi `20260911_0021` dan grant runtime diperlukan.
Seluruh path memakai prefix `/api/v1`. Header wajib Authorization: Bearer
<access_token>; POST Content-Type: application/json. Tenant/operator dari session,
bukan payload. Respons envelope standar success/code/message/data/errors/meta,
Cache-Control no-store, Pragma no-cache dan X-Request-ID.

| Method/path | Tujuan | Permission | Body/query | Sukses |
|---|---|---|---|---|
| POST `/deliveries` | Buat manifest, reservasi dan estimasi route | Delivery.Write | DeliveryInput; tanpa query | 201 DeliveryDetail |
| GET `/deliveries` | Daftar header perjalanan | Delivery.Read | Tanpa body; offset/limit/kitchen_id/vehicle/driver/status | 200 DeliveryPage |
| GET `/deliveries/packages/by-vehicle` | Ringkasan kemasan per armada | Delivery.Read | Tanpa body; offset/limit/vehicle/status | 200 VehicleSummaryPage |
| GET `/deliveries/packages/by-destination` | Ringkasan kemasan per tujuan sekolah | Delivery.Read | Tanpa body; offset/limit/school_id/status | 200 DestinationSummaryPage |
| GET `/deliveries/{identifier}` | Detail manifest dan paket terkini | Delivery.Read | UUID path; tanpa body/query | 200 DeliveryDetail |
| GET `/deliveries/{identifier}/tracking` | Tracking GPS/suhu terakhir dan sisa jarak/waktu | Delivery.Read | UUID path; tanpa body/query | 200 TrackingData |
| POST `/deliveries/{identifier}/depart` | Berangkat + loading | Delivery.Depart | UUID path; DepartureInput; tanpa query | 200 DeliveryDetail |
| POST `/deliveries/{identifier}/complete` | Konfirmasi seluruh tujuan selesai | Delivery.Complete | UUID path; expected_version; tanpa query | 200 DeliveryDetail |
| POST `/deliveries/{identifier}/cancel` | Batalkan sebelum berangkat | Delivery.Cancel | UUID path; expected_version; tanpa query | 200 DeliveryDetail |

Read/Write/Depart/Complete/Cancel independen. Delivery.Read/aksi memberikan informasi
paket yang diperlukan manifest tanpa Package.Read. Tidak memerlukan permission
registry atau movement terpisah; tenant/referensi tetap diverifikasi oleh service.
Tidak ada PUT/PATCH/DELETE manifest; koreksi CREATED dengan cancel lalu create baru.

### Payload dan validasi manifest

DeliveryInput semua field wajib nonnull:

| Field | Tipe | Validasi |
|---|---|---|
| kitchen_id | UUID | Kitchen asal aktif satu tenant |
| vehicle | UUID | Kendaraan aktif; bukan field vehicle_id |
| driver | UUID | Driver aktif; bukan field driver_id |
| average_speed_kmph | Decimal/null opsional | >0, maksimal 6 digit/2 desimal; default estimasi 30 km/jam |
| items | array ManifestItem | 1..100 paket unik, satu school per paket |
| items[].package_id | UUID | Paket RELEASED dengan quantity nonnull, timer SAFE/WARNING |
| items[].school_id | UUID | Sekolah aktif satu tenant dan kitchen sama dengan asal |
| items[].expected_version | integer strict | 1..2147483647, **version paket** dari GET package/QR resolve |

Paket berasal dari produksi COMPLETED di kitchen asal dan sudah menyelesaikan holding
release. Driver pilihan harus sama dengan vehicle.driver_id bila kendaraan memiliki
assignment default; jika null, driver aktif pilihan diperbolehkan. Vehicle/driver
hanya boleh digunakan satu delivery CREATED atau IN_TRANSIT sekaligus. Paket hanya
boleh berada pada satu manifest non-CANCELLED, termasuk yang COMPLETED. Check dilakukan
di bawah row lock driver, vehicle, kitchen, sekolah, dan paket berurutan.

Create menghitung estimasi jarak dan durasi dari koordinat kitchen asal ke sekolah
tujuan terjauh memakai rumus garis lurus/haversine dan default 30 km/jam bila
`average_speed_kmph` tidak dikirim. Untuk multi-sekolah, estimasi adalah jarak
terjauh satu arah, bukan optimasi rute multi-stop. Jika koordinat kitchen/sekolah
belum lengkap, field estimasi null dan depart wajib menerima ETA manual. Create
mengubah package.status menjadi ALLOCATED dan version paket +1, membuat header/
version 1 dan manifest immutable, sync registry paket/delivery serta event. Tidak
membuat movement sebelum berangkat. Paket/kendaraan/driver tetap dicadangkan sampai
delivery dibatalkan atau selesai. Tidak ada auto-release reservasi expired. Seluruh
pemeriksaan/write atomik; satu item gagal menggagalkan seluruh manifest. Tidak ada
idempotency key create: retry dengan version paket lama 409, bukan create manifest
kedua. Baca ulang daftar/detail ketika hasil request tidak diketahui.

DepartureInput: expected_version integer strict 1..2147483647 wajib nonnull untuk
**delivery**, dan estimated_arrival_time datetime ISO8601 opsional nullable dengan
timezone bila dikirim. Jika omitted, backend menghitung ulang ETA dari jarak/durasi
route memakai departure_time server. Service memeriksa ETA masih future setelah
memperoleh lock. ETA harus **lebih awal** dari expired_at setiap paket; tepat pada
deadline ditolak. Parent/assignment aktif, status ALLOCATED dan timer dicek ulang
saat depart. Sukses mengubah delivery dan paket ke IN_TRANSIT, mencatat departure_time
server UTC dan ETA, version delivery/paket +1, edge LOADED dan movement VEHICLE_LOADING
menuju kendaraan. Tidak ada status LOADED terpisah, GPS live atau pengubahan ETA
setelah depart.

Complete: expected_version wajib di body, hanya IN_TRANSIT. Pemanggil mengonfirmasi
**seluruh** paket telah tiba secara fisik di sekolah pada manifest. Arrival_time server
UTC berlaku untuk penyelesaian perjalanan, bukan timestamp individual setiap stop.
Delivery COMPLETED dan paket DELIVERED, version naik, edge/movement ke masing-masing
sekolah. Kedatangan terlambat/expired atau parent menjadi INACTIVE tidak memblokir
pencatatan fakta kedatangan. Timer tetap berjalan, effective_status bisa EXPIRED.
Complete **tidak** membuat school_receiving, accepted, bukti kondisi/foto, konsumsi,
atau menyatakan makanan layak. Verifikasi penerimaan sekolah merupakan modul berikutnya.

Cancel: hanya CREATED dengan expected_version delivery; paket ALLOCATED dilepas ke
RELEASED bila timer SAFE/WARNING, selain itu EXPIRED. Version paket/delivery naik,
manifest tetap tersimpan dan driver/kendaraan bebas dipilih kembali. Tidak membuat
movement/edge, tidak mereset deadline, tidak boleh cancel IN_TRANSIT/COMPLETED.
Paket yang dibatalkan boleh dialokasikan ulang jika kembali memenuhi syarat.

Seluruh aksi holding pada paket ALLOCATED/IN_TRANSIT/DELIVERED ditolak 409
`Package is managed by delivery or downstream workflow`. GET paket/QR tetap
mengevaluasi expiry tanpa mutasi. holding_eligible false ketika paket sudah dialokasikan;
depart memakai pemeriksaan timer dan status ALLOCATED sendiri.

List: offset integer 0..2147483647 default 0; limit integer 1..100 default 20;
kitchen_id/vehicle/driver optional UUID, status optional CREATED/IN_TRANSIT/COMPLETED/
CANCELLED. AND filters, hanya nondeleted tenant, created_at/ID descending. Foreign
filter memberi list kosong; detail foreign/deleted/missing 404. Tidak ada total count.
Page required items array DeliveryData (tanpa manifest), offset/limit integer dan
next_offset integer nullable. Detail items sorted package_id ascending, bukan urutan
rute; nested package merupakan **keadaan/timer terkini**, bukan snapshot sejarah.
Misalnya manifest CANCELLED dapat memperlihatkan paket yang kemudian dikirim ulang.
Snapshot historis tiap transisi tersedia pada event internal, bukan GET detail lama.

Ringkasan kemasan per armada/tujuan memakai Delivery.Read dan tidak membuat event.
`/deliveries/packages/by-vehicle` menerima query `vehicle` UUID opsional dan
`status` opsional; hasil digroup per vehicle. `/deliveries/packages/by-destination`
menerima `school_id` UUID opsional dan `status` opsional; hasil digroup per school.
Kedua endpoint menerima offset/limit seperti list delivery, urutan package_count lalu
delivery_count menurun. Field item: `vehicle` atau `school_id` UUID, `delivery_count`
integer, `package_count` integer, `total_quantity` decimal string, dan `uom` string
nullable. `uom=null` berarti group berisi paket dengan output UOM berbeda atau UOM
legacy tidak lengkap. `total_quantity` menjumlahkan package.quantity yang diketahui;
jumlah kemasan gunakan `package_count`.

Tracking delivery memakai Delivery.Read dan read-only. `GET /deliveries/{identifier}/tracking`
mengambil GPS terakhir dari `gps_log` berdasarkan vehicle manifest, suhu terakhir dari
`temperature_log` device GPS kendaraan bila ada, lalu menghitung sisa jarak garis lurus
ke sekolah tujuan terjauh. Remaining duration memakai speed GPS terakhir; bila speed
kosong/nol, memakai estimasi route delivery; fallback 30 km/jam. Jika belum ada GPS
atau koordinat tujuan tidak lengkap, `latest_gps` dan remaining field dapat null.
Response field: delivery_id, vehicle, status, destination_count, latest_gps nullable
(gps_log_id, recorded_at, latitude, longitude, speed, heading), latest_temperature
nullable (temperature_log_id, device_uuid, recorded_at, temperature, unit),
remaining_distance_km nullable, remaining_duration_minutes nullable,
estimated_arrival_time nullable dan calculated_at UTC. Endpoint ini bukan MQTT
ingestion, bukan WebSocket dan tidak menulis event.

### HTTP ingestion telemetry GPS dan suhu

Status **aktif HTTP ingestion**, bukan MQTT broker. Prefix `/api/v1/telemetry`,
bearer session wajib dengan permission `Telemetry.Ingest`; tenant/actor dari sesi.
Kedua endpoint append-only, `mqtt_message_id=null`, tidak menulis event_log, dan
dipakai oleh dashboard/tracking sebagai sampel terakhir.

| Method/path | Payload | Sukses |
|---|---|---|
| POST `/telemetry/gps` | vehicle_uuid, latitude, longitude, speed/heading/altitude/hdop/satellite opsional, recorded_at opsional | 201 GpsIngestData |
| POST `/telemetry/temperatures` | device_uuid, storage_uuid opsional, temperature, unit C/F/K default C, recorded_at opsional | 201 TemperatureIngestData |

`recorded_at` opsional timezone-aware dan tidak boleh masa depan; bila null/omitted,
server memakai waktu UTC sekarang. GPS memerlukan vehicle aktif satu tenant.
Temperature memerlukan device REGISTERED/ACTIVE satu tenant; storage bila dikirim
harus aktif satu tenant. Tidak ada deduplikasi idempotency payload, API key device,
validasi binding device-ke-vehicle/storage, atau parsing MQTT pada endpoint ini.

```http
POST /api/v1/telemetry/gps
Authorization: Bearer <access_token>
Content-Type: application/json

{"vehicle_uuid":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","latitude":"-7.250000","longitude":"112.750000","speed":"30.000","heading":"90.000","recorded_at":"2026-09-11T09:15:00Z"}
```

```http
POST /api/v1/telemetry/temperatures
Authorization: Bearer <access_token>
Content-Type: application/json

{"device_uuid":"33333333-3333-4333-8333-333333333333","storage_uuid":null,"temperature":"60.500","unit":"C","recorded_at":"2026-09-11T09:15:00Z"}
```

### Contoh pengiriman

Contoh UUID fiktif: paket sudah RELEASED version 3, produksi/kitchen dan sekolah
berasal dari tenant yang sama. Request create:

```http
POST /api/v1/deliveries
Authorization: Bearer <access_token>
Content-Type: application/json

{"kitchen_id":"99999999-9999-4999-8999-999999999999","vehicle":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","driver":"bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb","average_speed_kmph":"30.00","items":[{"package_id":"22222222-2222-4222-8222-222222222222","school_id":"cccccccc-cccc-4ccc-8ccc-cccccccccccc","expected_version":3}]}
```

Contoh **data** respons 201:

```json
{
  "tenant_id": "77777777-7777-4777-8777-777777777777",
  "created_at": "2026-09-11T09:05:00Z",
  "updated_at": "2026-09-11T09:05:00Z",
  "deleted_at": null,
  "created_by": "88888888-8888-4888-8888-888888888888",
  "updated_by": "88888888-8888-4888-8888-888888888888",
  "deleted_by": null,
  "version": 1,
  "delivery_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
  "kitchen_id": "99999999-9999-4999-8999-999999999999",
  "vehicle": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
  "driver": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
  "status": "CREATED",
  "departure_time": null,
  "estimated_arrival_time": "2026-09-11T09:25:00Z",
  "estimated_distance_km": "9.850",
  "estimated_duration_minutes": 20,
  "arrival_time": null,
  "items": [
    {
      "tenant_id": "77777777-7777-4777-8777-777777777777",
      "created_at": "2026-09-11T09:05:00Z",
      "updated_at": "2026-09-11T09:05:00Z",
      "deleted_at": null,
      "created_by": "88888888-8888-4888-8888-888888888888",
      "updated_by": "88888888-8888-4888-8888-888888888888",
      "deleted_by": null,
      "version": 1,
      "delivery_item_id": "eeeeeeee-eeee-4eee-8eee-eeeeeeeeeeee",
      "delivery_id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
      "package_id": "22222222-2222-4222-8222-222222222222",
      "school_id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
      "package": {
        "tenant_id": "77777777-7777-4777-8777-777777777777",
        "version": 4,
        "created_at": "2026-09-11T09:05:00Z",
        "updated_at": "2026-09-11T09:05:00Z",
        "deleted_at": null,
        "created_by": "88888888-8888-4888-8888-888888888888",
        "updated_by": "88888888-8888-4888-8888-888888888888",
        "deleted_by": null,
        "package_id": "22222222-2222-4222-8222-222222222222",
        "package_code": "PKG-001",
        "production_batch_id": "44444444-4444-4444-8444-444444444444",
        "package_type_id": "11111111-1111-4111-8111-111111111111",
        "package_number": 1,
        "quantity": "2.000000",
        "uom": "portion",
        "status": "ALLOCATED",
        "effective_status": "ALLOCATED",
        "qr_payload": "fsos:package:22222222-2222-4222-8222-222222222222",
        "holding_started_at": "2026-09-11T09:00:00Z",
        "holding_finished_at": "2026-09-11T09:04:00Z",
        "expired_at": "2026-09-11T10:00:00Z",
        "remaining_minutes": 55,
        "remaining_seconds": 3300,
        "timer_status": "SAFE",
        "holding_eligible": false,
        "calculated_at": "2026-09-11T09:05:00Z",
        "holding_policy": {
          "schema_version": 1,
          "rule_id": "33333333-3333-4333-8333-333333333333",
          "rule_version": 1,
          "food_category": "EXAMPLE_ONLY",
          "maximum_minutes": 60,
          "warning_minutes": 30,
          "discard_minutes": 90
        }
      }
    }
  ]
}
```

Semua field respons hadir. DeliveryData: delivery_id/vehicle/driver UUID nonnull,
kitchen_id UUID nullable untuk legacy; status string; departure_time/arrival_time/
estimated_arrival_time UTC nullable; estimated_distance_km decimal string nullable
dan estimated_duration_minutes integer nullable. Audit version integer, created_at/
updated_at UTC nonnull, deleted_at UTC nullable, created_by/updated_by/deleted_by
UUID nullable (write HTTP mengisi actor). Detail items array required; item berisi
primary/delivery/package/school UUID nonnull dan audit yang sama, version item tetap
1. Nested package semua field mengikuti PackageData pada kontrak holding; quantity/
UOM dibaca dari paket, tidak dikirim ulang pada manifest.

```http
GET /api/v1/deliveries?status=CREATED&kitchen_id=99999999-9999-4999-8999-999999999999&offset=0&limit=20
GET /api/v1/deliveries/packages/by-vehicle?status=IN_TRANSIT&offset=0&limit=20
GET /api/v1/deliveries/packages/by-destination?school_id=cccccccc-cccc-4ccc-8ccc-cccccccccccc&status=COMPLETED
GET /api/v1/deliveries/dddddddd-dddd-4ddd-8ddd-dddddddddddd
GET /api/v1/deliveries/dddddddd-dddd-4ddd-8ddd-dddddddddddd/tracking
```

Header bearer wajib; tidak ada body. Detail memakai data di atas dengan timer saat
request; page kosong `{"items":[],"offset":0,"limit":20,"next_offset":null}`.
Contoh item ringkasan armada:

```json
{"vehicle":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","delivery_count":2,"package_count":50,"total_quantity":"100.000000","uom":"portion","tenant_id":"77777777-7777-4777-8777-777777777777","version":1,"created_at":"2026-09-11T09:05:00Z","updated_at":"2026-09-11T09:05:00Z","deleted_at":null,"created_by":"88888888-8888-4888-8888-888888888888","updated_by":"88888888-8888-4888-8888-888888888888","deleted_by":null}
```

Contoh data tracking:

```json
{"delivery_id":"dddddddd-dddd-4ddd-8ddd-dddddddddddd","vehicle":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","status":"IN_TRANSIT","destination_count":1,"latest_gps":{"gps_log_id":"11111111-1111-4111-8111-111111111111","recorded_at":"2026-09-11T09:15:00Z","latitude":"-7.250000","longitude":"112.750000","speed":"30.000","heading":"90.000"},"latest_temperature":{"temperature_log_id":"22222222-2222-4222-8222-222222222222","device_uuid":"33333333-3333-4333-8333-333333333333","recorded_at":"2026-09-11T09:15:00Z","temperature":"60.500","unit":"C"},"remaining_distance_km":"4.120","remaining_duration_minutes":9,"estimated_arrival_time":"2026-09-11T09:24:00Z","calculated_at":"2026-09-11T09:15:10Z"}
```

```http
POST /api/v1/deliveries/dddddddd-dddd-4ddd-8ddd-dddddddddddd/depart
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":1}
```

Jika manifest memiliki koordinat lengkap, backend menghitung ETA dari waktu depart.
Frontend tetap boleh mengirim estimated_arrival_time manual untuk override. Sukses
200 data yang sama dengan delivery.status IN_TRANSIT/version 2, departure_time server
UTC, estimated_arrival_time hasil hitung/override, package.status IN_TRANSIT/version
5. Item manifest tetap version 1; deadline, quantity dan policy tidak berubah.

```http
POST /api/v1/deliveries/dddddddd-dddd-4ddd-8ddd-dddddddddddd/complete
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":2}
```

200: delivery COMPLETED/version 3, arrival_time server UTC; package DELIVERED/version 6.
Jika tiba sesudah deadline, nested package effective_status EXPIRED dengan
holding_eligible false. Tidak ada school_receiving otomatis.

Cancel contoh untuk delivery **lain** yang masih CREATED:

```http
POST /api/v1/deliveries/ffffffff-ffff-4fff-8fff-ffffffffffff/cancel
Authorization: Bearer <access_token>
Content-Type: application/json

{"expected_version":1}
```

200: header CANCELLED/version 2, departure_time/arrival_time/estimated_arrival_time
masih null; tiap package ALLOCATED menjadi RELEASED atau EXPIRED, version +1. Status
manifest final, tetapi paket dapat digunakan delivery baru bila eligible.

### Error dan efek samping pengiriman

| Status | Message/kondisi |
|---|---|
| 400 | Validation Error; payload/path/query, duplicate package, version/bool, ETA tanpa timezone atau bukan future; tanpa 422 |
| 401 | Invalid credentials or session |
| 403 | Required permission is not granted |
| 404 | Delivery not found; ID delivery missing/deleted/tenant lain |
| 409 | Delivery or package changed; reload before retrying |
| 409 | Delivery parents unavailable in this tenant |
| 409 | Active driver, vehicle, kitchen and schools required |
| 409 | Destination schools must belong to origin kitchen |
| 409 | Selected driver differs from vehicle assigned driver |
| 409 | Vehicle or driver already reserved by an active delivery |
| 409 | Package unavailable in this tenant |
| 409 | Package must originate from completed production in origin kitchen |
| 409 | Package must be released and unexpired for dispatch (create RELEASED, depart ALLOCATED) |
| 409 | Package already assigned to a noncancelled delivery |
| 409 | Estimated arrival required when route coordinates are incomplete |
| 409 | Estimated arrival must precede every package holding deadline |
| 409 | Estimated arrival must be in the future at departure (menjadi stale saat menunggu lock) |
| 409 | Delivery must be CREATED / Delivery must be IN_TRANSIT |
| 409 | Package state differs from delivery state |
| 409 | Legacy delivery has no executable origin kitchen / Delivery manifest cannot be empty |
| 409 | Delivery manifest conflict / Delivery reference unavailable (constraint) |
| 500/503 | Error server/database/auth standar, tidak ada write parsial |

Contoh error:

```json
{"success":false,"code":409,"message":"Estimated arrival must precede every package holding deadline","data":null,"errors":[],"meta":{"request_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","correlation_id":"aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa","timestamp":"2026-09-11T09:05:00Z","execution_time_ms":1.2}}
```

Registry DELIVERY/PACKAGE diperbarui atomik. Depart: edge LOADED dari package ke
delivery, movement VEHICLE_LOADING dari kitchen ke vehicle. Complete: edge DELIVERED
dari package ke school, movement DELIVERY dari vehicle ke school. UUID lokasi adalah
asset_uuid registry, bukan ID master; remarks movement memuat delivery_item_id.
Create/cancel tidak membuat movement/edge. Event delivery.created/departed/completed/
cancelled tersimpan internal dengan snapshot lengkap; tidak ada publisher realtime.

DeliveryItem immutable melalui trigger UPDATE/DELETE/TRUNCATE; data tidak dihapus
saat cancel. Master driver/vehicle/kitchen/sekolah yang dirujuk tetap terlindungi
soft delete, termasuk riwayat canceled/completed. Legacy delivery kitchen_id null
hanya dapat dibaca; migrasi tidak menebak origin atau membuat data bisnis.
Belum ada edit manifest, route ordering/per-stop arrival, GPS/geofence/live ETA,
pengecekan kapasitas otomatis (unit capacity master belum ditetapkan), cancellation
saat perjalanan, acceptance sekolah, complaint/recall atau notifikasi. Complete
mewakili konfirmasi semua tujuan, bukan bukti penerimaan masing-masing sekolah.
Lima permission minimum development disediakan oleh CLI receiving:
Delivery.Read/Write/Depart/Complete/Cancel; tidak membuat akun atau seed transaksi baru.


## Kontrak penerimaan sekolah dan konsumsi

Status **aktif**, enam operasi di prefix `/api/v1`, migrasi `20260911_0022`.
Autentikasi bearer dengan account, tenant dan sesi aktif; permission diperiksa
kembali dari DB pada setiap operasi. Tenant/operator diambil dari token, tidak
boleh dikirim dalam payload. Permission berlaku dalam tenant, belum ada pembatasan
user ke sekolah tertentu. Semua respons memakai envelope, X-Request-ID,
Cache-Control no-store dan Pragma no-cache. POST wajib Content-Type application/json.

| Method/path | Tujuan | Permission | Request | Sukses |
|---|---|---|---|---|
| POST /school-receivings | Keputusan penerimaan satu paket manifest | SchoolReceiving.Write | ReceiptInput di bawah | 201 ReceiptData |
| GET /school-receivings | Daftar bukti penerimaan | SchoolReceiving.Read | Tanpa body/path; query offset, limit, package_id, school, delivery_id | 200 ReceiptPage |
| GET /school-receivings/{identifier} | Detail bukti | SchoolReceiving.Read | Path UUID school_receiving_id wajib; tanpa body/query | 200 ReceiptData |
| POST /consumptions | Finalisasi jumlah dikonsumsi/dibuang | Consumption.Write | ConsumptionInput di bawah | 201 ConsumptionData |
| GET /consumptions | Daftar bukti konsumsi | Consumption.Read | Tanpa body/path; query offset, limit, package_id | 200 ConsumptionPage |
| GET /consumptions/{identifier} | Detail bukti | Consumption.Read | Path UUID consumption_id wajib; tanpa body/query | 200 ConsumptionData |

POST tidak memiliki path/query parameter. List memakai offset integer 0..2147483647
(default 0), limit integer 1..100 (default 20); filter UUID opsional jika tidak
memfilter dihilangkan, bukan string `null`. Semua filter digabung AND; referensi
lintas tenant/tidak ditemukan menghasilkan daftar kosong. Urutan created_at DESC,
ID DESC. Page: items array data terkait, offset/limit integer, next_offset integer
atau null. Offset tidak memberikan snapshot lintas request. Detail lintas tenant,
missing/deleted memberikan 404. GET tidak mengubah timer, bukti atau event.

### Payload dan validasi

Semua field di bawah required dan nonnullable kecuali ditandai opsional. Extra
field ditolak; string dipangkas dan NUL/UTF-8 tidak valid ditolak. Numeric tidak
menerima boolean/NaN/infinity. Quantity decimal maksimal 14 digit total dan 6
pecahan, >=0; disarankan kirim string decimal. Respons quantity berupa string.
`expected_version` selalu version **paket**, integer strict 1..2147483647, bukan
version delivery/receipt. Waktu transaksi ditentukan server setelah row lock.

| ReceiptInput | Tipe | Validasi/makna |
|---|---|---|
| delivery_id | UUID | Delivery COMPLETED dengan arrival_time |
| package | UUID | Paket DELIVERED; cocok item manifest |
| school | UUID | Sekolah tujuan tepat pada manifest, satu tenant |
| expected_version | integer | Versi paket terkini |
| received_quantity | decimal | 0..quantity paket; kelebihan jumlah ditolak |
| condition | enum string | GOOD, DAMAGED, MISSING |
| accepted | boolean strict | Hanya true/false JSON, bukan string/integer |
| temperature | decimal/null, opsional default null | -9999.99..9999.99, 6 digit total/2 pecahan; observasi Celsius, belum dievaluasi terhadap rule suhu |
| photo | string/null, opsional default null | 1..1024 karakter; referensi bukti saja, tidak di-fetch/upload/diverifikasi backend |
| notes | string/null, opsional default null | 1..2000 karakter; wajib nonempty untuk penolakan atau selisih |

MISSING tepat untuk jumlah nol; GOOD/DAMAGED memerlukan jumlah positif. Penerimaan
accepted=true memerlukan GOOD dan timer SAFE/WARNING dengan policy dikenal.
Jumlah kurang boleh diterima dengan notes; discrepancy_quantity adalah
expected_quantity - received_quantity. Penolakan boleh dicatat walaupun expired,
policy unknown atau master sekolah sudah inactive; tidak membuat klaim disposal.
Paket DELIVERED -> RECEIVED bila diterima, -> REJECTED bila ditolak. Satu keputusan
per paket; row lock/version mencegah duplikasi. Legacy quantity null ditolak.
Received_time tidak boleh mendahului arrival_time. Tidak mengubah deadline,
manifest, jumlah paket asli, hasil produksi atau stok bahan.

| ConsumptionInput | Tipe | Validasi/makna |
|---|---|---|
| package_id | UUID | Paket RECEIVED dengan bukti accepted dan received_quantity diketahui |
| expected_version | integer | Versi paket setelah penerimaan |
| consumed_quantity | decimal | Jumlah yang telah dikonsumsi |
| discarded_quantity | decimal | Jumlah yang dibuang |
| notes | string/null, opsional default null | 1..2000 karakter; wajib bila discarded_quantity > 0 atau konsumsi melanggar holding |

Consumed + discarded harus tepat sama dengan received_quantity; satu finalisasi
per paket. Consumed_at adalah waktu pencatatan server dan tidak boleh mendahului
received_time; input waktu mundur tidak tersedia. `safe` adalah hasil pemeriksaan
**holding saja pada saat pencatatan**, bukan jaminan keamanan makanan atau hasil
pemeriksaan suhu: true untuk konsumsi pada SAFE/WARNING, false untuk konsumsi
EXPIRED/DISCARD_RECOMMENDED/UNKNOWN; null jika consumed_quantity=0. Pencatatan
kejadian konsumsi setelah deadline tetap diperbolehkan dengan notes wajib;
frontend perlu menampilkan pelanggaran tersebut. Tidak tersedia workflow izin
menyajikan makanan atau pelaporan konsumsi bertahap/backdated.

Jika consumed_quantity>0, paket menjadi CONSUMED termasuk ketika ada sisa dibuang;
jika seluruh isi dibuang, status DISCARDED. Version paket naik satu pada setiap
penerimaan/finalisasi, receipt dan consumption immutable tetap version=1.
GET package/resolve dan nested package delivery mempertahankan effective_status
CONSUMED/REJECTED/DISCARDED meski deadline berlalu; timer_status tetap dihitung live.
Untuk RECEIVED, effective_status masih menjadi EXPIRED saat deadline berlalu.
Holding start/update/finish dan delivery allocation tidak menerima status downstream.

### Respons dan contoh

Data berikut adalah snapshot immutable, bukan PackageData live. Field baru nullable
untuk kompatibilitas bukti legacy, tanpa backfill: legacy acceptance/quantity null
bukan izin melakukan konsumsi. Semua field respons selalu hadir.

| Field umum kedua data | Tipe |
|---|---|
| tenant_id | UUID |
| version | integer >=1 |
| created_at, updated_at | ISO datetime UTC |
| deleted_at | ISO datetime UTC/null (record API baru null) |
| created_by, updated_by, deleted_by | UUID/null; API baru actor/actor/null |
| notes, uom, timer_status | string/null; timer_status snapshot SAFE/WARNING/EXPIRED/DISCARD_RECOMMENDED/UNKNOWN |

| ReceiptData tambahan | Tipe |
|---|---|
| school_receiving_id, delivery_id, package, school | UUID |
| received_time | ISO datetime UTC |
| expected_quantity, received_quantity, discrepancy_quantity | string decimal/null |
| condition | GOOD/DAMAGED/MISSING atau null legacy |
| accepted | boolean/null legacy |
| temperature | string decimal/null |
| photo | string/null |

| ConsumptionData tambahan | Tipe |
|---|---|
| consumption_id, package_id | UUID |
| school_receiving_id | UUID/null legacy |
| consumed_at | ISO datetime UTC |
| consumed_quantity, discarded_quantity | string decimal/null legacy |
| remaining_minutes | integer/null; floor detik tersisa / 60, dapat negatif |
| safe | boolean/null sesuai aturan di atas |

Contoh berikut memakai UUID sintetis; gunakan ID dan version dari transaksi nyata.
POST `/api/v1/school-receivings` (Authorization bearer dan Content-Type JSON):

```json
{"delivery_id":"11111111-1111-4111-8111-111111111111","package":"22222222-2222-4222-8222-222222222222","school":"33333333-3333-4333-8333-333333333333","expected_version":8,"received_quantity":"1.5","condition":"GOOD","accepted":true,"temperature":"45.25","photo":"example/receipt.jpg","notes":"Shortage of 0.5 portion"}
```

Contoh data respons 201 (envelope lengkap mengikuti bagian Envelope API):

```json
{"school_receiving_id":"44444444-4444-4444-8444-444444444444","delivery_id":"11111111-1111-4111-8111-111111111111","package":"22222222-2222-4222-8222-222222222222","school":"33333333-3333-4333-8333-333333333333","received_time":"2026-09-11T09:10:00Z","expected_quantity":"2.000000","received_quantity":"1.500000","discrepancy_quantity":"0.500000","condition":"GOOD","accepted":true,"temperature":"45.25","photo":"example/receipt.jpg","notes":"Shortage of 0.5 portion","uom":"portion","timer_status":"SAFE","tenant_id":"77777777-7777-4777-8777-777777777777","version":1,"created_at":"2026-09-11T09:10:00Z","updated_at":"2026-09-11T09:10:00Z","deleted_at":null,"created_by":"88888888-8888-4888-8888-888888888888","updated_by":"88888888-8888-4888-8888-888888888888","deleted_by":null}
```

POST `/api/v1/consumptions` setelah paket version=9:

```json
{"package_id":"22222222-2222-4222-8222-222222222222","expected_version":9,"consumed_quantity":"1","discarded_quantity":"0.5","notes":"Unused portion discarded"}
```

Contoh data respons 201 (misalnya deadline 10:00 UTC):

```json
{"consumption_id":"55555555-5555-4555-8555-555555555555","package_id":"22222222-2222-4222-8222-222222222222","school_receiving_id":"44444444-4444-4444-8444-444444444444","consumed_at":"2026-09-11T09:15:00Z","consumed_quantity":"1.000000","discarded_quantity":"0.500000","remaining_minutes":45,"safe":true,"notes":"Unused portion discarded","uom":"portion","timer_status":"SAFE","tenant_id":"77777777-7777-4777-8777-777777777777","version":1,"created_at":"2026-09-11T09:15:00Z","updated_at":"2026-09-11T09:15:00Z","deleted_at":null,"created_by":"88888888-8888-4888-8888-888888888888","updated_by":"88888888-8888-4888-8888-888888888888","deleted_by":null}
```

Contoh request baca (seluruhnya Authorization bearer, tanpa body):

```http
GET /api/v1/school-receivings?delivery_id=11111111-1111-4111-8111-111111111111&school=33333333-3333-4333-8333-333333333333&package_id=22222222-2222-4222-8222-222222222222&offset=0&limit=20
GET /api/v1/school-receivings/44444444-4444-4444-8444-444444444444
GET /api/v1/consumptions?package_id=22222222-2222-4222-8222-222222222222&offset=0&limit=20
GET /api/v1/consumptions/55555555-5555-4555-8555-555555555555
```

Detail 200 memuat data persis contoh masing-masing di atas. List 200 memuat
`{"items":[data_terkait],"offset":0,"limit":20,"next_offset":null}` sebagai data;
list kosong memakai items=[] dan next_offset=null.

### Error, efek atomik dan batas implementasi

Seluruh enam endpoint mendokumentasikan 400 invalid UUID/query/body/extra fields,
401 sesi invalid, 403 permission hilang, 404 detail tidak terlihat, 409 konflik,
500 unexpected server error, 503 auth/database unavailable. Validasi memakai 400,
bukan 422. Error umum data=null; validation errors memakai array detail sesuai
kontrak global. Contoh envelope 409 finalisasi jumlah tidak cocok:

```json
{"success":false,"code":409,"message":"Consumed plus discarded quantity must equal received quantity","data":null,"errors":[],"meta":{"request_id":"99999999-9999-4999-8999-999999999999","correlation_id":"example-finalize","timestamp":"2026-09-11T09:15:00Z","execution_time_ms":1}}
```

409 juga mencakup stale version, referensi asing/missing, manifest tidak cocok,
delivery belum selesai, paket/receipt legacy tidak executable, duplicate, kondisi
atau waktu invalid, notes wajib tidak diberikan. Setelah timeout/409, baca daftar
berfilter package_id dan GET package; jangan otomatis menaikkan version lalu
mengirim ulang. Tidak ada idempotency key, edit/delete/void bukti atau koreksi otomatis.

Penerimaan menulis registry status paket, edge RECEIVED package -> school hanya
untuk accepted, serta movement SCHOOL_RECEIVING di sekolah untuk semua keputusan
(termasuk rejection/missing, sebagai inspeksi dan bukan perpindahan fisik ulang).
Remarks berisi school_receiving_id. Finalisasi membuat registry CONSUMPTION,
edge CONSUMED package -> consumption dan movement CONSUMED bila consumed>0,
movement DISCARD bila discarded>0. Movement finalisasi dari sekolah ke null,
remarks consumption_id. Quantity rinci berada pada bukti, bukan ledger stok bahan.

Bukti, package version/status, registry, relationships, movement dan event
`school_receiving.recorded`/`consumption.recorded` berada dalam satu transaksi;
kegagalan event membatalkan semuanya. Trigger DB menolak update/delete/truncate
bukti; tidak ada update/soft-delete HTTP. Event hanya PostgreSQL internal,
belum MQTT/WebSocket/worker/replay atau alarm otomatis. Tidak ada adapter registry
SCHOOL_RECEIVING tersendiri; bukti tertaut melalui manifest, package, school dan
consumption. Investigasi/recall dan tindak lanjut paket ditolak menyusul.


## Kontrak complaint intake

Status **aktif**, lima operasi di prefix `/api/v1`. Complaint adalah bukti
immutable laporan sekolah atas package yang ada pada manifest noncancelled untuk
sekolah tersebut. Intake mendukung scan `package_code` dari frontend dan foto
bukti operasional sebagai referensi. Endpoint report menyatukan konteks package,
batch produksi, lokasi terdeteksi, receipt sekolah, konsumsi, bahan baku dan
traceability movement untuk dashboard/analisa insiden. Complaint tidak mengubah
status package, tidak membuat recall otomatis dan tidak mengirim provider eksternal.

Semua operasi wajib bearer session aktif. Permission `Complaint.Write` diperlukan
untuk create; `Complaint.Read` untuk list/detail/report. POST wajib
`Content-Type: application/json`. Tenant/operator berasal dari sesi, bukan payload.
Respons memakai envelope, X-Request-ID, Cache-Control no-store dan Pragma no-cache.

| Method/path | Tujuan | Permission | Request | Sukses |
|---|---|---|---|---|
| POST /complaints | Catat laporan complaint | Complaint.Write | ComplaintInput | 201 ComplaintData |
| GET /complaints | Daftar complaint | Complaint.Read | Query offset, limit, package_id, school_id | 200 ComplaintPage |
| GET /complaints/reports | Daftar laporan insiden lengkap | Complaint.Read | Query offset, limit, package_id, school_id | 200 ComplaintReportPage |
| GET /complaints/{identifier} | Detail complaint | Complaint.Read | Path UUID complaint_id wajib | 200 ComplaintData |
| GET /complaints/{identifier}/report | Analisa laporan insiden | Complaint.Read | Path UUID complaint_id wajib | 200 ComplaintReportData |

Payload `ComplaintInput`:

| Field | Tipe / required / nullable | Validasi |
|---|---|---|
| package_id | UUID / kondisional / ya | Kirim salah satu dari package_id atau package_code |
| package_code | string / kondisional / ya | 1..100; hasil scan QR/label frontend; kirim salah satu dari package_id atau package_code |
| school_id | UUID / ya / tidak | School aktif, nondeleted dan satu tenant |
| description | string / ya / tidak | 1..4000 setelah trim; NUL/UTF-8 invalid ditolak |
| photo | string / tidak / ya | 1..1024; referensi foto bukti operasional, bukan upload multipart |

Respons `ComplaintData` menambahkan `complaint_id`, `reported_at` UTC server,
`tenant_id`, audit timestamps/by, `version=1`, `package_id`, `school_id`,
`description` dan `photo`. `package_code` tidak disimpan karena backend
menyelesaikannya menjadi `package_id`. GET list menerima `offset` 0..2147483647
default 0, `limit` 1..100 default 20, serta filter opsional `package_id` dan
`school_id` dengan AND. Urutan `created_at DESC, complaint_id DESC`.

Respons `ComplaintReportData` memuat semua field `ComplaintData` ditambah
`package`, `production_batch`, `current_location`, `delivery_manifest`,
`school_receivings`, `consumption`, `raw_materials` dan `traceability`.
`current_location` bernilai `SCHOOL` bila receipt sekolah sudah ada, termasuk
status RECEIVED/REJECTED dan waktu deteksi; bila belum diterima sekolah tetapi
manifest ada, bernilai `DELIVERY` dengan delivery/vehicle/status. `raw_materials`
memuat production_item, batch_code bahan, expired_date, status batch bahan,
received_at, suhu/condition/foto receiving, serta `manual_issues` dari pengeluaran
bahan manual/scan. `traceability` memuat asset UUID package/complaint dan 100
movement package terbaru.

Contoh POST:

```json
{
  "package_code": "PKG-2026-0001",
  "school_id": "22222222-2222-4222-8222-222222222222",
  "description": "Nasi diterima dengan bau asam sebelum dibagikan.",
  "photo": "example/complaints/pkg-2026-0001.jpg"
}
```

Contoh GET:

`GET /api/v1/complaints?package_id=11111111-1111-4111-8111-111111111111&offset=0&limit=20`

Error utama:

| HTTP | message | Kondisi |
|---|---|---|
| 400 | Validation Error | UUID/body/query invalid, description kosong atau terlalu panjang |
| 400 | Validation Error | package_id dan package_code kosong semua atau dikirim bersamaan |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi mati |
| 403 | Required Complaint permission is not granted | Permission belum tersedia/dicabut |
| 404 | Complaint not found | Detail ID hilang, deleted atau tenant lain |
| 409 | Package and school in this tenant required | Package/school hilang, deleted atau tenant lain |
| 409 | Active school required | School tidak ACTIVE |
| 409 | Package and school manifest required | Package tidak pernah dimanifestkan ke school tersebut pada delivery noncancelled |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database tidak tersedia |
| 500 | Internal Server Error | Kegagalan tak terduga |

POST membuat row complaint, registry `COMPLAINT`, edge `REPORTED`
package -> complaint, movement `COMPLAINT` dari asset school ke null dengan
remarks complaint_id, dan event internal `complaint.recorded` dalam satu transaksi.
Kegagalan event/registry/movement membatalkan complaint. Tidak ada update, delete,
void, idempotency key, notifikasi realtime, subscription, atau replay endpoint.
GET report adalah snapshot read-only dan tidak menulis registry/movement/event baru.


## Kontrak recall dasar

Status **aktif**, tujuh operasi di prefix `/api/v1`. Recall mencatat kasus pada
satu production batch, mengembalikan snapshot package terdampak dari batch tersebut,
dapat dieksekusi untuk menandai package nonterminal sebagai `RECALLED`, lalu dapat
ditutup. Tahap ini tidak membuat notifikasi, tidak memaksa paket kembali secara
fisik, dan impact lintas graph tersedia terpisah melalui traceability read.

Semua operasi wajib bearer session aktif. Permission `Recall.Execute` diperlukan
untuk start/execute/withdrawal/close; `Recall.Read` untuk list/detail/withdrawal list. POST wajib
`Content-Type: application/json`. Tenant/operator berasal dari sesi, bukan payload.
Respons memakai envelope, X-Request-ID, Cache-Control no-store dan Pragma no-cache.

| Method/path | Tujuan | Permission | Request | Sukses |
|---|---|---|---|---|
| POST /recalls | Mulai recall production batch | Recall.Execute | RecallInput | 201 RecallData |
| GET /recalls | Daftar recall | Recall.Read | Query offset, limit, production_batch_id, open_only | 200 RecallPage |
| GET /recalls/{identifier} | Detail recall | Recall.Read | Path UUID recall_id wajib | 200 RecallData |
| POST /recalls/{identifier}/execute | Eksekusi recall terbuka | Recall.Execute | RecallExecuteInput | 200 RecallData |
| POST /recalls/{identifier}/withdrawals | Catat bukti penarikan fisik | Recall.Execute | RecallWithdrawalInput | 201 RecallWithdrawalData |
| GET /recalls/{identifier}/withdrawals | Daftar bukti penarikan | Recall.Read | offset, limit, package_id opsional | 200 RecallWithdrawalPage |
| POST /recalls/{identifier}/close | Tutup recall terbuka | Recall.Execute | RecallCloseInput | 200 RecallData |

Payload `RecallInput`:

| Field | Tipe / required / nullable | Validasi |
|---|---|---|
| production_batch_id | UUID / ya / tidak | Production batch nondeleted dalam tenant |
| reason | string / ya / tidak | 1..4000 setelah trim; NUL/UTF-8 invalid ditolak |

Payload `RecallCloseInput`:

| Field | Tipe / required / nullable | Validasi |
|---|---|---|
| expected_version | integer / ya / tidak | 1..2147483647; harus sama dengan version recall saat ini |

Payload `RecallExecuteInput` memakai bentuk sama: hanya `expected_version`.

Payload `RecallWithdrawalInput`:

| Field | Tipe / wajib / nullable | Validasi |
|---|---|---|
| expected_version | integer / ya / tidak | 1..2147483647; harus sama dengan version recall saat ini |
| package_id | UUID / tidak / ya | Jika dikirim harus package dari production batch recall |
| evidence_code | string / ya / tidak | 1..100, unik per tenant; kode bukti untuk scan/foto dokumen |
| quantity | decimal / tidak / ya | >=0, maksimal 12 digit 3 desimal; wajib berpasangan dengan uom |
| uom | string / tidak / ya | 1..20; wajib berpasangan dengan quantity |
| condition_note | string / ya / tidak | 1..4000; kondisi fisik saat ditarik |
| photo | string / tidak / ya | Maksimal 1024; URI/path foto bukti, bukan file upload multipart |
| withdrawn_at | datetime / tidak / ya | ISO 8601 timezone-aware; default waktu server; tidak boleh future |
| completed_at | datetime / tidak / ya | ISO 8601 timezone-aware; tidak boleh sebelum withdrawn_at |

Respons `RecallData` berisi `recall_id`, `production_batch_id`, `reason`,
`started_at`, `completed_at`, audit/version dan `affected_packages`. Setiap package
terdampak memuat snapshot package dari batch: `package_id`, `package_code`,
`production_batch_id`, `package_number`, `quantity`, `status` dan audit/version.
Respons `RecallWithdrawalData` berisi `withdrawal_id`, `recall_id`,
`package_id`, `evidence_code`, `quantity`, `uom`, `condition_note`, `photo`,
`withdrawn_at`, `completed_at` dan audit/version.
GET list menerima `offset` 0..2147483647 default 0, `limit` 1..100 default 20,
`production_batch_id` opsional dan `open_only` boolean opsional. Urutan
`created_at DESC, recall_id DESC`.

Contoh start:

```json
{
  "production_batch_id": "33333333-3333-4333-8333-333333333333",
  "reason": "Complaint bau asam pada salah satu paket hasil batch ini."
}
```

Contoh close:

```json
{
  "expected_version": 1
}
```

Contoh execute:

```json
{
  "expected_version": 1
}
```

Contoh GET:

`GET /api/v1/recalls?production_batch_id=33333333-3333-4333-8333-333333333333&open_only=true&offset=0&limit=20`

Error utama:

| HTTP | message | Kondisi |
|---|---|---|
| 400 | Validation Error | UUID/body/query invalid, reason kosong atau terlalu panjang |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi mati |
| 403 | Required Recall permission is not granted | Permission belum tersedia/dicabut |
| 404 | Recall not found | Detail/close ID hilang, deleted atau tenant lain |
| 409 | Production batch in this tenant required | Batch produksi hilang, deleted atau tenant lain |
| 409 | Recall changed; reload before retrying | expected_version close kedaluwarsa |
| 409 | Recall already completed | Close dipanggil pada recall yang sudah selesai |
| 409 | Completed recall cannot be executed | Execute dipanggil pada recall yang sudah selesai |
| 409 | Completed recall cannot receive withdrawal evidence | Bukti ditambahkan setelah recall ditutup |
| 409 | Package in this recall required | package_id tidak ditemukan di tenant atau bukan batch recall |
| 409 | Recall reference unavailable | Constraint FK/unique evidence_code gagal |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database tidak tersedia |
| 500 | Internal Server Error | Kegagalan tak terduga |

POST start membuat row recall, registry `RECALL`, edge `RECALLED`
production_batch -> recall, movement `RECALL` untuk setiap package pada batch dengan
remarks recall_id, dan event internal `recall.started` dalam satu transaksi. POST
execute mengubah package berstatus nonterminal menjadi `RECALLED`, mempertahankan
package `CONSUMED`/`DISCARDED`/`REJECTED` apa adanya, membuat edge `RECALLED`
package -> recall, movement `RECALL` per package, menaikkan version recall dan
mencatat event `recall.executed`. POST withdrawal membuat bukti append-only,
movement `RECALL` pada package terkait atau asset recall, menaikkan version recall
dan event `recall.withdrawal_recorded`. POST close mengisi `completed_at`,
menaikkan version, menyinkronkan registry RECALL dan mencatat event internal
`recall.completed`. Tidak ada update reason, delete, void, idempotency key,
notifikasi realtime, verifikasi penarikan otomatis, subscription, atau replay endpoint.


## Kontrak notification outbox

Status **aktif internal-operasional**, tiga operasi di prefix `/api/v1`.
Endpoint ini membaca dan memperbarui status antrian notifikasi internal. Event
recall membuat item `DASHBOARD` `PENDING` secara atomik; endpoint ini belum
mengirim email/WhatsApp/Telegram ke provider eksternal.

Semua operasi wajib bearer session aktif. Permission `Notification.Read` untuk
list dan `Notification.Dispatch` untuk mark sent/failed. POST wajib
`Content-Type: application/json`. Tenant/operator berasal dari sesi.

| Method/path | Tujuan | Permission | Request | Sukses |
|---|---|---|---|---|
| GET /notifications | Daftar outbox tenant | Notification.Read | offset, limit, status, channel, entity_type, entity_uuid | 200 NotificationPage |
| POST /notifications/{identifier}/mark-sent | Tandai terkirim | Notification.Dispatch | NotificationMarkSentInput | 200 NotificationData |
| POST /notifications/{identifier}/mark-failed | Tandai gagal | Notification.Dispatch | NotificationMarkFailedInput | 200 NotificationData |

`NotificationData` berisi `notification_id`, `entity_type`, `entity_uuid`,
`event_type`, `channel`, `recipient`, `subject`, `message`, `status`,
`scheduled_at`, `sent_at`, `failure_reason` dan audit/version. Status aktif:
`PENDING`, `SENT`, `FAILED`, `CANCELLED`. Channel aktif untuk outbox:
`DASHBOARD`, `EMAIL`, `WHATSAPP`, `TELEGRAM`; saat ini auto-enqueue recall memakai
`DASHBOARD`.

Payload `NotificationMarkSentInput`: `expected_version` wajib dan `sent_at`
opsional timezone-aware, default waktu server, tidak boleh future atau sebelum
`scheduled_at`.

Payload `NotificationMarkFailedInput`: `expected_version` wajib dan
`failure_reason` string 1..4000 wajib.

GET list memakai `offset` 0..2147483647 default 0, `limit` 1..100 default 20,
filter opsional `status`, `channel`, `entity_type` dan `entity_uuid`. Urutan
`created_at DESC, notification_id DESC`.

Error utama:

| HTTP | message | Kondisi |
|---|---|---|
| 400 | Validation Error | UUID/body/query invalid, sent_at future atau failure_reason kosong |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi mati |
| 403 | Required Notification permission is not granted | Permission belum tersedia/dicabut |
| 404 | Notification not found | ID hilang, deleted atau tenant lain |
| 409 | Notification changed; reload before retrying | expected_version kedaluwarsa |
| 409 | Notification already sent | Mark sent dipanggil ulang pada status SENT |
| 409 | Cancelled notification cannot be sent | Status CANCELLED tidak bisa dikirim |
| 409 | Sent notification cannot be failed | Status SENT tidak bisa digagalkan |
| 409 | Cancelled notification cannot be failed | Status CANCELLED tidak bisa digagalkan |

Efek samping: mark sent/failed hanya mengubah status outbox dan audit/version.
Tidak ada event baru, retry otomatis, worker, SMTP, WhatsApp API, broker atau
subscription frontend. Frontend dapat polling outbox untuk badge/daftar tugas.


## Kontrak traceability read

Status **aktif read-only**, enam operasi di prefix `/api/v1/traceability/assets`.
Endpoint ini membaca registry `digital_asset`, edge `asset_relationship`, dan
timeline `asset_movement` untuk investigasi package/batch/complaint/recall.
Endpoint tidak membuat registry, tidak memperbaiki drift, tidak menulis movement
baru dan tidak menerbitkan event.

Semua operasi wajib bearer session aktif dan permission `Traceability.Read`.
`asset_uuid` adalah UUID registry, bukan ID sumber seperti package_id atau
production_batch_id. Respons memakai envelope, X-Request-ID, Cache-Control no-store
dan Pragma no-cache.

| Method/path | Tujuan | Permission | Query | Sukses |
|---|---|---|---|---|
| GET /traceability/assets/{asset_uuid} | Detail asset registry | Traceability.Read | Tidak ada | 200 AssetData |
| GET /traceability/assets/{asset_uuid}/relationships | Relasi langsung | Traceability.Read | direction, offset, limit | 200 RelationshipPage |
| GET /traceability/assets/{asset_uuid}/movements | Timeline movement | Traceability.Read | offset, limit | 200 MovementPage |
| GET /traceability/assets/{asset_uuid}/passport | Passport asset | Traceability.Read | Tidak ada | 200 AssetPassportData |
| GET /traceability/assets/{asset_uuid}/impact | Impact downstream | Traceability.Read | depth, limit | 200 ImpactData |
| GET /traceability/assets/{asset_uuid}/traverse | Traversal graph terbatas | Traceability.Read | direction, depth, limit | 200 TraceGraphData |

Query relationships: `direction=children` membaca edge keluar parent->child,
`direction=parents` membaca edge masuk. Keduanya menerima `offset` 0..2147483647
default 0 dan `limit` 1..100 default 20.

Query movements: `offset` 0..2147483647 default 0 dan `limit` 1..100 default 20.
Urutan movement `movement_time DESC, movement_id DESC`.

Passport mengembalikan snapshot asset, maksimal 100 parent edge langsung, maksimal
100 child edge langsung, dan maksimal 100 movement terbaru.

Impact memakai traversal forward dari root, `depth` 1..6 default 6 dan `limit`
1..200 default 200. Respons berisi `impacted_assets`, `affected_counts` per
asset_type, subset `package_assets`, `complaint_assets`, `recall_assets`, edge yang
dilewati dan `truncated`.

Query traverse: `direction=forward` mengikuti parent->child, `direction=backward`
mengikuti child->parent, `depth` 1..6 default 3, dan `limit` 1..200 default 100
untuk jumlah node maksimum.

`TraceGraphData` berisi `root_asset_uuid`, `direction`, `depth`, daftar `nodes`,
daftar `edges`, dan `truncated`. `truncated=true` berarti traversal mencapai batas
node; frontend dapat menurunkan depth atau menaikkan limit sampai maksimum.

Contoh:

`GET /api/v1/traceability/assets/11111111-1111-4111-8111-111111111111/traverse?direction=backward&depth=4&limit=100`

`GET /api/v1/traceability/assets/11111111-1111-4111-8111-111111111111/impact?depth=6&limit=200`

Error utama:

| HTTP | message | Kondisi |
|---|---|---|
| 400 | Validation Error | UUID/query invalid |
| 400 | Invalid traversal bounds | depth/limit di luar kontrak |
| 401 | Invalid credentials or session | Bearer hilang/invalid/sesi mati |
| 403 | Required Traceability permission is not granted | Permission belum tersedia/dicabut |
| 404 | Asset not found | Asset hilang, deleted atau tenant lain |
| 503 | Authentication unavailable | Konfigurasi autentikasi atau database tidak tersedia |
| 500 | Internal Server Error | Kegagalan tak terduga |

Traversal membaca edge yang sudah tersimpan oleh modul receiving, stok, produksi,
packaging, delivery, school receiving, consumption, complaint dan recall. Endpoint
ini bukan guarantee completeness bila data legacy belum punya registry/edge.


## Kontrak dashboard read

Status **aktif read-only**, tujuh operasi di prefix `/api/v1/dashboard`.
Endpoint ini memberi ringkasan counter tenant untuk home, storage, fleet, holding,
recall, notification outbox, serta monitor suhu terbaru per ruang penyimpanan.
Semua operasi wajib bearer session aktif dan permission `Dashboard.Read`.
Respons memakai envelope, X-Request-ID, Cache-Control no-store dan Pragma no-cache.

| Method/path | Tujuan | Permission | Query/body | Sukses |
|---|---|---|---|---|
| GET /dashboard/home | Ringkasan operasional tenant | Dashboard.Read | Tidak ada | 200 DashboardHomeData |
| GET /dashboard/storage | Ringkasan storage | Dashboard.Read | Tidak ada | 200 DashboardStorageData |
| GET /dashboard/storage-temperatures | Monitor suhu terbaru storage aktif | Dashboard.Read | offset integer default 0; limit integer 1..100 default 20 | 200 DashboardStorageTemperaturePage |
| GET /dashboard/fleet | Ringkasan fleet | Dashboard.Read | Tidak ada | 200 DashboardFleetData |
| GET /dashboard/holding | Ringkasan holding | Dashboard.Read | Tidak ada | 200 DashboardHoldingData |
| GET /dashboard/recall | Ringkasan recall | Dashboard.Read | Tidak ada | 200 DashboardRecallData |
| GET /dashboard/notifications | Ringkasan notification outbox | Dashboard.Read | Tidak ada | 200 DashboardNotificationData |

`DashboardHomeData`:

| Field | Tipe | Makna |
|---|---|---|
| complaints_open | integer | Jumlah complaint aktif/nondeleted |
| recalls_open | integer | Recall yang belum completed_at |
| deliveries_in_transit | integer | Delivery status IN_TRANSIT |
| packages_recalled | integer | Package status RECALLED |
| packages_delivered | integer | Package status DELIVERED |
| packages_received | integer | Package status RECEIVED |
| packages_consumed | integer | Package status CONSUMED |
| packages_discarded | integer | Package status DISCARDED |
| production_completed | integer | Production batch status COMPLETED |
| raw_batches_available | integer | Raw material batch status ACCEPTED |

`DashboardStorageData`: `storages_active`, `storage_zones`,
`raw_batches_accepted`, `stock_entries`, `temperature_logs`.

`DashboardStorageTemperaturePage`: `items`, `offset`, `limit`, `next_offset`.
Setiap item memuat `storage_id`, `storage_name`, `storage_type`,
`temperature_min`, `temperature_max`, `device_uuid`, `temperature_log_id`,
`recorded_at`, `temperature`, `unit` dan `status`. Status bernilai `NO_DATA`
bila belum ada log suhu untuk storage, `OK` bila sampel Celsius terakhir masih
dalam batas, `LOW` atau `HIGH` bila melewati batas storage, dan
`UNSUPPORTED_UNIT` bila sampel terakhir bukan Celsius sehingga tidak dibandingkan
dengan ambang storage. Endpoint membaca `temperature_log` terbaru yang sudah
diisi ingestion HTTP/MQTT; tidak membuat device, subscription atau event baru.

`DashboardFleetData`: `vehicles_active`, `drivers_active`, `deliveries_created`,
`deliveries_in_transit`, `deliveries_completed`, `gps_logs`.

`DashboardHoldingData`: `packages_created`, `packages_packaged`,
`packages_released`, `packages_expired`, `packages_recalled`, `holding_logs`,
`alarms_open`.

`DashboardRecallData`: `complaints_open`, `recalls_open`, `recalls_completed`,
`packages_recalled`, `recall_movements`.

`DashboardNotificationData`: `pending`, `sent`, `failed`, `cancelled`,
`dashboard_pending`, `email_pending`, `whatsapp_pending`, `telegram_pending`.

Semua hitungan dibatasi tenant bearer dan record nondeleted. Ini snapshot query saat
request, bukan agregat materialized, cache, event stream, alarm, atau indikator SLA.



