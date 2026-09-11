# Event catalog FSOS

Terakhir diperbarui: 2026-09-11. Status: **event receiving tersimpan di database; belum ada event yang dipublikasikan ke transport**.

Endpoint login/refresh/logout terhubung ke SessionService dan mengubah database,
tanpa event bus/notifikasi. Log operasional mencatat action/outcome/request_id;
ini bukan audit persisten atau event untuk subscription frontend. REUSED adalah status internal, bukan event frontend.
Autentikasi akun, resolusi identitas, primitive password dan access JWT belum
menerbitkan event login/logout; belum ada audit keamanan persisten atau transport baru. GET /auth/me tidak mengubah data atau menerbitkan event.

Bootstrap akun manusia development membuat user/membership serta kolom audit,
tanpa event user.created, email, token atau sesi otomatis. Mode --check tidak
menulis data. Tidak ada producer/consumer atau channel frontend baru.

Tabel `event_log` dan bukti telemetry sudah tersedia. Event bus, publisher,
transactional outbox, worker, MQTT ingestion, WebSocket, dan SSE belum tersedia.
Insert database tidak otomatis menerbitkan event. Frontend belum memiliki channel
untuk subscribe. Kedua endpoint sistem saat ini tidak menghasilkan event bisnis.
Repository kitchen juga belum menerbitkan event; create/update/soft delete hanya
mengubah record di dalam transaksi milik application service.
Endpoint alarm-rule create/update/ubah enabled dan holding-rule create/update
mencatat revisi dalam transaksi database;
list/detail/history tidak mengubah data. Tidak ada event perubahan rule, transport,
consumer atau subscription baru; frontend perlu fetch ulang setelah mutasi.
History revisi alarm/holding rule dicatat trigger database; ini tidak menerbitkan
event perubahan aturan ke frontend. Validator DSL juga tidak menjalankan aksi.
Service simpan/aktivasi aturan menggunakan trigger history yang sama dan belum
memiliki publisher/outbox. enabled=true tidak memulai evaluator atau notifikasi.
Rekonsiliasi registry hanya menghasilkan laporan CLI/service; SOURCE_MISSING dan
PROJECTION_MISMATCH adalah status temuan, bukan event yang diterbitkan. Tidak ada
producer, transport, retry/replay atau channel frontend untuk hasil scan.
Sync/backfill registry digital asset juga hanya memperbarui database. Integrasi
KitchenRepository belum menerbitkan event registry atau perubahan kitchen.
Seed development dan backfill FSOS_DEV juga tidak menerbitkan event ke frontend;
penambahan fixture database bukan contoh delivery/replay event runtime.
Pembacaan daftar/detail alarm dan sesi memakai status efektif, tanpa mutasi bukti
atau event. Filter status dan pagination tidak membuat subscription atau channel.
Service acknowledgment alarm dan penutupan sesi juga belum menerbitkan event.
device.disconnected pada daftar rencana belum otomatis dikirim ketika close_session dipanggil.
Maintenance partisi tidak menerbitkan event atau notifikasi frontend; hasilnya
berupa laporan JSON lokal dan exit code proses/task scheduler.
Provisioning role runtime dan pengerasan fungsi history tidak menerbitkan event
frontend. Trigger aturan tetap menyimpan snapshot internal, bukan delivery event.
Bootstrap login PostgreSQL dan pemisahan pool database juga tidak menerbitkan
event ke frontend atau membuat event login user aplikasi.

Tautan: [API frontend](frontend-api.md), [changelog](frontend-changelog.md),
[TODO](../../TODO.md).

## Rencana event telemetry

Nama berikut berasal dari [docs/08 bagian 20](../../docs/08_ERD_Telemetry.md).
Trigger, producer, dan consumer di bawah adalah arah implementasi, belum kontrak
runtime. Nama `updated` tidak berarti bukti telemetry boleh diubah.

| Event | Status | Trigger yang direncanakan | Producer yang direncanakan | Consumer yang direncanakan |
| --- | --- | --- | --- | --- |
| `temperature.updated` | Rencana | Sampel suhu baru tervalidasi dan tersimpan | Telemetry ingestion | Rule engine, tampilan storage |
| `gps.updated` | Rencana | Posisi baru tersimpan | Telemetry ingestion | Fleet, peta |
| `holding.updated` | Rencana | Snapshot holding baru tersimpan | Holding engine | Tampilan holding, notifikasi |
| `heartbeat.updated` | Rencana | Heartbeat baru tersimpan | Telemetry ingestion | Digital twin, status device |
| `alarm.created` | Rencana | Bukti alarm baru tersimpan | Alarm/rule engine | Tampilan alarm, notifikasi |
| `device.connected` | Rencana | Sesi perangkat mulai tercatat | Pengelola sesi device | Digital twin, tampilan device |
| `device.disconnected` | Rencana | Akhir sesi perangkat tercatat | Pengelola sesi device | Digital twin, tampilan device |

Untuk **seluruh event rencana** di atas: versi kontrak, JSON payload, field wajib,
nullable, satuan, topic/channel, auth/permission, serta pemetaan tenant belum
ditetapkan sebagai kontrak publik. Tidak ada jaminan delivery, ordering, retry,
replay, atau deduplikasi runtime. Jangan membangun subscriber berdasarkan dugaan
struktur tabel database.

## Penyimpanan internal yang sudah tersedia

`event_log` merupakan tabel audit internal, **bukan envelope pesan frontend**:

| Field | Tipe database | Required | Makna |
| --- | --- | --- | --- |
| `event_uuid` | UUID PK | Ya | Identitas event, default UUID dari aplikasi |
| `tenant_id` | UUID FK | Ya | Tenant pemilik event |
| `event_type` | varchar(100) | Ya | Nama event tidak kosong; belum enum catalog |
| `entity_type` | varchar(100) | Ya | Jenis entity tidak kosong |
| `entity_uuid` | UUID | Ya | Identitas entity sumber; referensi polimorfik belum FK sumber |
| `payload` | JSONB object | Ya | Object; event receiving divalidasi dengan ReceivingDetail dan schema_version=1 |
| `created_at`, `updated_at` | timestamptz | Ya | Timestamp audit, default waktu database |
| `created_by`, `updated_by` | UUID | Tidak | Actor audit; receiving memakai actor sesi tervalidasi |
| `deleted_at`, `deleted_by` | timestamp/UUID | Harus null | Soft delete bukti ditolak |
| `version` | integer | Ya | Default 1; bukan versi schema event publik |

Contoh ilustrasi representasi JSON **record internal**, bukan pesan subscribe:

```json
{
  "event_uuid": "0e363bbc-5b44-467c-bfdf-406dc78a2d3e",
  "tenant_id": "f53bed5e-d759-405b-8cb5-93df698d81b4",
  "event_type": "temperature.updated",
  "entity_type": "DEVICE",
  "entity_uuid": "aec7bfba-6598-43f9-a5ef-7c0ed0fc652f",
  "payload": {"example_only": true},
  "created_at": "2026-09-11T09:00:00Z",
  "updated_at": "2026-09-11T09:00:00Z",
  "created_by": null,
  "updated_by": null,
  "deleted_at": null,
  "deleted_by": null,
  "version": 1
}
```

Database menolak event_uuid duplikat serta UPDATE/DELETE/TRUNCATE record bukti.
Ini belum menyediakan mekanisme retry idempotent atau delivery exactly-once.
Urutan record tidak menjamin urutan pengiriman. Record acknowledgment alarm dan
akhir sesi adalah bukti tambahan; belum ada publisher atau nama event publik
untuk kedua aksi itu.

## Format wajib saat event diimplementasikan

Setiap event aktif harus mempunyai entri lengkap sebelum consumer frontend
dianggap dapat menggunakannya:

| Bagian | Isi yang harus dijelaskan |
| --- | --- |
| Identitas | Nama, versi schema publik, status aktif/deprecated, tanggal perubahan |
| Trigger | Kondisi bisnis dan kapan event diterbitkan relatif terhadap commit |
| Producer/consumer | Modul pembuat, penerima, dan dampak yang diharapkan |
| Transport | Internal bus/MQTT/WebSocket/SSE, channel/topic dan cara subscribe |
| Akses | Auth, permission, tenant scope, penyaringan data sensitif |
| Payload | Field, tipe, required/nullable, satuan, timestamp, contoh JSON lengkap |
| Identitas pesan | Event ID, entity ID, correlation ID, idempotency key bila tersedia |
| Pengiriman | Ordering, retry/backoff, duplikasi, dedupe key, reconnect/replay/retention |
| Error | Invalid payload, subscription ditolak, gap event, fallback fetch snapshot |
| Evolusi | Kompatibilitas, deprecation, langkah migrasi frontend dan pengujian |

Catalog diperbarui bersama implementasi producer/consumer dan
[changelog frontend](frontend-changelog.md), bukan hanya ketika tabel dibuat.


## Konfigurasi alarm melalui HTTP

Status: manajemen konfigurasi alarm sudah tersedia; publikasi event belum tersedia.
POST /alarm-rules dan PUT definisi/ubah enabled mencatat snapshot melalui trigger
PostgreSQL dalam transaksi yang sama dengan mutasi. GET tidak mengubah data;
PUT enabled identik dengan versi terkini tidak menambah revisi. Tidak ada producer,
consumer, transport/channel, payload event berversi atau subscription baru.
Revision bukan event message dan tidak memiliki mekanisme retry/replay transport.
Tenant/actor diambil dari bearer session; Read/Write/Activate diperiksa terpisah.
History diurutkan version DESC; expected_version melindungi update bersamaan.
Contoh payload request dan snapshot ada di
[kontrak alarm HTTP](frontend-api.md#kontrak-alarm-rule-http).

Enabled=true belum memicu evaluasi telemetry, alarm.created, notifikasi atau aksi
recall/discard. Event alarm.created di tabel rencana tetap berstatus rencana.
Kontrak producer/consumer, ordering, deduplikasi, retry dan replay akan ditetapkan
bersama implementasi engine dan transport; jangan subscribe berdasarkan revision_id.


## HTTP acknowledgment alarm telemetry

Status: GET /api/v1/alarms, GET detail dan POST acknowledgment sudah tersedia.
POST mencatat bukti pertama di alarm_acknowledgment dengan actor/tenant dari bearer
session, permission Alarm.Acknowledge. Retry mengembalikan bukti yang sama; snapshot
impor yang sudah acknowledged tidak ditambah bukti. GET memakai Alarm.Read.
Tidak ada publisher/consumer, channel/transport atau payload event baru. Bukti ini
bukan pesan event dan tidak memiliki retry/replay transport. Constraint unik tenant/
alarm dan lock parent mencegah duplikasi melalui service; ordering pembacaan daftar
recorded_at DESC lalu alarm_id DESC tidak menyatakan urutan pengiriman event.
Contoh request dan snapshot ada di [kontrak HTTP](frontend-api.md#kontrak-alarm-telemetry-http).
Notifikasi dan event acknowledgment masih rencana; tidak ada subscription frontend.


## HTTP akhir sesi dan provisioning permission

Status: POST /api/v1/device-sessions/{session_id}/end tersedia dan mencatat satu
bukti device_session_end; GET list/detail membaca status efektif. Tenant/actor berasal
dari bearer, DeviceSession.Read/Close independen. Parent lock dan constraint unik
melindungi finalisasi; retry instant sama mengembalikan bukti pertama, berbeda 409.
Daftar diurutkan connected_at DESC lalu session_id DESC, bukan urutan delivery event.
Contoh request dan snapshot: [kontrak sesi](frontend-api.md#kontrak-sesi-perangkat-http).

Tidak ada event baru: device.disconnected tetap rencana. Tidak ada producer/consumer,
transport/channel, payload event berversi, subscription atau retry/replay transport.
CLI provisioning telemetry menambah permission/grant dengan audit dalam satu transaksi;
tidak menerbitkan permission.changed. Snapshot DB bukan pesan event. Frontend dapat
memuat ulang /auth/me sesudah provisioning dan daftar sesi sesudah finalisasi.


## Master kitchen/storage/zone melalui HTTP

Status: 12 operasi master tersedia. POST/PUT kitchen dan storage menulis sumber serta
proyeksi digital_asset atomik; zone hanya menulis storage_zone. Tenant/actor dari
bearer; Kitchen/Storage/StorageZone.Read atau Write sesuai operasi. Version sumber
bertambah setiap PUT, termasuk definisi identik; POST duplicate code 409 dan tidak
memiliki idempotency key. Konflik version 409; tidak ada replay otomatis.

Tidak ada event baru, producer/consumer, payload event berversi, channel/transport,
ordering delivery, retry atau replay broker. Tidak membuat asset_relationship,
asset_movement atau event_log. Registry bukan pesan notifikasi/realtime. Contoh
request/response ada di [kontrak master](frontend-api.md#kontrak-master-kitchen-storage-zone).
Event receiving kini tersimpan seperti bagian berikut; event production tetap TODO.


## Supplier, bahan baku dan relasi pemasok-bahan

Status: 12 operasi master tersedia. POST/PUT supplier dan raw-material menyimpan
sumber serta digital_asset dalam transaksi yang sama; supplier-material hanya
menyimpan pasangan sumber. Tenant/actor dari bearer, Read/Write masing-masing modul.
Version naik setiap PUT; kode/pasangan duplikat dan stale version menghasilkan 409.
POST tidak memiliki idempotency key; tidak ada replay otomatis.

Tidak ada event baru, producer/consumer, transport/channel, payload event berversi,
ordering delivery atau retry/replay broker. Tidak membuat asset_relationship,
movement, receiving, stok atau event_log. Nama relasi supplier-material tidak
menyatakan edge graph traceability sudah dibuat. Contoh request/response ada di
[kontrak frontend](frontend-api.md#kontrak-supplier-bahan-dan-relasi).


## Soft delete enam master

Status: enam DELETE kitchen/storage/zone/supplier/raw-material/supplier-material
tersedia. Trigger operasinya request DELETE dengan expected_version, bearer tenant/
actor dan permission modul.Delete. Sumber ditandai deleted_at/deleted_by dan version
naik; registry kitchen/storage/supplier/raw-material mengikuti dalam transaksi sama.
Zone/relasi tidak memiliki proyeksi asset. Referensi nondeleted memblokir penghapusan;
tidak ada cascade, penghapusan bukti, event_log baru atau mutasi graph/movement.

Tidak ada producer/consumer event, channel/transport, payload event berversi,
ordering delivery, deduplikasi/retry/replay broker. DELETE ulang adalah 404, bukan
pengiriman ulang event. Contoh request/respons lengkap dan error ada di
[kontrak soft delete](frontend-api.md#soft-delete-master-operasional).
Event master.deleted masih belum diimplementasikan; jangan berlangganan berdasar
perubahan deleted_at registry. Frontend memperbarui daftar dari respons/GET.


## Cakupan modul sekolah dan master lain

CRUD sekolah kini tersedia. Kendaraan/driver juga kini memiliki CRUD. Menu/resep, jenis kemasan serta
master device/binding belum memiliki endpoint. Keberadaan tabel, registry source adapter atau referensi
penghalang delete tidak berarti terdapat producer/event runtime dari modul tersebut.
Matriks HTTP terverifikasi ada di [cakupan frontend](frontend-api.md#cakupan-crud-dan-status-modul).
Klarifikasi status ini tidak menambahkan event, channel atau payload baru.


## CRUD sekolah

Status: lima operasi master sekolah tersedia, bukan transaksi school receiving.
POST/PUT/DELETE memutasi school dan digital_asset SCHOOL secara atomik dengan tenant/
actor bearer, permission School.Write/Delete dan version. DELETE ditolak bila masih
ada delivery_item, school_receiving atau complaint nondeleted. GET memakai School.Read.

Tidak ada producer/consumer event, channel/transport, payload event berversi, ordering
delivery atau retry/replay broker baru. Tidak menulis movement/relationship/event_log,
membuat penerimaan sekolah atau mengirim notifikasi. POST duplicate code 409; DELETE
ulang 404; registry bukan pesan event. Contoh lengkap ada di
[kontrak sekolah](frontend-api.md#kontrak-crud-sekolah).


## CRUD kendaraan dan driver

Status: 10 operasi master kendaraan/driver tersedia. Mutasi vehicle dan registry
VEHICLE atomik dengan actor/tenant bearer, permission Vehicle.Write/Delete; driver
menggunakan Driver.Write/Delete tanpa proyeksi registry. Read terpisah. Version
bertambah setiap PUT/DELETE, duplicate code/plat dan stale version 409. Referensi
vehicle/delivery/gps_log menjaga soft delete sesuai target.

Tidak ada event baru, producer/consumer, transport/channel, payload event berversi,
ordering pengiriman, retry/replay broker atau subscription. Mengganti driver/GPS pada
vehicle tidak mencatat movement/GPS/delivery atau mengubah riwayat pengiriman lama.
POST duplicate retry 409; DELETE ulang 404. Contoh lengkap ada di
[kontrak kendaraan/driver](frontend-api.md#kontrak-kendaraan-dan-driver).


## Event receiving tersimpan

Status: aktif sebagai **record internal event_log**, bukan pesan realtime frontend.
Producer: ReceivingService, bersama transaksi API /receivings. Consumer runtime:
belum ada. Transport/channel/topic: belum tersedia, hanya PostgreSQL event_log.
Frontend menggunakan response mutasi lalu GET, tidak melakukan subscribe.

| Event | Trigger commit berhasil | Permission producer | Snapshot |
| --- | --- | --- | --- |
| receiving.created | POST /receivings | Receiving.Write | CREATED, item.accepted null, batch CREATED |
| receiving.completed | POST /receivings/{id}/complete | Receiving.Complete | COMPLETED, batch ACCEPTED/REJECTED dan keputusan semua item |
| receiving.cancelled | POST /receivings/{id}/cancel | Receiving.Cancel | CANCELLED, batch CANCELLED, accepted null |

Ketiga event memakai entity_type RECEIVING, entity_uuid receiving_id, event_uuid
UUID baru. tenant_id dan actor berasal dari sesi aktif dan permission tenant, tidak
berasal dari request. created_by/updated_by berisi actor producer; deleted_at/by
null dan version record 1. Bukti append-only, tanpa UPDATE/DELETE runtime.

Payload **v1** sama untuk ketiganya, seluruh field wajib dan nonnull:

- schema_version: integer literal 1, versi payload (berbeda dari version record).
- actor_id: string UUID actor pembuat event; berbeda dari operator receiving jika
  inspeksi diselesaikan pengguna lain.
- receiving: snapshot lengkap ReceivingDetail sesuai [kontrak API](frontend-api.md#kontrak-receiving-dan-batch-bahan),
  termasuk semua item, batch dan audit. Nullable field mengikuti kontrak tersebut;
  decimal berupa string, datetime UTC, ID UUID string. Urutan item UUID ascending.

Ordering: create mendahului finalisasi receiving yang sama; lock header dan versi
mengizinkan hanya satu finalisasi. Gunakan receiving.version untuk urutan agregat,
bukan created_at/event_uuid untuk urutan global. Tidak ada jaminan ordering antar
receiving. Deduplikasi finalisasi melalui expected_version + status CREATED;
retry setelah sukses 409 tanpa event tambahan. Create belum memiliki idempotency
key; kode batch/QR unik menolak duplikasi dengan rollback. Retry transaksi gagal
hanya sesudah membaca hasil/menyelesaikan konflik; tidak ada automatic retry,
outbox, broker acknowledgment, replay worker atau endpoint pembacaan event.
Kegagalan penulisan event menggagalkan keseluruhan transaksi bisnis. Database
snapshot ini belum dapat diasumsikan sebagai kontrak publik transport masa depan.

Contoh payload aktif receiving.created (UUID fiktif); receiving.completed/cancelled
menggunakan struktur sama dengan snapshot final dan actor penyelesaian:

```json
{
  "schema_version": 1,
  "actor_id": "88888888-8888-4888-8888-888888888888",
  "receiving": {
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
  }
}
```
