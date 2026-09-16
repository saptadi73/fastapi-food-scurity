# Perubahan kontrak frontend

## 2026-09-17 - Routing jalan fleet Google Routes API

- Estimasi pada create/depart delivery dan `GET /api/v1/deliveries/{identifier}/tracking` sekarang hanya memakai Google Routes API `computeRouteMatrix`, tanpa Mapbox, OSRM atau Haversine.
- Method, path, payload dan bentuk response tidak berubah. Nilai `estimated_distance_km`, `estimated_duration_minutes`, `remaining_distance_km`, `remaining_duration_minutes`, dan `estimated_arrival_time` kini dapat berasal dari jarak/durasi berkendara aktual.
- Frontend tidak mengirim atau menerima Google API key. Koordinat berasal dari master kitchen/sekolah dan GPS armada; untuk multi-tujuan backend memilih tujuan dengan durasi terlama, belum mengoptimalkan urutan stop. Jika Google tidak tersedia, field estimasi dapat null.
- Halaman frontend `/deliveries/tracking` menampilkan marker armada, dapur dan sekolah tujuan serta garis rute berkendara Google Maps. Konteks tujuan dibaca dari detail delivery dan master lokasi; rute dihitung ulang setelah armada berpindah minimal sekitar 100 meter untuk mengendalikan pemakaian API.

## 2026-09-16 - Frontend School Consumption workflow

- Project frontend memperluas halaman scan `Penerimaan Sekolah` (`/scan/school-receiving`) dengan form finalisasi konsumsi/discard setelah paket diterima sekolah.
- Tidak ada endpoint backend baru; frontend memakai kontrak aktif `POST /api/v1/consumptions`, `GET /api/v1/consumptions`, dan `GET /api/v1/consumptions/{identifier}`.
- Form mengirim `package_id`, `expected_version`, `consumed_quantity`, `discarded_quantity`, dan `notes`. Backend tetap memvalidasi package sudah `RECEIVED`, receipt accepted tersedia, consumed + discarded sama dengan received quantity, dan notes wajib untuk discard atau konsumsi di luar holding policy.
## 2026-09-16 - Package delivery context untuk school receiving

- Menambahkan `GET /api/v1/packages/{identifier}/delivery-context` dengan `Package.Read` untuk auto-fill form penerimaan sekolah setelah scan QR paket.
- Response berisi `package_id`, `package_version`, `package_status`, serta konteks manifest non-CANCELLED terbaru bila ada: `delivery_item_id`, `delivery_id`, `delivery_status`, `school`, `departure_time`, `arrival_time`, dan `estimated_arrival_time`.
- Endpoint read-only; tidak membuat school receiving, tidak mengubah timer/status paket, delivery, movement, atau event. Frontend `/scan/school-receiving` kini memakai endpoint ini untuk mengisi otomatis `delivery_id`, `school`, dan version paket sebelum submit `POST /school-receivings`.
## 2026-09-16 - Frontend School Receiving scan workflow

- Project frontend memperluas halaman scan `Penerimaan Sekolah` (`/scan/school-receiving`) untuk desain point 13: resolve QR paket, auto-fill version paket dan quantity, lalu mencatat penerimaan sekolah dengan `delivery_id`, `school`, `received_quantity`, `condition`, `accepted`, suhu manual, referensi foto, dan notes.
- Tidak ada endpoint backend baru; halaman memakai kontrak aktif `GET /api/v1/packages/resolve` dan `POST /api/v1/school-receivings`. Frontend juga menambahkan helper typed untuk `GET /school-receivings`, `GET /school-receivings/{identifier}` dan `POST /school-receivings`.
- Dampak frontend: operator sekolah dapat scan paket yang tiba, mencatat suhu manual dan bukti operasional, serta menentukan accepted/rejected sesuai kondisi fisik. Delivery harus sudah `COMPLETED` dan package harus `DELIVERED`; backend tetap memvalidasi manifest, tujuan sekolah, version paket, timer, quantity dan aturan notes.
## 2026-09-16 - Frontend Delivery manifest dan dispatch

- Project frontend memperluas halaman `Pengiriman Aktif` (`/deliveries`) menjadi workflow operasional untuk desain point 9, 11 dan 12: create manifest, daftar/filter status delivery, detail paket per manifest, depart/loading armada dengan ETA opsional, complete perjalanan, cancel manifest `CREATED`, dan tautan live tracking.
- Tidak ada endpoint backend baru; halaman memakai kontrak aktif `POST /api/v1/deliveries`, `GET /api/v1/deliveries`, `GET /api/v1/deliveries/{identifier}`, `POST /api/v1/deliveries/{identifier}/depart`, `POST /api/v1/deliveries/{identifier}/complete`, `POST /api/v1/deliveries/{identifier}/cancel`, dan `GET /api/v1/deliveries/{identifier}/tracking`.
- Dampak frontend: operator dapat mengisi paket hasil scan/label, tujuan sekolah, version paket, armada dan driver untuk membuat manifest; kemudian mengubah status menjadi `IN_TRANSIT` saat loading/berangkat dan `COMPLETED` saat perjalanan selesai. Penerimaan sekolah dengan suhu manual/foto tetap menjadi prioritas UI berikutnya.
## 2026-09-16 - Frontend Production Batch workflow

- Project frontend menambahkan halaman `Production Batch` (`/production-batches`) untuk daftar/filter batch produksi, pembuatan manufacturing order/cooking batch, detail bahan terpakai, pembatalan batch `CREATED`, dan penyelesaian batch `RUNNING` dengan `actual_quantity` serta `initial_temperature`.
- Tidak ada endpoint backend baru; halaman memakai kontrak aktif `GET/POST /api/v1/production-batches`, `GET /api/v1/production-batches/{identifier}`, `POST /api/v1/production-batches/{identifier}/complete`, dan `POST /api/v1/production-batches/{identifier}/cancel`.
- Dampak frontend: desain point 6-7 kini memiliki screen khusus untuk kode masak/manufacturing order, jumlah produksi, status cooking, waktu selesai masak, suhu inti awal, dan dasar alur holding/packaging berikutnya. Aksi start produksi dengan scan/pemakaian bahan masih menjadi prioritas lanjutan agar point 6 lengkap end-to-end di UI.
- Update lanjutan: frontend sekarang menyediakan aksi `Mulai` untuk batch `CREATED` melalui `POST /api/v1/production-batches/{identifier}/start`. Modal menerima daftar bahan hasil scan/manual input berisi `raw_material_batch_id`, `storage_id`, `expected_version` batch bahan, dan `quantity`. Endpoint backend tetap kontrak aktif yang sama; backend melakukan validasi stok, expiry, tenant, version dan pengurangan stok atomik.
- Update cek stok bahan: modal start produksi frontend sekarang memakai `GET /api/v1/raw-material-batches/{identifier}/stock` untuk mengisi otomatis `expected_version` batch bahan, `storage_id` pertama yang memiliki `available_quantity > 0`, dan default `quantity` sesuai saldo tersedia. Ini memperhalus flow FEFO/FIFO karena operator dapat memilih batch dari daftar FEFO lalu memvalidasi saldo aktual sebelum `POST /production-batches/{identifier}/start`.
## 2026-09-15 - Login memakai tenant code

- `POST /api/v1/auth/login` sekarang menerima field `tenant` berisi tenant code
  seperti `FSOS_DEMO` atau UUID tenant.
- Field legacy `tenant_id` UUID masih diterima untuk kompatibilitas, tetapi
  frontend baru disarankan memakai `tenant`.
- Tidak ada endpoint baru; response token tetap sama dan token tetap membawa UUID
  tenant terverifikasi.

## 2026-09-15 - Seed demo frontend end-to-end

- Menambahkan `backend/scripts/seed_demo_ready.py` untuk data demo frontend:
  tenant/user login, permission lengkap, master operasional, workflow 14 tahap,
  IoT sample, complaint report, recall withdrawal dan notification outbox.
- Menambahkan `backend/scripts/migrate_with_status.py` agar migration command
  memberi output JSON before/after dan status sukses/gagal.
- Tidak ada endpoint baru; kontrak HTTP tetap 165 operasi aktif.
- Dokumentasi frontend menunjuk ke data login/kode demo di `development-seed.md`.

## 2026-09-15 - Complaint incident report dan foto bukti

- `POST /api/v1/complaints` sekarang menerima salah satu dari `package_id` atau
  `package_code`; `package_code` mendukung hasil scan QR/label di frontend.
- `ComplaintInput` dan `ComplaintData` menambah `photo` nullable untuk referensi
  foto bukti operasional.
- Menambahkan `GET /api/v1/complaints/reports` dan
  `GET /api/v1/complaints/{identifier}/report` dengan `Complaint.Read`.
- Report menyatukan complaint, package, batch produksi, lokasi/delivery/receipt
  sekolah, konsumsi, bahan baku produksi, expiry bahan, suhu receiving, manual
  issue bahan dan traceability movement. Operasi aktif naik menjadi 165.

## 2026-09-15 - Dashboard notification outbox

- Menambahkan `GET /api/v1/dashboard/notifications` dengan `Dashboard.Read`.
- Response berisi jumlah outbox `PENDING`, `SENT`, `FAILED`, `CANCELLED` dan
  pending per channel dashboard/email/whatsapp/telegram. Operasi aktif naik
  menjadi 163.
- Endpoint read-only; tidak mengirim provider eksternal atau membuka subscription.

## 2026-09-15 - Notification outbox operasional

- Menambahkan `GET /api/v1/notifications`,
  `POST /api/v1/notifications/{identifier}/mark-sent` dan
  `POST /api/v1/notifications/{identifier}/mark-failed`.
- Event recall otomatis membuat item outbox `DASHBOARD` `PENDING`; worker/operator
  dapat menandai `SENT` atau `FAILED` dengan `Notification.Dispatch`.
- Menambahkan permission `Notification.Read` dan `Notification.Dispatch`.
  Operasi aktif naik menjadi 162.
- Ini belum integrasi provider email/WhatsApp/Telegram, retry worker atau
  subscription realtime frontend.

## 2026-09-15 - Bukti penarikan fisik recall

- Menambahkan `POST /api/v1/recalls/{identifier}/withdrawals` untuk mencatat
  bukti penarikan fisik append-only dengan `Recall.Execute`.
- Menambahkan `GET /api/v1/recalls/{identifier}/withdrawals` untuk daftar bukti
  dengan `Recall.Read`, pagination dan filter `package_id`.
- Bukti mencatat kode evidence, package opsional, jumlah/uom opsional, kondisi,
  foto URI/path, waktu penarikan dan selesai. Operasi aktif naik menjadi 159.
- Backend menulis movement `RECALL`, menaikkan version recall dan event internal
  `recall.withdrawal_recorded`; belum ada notifikasi atau verifikasi otomatis.

## 2026-09-15 - Dashboard suhu storage terbaru

- Menambahkan `GET /api/v1/dashboard/storage-temperatures` dengan permission
  `Dashboard.Read`.
- Response paginated memuat storage aktif, sampel suhu terakhir, batas suhu,
  device terkait dan status `OK`, `LOW`, `HIGH`, `UNSUPPORTED_UNIT` atau
  `NO_DATA`. Operasi aktif naik menjadi 157.
- Endpoint ini read-only dari `temperature_log`; belum WebSocket, MQTT
  subscription, alarm evaluator atau grafik historis.

## 2026-09-15 - HTTP ingestion telemetry GPS/suhu

- Menambahkan `POST /api/v1/telemetry/gps` dan
  `POST /api/v1/telemetry/temperatures` dengan permission `Telemetry.Ingest`.
- Endpoint append-only mengisi `gps_log` dan `temperature_log` yang dibaca oleh
  tracking delivery. Operasi aktif naik menjadi 156.
- Ini belum MQTT broker, API key device, deduplikasi payload atau WebSocket live.

## 2026-09-15 - Tracking delivery read-only

- Menambahkan `GET /api/v1/deliveries/{identifier}/tracking` dengan `Delivery.Read`.
- Response berisi GPS terakhir kendaraan, suhu terakhir dari device GPS kendaraan
  bila ada, sisa jarak garis lurus dan estimasi sisa waktu ke tujuan terjauh.
- Operasi aktif naik menjadi 154. Endpoint ini read-only, bukan MQTT ingestion,
  WebSocket atau live push.

## 2026-09-15 - Ringkasan kemasan delivery

- Menambahkan `GET /api/v1/deliveries/packages/by-vehicle` untuk jumlah kemasan
  dan total quantity per armada.
- Menambahkan `GET /api/v1/deliveries/packages/by-destination` untuk jumlah kemasan
  dan total quantity per sekolah tujuan.
- Keduanya read-only dengan `Delivery.Read`, offset/limit dan filter status.
  Operasi aktif naik menjadi 153.

## 2026-09-15 - Estimasi route delivery

- `POST /api/v1/deliveries` menerima `average_speed_kmph` opsional dan menghitung
  `estimated_distance_km`, `estimated_duration_minutes`, serta
  `estimated_arrival_time` dari koordinat kitchen ke sekolah tujuan.
- `POST /api/v1/deliveries/{identifier}/depart` kini boleh tanpa
  `estimated_arrival_time`; backend menghitung ETA otomatis bila koordinat lengkap.
- `DeliveryData` menambah `estimated_distance_km` dan `estimated_duration_minutes`.
  Tidak ada endpoint baru; operasi aktif tetap 151.

## 2026-09-15 - Suhu awal pengemasan

- `POST /api/v1/packages` menerima `initial_temperature` opsional nullable sebagai
  suhu awal manual saat kemasan dibuat.
- `PackageData` pada detail/list/resolve dan event package menambah
  `initial_temperature`. Tidak ada endpoint baru; operasi aktif tetap 151.

## 2026-09-15 - Suhu awal selesai masak

- `POST /api/v1/production-batches/{identifier}/complete` menerima
  `initial_temperature` opsional nullable sebagai suhu makanan awal manual saat
  selesai masak.
- `ProductionData` pada detail/list/event production menambah
  `initial_temperature`. Tidak ada endpoint baru; operasi aktif tetap 151.

## 2026-09-15 - Pengeluaran bahan manual/scan

- Menambahkan `POST /api/v1/raw-material-batches/{identifier}/manual-stock-issues`
  dengan permission `Stock.Issue` untuk mencatat bahan keluar dari storage tanpa
  production batch.
- Menambahkan `GET /api/v1/raw-material-batches/{identifier}/manual-stock-issues`
  dengan `Stock.Read` untuk ledger manual issue. Operasi aktif naik menjadi 151.
- GET stock sekarang mengurangi `available_quantity` dengan issue produksi dan
  manual issue. Start produksi juga memperhitungkan manual issue agar stok tidak
  terpakai ganda.

## 2026-09-15 - Search batch FEFO/FIFO

- `GET /api/v1/raw-material-batches` menambah query `search`, `material_category`
  dan `sort=CREATED_DESC|FIFO|FEFO`.
- `search` mencari `material_code`, `material_name` dan `batch_code` secara
  case-insensitive. `FEFO` menaruh expired date terdekat lebih dulu dan null
  terakhir; `FIFO` memakai waktu receiving paling lama.
- Tidak ada endpoint baru, response schema tetap `BatchPage`.

## 2026-09-15 - Putaway sampai storage zone/rak

- `POST /api/v1/raw-material-batches/{identifier}/putaway` menerima `zone_id`
  opsional nullable untuk menempatkan batch bahan ke slot/rak storage.
- `StockEntryData` pada respons putaway, ledger dan payload event `stock.putaway`
  menambah `zone_id`. Balance tetap agregasi per storage karena issue produksi
  saat ini masih memilih storage, belum zone.
- Tidak ada endpoint baru; jumlah operasi HTTP tetap 149.

## 2026-09-15 - Bukti kondisi penerimaan bahan baku

- `POST /api/v1/receivings` menerima `items[].condition` dan `items[].photo`
  opsional untuk inspeksi visual/foto bahan baku. Keduanya ikut muncul di
  `ReceivingDetail.items[]` dan payload event receiving internal.
- Tidak ada endpoint baru; jumlah operasi HTTP tetap 149. `photo` hanya referensi
  file/URL, bukan upload atau validasi akses file oleh backend.

## 2026-09-15 - Dashboard domain aktif

- Menambahkan `GET /api/v1/dashboard/storage`, `/fleet`, `/holding` dan `/recall`
  dengan permission `Dashboard.Read`.
- Endpoint read-only mengembalikan counter tenant per domain untuk storage,
  armada/pengiriman, holding/alarm dan recall.
- Operasi aktif naik menjadi 149. Analytics dashboard, cache materialized,
  subscription realtime dan SLA alert masih belum tersedia.

## 2026-09-15 - Dashboard home aktif

- Menambahkan `GET /api/v1/dashboard/home` dengan permission `Dashboard.Read`.
- Endpoint read-only mengembalikan counter tenant: complaint aktif, recall terbuka,
  delivery in transit, package per status utama, production completed dan batch
  bahan accepted.
- Operasi aktif naik menjadi 145. Tidak ada cache materialized, event baru,
  subscription realtime, SLA alarm atau agregasi lintas tenant.

## 2026-09-15 - Traceability passport dan impact aktif

- Menambahkan `GET /api/v1/traceability/assets/{asset_uuid}/passport` untuk
  snapshot asset, relasi parent/child langsung dan movement terbaru.
- Menambahkan `GET /api/v1/traceability/assets/{asset_uuid}/impact` untuk impact
  downstream berbasis traversal forward, termasuk affected_counts dan subset
  package/complaint/recall.
- Operasi aktif naik menjadi 144. Endpoint tetap read-only dengan `Traceability.Read`;
  tidak ada registry repair, event baru, status package baru atau subscription.

## 2026-09-14 - Eksekusi recall paket aktif

- Menambahkan endpoint `POST /api/v1/recalls/{identifier}/execute` dengan
  `Recall.Execute` dan `expected_version`.
- Execute menandai package terdampak nonterminal menjadi `RECALLED`, mempertahankan
  package `CONSUMED`/`DISCARDED`/`REJECTED`, menulis edge package -> recall,
  movement `RECALL`, menaikkan version recall dan event internal `recall.executed`.
- Operasi aktif naik menjadi 142. Tidak ada notifikasi, bukti penarikan fisik,
  idempotency key, update reason, delete recall atau subscription frontend.

## 2026-09-14 - Traceability read aktif

- Menambahkan endpoint `GET /api/v1/traceability/assets/{asset_uuid}`,
  `/relationships`, `/movements` dan `/traverse` untuk investigasi graph/movement.
- Endpoint memakai permission `Traceability.Read`, membaca `digital_asset`,
  `asset_relationship` dan `asset_movement` secara read-only.
- Traversal mendukung `direction=forward|backward`, `depth` 1..6 dan batas node
  `limit` 1..200; response menyertakan `truncated` bila batas node tercapai.
- Operasi aktif naik menjadi 141. Tidak ada registry repair, movement baru, event
  baru, replay, subscription frontend atau eksekusi recall otomatis.

## 2026-09-14 - Recall dasar aktif

- Menambahkan endpoint `POST /api/v1/recalls`, `GET /api/v1/recalls`,
  `GET /api/v1/recalls/{identifier}` dan `POST /api/v1/recalls/{identifier}/close`.
- Recall memakai permission `Recall.Execute` untuk start/close dan `Recall.Read`
  untuk list/detail; response detail menyertakan snapshot package terdampak dari
  production batch.
- Start recall menyimpan registry `RECALL`, edge `RECALLED`, movement `RECALL`
  per package batch dan event internal `recall.started`. Close mengisi
  `completed_at`, menaikkan version dan menulis event `recall.completed`.
- Operasi aktif naik menjadi 137. Tidak ada perubahan status package, notifikasi,
  penarikan fisik, impact analysis lintas graph atau subscription frontend.

## 2026-09-14 - Complaint intake aktif

- Menambahkan endpoint `POST /api/v1/complaints`, `GET /api/v1/complaints` dan
  `GET /api/v1/complaints/{identifier}` untuk mencatat dan membaca keluhan paket.
- Complaint memakai permission `Complaint.Write`/`Complaint.Read`, package dan
  school satu tenant, school aktif, serta manifest delivery noncancelled yang
  menghubungkan package ke school tersebut.
- POST menyimpan complaint immutable, registry `COMPLAINT`, edge `REPORTED`,
  movement `COMPLAINT` dan event internal `complaint.recorded` secara atomik.
- Operasi aktif naik menjadi 133. Tidak ada update/delete complaint, perubahan
  status package, recall otomatis, notifikasi realtime atau subscription frontend.

## 2026-09-14 - CRUD binding perangkat-kendaraan aktif

- Menambahkan endpoint `GET /api/v1/device-bindings`,
  `POST /api/v1/device-bindings`, `GET /api/v1/device-bindings/{identifier}`,
  `PUT /api/v1/device-bindings/{identifier}` dan
  `DELETE /api/v1/device-bindings/{identifier}`.
- Binding memakai permission `Device.Read`, `Device.Write`, `Device.Delete`,
  validasi device aktif bertipe `GPS`, vehicle aktif, tenant sama, unique pair,
  soft delete dan `expected_version`.
- `frontend-api.md` diperbarui (operasi aktif: 130; CRUD menjadi 14 master),
  `event-catalog.md` menandai binding CRUD aktif tanpa producer/consumer realtime,
  dan Alembic head menjadi `20260911_0023`.
- Tidak ada event runtime, movement, GPS log, cascade delete atau subscription
  frontend baru; frontend memakai respons mutasi dan GET ulang.

## 2026-09-14 - CRUD master device aktif

- Menambahkan endpoint `GET /api/v1/devices`, `POST /api/v1/devices`,
  `GET /api/v1/devices/{identifier}`, `PUT /api/v1/devices/{identifier}` dan
  `DELETE /api/v1/devices/{identifier}` untuk CRUD master perangkat.
- Mengaktifkan permission `Device.Read`, `Device.Write`, `Device.Delete`, `expected_version`,
  parent `zone_id` aktif dan soft delete; registrasi `DEVICE` disinkronkan atomik.
- Binding perangkat-kendaraan ditambahkan pada entri berikutnya; event runtime belum ada.
- `frontend-api.md` diperbarui (operasi aktif: 125; CRUD menjadi 13 master),
  dan `event-catalog.md` kini menandai CRUD device aktif tanpa producer/consumer aktif.
- [Kontrak frontend master device](frontend-api.md#kontrak-master-device-dan-binding) dan
  [catatan event device](event-catalog.md#crud-master-device) ditambahkan.

## 2026-09-11 - Penerimaan bahan dan batch

- Tujuh operasi receiving/batch tersedia; total 75 operasi HTTP, master CRUD tetap
  45 operasi. Create header/item/batch atomik, GET list/detail, complete inspeksi,
  cancel draft dan baca batch. Tidak ada edit/delete langsung transaksi historis.
- Receiving.Read/Write/Complete/Cancel dan RawMaterialBatch.Read independen; hak
  minimum runtime dan DEV_MAINTENANCE lokal telah diterapkan.
- Frontend mengirim seluruh keputusan bool + expected_version untuk complete;
  expired sebelum tanggal UTC hari ini tidak boleh accepted. Batch ditolak tetap
  tercatat. Retry finalisasi sukses 409; reload sebelum mencoba kembali.
- Registry, SUPPLIED/RECEIVED, movement dan event_log tersimpan atomik. Event baru
  created/completed/cancelled belum diterbitkan ke broker/frontend.
- [Kontrak lengkap](frontend-api.md#kontrak-receiving-dan-batch-bahan) dan
  [event catalog](event-catalog.md#event-receiving-tersimpan) menjelaskan payload,
  respons, permission, pagination, error dan efek samping. Stok/saldo/putaway,
  produksi, inspeksi parsial/foto serta reversal masih TODO.
- Pemeriksaan HTTP memakai role runtime mencakup rollback, tenant/permission,
  expiry, lifecycle dan bukti event/movement. Contoh JSON diverifikasi ke schemas
  dan jumlah operasi ke OpenAPI. Tidak ada migrasi atau seeding bisnis lokal.

## 2026-09-11 - CRUD kendaraan dan driver

- Sepuluh operasi GET list/detail, POST, PUT, DELETE tersedia untuk /drivers dan
  /vehicles. Driver/Vehicle.Read/Write/Delete independen; akses minimum lokal tersedia.
- Driver/GPS opsional dan boleh dilepas dengan null; bila diisi harus aktif satu
  tenant, GPS harus tipe GPS dan menggunakan device_id internal, bukan device_uuid.
- Koordinat/kapasitas divalidasi; PUT mengganti definisi dan memakai expected_version.
  Penggantian driver pada master tidak mengubah driver historis pada delivery.
- Soft delete driver ditolak bila masih ada vehicle/delivery; vehicle ditolak bila
  masih ada delivery/gps_log nondeleted. Registry VEHICLE mengikuti mutasi atomik;
  driver tidak menjadi digital_asset. Tidak ada cascade/restore/event baru.
- [Kontrak frontend](frontend-api.md#kontrak-kendaraan-dan-driver) memuat seluruh
  payload/response, contoh, permission, error dan batas integrasi GPS. Matriks kini
  68 operasi HTTP, 45 operasi CRUD sembilan master. API delivery/device masih TODO.
- Dua belas pemeriksaan terkait lulus; Ruff bersih. Tidak ada migrasi atau fixture
  bisnis lokal baru; grant minimum runtime dan role development diperbarui.

## 2026-09-11 - CRUD master sekolah

- GET/POST /schools dan GET/PUT/DELETE /schools/{identifier} tersedia. School.Read,
  Write dan Delete independen, sudah diberikan ke DEV_MAINTENANCE lokal.
- Kitchen harus aktif satu tenant untuk create/update dan tidak dapat dipindahkan.
  Koordinat berpasangan, student_count integer nonnegatif. PUT mengganti definisi
  dengan expected_version; DELETE memakai expected_version query dan body kosong.
- Soft delete ditolak bila delivery_item, school_receiving atau complaint nondeleted
  merujuk sekolah. Source dan registry SCHOOL disinkronkan atomik pada setiap mutasi.
- [Kontrak sekolah](frontend-api.md#kontrak-crud-sekolah) memuat field/payload,
  respons, contoh, permission, validasi, pagination dan error. Matriks kini 58 operasi
  HTTP, 35 di antaranya CRUD tujuh master. Transaksi penerimaan sekolah tetap TODO.
- Pemeriksaan terarah sekolah lulus setelah koreksi ekspektasi urutan fixture dengan
  timestamp sama; regresi lokasi/delete/API juga diperiksa. Tidak ada migrasi,
  seeding sekolah lokal atau event runtime baru.

## 2026-09-11 - Klarifikasi cakupan CRUD dan sekolah

- Tambahkan [matriks cakupan](frontend-api.md#cakupan-crud-dan-status-modul) berdasarkan
  router/OpenAPI: 53 operasi aktif, 30 di antaranya CRUD enam master.
- CRUD sekolah, kendaraan, driver, menu/food item, resep, jenis kemasan dan master
  device/binding belum tersedia; schema/fixture/adapter bukan kontrak endpoint.
- Master sekolah dibedakan dari transaksi penerimaan sekolah, dan master device
  dibedakan dari API sesi perangkat. Keduanya tidak boleh disamakan statusnya.
- Pembaruan dokumentasi/status saja; tidak ada perubahan endpoint, payload,
  permission, data, event atau implementasi CRUD baru pada perubahan ini.

## 2026-09-11 - CRUD lengkap dengan soft delete enam master

- DELETE /kitchens/{identifier}, /storages/{identifier}, /storage-zones/{identifier},
  /suppliers/{identifier}, /raw-materials/{identifier}, /supplier-materials/{identifier}
  ditambahkan. expected_version query wajib; tanpa body; sukses 200 snapshot terhapus.
- Permission Kitchen/Storage/StorageZone/Supplier/RawMaterial/SupplierMaterial.Delete
  terpisah dari Read/Write, sudah diberikan eksplisit ke DEV_MAINTENANCE lokal.
- Soft delete mengisi actor/waktu audit dan menaikkan version; source/registry
  kitchen/storage/supplier/bahan atomik. Tidak ada DELETE SQL, cascade atau event baru.
- Referensi nondeleted (termasuk INACTIVE dan transaksi selesai) memblokir 409;
  daftar tabel penghalang dan contoh lengkap di [kontrak DELETE](frontend-api.md#soft-delete-master-operasional).
- Frontend sembunyikan aksi tanpa Delete; kirim version terakhir. Setelah sukses
  hapus row dari tampilan; GET/PUT/DELETE ulang 404. Kode/pasangan tidak bisa dipakai
  ulang dan tidak ada restore otomatis. Riwayat/transaksi tidak dihapus.
- Sepuluh pemeriksaan terarah lulus: enam lifecycle DELETE, audit/registry, permission
  terpisah/dicabut, tenant lain, version, referensi serta regresi create/read/update.

## 2026-09-11 - Supplier, bahan baku dan relasi pemasok

- Dua belas operasi list/detail/create/replace tersedia pada /suppliers,
  /raw-materials dan /supplier-materials; bearer dan Read/Write tiap modul terpisah.
- Banyak supplier per bahan; pasangan aktif satu tenant wajib, duplicate/version
  conflict 409. PUT relasi boleh mengoreksi pasangan tanpa mengubah transaksi lama.
- Uom bahan tetap setelah create; suhu/durasi/email divalidasi. PUT mengganti semua
  definisi, optional yang dihilangkan reset default; decimal respons string.
- Supplier/material registry sinkron atomik; relasi tidak membuat edge graph,
  stok, receiving atau event runtime. Tidak ada delete/unlink/restore.
- [Kontrak frontend](frontend-api.md#kontrak-supplier-bahan-dan-relasi) memuat seluruh
  payload, contoh respons, filter/pagination, nullable, permission, error dan efek samping.
- Akses minimum DEV_MAINTENANCE dan runtime diterapkan tanpa migrasi/seeding bisnis.
  Delapan pemeriksaan terarah lulus; Ruff bersih. Selanjutnya transaksi receiving.

## 2026-09-11 - Master kitchen, storage dan zone

- Dua belas operasi tersedia: list/detail/create/replace untuk /kitchens, /storages
  dan /storage-zones. Bearer dan Read/Write masing-masing modul; grant minimum lokal
  tersedia pada DEV_MAINTENANCE. Tidak ada perubahan seeding atau fixture bisnis.
- POST 201; GET/PUT 200; expected_version mencegah lost update. PUT mengganti seluruh
  definisi, termasuk reset field opsional yang dihilangkan; parent tidak dapat diganti.
- Parent wajib aktif dan satu tenant; INACTIVE tidak menghapus/mengubah anak secara
  cascade. Koordinat/suhu divalidasi; decimal respons string dan audit timestamp UTC.
- Registry kitchen/storage sinkron atomik; zone tidak menjadi digital_asset.
  Tidak ada delete, movement, relationship atau event runtime baru.
- [Kontrak frontend](frontend-api.md#kontrak-master-kitchen-storage-zone) memuat
  payload/response lengkap, contoh semua operasi, pagination, auth, validasi dan error.
- Tujuh pemeriksaan terarah lulus; dua tes HTTP lulus ulang dengan kasus tenant lain.
  Ruff bersih. Tidak ada migrasi; grant runtime storage/zone disesuaikan minimum.

## 2026-09-11 - HTTP sesi perangkat dan provisioning telemetry

- GET /device-sessions, GET /device-sessions/{session_id} dan POST
  /device-sessions/{session_id}/end tersedia dengan DeviceSession.Read/Close terpisah.
- POST menerima disconnected_at ISO 8601 bertimezone; retry instant sama 200,
  waktu berbeda 409. Frontend memakai is_open/effective_disconnected_at, bukan snapshot
  disconnected_at. Respons UTC, no-store, filter status/waktu/perangkat dan next_offset.
- [Kontrak frontend lengkap](frontend-api.md#kontrak-sesi-perangkat-http) mencakup
  payload, field respons, nullable, contoh, permission, validasi, error dan efek samping.
- [CLI provisioning](telemetry-permissions.md) tersedia, default check dan --apply
  eksplisit; empat permission/grant diterapkan ke DEV_MAINTENANCE di FSOS_DEV lokal.
  Pengulangan tidak membuat row baru; revoked grant tidak dipulihkan; seed tidak berubah.
- Akun anggota role tersebut dapat memuat ulang /auth/me untuk izin terbaru.
  Tidak ada akun/password/membership baru, migrasi, ingestion/reconnect atau event runtime.
- Verifikasi 25 tes terkait lulus; Ruff bersih. Pemeriksaan runtime grant lokal berhasil.

## 2026-09-11 - HTTP alarm telemetry dan acknowledgment

- Tiga operasi tersedia: GET /alarms, GET /alarms/{alarm_id}, POST
  /alarms/{alarm_id}/acknowledgment. Bearer dengan Alarm.Read/Alarm.Acknowledge terpisah.
- Filter status efektif/perangkat/waktu, offset/limit/next_offset; respons terstruktur
  UTC/no-store. POST wajib tanpa body; actor/waktu server, retry mempertahankan bukti.
- Frontend memakai effective_acknowledged, bukan snapshot acknowledged; metadata
  acknowledgment impor dapat null. Kontrak payload/response/error dan contoh lengkap
  ada di [panduan frontend](frontend-api.md#kontrak-alarm-telemetry-http).
- Permission telemetry belum ditambahkan ke role lokal; provisioning administratif
  tetap TODO. AlarmRule.* tidak memberikan akses Alarm.*.
- Tidak ada migrasi, ingestion, notifikasi atau event runtime. API sesi masih TODO.
- Verifikasi 26 tes terkait lulus, termasuk runtime database role, tenant lain,
  izin dicabut, retry tanpa duplikasi, filter efektif dan snapshot impor.

## 2026-09-11 - Endpoint manajemen dan aktivasi alarm rule

- Enam operasi HTTP: list/create/detail/replace/history dan PUT enabled.
  Bearer session wajib; AlarmRule.Read/Write/Activate independen, scope tenant dari sesi.
- POST 201 membuat konfigurasi disabled. Edit disabled dan aktivasi memakai
  expected_version; stale/duplikat/edit aktif 409, DSL invalid 400. Enable memvalidasi
  ulang DSL; disable legacy invalid tetap boleh. No-op enabled tidak menambah revisi.
- Schema respons lengkap, timestamp UTC, pagination offset/limit, no-store dan
  error mapping terdokumentasi dalam [kontrak frontend](frontend-api.md#kontrak-alarm-rule-http).
- Frontend editor harus memisahkan izin aktivasi dari izin edit, menyimpan version
  terbaru dari respons, serta meminta reload/peninjauan saat konflik versi.
- Pengetatan validator: metadata alarm dan nilai teks DSL tidak menerima NUL atau
  Unicode invalid. DSL struktur belum memvalidasi template/target/transisi executor.
- Tidak ada migrasi, engine, alarm_log baru atau publikasi event. Enabled merupakan
  status konfigurasi, bukan bukti pemantauan alarm sudah berjalan.
- Verifikasi 39 tes terkait lulus, lalu dua tes HTTP alarm diperluas dan lulus ulang
  untuk legacy invalid dan Activate tanpa Read/Write; Ruff bersih.

## 2026-09-11 - Endpoint manajemen holding rule

- Lima operasi HTTP tersedia: list/create/detail/replace/history di /holding-rules.
  Read/Write terpisah, tenant/actor dari bearer session dan transaksi atomik history.
- POST 201, GET/PUT 200; validasi 400, auth 401, permission 403, record 404 dan
  duplicate/version 409. Respons bertipe terstruktur, UTC dan no-store.
- PUT membutuhkan empat field definisi dan expected_version; tidak ada PATCH/delete.
  Nilai menit integer dibatasi 2147483647, warning <= maximum <= discard.
- [Kontrak frontend lengkap](frontend-api.md#kontrak-holding-rule-http) memuat
  field, contoh request/response, pagination, error dan efek samping.
- Tidak ada event/publisher atau holding engine yang dijalankan. Tidak ada migrasi.
- Verifikasi: 37 tes terkait lulus setelah normalisasi UTC; HTTP diuji dengan role
  database fsos_runtime, termasuk izin dicabut, tenant lain dan history atomik.

## 2026-09-11 - Bootstrap akun manusia development

- CLI administratif membuat akun ACTIVE baru dan membership role tenant yang
  dipilih, dengan password tersembunyi dan hash bcrypt. Akun existing tidak diubah.
- --check memeriksa profil/tenant/actor/role tanpa insert atau prompt password.
  [Panduan lengkap](human-bootstrap.md) mencakup command, input/output dan error.
- Login/me memakai kontrak yang sama; tidak ada signup HTTP, event atau email baru.
  Actor dev-maintenance tetap tanpa password. Bootstrap production masih TODO.
- Verifikasi: 113 tes lulus, Ruff bersih; --check lokal tidak membuat akun contoh.

## 2026-09-11 - Endpoint autentikasi HTTP aktif

- POST /api/v1/auth/login, /auth/refresh, /auth/logout serta GET /auth/me tersedia.
  Payload JSON, respons data terstruktur, bearer, error 400/401/429/503 dan contoh
  lengkap ada pada [panduan frontend](frontend-api.md#kontrak-autentikasi-http).
- Response token hanya dikirim sesudah commit; refresh reuse commit revokasi
  sebelum 401. Logout selalu 200 logged_out=true untuk token lolos schema.
- /me memeriksa sid/akun/tenant dan membaca RBAC terkini. Tidak ada cookie auth.
- Semua respons auth no-store. Limiter sementara 100 request/menit/IP per proses
  mengirim Retry-After; CORS tetap tersedia pada 429. OpenAPI auth memakai 400,
  tanpa 422 otomatis, serta schema respons yang terstruktur.
- JWT_SECRET acak disiapkan hanya di .env lokal yang diabaikan Git; restart proses
  lama untuk memuat konfigurasi. Tidak ada password akun manusia yang dibuat.
- Log operasional auth tanpa secret tersedia; tidak ada event bus baru. Audit
  persisten dan limiter Redis lintas worker tetap TODO.
- Verifikasi: suite 103 tes lulus; sesudah perbaikan urutan CORS, 20 tes API,
  readiness dan autentikasi dijalankan ulang dan lulus (104 kasus tersedia).

## 2026-09-11 - Penyimpanan dan rotasi refresh token

- Migrasi 0017 menambah auth_session dan refresh_token dengan hash, tanpa plaintext.
- SessionService menyediakan login internal, rotasi, deteksi reuse, logout keluarga
  dan resolver access yang memeriksa sid. Expiry keluarga tetap tujuh hari.
- Tidak ada endpoint HTTP/event baru. [Panduan sesi](refresh-sessions.md) menjelaskan
  hasil/error, commit revokasi, refresh bersamaan serta langkah integrasi frontend.
- Verifikasi: 99 tes lulus, migrasi/grant 0017 diterapkan pada fsos, Alembic check bersih.

## 2026-09-11 - Autentikasi akun melalui database

- AccountService memverifikasi username/password per tenant dan menghasilkan
  identitas serta snapshot RBAC aktif. Kegagalan kredensial memakai pesan seragam
  dan bcrypt dummy untuk akun tidak ditemukan atau hash tidak tersedia.
- resolve_access memvalidasi JWT dan akun/tenant terkini; permission operasi tetap
  diperiksa dari database. Password reset belum mencabut JWT lama secara otomatis.
- Kontrak input/hasil/error dan transaksi tersedia di [autentikasi](authentication.md).
  Belum ada endpoint login/refresh/logout, event atau respons HTTP baru.
- Verifikasi: suite 93 tes lulus; setelah empat kasus input baru, lima tes akun
  dijalankan ulang dan lulus. Ruff bersih.

## 2026-09-11 - Primitive password dan access JWT

- bcrypt cost 12, kebijakan panjang UTF-8, salt acak serta wrapper async tersedia.
- Codec access JWT 15 menit memvalidasi signature/algoritma, issuer/audience,
  tujuan token, claim wajib dan UUID. RBAC tetap perlu dibaca dari database.
- Belum ada endpoint login/refresh/logout atau bearer dependency. Tidak ada akun
  diberi password, perubahan secret lokal, kontrak HTTP atau event baru.
- [Panduan autentikasi](authentication.md) mencatat parameter, hasil, error dan
  pekerjaan integrasi yang masih diperlukan sebelum frontend dapat login.
- Verifikasi: 89 tes lulus, Ruff dan pip check bersih.

## 2026-09-11 - Daftar status efektif alarm dan sesi

- Service list_alarms/list_sessions menambahkan pagination, filter UUID publik
  perangkat, status efektif dan rentang waktu. Daftar/detail memakai proyeksi sama.
- Alarm dari snapshot impor atau bukti acknowledgment termasuk dalam filter
  acknowledged=True; sesi impor/ditutup melalui bukti termasuk is_open=False.
- [Input, hasil, permission dan error](telemetry-lifecycle.md#daftar-alarm-dan-sesi-service-internal)
  didokumentasikan sebagai kontrak internal. Belum ada endpoint/payload HTTP
  frontend atau event baru; integrasi browser menunggu autentikasi dan route.
- Verifikasi: 66 tes lulus dan Ruff bersih, termasuk kesesuaian daftar/detail
  serta akses dengan role database terbatas. Tidak ada migrasi baru.

## 2026-09-11 - Rekonsiliasi sumber digital asset

- Service internal dan CLI mendeteksi sumber hilang serta perbedaan proyeksi per
  tenant/type; scope actor/permission tetap diwajibkan dan hasil dipaginasi.
- Tidak ada endpoint, request/response HTTP, event atau channel subscribe baru.
  Frontend belum dapat mengambil laporan ini melalui API.
- Payload CLI, status temuan, cursor, error dan langkah tindak lanjut tersedia
  pada [panduan registry](asset-registry.md#rekonsiliasi-registry-laporan-tanpa-mutasi).
- Pemeriksaan tidak mengubah UUID/version atau menghapus bukti traceability.
- Verifikasi: 56 tes lulus; scan runtime FSOS_DEV atas 15 tipe menemukan enam
  registry sinkron. Health/readiness dan kontrak HTTP tetap diuji dalam suite.

## 2026-09-11 â€” Pemisahan koneksi API dan admin

- API/readiness/backfill memakai pool DATABASE_URL; migrasi, seed, provisioning
  serta maintenance memakai pool ADMIN_DATABASE_URL tanpa fallback ke runtime.
- Bootstrap lokal fsos_app menghasilkan secret tanpa mencetaknya, memverifikasi
  hak runtime, dan memperbarui konfigurasi lokal. Akun ini bukan login frontend.
- Tidak ada endpoint, payload, respons HTTP, atau event runtime baru.
  Proses backend yang sudah berjalan perlu restart agar konfigurasi baru terbaca.

## 2026-09-11 â€” Profil privilege runtime database

- Migrasi 0016 memperketat fungsi capture history aturan; grup fsos_runtime
  membatasi akses DML/DDL untuk service yang tersedia.
- Tidak ada endpoint, payload/respons HTTP, login frontend, atau event baru.
  NOLOGIN adalah atribut role PostgreSQL, bukan status akun aplikasi.
- Koneksi lokal belum dialihkan; pemisahan login/secret API dan maintenance
  tetap tahap berikutnya sebelum production.

## 2026-09-11 â€” Rolling maintenance partisi

- CLI check/ensure memeriksa batas UTC dan guard append-only; fsos disiapkan untuk
  enam bulan (24 partisi). Task development berjalan harian dan saat logon.
- Tidak ada endpoint, response/payload HTTP atau event baru. Readiness HTTP tidak
  berubah; hasil maintenance tersedia sebagai laporan administratif lokal.
- Retensi draft didokumentasikan, seluruh bukti tetap disimpan; arsip/penghapusan
  otomatis belum diimplementasikan. 21 tes terkait dan Alembic check lulus.

## 2026-09-11 â€” Status efektif dan finalisasi telemetry internal

- Service baru: get_alarm, get_session, acknowledge, close_session dengan permission
  Alarm.Read/Acknowledge dan DeviceSession.Read/Close. Belum diberikan oleh seed.
- Acknowledgment berulang mempertahankan bukti pertama; penutupan ulang dengan
  waktu berbeda ditolak. Parent telemetry tetap immutable.
- Tidak ada endpoint, payload HTTP, atau event runtime baru. Frontend menunggu
  API autentikasi dan schema respons; detail status efektif ada di telemetry-lifecycle.md.
- Verifikasi: 45 tes terkait lulus, termasuk permission, tenant, retry, konflik,
  validasi waktu dan rollback; tidak ada data telemetry baru pada fsos.

## 2026-09-11 â€” Seed development dan backfill lokal

- Tenant FSOS_DEV, actor pemeliharaan tanpa password, role/permission dan master
  contoh ditambahkan; registry sumber contoh sudah di-backfill.
- Tidak ada perubahan endpoint, payload, respons HTTP, maupun event runtime.
  Fixture belum tersedia lewat CRUD frontend dan actor seed bukan akun login.
- Verifikasi: 44 tes terkait lulus; seed dijalankan dua kali pada fsos,
  created berturut-turut 23 dan 0, dengan enam aset registry.

## 2026-09-11 â€” Adapter dan backfill registry

- Internal: 15 pemetaan sumber, sync tenant/type/entity, backfill per batch dengan
  permission AssetRegistry.Sync, dan integrasi otomatis KitchenRepository.
- Registry mempertahankan asset_uuid; sinkronisasi identik tidak menaikkan version.
- Tidak ada endpoint/payload HTTP atau event runtime baru. Tidak perlu perubahan
  frontend; identitas registry/sumber dijelaskan di asset-registry.md.
- Verifikasi mencakup seluruh adapter, izin, tenant/type salah, pengulangan,
  pagination, perubahan nama, soft delete dan rollback.

Catat perubahan API/event yang memengaruhi frontend pada setiap implementasi.
Setiap entri menyebut tanggal, endpoint/event, status, perubahan payload/respons,
dampak kompatibilitas, tindakan frontend, dan verifikasi.

## 2026-09-11 â€” Riwayat aturan dan validator DSL internal

- Migrasi 0015 menambahkan snapshot alarm/holding rule yang immutable.
- Validator DSL v1 tersedia untuk struktur condition/action; integrasi ke
  service simpan/aktivasi, evaluator, dan API masih belum tersedia.
- Kontrak frontend tidak berubah. Tidak ada endpoint atau event runtime baru.
- Tindakan frontend: gunakan dokumen rule-versioning untuk memahami rancangan;
  jangan memanggil route manajemen aturan sebelum statusnya menjadi aktif.

## 2026-09-11 â€” Service simpan/aktivasi aturan

- Service alarm/holding kini memvalidasi definisi sebelum menyimpan, memeriksa
  tenant/actor aktif serta permission Read/Write/Activate, dan menolak version lama.
- Alarm dibuat nonaktif, edit alarm aktif ditolak, enable memvalidasi ulang DSL.
  Penggantian definisi dan history berlangsung dalam transaksi yang sama.
- Kontrak HTTP belum berubah; belum ada route, payload HTTP, atau error mapping baru.
  Frontend tidak dapat memanggil service langsung. Autentikasi endpoint menunggu P2.
- Event catalog: tidak ada publisher baru. Enable hanya mengubah konfigurasi,
  belum menjalankan evaluator/aksi/notifikasi.
- Verifikasi PostgreSQL mencakup permission terpisah/dicabut, actor/tenant,
  konflik versi, input invalid, lifecycle, history dan rollback.

## 2026-09-11 â€” Dokumentasi awal, aplikasi 0.1.0

- Aktif: `GET /api/v1/health`, `GET /api/v1/ready`; keduanya tanpa request body.
- Dokumentasi mencakup envelope, header, CORS, respons 200/503, error bersama,
  tipe field, contoh Fetch, serta lokasi Swagger/ReDoc/OpenAPI.
- Event catalog membedakan schema penyimpanan yang tersedia dan event rencana
  yang belum diterbitkan. Tidak ada kontrak subscribe yang aktif.
- Dampak kompatibilitas: tidak mengubah endpoint atau perilaku runtime.
- Tindakan frontend: gunakan dua endpoint sistem sesuai kebutuhan; API bisnis,
  login, serta realtime menunggu implementasi dan pembaruan catalog.
- Verifikasi: contoh struktur respons dicocokkan dengan route, handler, probe,
  OpenAPI, dan pengujian API/readiness. Nilai waktu/UUID dalam contoh ilustratif.

## 2026-09-11 â€” Fondasi repository kitchen

- Internal: tenant/actor scope, audit, soft delete, serta optimistic concurrency
  menggunakan expected_version ditambahkan pada repository kitchen.
- Kontrak frontend: tidak ada endpoint/payload/respons baru atau perubahan HTTP.
  Belum ada pemetaan exception repository ke respons API bisnis.
- Event: tidak ada publisher baru; operasi repository belum menerbitkan event.
- Tindakan frontend: belum perlu perubahan. Form kitchen menunggu API berautentikasi.
- Verifikasi: tes PostgreSQL mencakup akses lintas tenant, actor/tenant tidak aktif,
  version lama, audit, soft delete, pembatasan field, pagination dan rollback.


## 2026-09-11 ? Putaway dan stok penerimaan

- Tiga endpoint batch baru: POST putaway, GET stock, GET stock-entries; permission
  Stock.Putaway/Read terpisah. Migrasi 0018 menambahkan ledger immutable.
- ACCEPTED belum menghasilkan saldo tersedia sampai putaway. Alokasi parsial,
  version batch, lokasi kitchen/storage, status dan expiry UTC diperiksa atomik.
- Frontend perlu memperbarui version batch dari respons/GET stock setelah putaway;
  retry stale menghasilkan 409. Version header receiving tidak berubah.
- Quantity decimal string; saldo per storage dan ketersediaan tidak mencakup
  reservasi/pemakaian produksi. Storage bereferensi ledger tidak dapat dihapus.
- Event stock.putaway internal serta movement STORAGE dicatat atomik; tidak ada
  publisher realtime. Kontrak lengkap pada bagian stok di frontend-api.md.


## 2026-09-11 ? Master menu dan resep

- Sepuluh operasi list/detail/create/replace/soft-delete food-items/recipes aktif;
  permission FoodItem/Recipe.Read, Write, Delete terpisah, tenant dan audit server.
- Resep satu baris per pasangan menu?bahan, quantity positif per satu unit hasil
  menu dan uom wajib sama dengan bahan. Parent aktif satu tenant; pasangan tetap.
- Unit menu immutable; PUT optional yang dihilangkan reset default. Gunakan
  expected_version pada PUT/body dan DELETE/query; stale 409, deleted/foreign 404.
- Menu bereferensi recipe/production_batch tidak dapat dihapus. Kode/pasangan
  terhapus tetap dicadangkan. Tidak ada event/registry/movement baru pada CRUD ini.
- Cakupan OpenAPI kini 88 operasi, termasuk 55 CRUD sebelas master. Produksi dan
  pemakaian stok tetap belum tersedia; lihat kontrak menu/resep untuk contoh lengkap.


## 2026-09-11 ? Transaksi produksi dan pengeluaran stok

- Enam endpoint production-batches aktif: create/list/detail/start/complete/cancel.
  Snapshot resep saat create, kebutuhan HALF_UP 6 desimal, hasil aktual 0..planned.
- Start memakai stok atomik sesuai snapshot, version produksi dan version batch bahan;
  parent aktif satu tenant/kitchen, expiry, UOM, quantity dan saldo diperiksa.
- GET stock menambah issued_quantity total/per storage dan available kini dikurangi
  pemakaian. Quantity storage dan putaway_quantity tetap historis; jangan memakai
  keduanya sebagai saldo tersisa. GET stock-issues baru dengan Stock.Read.
- Migration 0019 menambah snapshot/rencana/hasil, storage/version pada item produksi,
  constraint serta trigger immutable. Legacy tanpa snapshot tetap read-only melalui API.
- Event production.* internal, edge USED, movement ISSUE/PRODUCTION dan registry atomik;
  belum ada package/holding atau publikasi realtime. OpenAPI kini 95 operasi.


## 2026-09-11 ? Jenis kemasan, paket dan holding

- 13 operasi baru: 5 CRUD packaging-types, create/list/detail/resolve paket,
  allocation summary, holding start/update/finish. Total OpenAPI 108 operasi.
- Package quantity dibatasi hasil aktual produksi; expected_version create mengacu
  produksi, holding mengacu paket. Discard tidak membebaskan alokasi.
- Snapshot produksi v1 menambah nullable food_category/holding_limit_minutes;
  policy dibekukan saat pengemasan pertama dan clock berawal dari cooking finished.
- Frontend gunakan effective_status/timer_status/holding_eligible, bukan status
  tersimpan saja. Release tidak menghentikan countdown. QR payload hanya identitas;
  rendering QR pada client, resolve tetap membutuhkan bearer.
- Migrasi 0020 dan grant minimum; package/holding events serta holding_log atomik.
  Tidak ada background expiry notification, scheduler, telemetry adjustment atau
  auto discard; GET live dan POST update materialisasi tersedia.


## 2026-09-11 ? Manifest dan perjalanan pengiriman

- Enam endpoint deliveries create/list/detail/depart/complete/cancel; permission
  independen. Total OpenAPI kini 114 operasi, migrasi 0021 menambah origin/ETA dan
  proteksi manifest immutable.
- Create mencadangkan driver/kendaraan/paket; package ALLOCATED, depart IN_TRANSIT,
  complete DELIVERED. Expected_version item create mengacu paket, aksi mengacu delivery.
- Depart memeriksa ulang timer dan ETA sebelum expiry. Complete tetap mencatat
  kedatangan expired/terlambat; tidak otomatis membuat penerimaan sekolah.
- Aksi holding paket yang dikelola pengiriman kini 409; GET/QR tetap live. Cancel
  CREATED melepas paket ke RELEASED/EXPIRED, tidak mereset timer atau menghapus sejarah.
- Registry, edge LOADED/DELIVERED, movement dan delivery.* internal atomik; GPS,
  routing/per-stop proof, acceptance sekolah dan publisher realtime belum tersedia.


## 2026-09-11 ? Penerimaan sekolah dan konsumsi

- Enam endpoint create/list/detail school-receivings dan consumptions aktif;
  total OpenAPI 120 operasi. Permission SchoolReceiving.Read/Write dan
  Consumption.Read/Write, bearer/tenant, expected_version paket dan pagination.
- Inspeksi manifest yang selesai, quantity expected/received/discrepancy,
  condition, accepted, temperature/photo/notes; shortage atau rejection wajib alasan.
  Acceptance memerlukan GOOD dan holding SAFE/WARNING; paket RECEIVED/REJECTED.
- Finalisasi consumed+discarded=received dengan snapshot holding; konsumsi setelah
  deadline boleh dicatat sebagai kejadian dengan safe=false dan notes wajib.
  safe=null untuk semua dibuang, bukan jaminan keamanan makanan. Paket terminal
  CONSUMED/DISCARDED; GET effective_status terminal tidak ditimpa expiry.
- Event school_receiving.recorded/consumption.recorded, registry, relationships
  dan movements atomik; bukti immutable. Tidak ada edit/delete/backdated/automatic alarm.
- Migrasi 0022 menambah kolom nullable untuk legacy tanpa backfill, constraints dan
  immutable triggers. Frontend reload package version setelah transaksi; gunakan
  daftar bukti berfilter package_id sebelum retry. Foto hanya referensi, bukan upload.


## 2026-09-11 ? Sinkronisasi dokumentasi operasional

README/indeks backend kini merangkum 120 operasi dan dua belas master. Panduan
database/koneksi/runtime diselaraskan ke head 0022; permission supply diperluas
pada dokumentasi menjadi 18 kode dan transaksi menjadi 26 kode. Status registry,
penerimaan sekolah, konsumsi, stok dan pengiriman diperbarui; artefak NUL README
dibersihkan. Ini pembaruan dokumentasi, tanpa perubahan endpoint/payload/event.












