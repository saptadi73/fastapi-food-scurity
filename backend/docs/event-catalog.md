# Event catalog FSOS

Terakhir diperbarui: 2026-09-11. Status: **event receiving, stok, produksi, paket, holding dan pengiriman tersimpan internal; belum dipublikasikan ke transport**.

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
| `holding.updated` | Aktif internal, lihat kontrak paket/holding | POST refresh | PackageService | Publisher/notifikasi belum tersedia |
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

CRUD sekolah kini tersedia. Kendaraan/driver juga kini memiliki CRUD. Menu/resep kini memiliki CRUD. Jenis kemasan kini memiliki CRUD;
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


## Event stok tersimpan

`stock.putaway` **aktif internal**: producer `StockService.putaway`, trigger POST
batch putaway sukses, disimpan atomik bersama ledger, audit/version, registry dan
movement STORAGE di PostgreSQL `event_log`. Entity type RAW_MATERIAL_BATCH,
entity_uuid = ID batch. Consumer eksternal, bus, MQTT/WebSocket, retry publisher,
replay dan notifikasi belum diimplementasikan; bukan channel realtime frontend.
Tenant dari bearer account dengan permission Stock.Putaway; payload actor sama dengan
created_by. Tidak membawa kredensial. Event immutable, tidak boleh dipindahkan tenant.
Ordering per batch memakai entry.batch_version, bukan created_at; lock batch dan
expected_version mencegah event ganda untuk write version sama. UUID event unik;
retry sukses dengan version lama 409, rollback tidak menyisakan event/ledger/movement.
Tidak ada urutan global atau jaminan delivery eksternal.

Payload v1 required: schema_version integer 1, actor_id UUID string, entry object
schema StockEntryData (semua field persis respons putaway), uom string snapshot
receiving item. Contoh konstruksi payload dari respons putaway:

```javascript
const payload = {
  schema_version: 1,
  actor_id: "88888888-8888-4888-8888-888888888888",
  entry: putawayResponse.data,
  uom: "kg"
};
```

Contoh JSON entry lengkap tersedia pada [kontrak putaway](frontend-api.md#stok-batch-bahan-dan-putaway).
Movement STORAGE memakai asset_uuid registry batch/kitchen/storage, remarks UUID
entry. Qty parsial terdapat pada entry.quantity; event ini tidak menyatakan seluruh
batch berada di satu storage. Tidak ada event baru saat GET saldo, expiry tanggal,
atau master menjadi inactive; saldo available dihitung saat baca. Pemakaian bahan tersedia melalui production.started;
transfer dan adjustment ledger/event tetap rencana.


## CRUD menu dan resep

Status: 10 operasi HTTP aktif pada food-items/recipes. Producer tulis adalah
FoodService dengan tenant/actor bearer dan permission FoodItem/Recipe.Read, Write,
Delete terpisah. Quantity resep adalah kebutuhan per satu unit food_item.uom;
uom resep sama dengan bahan. Audit dan version berubah atomik, delete bersifat soft.
**Tidak ada event baru** pada CRUD ini: tidak menulis event_log, movement atau
registry FOOD_ITEM/RECIPE (tipe belum didukung). Relasi recipe merupakan FK, bukan
asset_relationship. Consumer, transport/channel, payload event, ordering,
deduplikasi/retry/replay tidak berlaku. Production snapshot/usage event kini tersimpan internal seperti bagian produksi
di bawah, bukan subscription frontend aktif. Contoh request/response ada di
[kontrak menu/resep](frontend-api.md#kontrak-menu-dan-resep).


## Event produksi tersimpan

Status **aktif internal PostgreSQL event_log**, producer ProductionService.
Entity type PRODUCTION_BATCH, entity_uuid ID batch. Empat event:

| Event | Trigger/permission | Efek atomik |
|---|---|---|
| production.created | POST create, Production.Write | Rencana CREATED, snapshot resep, registry |
| production.started | POST start, Production.Start | RUNNING, ledger production_item, version bahan, edge USED, movement ISSUE, registry |
| production.completed | POST complete, Production.Complete | COMPLETED, actual quantity, waktu, registry dan movement PRODUCTION di kitchen |
| production.cancelled | POST cancel CREATED, Production.Cancel | CANCELLED, registry; tanpa stok/movement |

Semua payload v1: schema_version integer 1, actor_id UUID string,
production object persis ProductionDetail pada respons action. Field, required,
nullable, contoh snapshot/header/item lengkap di [kontrak produksi](frontend-api.md#kontrak-transaksi-produksi).
Tenant dari bearer dan tenant_id EventLog; actor sama dengan audit write. Consumer
internal dapat membaca bukti, tetapi tidak ada subscriber/worker/transport MQTT atau
WebSocket yang diimplementasikan. Channel saat ini tabel event_log, bukan event bus.
Tidak ada retry publisher/replay otomatis atau ordering global.

Ordering per produksi memakai production.version; version 1 created, 2 started
atau cancelled, 3 completed. Issue juga menyimpan batch_version bahan setelah write.
Row lock dan expected_version menjaga sekali transisi, retry stale 409; event_uuid
unik. Gagal transaksi membatalkan stok, edge, movement, version dan event sekaligus.
Consumer masa depan harus deduplikasi event_uuid; delivery eksternal belum dijamin.

Contoh payload created (production adalah objek contoh data create lengkap pada kontrak):

```javascript
const payload = {
  schema_version: 1,
  actor_id: "88888888-8888-4888-8888-888888888888",
  production: createProductionResponse.data
};
```

Started menyertakan item sumber, quantity/UOM/storage dan batch_version; completed
menyertakan hasil aktual tanpa mengembalikan stok untuk yield loss, cancelled tidak
memiliki item. Movement ISSUE menggunakan asset_uuid batch bahan/storage/kitchen,
remarks UUID production_item; movement PRODUCTION menggunakan asset_uuid hasil dan
kitchen. Snapshot tidak berubah ketika resep master diperbarui. Tidak ada event
Stock.Read/GET atau event terpisah stock.issued; bukti pengeluaran ada pada
production.started. Event paket/holding kini tersedia internal seperti bagian berikut; traversal API belum tersedia.


## Paket dan holding internal

Status: **aktif internal**, producer PackageService, tabel PostgreSQL event_log,
entity_type PACKAGE dan entity_uuid package_id. Tenant/actor dari bearer, tidak ada
credential pada QR/payload. Master PackagingType CRUD hanya audit/version, tidak
menghasilkan event/registry. Event berikut memakai payload schema_version 1,
actor_id UUID string dan package object persis PackageData respons aksi (termasuk
calculated_at, timer, frozen policy dan QR). Field/nullable dan contoh record lengkap
ada di [kontrak paket/holding](frontend-api.md#kontrak-kemasan-paket-dan-holding).

| Event | Trigger/permission | Efek transaksi |
|---|---|---|
| package.created | POST packages / Package.Write | Alokasi hasil, version produksi, policy frozen, package registry, PACKAGED edge, PACKAGING movement |
| holding.started | POST holding/start / Holding.Start | Paket PACKAGED, anchor cooking finish, version, registry, holding_log |
| holding.updated | POST holding/update / Holding.Update | Refresh timer, version, registry, holding_log; termasuk refresh EXPIRED yang sudah tercatat |
| holding.expired | POST holding/update pertama menjadi EXPIRED / Holding.Update | Materialisasi expiry, version, registry, holding_log |
| holding.finished | POST holding/finish / Holding.Finish | RELEASED atau DISCARDED, finish timestamp, version, registry, holding_log |

Lima nama event (holding.finished memiliki dua outcome). Holding update setelah
release tetap mengukur deadline awal; release tidak memperpanjang umur paket.
Discard recommendation bukan auto discard. GET/list/resolve selalu menghitung waktu
terkini tetapi tidak menulis log/event. Tanpa POST update, expiry dapat hanya terlihat
pada effective_status respons; belum ada background scheduler/alarm publisher.

Ordering per paket memakai package.version (create=1, setiap aksi +1), bukan urutan
calculated_at global. Version produksi ikut naik setiap alokasi; package.created
menunjuk produksi tetapi tidak menggantikan GET allocation untuk memperoleh version
produksi terkini. Expected_version dan row lock mencegah pengulangan mutasi sukses;
retry stale 409, event_uuid unik. Duplikasi code/number atau kegagalan log/event
membatalkan seluruh write/alokasi/version. Consumer masa depan harus deduplikasi
UUID event. Belum ada consumer runtime eksternal, channel MQTT/WebSocket, retry
publisher, replay atau jaminan delivery ke frontend.

Contoh payload dari respons aksi yang lengkap:

```javascript
const payload = {
  schema_version: 1,
  actor_id: "88888888-8888-4888-8888-888888888888",
  package: packageResponse.data
};
```

Transport sekarang hanya penyimpanan atomik di DB. HoldingLog menggunakan package_id,
recorded_at UTC, elapsed/remaining_minutes, effective_status dan timer_status pada
warning_level; mqtt_message_id null karena aksi HTTP. Log append-only. Timer memakai
policy yang dibekukan saat alokasi pertama, bukan rule terbaru. Snapshot produksi
v1 bertambah field nullable food_category/holding_limit_minutes; payload produksi
lama tetap valid dan dibaca default null, tidak dibackfill.


## Event pengiriman internal

Status **aktif internal PostgreSQL event_log**, producer DeliveryService. Entity type
DELIVERY, entity_uuid ID delivery. Tenant dan actor berasal dari bearer dan permission
aksi, tidak dari payload. Empat event memakai schema_version 1, actor_id UUID string,
delivery object persis DeliveryDetail saat aksi selesai (header, items dan PackageData
nested termasuk timer/calculated_at). Field/nullable dan contoh snapshot lengkap pada
[kontrak pengiriman](frontend-api.md#kontrak-pengiriman).

| Event | Trigger/permission | Efek atomik |
|---|---|---|
| delivery.created | POST deliveries / Delivery.Write | Reservasi vehicle/driver/paket, ALLOCATED dan version paket, manifest, registry; tanpa movement |
| delivery.departed | POST depart / Delivery.Depart | IN_TRANSIT, departure/ETA, package versions, registry, edge LOADED dan movement VEHICLE_LOADING |
| delivery.completed | POST complete / Delivery.Complete | COMPLETED dan arrival time, paket DELIVERED, registry, edge/movement DELIVERED/DELIVERY |
| delivery.cancelled | POST cancel CREATED / Delivery.Cancel | CANCELLED, paket RELEASED atau EXPIRED, resource bebas, registry; manifest tetap, tanpa movement |

Ordering per delivery memakai delivery.version: create=1, depart/cancel=2,
complete=3. Package.version juga naik setiap reservasi/transisi, bukan version item
manifest. Row locks parent/paket dan expected_version mencegah reservasi ganda serta
retry mutasi sukses; retry stale 409. Event UUID unik; kegagalan item, reference,
registry atau event membatalkan semua write dalam transaksi. Consumer masa depan
harus deduplikasi event_uuid, tetapi subscriber/worker, transport MQTT/WebSocket,
retry publisher/replay dan delivery eksternal belum tersedia. Channel saat ini tabel
DB internal, bukan subscription frontend. GET tidak menulis event atau movement.

Contoh payload dari respons aksi:

```javascript
const payload = {
  schema_version: 1,
  actor_id: "88888888-8888-4888-8888-888888888888",
  delivery: deliveryResponse.data
};
```

Snapshot event mempertahankan kondisi saat transisi, sedangkan GET detail memuat
keadaan paket terkini (termasuk setelah cancel/reassignment). LOADED menghubungkan
registry package -> delivery; DELIVERED package -> school. Movement memakai
asset_uuid kitchen/vehicle/school dan remarks delivery_item_id. Complete yang terlambat
tetap mencatat kedatangan dengan nested package effective_status EXPIRED; event tidak
berarti sekolah menerima atau makanan aman. Tidak membuat school_receiving/event
acceptance/konsumsi. Holding action paket ALLOCATED/IN_TRANSIT/DELIVERED ditolak;
timer tetap dapat dievaluasi lewat GET tanpa menghasilkan holding.expired otomatis.


## Event penerimaan sekolah dan konsumsi internal

Status **aktif internal PostgreSQL event_log**, producer `SchoolWorkflowService`.
Consumer aktif: penyimpanan audit internal; belum ada subscriber, publisher,
notifikasi/alarm otomatis, MQTT/WebSocket, endpoint replay atau channel frontend.
Tenant/actor berasal dari bearer yang masih aktif dan permission DB saat transaksi.
Event memiliki event_uuid unik, entity_uuid ID bukti, audit tenant serta payload
schema_version=1, actor_id UUID string dan snapshot bukti sesuai kontrak frontend.

| Event | Trigger/auth | Entity type | Payload snapshot |
|---|---|---|---|
| school_receiving.recorded | POST /school-receivings; SchoolReceiving.Write | SCHOOL_RECEIVING | school_receiving: ReceiptData lengkap termasuk discrepancy_quantity |
| consumption.recorded | POST /consumptions; Consumption.Write | CONSUMPTION | consumption: ConsumptionData lengkap termasuk quantities, safe dan timer_status |

Field/nullable serta contoh data lengkap pada
[kontrak sekolah/konsumsi](frontend-api.md#kontrak-penerimaan-sekolah-dan-konsumsi).
Contoh payload persis dari respons POST yang sukses:

```javascript
const receiptEventPayload = {
  schema_version: 1,
  actor_id: "88888888-8888-4888-8888-888888888888",
  school_receiving: receivingResponse.data
};
const consumptionEventPayload = {
  schema_version: 1,
  actor_id: "88888888-8888-4888-8888-888888888888",
  consumption: consumptionResponse.data
};
```

Penerimaan memutasi PACKAGE ke RECEIVED/REJECTED, version+1, registry,
edge RECEIVED package -> school hanya accepted, dan movement SCHOOL_RECEIVING
untuk semua keputusan. Movement ini bukti inspeksi di sekolah, termasuk paket
missing/rejected, tidak mengklaim kedatangan fisik baru. Remarks=school_receiving_id.
Tidak membuat registry asset SCHOOL_RECEIVING tersendiri.

Finalisasi memutasi PACKAGE ke CONSUMED bila consumed_quantity>0, selainnya
DISCARDED, version+1. Membuat registry CONSUMPTION; edge CONSUMED package ->
consumption dan movement CONSUMED hanya jika consumed>0, movement DISCARD jika
discarded>0; remarks=consumption_id. Mixed outcome memiliki kedua movement.
Quantity disimpan di bukti, bukan ledger stok bahan. `safe` adalah snapshot holding
saat pencatatan; false pada konsumsi setelah deadline/unknown dengan notes wajib,
null jika semua dibuang. Tidak berarti hasil pemeriksaan keamanan menyeluruh.

Row locks school/delivery/package dan expected_version paket menjaga urutan per
paket: delivery completion -> satu receipt -> satu consumption untuk accepted.
Version bukti immutable selalu 1 untuk record API baru, bukan sequence event global.
Timestamps received_time/consumed_at server tidak mendahului tahap sebelumnya;
created_at bukan jaminan ordering lintas paket. Bukti, package version, registry,
edge/movement dan event commit/rollback atomik, termasuk kegagalan penulisan event.
Update/delete/truncate bukti ditolak DB. Retry POST sukses menghasilkan 409 karena
version/status/uniqueness, tanpa event kedua; belum ada idempotency key. Setelah
hasil request tidak pasti, klien membaca bukti berdasarkan package_id. Consumer
masa depan harus deduplikasi event_uuid; retry publisher/replay belum tersedia.
GET tidak membuat event. Snapshot event tidak berubah ketika timer paket bergerak.
Effective_status paket terminal CONSUMED/REJECTED/DISCARDED kini tetap terminal,
sedangkan timer_status dan remaining di GET tetap live.
