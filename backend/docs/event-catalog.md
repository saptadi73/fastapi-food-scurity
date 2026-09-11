# Event catalog FSOS

Terakhir diperbarui: 2026-09-11. Status: **belum ada event yang diterbitkan runtime**.

Tabel `event_log` dan bukti telemetry sudah tersedia. Event bus, publisher,
transactional outbox, worker, MQTT ingestion, WebSocket, dan SSE belum tersedia.
Insert database tidak otomatis menerbitkan event. Frontend belum memiliki channel
untuk subscribe. Kedua endpoint sistem saat ini tidak menghasilkan event bisnis.
Repository kitchen juga belum menerbitkan event; create/update/soft delete hanya
mengubah record di dalam transaksi milik application service.
History revisi alarm/holding rule dicatat trigger database; ini tidak menerbitkan
event perubahan aturan ke frontend. Validator DSL juga tidak menjalankan aksi.
Service simpan/aktivasi aturan menggunakan trigger history yang sama dan belum
memiliki publisher/outbox. enabled=true tidak memulai evaluator atau notifikasi.
Sync/backfill registry digital asset juga hanya memperbarui database. Integrasi
KitchenRepository belum menerbitkan event registry atau perubahan kitchen.
Seed development dan backfill FSOS_DEV juga tidak menerbitkan event ke frontend;
penambahan fixture database bukan contoh delivery/replay event runtime.
Service acknowledgment alarm dan penutupan sesi juga belum menerbitkan event.
device.disconnected pada daftar rencana belum otomatis dikirim ketika close_session dipanggil.
Maintenance partisi tidak menerbitkan event atau notifikasi frontend; hasilnya
berupa laporan JSON lokal dan exit code proses/task scheduler.
Provisioning role runtime dan pengerasan fungsi history tidak menerbitkan event
frontend. Trigger aturan tetap menyimpan snapshot internal, bukan delivery event.

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
| `payload` | JSONB object | Ya | Baru divalidasi sebagai objek, belum schema tiap jenis event |
| `created_at`, `updated_at` | timestamptz | Ya | Timestamp audit, default waktu database |
| `created_by`, `updated_by` | UUID | Tidak | Actor audit; validasi actor masih TODO |
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
