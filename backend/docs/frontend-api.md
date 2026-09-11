# Panduan integrasi frontend FSOS

Terakhir diperbarui: 2026-09-11. Versi aplikasi: 0.1.0.
Status: dua endpoint sistem tersedia; API bisnis dan autentikasi belum tersedia.

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
OpenAPI sudah mencantumkan endpoint serta envelope; `data` masih bertipe bebas
pada schema OpenAPI, sehingga detail field per endpoint ada di panduan ini.

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
| `Cache-Control: no-store` | Response `/ready` | Hasil probe tidak boleh disimpan cache |

Kedua endpoint sistem tidak membutuhkan token, API key, tenant ID, atau permission
khusus. Login JWT, refresh/logout, RBAC, dan API key device masih TODO.
Header `Authorization`/`X-API-Key` yang diizinkan CORS belum berarti autentikasi
sudah berfungsi. Jangan memasukkan kredensial PostgreSQL/MQTT ke frontend.

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
desain belum merupakan perilaku endpoint aktif.

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

Login, master data, device, telemetry, receiving, production, package, holding,
traceability, fleet, school, complaint, recall, dashboard, analytics, dan QR
belum memiliki endpoint aktif. Pagination, filter, sort, upload, serta endpoint
acknowledgment alarm/akhir sesi belum diimplementasikan. Payloadnya belum menjadi
kontrak; akan ditambahkan saat endpoint dibuat.

Tidak ada route WebSocket atau SSE aktif. Frontend belum dapat berlangganan
event. Lihat [event catalog](event-catalog.md) untuk status rencana.

## Pemeliharaan

Perubahan API wajib memperbarui halaman ini, OpenAPI/schema, contoh respons,
tes perilaku yang relevan, dan [changelog](frontend-changelog.md) dalam pekerjaan
yang sama. Jika ada event, perbarui catalog juga. Aturan proyek disimpan di
[AGENTS.md](../../AGENTS.md) agar berlaku pada pengembangan berikutnya.
