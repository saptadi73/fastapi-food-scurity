# Panduan integrasi frontend FSOS

Terakhir diperbarui: 2026-09-11. Versi aplikasi: 0.1.0.
Status: dua endpoint sistem dan empat endpoint autentikasi tersedia. API bisnis
(master, aturan, telemetry, dan lainnya) belum tersedia.

Dokumen ini menjelaskan implementasi yang dapat dipanggil sekarang.
[Desain API](../../docs/16_API_design.md) adalah roadmap draft, bukan daftar
endpoint aktif. Tabel database yang sudah ada belum menyediakan API CRUD.

Tautan: [Event catalog](event-catalog.md), [perubahan kontrak](frontend-changelog.md),
[database](database.md), [TODO](../../TODO.md).

## Koneksi dan dokumentasi interaktif

| Pengaturan | Nilai development default |
| --- | --- |
| Origin backend | `http://localhost:8000` |
| Prefix API | `/api/v1` (konfigurasi backend `API_PREFIX`) |
| Swagger | `GET /docs` — HTML interaktif |
| ReDoc | `GET /redoc` — HTML dokumentasi |
| OpenAPI | `GET /openapi.json` — dokumen JSON OpenAPI, tanpa envelope |
| Swagger OAuth redirect | `GET /docs/oauth2-redirect` — HTML internal Swagger; bukan login aplikasi |

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
| `Cache-Control: no-store` | Response `/ready` dan `/auth/*` | Respons tidak boleh disimpan cache |
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

## Daftar endpoint aktif

| Method | Path | Tujuan | Payload | Respons normal |
| --- | --- | --- | --- | --- |
| GET | `/api/v1/health` | Liveness proses API | Tidak ada | 200 |
| GET | `/api/v1/ready` | Kesiapan database aplikasi | Tidak ada | 200 atau 503 |
| POST | `/api/v1/auth/login` | Autentikasi akun dalam tenant | tenant_id, username, password | 200 |
| POST | `/api/v1/auth/refresh` | Rotasi token sesi | refresh_token | 200 |
| POST | `/api/v1/auth/logout` | Cabut satu sesi | refresh_token | 200 |
| GET | `/api/v1/auth/me` | Identitas dan RBAC aktif | Tidak ada; bearer header | 200 |

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
kini tersedia pada service internal dengan filter perangkat, status efektif,
rentang waktu dan pagination. Belum ada endpoint HTTP untuk memanggilnya dari
browser; query parameter dan JSON HTTP belum menjadi kontrak aktif. Panduan
service merinci input/hasil, izin, error dan batas pagination. Perubahan ini
tidak mengubah respons health/ready atau menyediakan subscription realtime.


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
dan mencatat acknowledgment/akhir sesi secara append-only. Belum ada endpoint HTTP
untuk operasi tersebut; tabel field dan contoh service adalah kontrak internal,
bukan payload frontend. Snapshot awal bisa berbeda dari status efektif setelah finalisasi.

[Fixture development](development-seed.md) kini tersedia di database lokal:
tenant FSOS_DEV dan data master contoh. dev-maintenance adalah actor internal
tanpa password login, bukan credential frontend. Data fixture belum bisa diambil
lewat API bisnis karena endpointnya belum tersedia. Jangan menaruh DATABASE_URL
di frontend atau memperlakukan UUID actor sebagai token.

Adapter dan [service registry digital asset](asset-registry.md) kini tersedia,
termasuk backfill dan sinkronisasi kitchen dalam transaksi yang sama. Tidak ada
endpoint registry baru. asset_uuid registry berbeda dari entity_uuid sumber;
frontend belum boleh mengasumsikan keduanya dapat saling menggantikan.

Riwayat revisi alarm/holding rule, validator DSL, dan [service aturan internal](rule-versioning.md)
dengan permission database tersedia. Belum ada endpoint baca history/simpan/aktivasi aturan;
contoh DSL bukan request body endpoint aktif. Frontend rule editor menunggu API
beserta validasi permission, error mapping, dan kontrak payload final.

Fondasi internal `KitchenRepository` sudah membatasi tenant/actor, mencatat audit,
menyembunyikan soft-deleted records, serta menolak update dengan version lama.
Belum ada route kitchen atau kontrak payload `expected_version` untuk HTTP.
Error internal repository belum dipetakan ke status HTTP bisnis; frontend
menunggu endpoint, schema, auth/permission, dan dokumentasinya saat diimplementasikan.

Master data, device, telemetry, receiving, production, package, holding,
traceability, fleet, school, complaint, recall, dashboard, analytics, dan QR
belum memiliki endpoint aktif. Pagination, filter, sort, upload, serta
acknowledgment alarm/akhir sesi belum tersedia melalui HTTP. Payloadnya belum menjadi
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
| tenant_id | string UUID | Ya / tidak | UUID tenant; bukan tenant_code |
| username | string | Ya / tidak | 1..100 karakter; angka/field tambahan ditolak |
| password | string secret | Ya / tidak | 1..72 karakter pada schema; kredensial harus memenuhi kebijakan 12 karakter sampai 72 byte UTF-8, tanpa NUL |

Password terlalu pendek menurut kebijakan, terlalu panjang dalam byte UTF-8,
username blank/NUL, akun tanpa hash, user tidak aktif, tenant salah dan password
salah menghasilkan 401 seragam. Panjang/tipenya melanggar schema, UUID tidak valid
atau JSON rusak menghasilkan 400. Tidak ada password default aplikasi.

Contoh request (nilai ilustratif, bukan akun yang sudah dibuat):

```http
POST /api/v1/auth/login HTTP/1.1
Content-Type: application/json
Accept: application/json

{
  "tenant_id": "11111111-1111-4111-8111-111111111111",
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
  body: JSON.stringify({ tenant_id: tenantId, username, password }),
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
