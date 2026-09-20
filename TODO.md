# TODO â€” Food Safety Operating System

Checklist instalasi dan roadmap berdasarkan docs/01â€“18. Tanggal awal: 2026-09-11.
`[x]` berarti telah tersedia dan diperiksa; `[ ]` berarti belum selesai.
Paket yang terpasang tidak berarti fitur bisnis sudah diimplementasikan.

## Prioritas kerja aktif - modul bisnis lebih dahulu

Arahan pengguna: dahulukan seluruh modul utama proses bisnis sebelum pekerjaan
terpisah untuk perluasan tes, deployment production, seeding tambahan, dan
penyempurnaan infrastruktur. Urutan di bagian ini mengesampingkan urutan label
P0-P5 di bawah; bagian lama tetap menjadi inventaris dan riwayat penyelesaian.
Schema yang tersedia belum berarti alur bisnis atau endpoint selesai.

Urutan implementasi berdasarkan dependensi alur operasional:

1. [x] **Master data operasional.** API kitchen, storage/zone, supplier, bahan baku,
   menu/food item, recipe, packaging type, school, vehicle dan driver; device/binding
   yang diperlukan untuk mengaitkan pemantauan ke lokasi/perangkat. Master produksi
   dan pengiriman tersedia pada tahap transaksi terkait.
2. [x] **Penerimaan bahan dan stok.** Receiving, item penerimaan, batch bahan,
   validasi pemasok/lokasi/kuantitas serta pencatatan pergerakan dan ketersediaan
   bahan sesuai desain. Selesaikan alur transaksi yang bisa dipakai melalui API.
3. [x] **Produksi.** Batch produksi, pemakaian bahan/resep, hasil produksi,
   transisi status dan hubungan batch bahan dengan hasil produksi.
4. [x] **Pengemasan dan holding.** Paket, jenis kemasan, identitas/QR, alokasi hasil
   produksi serta lifecycle holding start/update/finish/expired dan status kelayakan.
5. [x] **Pengiriman.** Manifest/alokasi paket, kendaraan/driver/tujuan sekolah,
   keberangkatan, perjalanan dan penyelesaian pengiriman beserta movement.
6. [x] **Penerimaan sekolah dan konsumsi.** Verifikasi paket/manifest, hasil penerimaan,
   kondisi/selisih serta pencatatan konsumsi dan status akhir paket.
7. [ ] **Keluhan, investigasi dan recall.** Complaint, penelusuran batch/paket terdampak,
   pembuatan/pelaksanaan/penyelesaian recall dan tindak lanjut sesuai desain.
8. [ ] **Lengkapi modul pendukung bisnis utama.** Pemantauan device/storage/fleet,
   ingestion telemetry, evaluasi rule/alarm, notifikasi operasional dan ringkasan
   dashboard untuk alur di atas. Konfigurasi rule dan API bukti yang sudah tersedia
   tidak menggantikan implementasi engine.

Traceability, registry/relationship/movement dan pencatatan event bisnis dikerjakan
bersama transaksi yang menghasilkannya. Traversal backward/forward, timeline,
passport dan impact analysis kini tersedia read-only untuk investigasi/recall. Engine holding
serta validasi rule/action dikerjakan pada tahap bisnis yang membutuhkannya;
jangan menunggu deployment untuk menyelesaikan logika bisnis.

Catatan frontend 2026-09-16: halaman Raw Material Receiving dan Production Batch
mulai diselaraskan dengan desain FSOS. Production Batch sudah menyediakan
list/filter, create manufacturing order/cooking batch, detail bahan, cancel
`CREATED`, dan complete `RUNNING` dengan jumlah aktual serta suhu inti awal.
Update frontend lanjutan: aksi Mulai produksi sudah tersedia untuk batch
`CREATED` dengan input hasil scan/manual `raw_material_batch_id`, `storage_id`,
`expected_version` bahan, dan `quantity`, lalu memanggil endpoint start agar stok
dikurangi atomik dan batch menjadi `RUNNING`. Cek stok bahan di modal Mulai produksi sudah memakai `GET /raw-material-batches/{id}/stock` untuk mengisi version, storage available, dan default quantity sebelum start. Prioritas UI berikutnya: lanjut delivery/school receiving yang belum sekaya desain awal.


Catatan frontend delivery 2026-09-16: halaman Delivery sudah menyediakan create manifest, detail paket, depart/loading armada dengan ETA opsional, complete perjalanan, cancel manifest CREATED, filter status/armada, dan tautan tracking. Ini menutup sebagian desain point 9, 11, dan 12. Prioritas UI berikutnya: penerimaan sekolah point 13 dengan scan paket, suhu manual, kondisi/foto, dan accepted/received quantity.

Catatan frontend school receiving 2026-09-16: halaman scan Penerimaan Sekolah sudah menyediakan resolve QR paket, form receipt dengan delivery_id, school, version paket, received_quantity, condition GOOD/DAMAGED/MISSING, accepted/rejected, suhu manual, referensi foto dan notes. Ini menutup desain point 13 secara operasional. Package delivery-context sudah tersedia untuk auto-fill delivery_id dan school setelah scan paket. Finalisasi consumed-discarded sudah tersedia pada scan Penerimaan Sekolah memakai endpoint consumptions. Prioritas berikutnya: build/test integrasi frontend-backend dan memperhalus UX picker/scan agar input UUID manual makin berkurang.

Catatan frontend/master 2026-09-20: relasi pemasok-bahan kini menampilkan nama
pemasok dan nama bahan baku pada tabel. UUID tetap dipakai untuk request dan
identitas sistem, bukan sebagai label yang harus dihafalkan pengguna.

Ketentuan pelaksanaan:

- Selesaikan alur modul secara utuh: operasi API, aturan/transisi bisnis, transaksi,
  isolasi tenant, permission, audit/version serta integrasi data yang diperlukan.
- Dokumentasi frontend tetap wajib bersamaan dengan fitur: endpoint, payload,
  respons, error, auth, pagination dan efek samping; event catalog/changelog juga
  diperbarui sesuai perubahan. Jangan menyatakan fitur aktif hanya karena tabel ada.
- Pemeriksaan terarah yang diperlukan untuk kebenaran fitur tetap bagian implementasi.
  Tunda proyek perluasan cakupan tes, stress/load, CI dan pengulangan suite luas
  yang tidak diperlukan oleh perubahan yang sedang dikerjakan.
- Tunda seeding/demo tambahan, bootstrap/provisioning umum, hardening dan deployment
  production, backup/restore serta penyempurnaan scheduler/monitoring. Kerjakan hanya
  dependensi minimum jika suatu modul tidak dapat berjalan tanpanya, lalu kembali
  ke alur bisnis; jangan menjadikannya fokus giliran berikutnya.
- Redis/Mosquitto tetap mengikuti keputusan integrasi/deployment; pemasangan layanan
  tidak mendahului pekerjaan modul bisnis yang bisa diselesaikan tanpa layanan itu.
- Integrasi eksternal ERP, AI/analytics lanjutan dan penyempurnaan visual/realtime
  mengikuti kebutuhan setelah alur bisnis utama tersedia.

- [x] API master kitchen/storage/zone: 15 operasi list/detail/create/replace/delete,
  tenant dan permission terpisah, expected_version, parent aktif, koordinat/suhu,
  audit serta sync registry kitchen/storage atomik. Soft delete tanpa cascade; induk tetap.
- [x] Dokumentasi frontend dan event diperbarui; tujuh pemeriksaan terarah lulus,
  dua tes HTTP diulang setelah menambah kasus tenant lain. Akses minimum lokal tersedia.

- [x] API supplier/bahan baku/relasi pemasok-bahan: 15 operasi list/detail/create/replace/delete,
  permission per modul, version, referensi aktif satu tenant, banyak pemasok per bahan,
  validasi suhu/durasi/email, uom tetap dan registry supplier/material atomik.
- [x] Kontrak frontend/event/changelog diperbarui; delapan pemeriksaan terarah lulus,
  akses minimum lokal tersedia tanpa seeding bisnis atau migrasi baru.

- [x] Lengkapi CRUD keenam master dengan DELETE soft delete, permission Delete
  terpisah, expected_version query, proteksi referensi nondeleted dan registry atomik.
  Tanpa cascade/hard delete/restore; kode dan pasangan lama tetap dicadangkan.
- [x] Sepuluh pemeriksaan terarah lulus; dokumentasi seluruh kontrak DELETE,
  event catalog, changelog dan grant minimum lokal diperbarui.

### Sisa CRUD master utama yang belum dibuat

Status dipisahkan dari migrasi/schema; tanda selesai hanya untuk API yang tersedia.
Matriks terverifikasi ada di [cakupan frontend](backend/docs/frontend-api.md#cakupan-crud-dan-status-modul).

- [x] CRUD sekolah (school): list/detail/create/replace/soft delete, kitchen aktif
  satu tenant dan tidak dapat dipindahkan, koordinat/jumlah siswa, permission School.*,
  version, registry atomik serta proteksi delivery_item/school_receiving/complaint.
  Transaksi school receiving tersedia pada tahap penerimaan sekolah di bawah. Dokumentasi dan akses minimum lokal diperbarui.
- [x] CRUD kendaraan (vehicle) dan driver: 10 operasi, permission terpisah,
  optional driver/GPS aktif satu tenant, koordinat/kapasitas, version dan soft delete.
  Registry VEHICLE atomik; riwayat delivery/GPS melindungi penghapusan. Dokumentasi
  frontend dan akses minimum lokal tersedia; 12 pemeriksaan terkait lulus.
- [x] CRUD menu/food item dan recipe: 10 operasi, permission Read/Write/Delete,
  quantity per unit hasil, uom sama dengan bahan, parent aktif satu tenant,
  pair/uom menu tetap, version dan soft delete terlindungi referensi produksi.
  Kontrak frontend/event/changelog diperbarui; enam tes terkait lulus.
  Akses minimum runtime/development tersedia tanpa migrasi atau seeding bisnis.
- [x] CRUD jenis kemasan: 5 operasi, volume milliliter, tenant/permission/version,
  soft delete terlindungi paket dan kode tetap dicadangkan.
- [x] CRUD master device dan binding device/vehicle: list/detail/create/replace/soft delete aktif (`Device.Read/Write/Delete`), zone_id opsional dengan validasi storage zone aktif; binding memerlukan device aktif bertipe GPS dan vehicle aktif satu tenant.
- [ ] API pengelolaan tenant/user/role/permission bila diperlukan alur bisnis;
  endpoint autentikasi dan CLI provisioning tidak menyelesaikan CRUD administrasi.

- [x] Transaksi receiving: create header + item/batch atomik, list/detail,
  complete seluruh keputusan inspeksi dan cancel CREATED; validasi parent aktif,
  relasi pemasok-bahan, quantity/uom, expired date, tenant/permission/version.
- [x] Bukti inspeksi bahan baku saat receiving: item penerimaan menyimpan suhu
  manual, kondisi visual dan referensi foto kondisi bahan; kode batch/QR tetap
  disiapkan untuk render/print di frontend.
- [x] List batch bahan mendukung pencarian kode/nama bahan atau kode batch, filter
  kategori bahan, serta urutan FIFO/FEFO untuk prioritas pemakaian.
- [x] Registry receiving/batch, SUPPLIED/RECEIVED, movement RECEIVING untuk accepted,
  event created/completed/cancelled internal dalam transaksi yang sama; baca batch.
- [x] Kontrak 7 endpoint baru, contoh payload/response, event catalog/changelog dan
  hak minimum runtime/development diperbarui tanpa migrasi atau data bisnis lokal.
  Sepuluh pemeriksaan terkait lulus; Ruff dan contoh OpenAPI/JSON diperiksa.
- [x] Stok penerimaan: putaway parsial ke storage satu kitchen, ledger append-only,
  saldo batch/per storage dan available quantity yang memperhitungkan expiry/status.
  Version batch mencegah alokasi ganda; validasi quantity, tipe storage dan permission
  Stock.Read/Putaway. Registry, movement STORAGE dan event stock.putaway atomik.
- [x] Penempatan bahan ke slot/rak: putaway menerima `zone_id` opsional, memvalidasi
  zone milik storage yang dipilih, dan menyimpan lokasi rak pada ledger immutable.
- [x] Pengeluaran bahan manual/scan dari penyimpanan: endpoint manual stock issue
  mencatat tanggal pengeluaran, storage/zone, quantity, reason/reference, movement
  ISSUE dan event internal; saldo available serta start produksi mengurangi issue ini.
- [x] Migrasi 0018 dan akses minimum runtime/development diterapkan lokal; kontrak
  frontend/event/changelog diperbarui. Empat tes HTTP/regresi terkait lulus;
  dua tes receiving diulang setelah kasus expiry, lintas tenant dan permission ditambah.
  Ruff dan Alembic check bersih. Pemakaian produksi tersedia pada tahap berikut di bawah; reservasi, transfer dan
  adjustment stok belum tersedia.

- [x] Produksi: create/list/detail/start/complete/cancel, snapshot resep dan kebutuhan
  per hasil rencana, pengeluaran stok atomik, quantity hasil aktual, tenant/permission,
  version produksi/bahan, edge USED dan movement ISSUE/PRODUCTION beserta event internal.
- [x] Selesai masak mencatat suhu makanan awal manual melalui `initial_temperature`
  pada complete produksi; holding time tetap mulai dari finished_at saat packaging.
- [x] Migrasi 0019, grant minimum runtime/development, GET stock-issues dan saldo
  issued/available terintegrasi. Tes HTTP produksi, receiving/stok dan master menu
  lulus; lint dan contoh kontrak diperiksa, upgrade/downgrade/upgrade uji bersih.
  Legacy tanpa snapshot tidak dapat dieksekusi; reservasi/reversal stok belum tersedia.
  Holding sudah tersedia pada tahap pengemasan berikut.

- [x] Pengemasan: alokasi hasil aktual dengan version produksi, paket/nomor unik,
  identitas QR + resolve bearer, registry/edge PACKAGED/movement dan event atomik.
- [x] Mulai pengemasan mencatat suhu awal manual per kemasan melalui
  `initial_temperature`; waktu awal pengemasan memakai created_at/movement PACKAGING
  dan QR payload tetap dirender/print frontend.
- [x] Holding start/update/finish dengan policy frozen, anchor cooking finish,
  timer live SAFE/WARNING/EXPIRED/DISCARD_RECOMMENDED, release/discard dan log immutable.
  Release tidak menghentikan deadline; discard tidak membebaskan hasil. Migrasi 0020
  dan akses minimum lokal diterapkan; kontrak frontend/event/changelog diperbarui.
  Delapan tes terkait lulus; enam tes packaging diulang setelah kasus frozen rule
  dan delete master ditambah. Scheduler expiry, alarm/notification, telemetry adjustment
  dan cetak label QR belum tersedia (QR payload sudah dapat dirender frontend).

- [x] Manifest/pengiriman: create/list/detail/depart/complete/cancel, reservasi
  paket/vehicle/driver, origin dan sekolah satu kitchen, validasi holding+ETA saat
  depart, arrival terpisah dari acceptance sekolah, cancel hanya CREATED.
- [x] Estimasi delivery saat scan/alokasi kemasan: create delivery menghitung jarak,
  durasi dan ETA sederhana dari koordinat kitchen ke sekolah; depart bisa memakai
  ETA otomatis bila frontend tidak mengirim override.
- [x] Ringkasan kemasan terkirim berdasarkan armada dan tujuan: endpoint Delivery.Read
  read-only mengagregasi delivery_count, package_count dan total_quantity per vehicle
  atau per school tujuan.
- [x] Tracking delivery read-only: endpoint mengambil GPS terakhir armada, suhu
  terakhir device terkait, serta menghitung sisa jarak/waktu sederhana ke tujuan
  terjauh. MQTT ingestion/live push dan geofence tetap pekerjaan pendukung berikutnya.
- [x] HTTP ingestion awal telemetry GPS/suhu: endpoint Telemetry.Ingest append-only
  mengisi gps_log dan temperature_log untuk tracking/dashboard. MQTT broker,
  API key device, deduplikasi payload dan WebSocket tetap belum selesai.
- [x] Sediakan `GET /api/v1/mqtt/events` read-only untuk discovery pesan MQTT yang
  sudah tersimpan di `mqtt_message_log`, dengan isolasi tenant, Device.Read,
  filter topic/processed/waktu dan pagination. Endpoint ini belum mengaktifkan
  consumer broker, live topic discovery, pembuatan Device atau binding otomatis.
- [x] Sediakan `GET /api/v1/mqtt/topics` read-only untuk daftar topic unik,
  jumlah event, waktu terakhir dan pagination sebagai langkah awal UI discovery.
- [x] Binding sensor makanan ke production batch/holding: `food_sensor_binding`,
  pilihan `food_sensor_device_uuid` saat complete production, `device_uuid` saat
  start holding, dan telemetry temperature yang wajib cocok dengan binding aktif.
  Frontend menyediakan pilihan sensor pada complete production dan start holding;
  MQTT consumer live opt-in tersedia dengan selector `mqtt_event`/`mqtt_sensor`,
  parsing payload `fsos/#`, dan penulisan `mqtt_message_log`, `gps_log` serta
  `temperature_log`. Deduplikasi broker dan event transport publik masih belum
  tersedia.
- [x] Monitor suhu storage dashboard: `GET /dashboard/storage-temperatures`
  menampilkan storage aktif, sampel suhu terakhir, batas min/max dan status
  OK/LOW/HIGH/UNSUPPORTED_UNIT/NO_DATA untuk kebutuhan dashboard. Grafik histori,
  WebSocket dan alarm otomatis masih TODO.
- [x] Status/version paket terintegrasi; holding tidak menimpa paket yang sudah
  dikelola pengiriman. Registry, edge LOADED/DELIVERED, movement dan event atomik.
  Migrasi 0021 dan akses minimum lokal diterapkan; dokumentasi diperbarui. Delapan
  tes terkait lulus; tes delivery diulang setelah isolasi tenant/rollback/immutability
  ditambah. GPS, route/per-stop arrival dan validasi capacity bersatuan belum tersedia.

- [x] Penerimaan sekolah: create/list/detail, verifikasi manifest COMPLETED, kondisi,
  jumlah/selisih, keputusan dan bukti, version paket, tenant/permission; acceptance
  GOOD + holding belum habis, rejection/shortage wajib alasan. Paket RECEIVED/REJECTED.
- [x] Konsumsi/finalisasi: jumlah dikonsumsi+dibuang sama dengan diterima, holding
  snapshot, unsafe holding dicatat dengan alasan, CONSUMED/DISCARDED. Bukti immutable,
  registry/edge/movement/event atomik; effective_status terminal tidak ditimpa expiry.
  Migrasi 0022 dan grant minimum runtime/development diterapkan lokal; 12 pemeriksaan
  terkait lulus, 3 diulang setelah kasus rollback event ditambah. Ruff, contoh JSON
  dan Alembic check bersih; upgrade/downgrade/upgrade database uji lulus.
  Enam endpoint beserta dokumentasi frontend/event/changelog tersedia. Koreksi bukti,
  backdated/partial reporting dan alarm otomatis belum tersedia.
- [x] Complaint intake: create/list/detail immutable (`Complaint.Write/Read`),
  validasi package dan school satu tenant, school aktif, manifest noncancelled,
  registry COMPLAINT, edge REPORTED, movement COMPLAINT dan event internal atomik.
  Kontrak frontend/event/changelog serta permission helper diperbarui.
- [x] Complaint incident report: intake mendukung scan `package_code` dan foto
  bukti operasional; endpoint report/list report menyatukan package, batch
  produksi, lokasi/delivery/receipt sekolah, konsumsi, bahan baku, expiry bahan,
  suhu receiving, manual issue bahan dan traceability movement. Recall otomatis
  dan update/delete complaint belum tersedia.
- [x] Recall dasar: start/list/detail/close (`Recall.Execute/Read`) untuk production
  batch satu tenant, snapshot package terdampak, registry RECALL, edge RECALLED,
  movement RECALL per package dan event `recall.started/completed` internal atomik.
  Eksekusi recall menandai package nonterminal menjadi RECALLED serta menulis
  edge/movement/event `recall.executed`. Penarikan fisik dan notification outbox
  sudah menyusul; provider eksternal dan verifikasi otomatis masih TODO.
- [x] Bukti penarikan fisik recall: endpoint append-only create/list withdrawal
  mencatat evidence_code, package opsional, quantity/uom, kondisi, foto dan waktu
  penarikan; menulis movement/event `recall.withdrawal_recorded` serta menaikkan
  version recall. Notifikasi dan verifikasi otomatis masih TODO.
- [x] Notification outbox operasional: event recall otomatis membuat item
  `DASHBOARD` PENDING; endpoint list/mark-sent/mark-failed tersedia dengan
  permission Notification.Read/Dispatch. Provider email/WhatsApp, retry worker dan
  subscription realtime masih TODO.
- [x] Dashboard notification outbox: `GET /dashboard/notifications` menampilkan
  jumlah PENDING/SENT/FAILED/CANCELLED dan pending per channel untuk monitoring
  operasional recall/notifikasi.
- [x] Seed demo frontend end-to-end: `backend/scripts/seed_demo_ready.py` membuat
  tenant/user login demo, permission lengkap, master, workflow 14 tahap, IoT
  sample, complaint report, recall withdrawal dan notification outbox untuk
  implementasi frontend/integration test development. Data demo dilarang untuk
  production.
- [x] Wrapper migration eksplisit: `backend/scripts/migrate_with_status.py`
  membungkus Alembic upgrade agar operator melihat output JSON before/after,
  returncode dan status.
- [x] Login frontend dipermudah: `POST /auth/login` menerima `tenant` berupa
  tenant_code seperti FSOS_DEMO atau UUID; `tenant_id` legacy tetap diterima.
- [x] Traceability read: detail asset, relasi langsung, timeline movement dan traversal
  forward/backward terbatas (`Traceability.Read`) untuk investigasi package/batch/
  complaint/recall. Passport asset dan impact downstream berbasis traversal forward
  tersedia read-only. Repair registry, replay event, bukti penarikan fisik dan
  notifikasi recall belum tersedia.
- [x] Dashboard read: `GET /dashboard/home`, `/storage`, `/storage-temperatures`,
  `/fleet`, `/holding` dan `/recall` (`Dashboard.Read`) menyediakan counter tenant
  dan suhu storage terakhir read-only untuk ringkasan operasional per domain.
  Realtime, cache materialized, SLA alarm dan analytics dashboard belum tersedia.

- [x] Sinkronisasi dokumentasi: README/indeks backend, schema dan runtime head 0029,
  permission master/transaksi, registry serta status frontend/TODO. Hapus artefak
  NUL README; verifikasi daftar operasi OpenAPI, permission dan tautan lokal.

**Pekerjaan berikutnya: notifikasi operasional, bukti penarikan fisik recall dan
dashboard/ringkasan bisnis.**

## P0 â€” Fondasi instalasi FastAPI

- [x] Perbaiki dan verifikasi venv Python 3.11 beserta pip.
- [x] Baca kebutuhan stack, struktur, framework, keamanan, API, dan deployment.
- [x] Buat folder backend sesuai docs/03 dan titik masuk FastAPI.
- [x] Siapkan requirements development dan production Linux.
- [x] Selesaikan instalasi dependensi dan simpan versi aktual untuk Windows Python 3.11.
- [x] Siapkan `.env.example`, `.env` lokal, dan `.gitignore`.
- [x] Siapkan SQLAlchemy async session dan konfigurasi Alembic (belum schema).
- [x] Siapkan endpoint `/api/v1/health`, Swagger, ReDoc, dan OpenAPI.
- [x] Terapkan envelope API docs/16, request ID, error handler, dan CORS.
- [x] Batasi CORS backend hanya untuk ENVIRONMENT development/testing; production ditangani NGINX/reverse proxy.
- [x] Siapkan JSON logging console.
- [x] Verifikasi pip check, tes API, lint, dan startup server HTTP.
- [x] Tulis panduan menjalankan aplikasi pada Windows di README.

- [x] Frontend raw material receiving form: supplier, dapur, tanggal, bahan, batch, qty, suhu, expired date, kondisi, foto dan QR; submit create+complete agar batch ACCEPTED siap print QR.
- [x] Perbaiki response `GET /production-batches` untuk data demo/legacy:
  `recipe_snapshot` pendek dinormalisasi agar list batch produksi tidak 500;
  seed demo baru menyimpan snapshot resep lengkap.
## P1 â€” Layanan dan database (docs/04, 06â€“08, 18)

- [x] Verifikasi PostgreSQL 18 yang sudah berjalan serta database/user yang disediakan pengguna.
- [x] Siapkan extension PostGIS dan pgcrypto melalui proses provisioning/migrasi.
- [x] Isi DATABASE_URL lokal dan uji koneksi async.
- [x] Buat ORM dan migrasi awal tenant/kitchen dengan UUID, kolom audit, dan lokasi PostGIS.
- [x] Terapkan revisi `20260911_0001` ke database lokal `fsos`; Alembic check tanpa perbedaan.
- [x] Buat ORM storage, storage_zone, dan device beserta migrasi `20260911_0002`;
  terapkan pada fsos dan verifikasi Alembic check.
- [x] Uji relasi tenant pada storage/zone/device, rentang suhu, UUID device unik,
  registrasi tanpa zone, serta downgrade tahap kedua yang mempertahankan tenant/kitchen.
- [x] Buat ORM vehicle, driver, dan school; terapkan migrasi `20260911_0003`
  pada fsos dan verifikasi Alembic check tanpa perbedaan.
- [x] Uji relasi vehicleâ€“driver/GPS dan schoolâ€“kitchen dalam tenant yang sama,
  kode/plat unik per tenant, lokasi sekolah, kapasitas/jumlah siswa nonnegatif,
  serta rollback tahap ketiga yang mempertahankan master data sebelumnya.
- [x] Buat supplier, raw_material, food_item, recipe, dan relasi supplier_material;
  terapkan migrasi `20260911_0004` pada fsos, Alembic check tanpa perbedaan.
- [x] Uji kode master unik per tenant, relasi resep/pemasok dalam tenant yang sama,
  beberapa pemasok per bahan, kuantitas desimal positif, satuan wajib, batas suhu/waktu,
  penolakan penghapusan master yang direferensikan, dan rollback tahap keempat.
- [x] Buat packaging_type, alarm_rule, holding_rule dan terapkan `20260911_0005`
  ke fsos; verifikasi Alembic check tanpa perbedaan.
- [x] Uji kode/kategori unik per tenant, FK tenant, volume valid, prioritas alarm,
  bentuk JSON condition/action, alarm default nonaktif, batas waktu holding,
  dan rollback tahap kelima yang mempertahankan resep serta pemasok.
- [x] Buat app_user, role, permission, user_role, role_permission pada modul authentication;
  terapkan migrasi `20260911_0006` dan verifikasi Alembic check tanpa perbedaan.
- [x] Uji username/email unik tanpa membedakan case/spasi tepi per tenant,
  FK tenant, relasi RBAC lintas tenant, pasangan duplikat, status awal akun,
  penghapusan master yang direferensikan, dan rollback tahap keenam.
- [x] Lengkapi history revisi aturan immutable dan validasi DSL condition/action
  sebelum menyediakan perubahan/aktivasi aturan melalui API.
  **Selesai pada jalur service internal:** history, DSL v1, validasi holding,
  permission database dan version terintegrasi. Endpoint/JWT serta evaluator
  tetap dilacak terpisah; bukan klaim API manajemen aturan sudah tersedia.
- [x] Terapkan `20260911_0015`: snapshot awal aturan lama, pencatatan revisi atomik,
  version bertambah, identitas tetap, dan penolakan mutasi/penghapusan history.
- [x] Implementasikan validator DSL v1 dengan allowlist field/operator/action,
  batas kompleksitas, dan penolakan input tidak valid; grammar didokumentasikan.
- [x] Verifikasi 42 tes (API, readiness, repository, DSL, migrasi/constraint),
  termasuk rollback history bersama transaksi dan downgrade yang mempertahankan aturan.
- [x] Hubungkan validator DSL ke service aturan dengan scope tenant/actor,
  permission Read/Write/Activate, expected_version, audit dan history atomik.
- [x] Uji service aturan pada PostgreSQL: permission terpisah/dicabut, actor/tenant
  nonaktif, referensi lintas tenant, payload invalid, lifecycle, version dan rollback.
- [x] Hubungkan endpoint holding rule list/create/detail/replace/history ke
  autentikasi bearer dan HoldingRule.Read/Write; seed role development sudah tersedia.
- [x] Uji 37 tes API/service/DSL/auth terkait: scope tenant, izin terpisah/dicabut,
  kategori/version conflict, validasi angka, history dan normalisasi timestamp UTC.
- [x] Lengkapi enam endpoint alarm rule: list/create/detail/replace/history dan
  aktivasi/nonaktif; bearer session, permission Read/Write/Activate terpisah,
  DSL v1, expected_version dan history atomik, respons UTC/no-store.
- [x] Verifikasi 39 tes terkait dan Ruff; dua tes HTTP alarm diperluas dan lulus
  ulang untuk legacy invalid, pencabutan izin dan Activate tanpa Read/Write.
  Kontrak frontend, event catalog, changelog dan panduan rule diperbarui.
- [ ] Lengkapi validasi semantik executor (template/target/transisi) sebelum
  menjalankan action; konfigurasi enabled belum menjalankan engine alarm.
- [x] Uji upgrade/downgrade/upgrade pada database uji terpisah; periksa FK tenant,
  kode kitchen unik per tenant, koordinat, dan pelestarian extension saat downgrade.
- [x] Terapkan role aplikasi terbatas pada development: login fsos_app dengan
  grup NOLOGIN fsos_runtime; DATABASE_URL runtime dipisah dari ADMIN_DATABASE_URL
  untuk migrasi, seed dan maintenance. Secret acak disimpan hanya di konfigurasi lokal.
- [x] Verifikasi 55 tes, pool terpisah tanpa fallback admin, bootstrap berulang,
  readiness 200, backfill runtime, Alembic check dan task partisi admin berhasil.
- [ ] Siapkan isolasi secret production, owner migrasi khusus tanpa superuser,
  rotasi credential serta pengujian TLS/deployment. File .env development masih
  menyimpan kedua koneksi; proses API production hanya boleh menerima secret runtime.
- [x] Terapkan migrasi `20260911_0016` untuk capture history aturan SECURITY DEFINER
  dengan target tetap/search_path terbatas, tanpa INSERT history langsung untuk runtime.
- [x] Uji runtime role pada database terpisah: service kitchen/registry/aturan berjalan;
  DDL, TEMP, hard delete, perubahan grant, disable trigger dan maintenance ditolak.
  Seluruh 53 tes lulus; Ruff dan Alembic check bersih.
- [x] Buat ORM dan migrasi master data: tenant, kitchen, storage/zone, device,
  vehicle/driver, school, supplier, material, food item, recipe, packaging,
  alarm/holding rule, user/role/permission (docs/06).
- [x] Buat migrasi digital asset, asset relationship, movement, operational
  event, produksi, paket, pengiriman, receiving, complaint, dan recall (docs/07).
  **Status: schema selesai.** Receiving hingga recall melalui revisi 0007â€“0010;
  digital asset/relationship/movement melalui 0011; operational event melalui 0012.
  Implementasi API/engine/publisher tetap dilacak terpisah di bawah.
- [x] Buat dan uji migrasi operational event/event_log (`20260911_0012`, docs/08
  bagian 14); terapkan pada fsos dan verifikasi Alembic check tanpa perbedaan.
- [x] Uji event UUID unik, tenant/payload, perlindungan UPDATE/DELETE/TRUNCATE,
  dan rollback event_log yang mempertahankan graph/movement.
- [x] Tahap penerimaan: receiving, raw_material_batch, receiving_item melalui
  `20260911_0007`; terapkan pada fsos dan verifikasi Alembic check.
- [x] Uji konsistensi header/supplier/batch, referensi tenant/operator/material,
  duplikasi batch/item, quantity, serta rollback yang mempertahankan master dan user.
- [x] Tahap produksi: production_batch, production_item, package melalui
  `20260911_0008`; terapkan pada fsos dan verifikasi Alembic check.
- [x] Uji relasi kitchen/menu/bahan/kemasan dalam tenant, jumlah bahan positif,
  kode/nomor paket unik, waktu produksi/holding, snapshot remaining negatif,
  serta rollback yang mempertahankan penerimaan bahan.
- [x] Tahap pengiriman: delivery, delivery_item, school_receiving melalui
  `20260911_0009`; terapkan pada fsos dan verifikasi Alembic check.
- [x] Uji referensi tenant kendaraan/driver/paket, tujuan sekolah sesuai manifest,
  duplikasi item/penerimaan, urutan waktu perjalanan, serta rollback yang mempertahankan produksi/paket.
- [x] Tahap konsumsi/keluhan/recall: consumption, complaint, recall melalui
  `20260911_0010`; terapkan pada fsos dan verifikasi Alembic check.
- [x] Uji referensi tenant/paket/batch, satu konsumsi final, alasan/waktu wajib,
  urutan waktu recall, nilai safe awal kosong, dan rollback yang mempertahankan pengiriman.
- [x] Digital asset, asset_relationship, asset_movement melalui `20260911_0011`;
  terapkan pada fsos dan verifikasi Alembic check.
- [x] Uji relasi/self-edge/duplikasi, tipe aset, lokasi/operator tenant,
  trigger penolakan UPDATE/DELETE/TRUNCATE movement, serta rollback yang mempertahankan recall.
- [x] Implementasikan adapter validasi sumber untuk 15 tipe aset serta service
  sync/backfill registry dengan scope tenant, permission dan transaksi caller.
- [x] Hubungkan create/update/soft delete KitchenRepository ke registry secara
  atomik; sync identik mempertahankan UUID/version, backfill memakai cursor UUID.
- [x] Uji seluruh adapter, tenant/type salah, permission, pengulangan, pagination,
  perubahan sumber, soft delete dan rollback; sediakan CLI backfill per tipe/tenant.
- [x] Jalankan seed actor/permission development dan backfill FSOS_DEV pada fsos:
  enam aset registry tersedia, pengulangan tidak menggandakan data.
- [ ] Hubungkan service tulis modul lain ke sync dan backfill tenant tambahan bila ada.
  Kitchen, storage, supplier dan bahan baku sudah tersinkron dari jalur tulis; modul lain tetap bertahap.
- [x] Implementasikan rekonsiliasi registry per tenant/type: laporan sumber hilang,
  proyeksi berbeda, pagination UUID dan CLI tanpa mutasi bukti. Dokumentasikan
  payload hasil, izin, exit code, batas scan dan tindak lanjut operator.
- [x] Verifikasi 56 tes dan Ruff; scan runtime FSOS_DEV untuk 15 tipe memeriksa
  enam registry dengan issue_count=0, tanpa perubahan data.
- [ ] Implementasikan pemulihan sumber hilang setelah investigasi, scheduler/alert
  rekonsiliasi serta endpoint laporan berautentikasi.
- [ ] Implementasikan event idempotency, pembangunan relationship dan traversal graph.
- [x] Buat migrasi telemetry, index, dan partisi bulanan (docs/08).
  **Status: schema selesai** melalui revisi 0013â€“0014, termasuk health/alarm/holding/
  signal/battery/device_session. Ingestion dan engine tetap dilacak terpisah.
- [x] Terapkan `20260911_0013`: empat sensor log berpartisi bulanan UTC serta
  mqtt_message_log; index timeline/GIS, FK tenant/device/pesan, dan bukti append-only.
- [x] Siapkan 12 partisi awal (Septemberâ€“November 2026) dan script maintenance
  create_telemetry_partitions.py untuk menambah bulan secara idempotent.
- [x] Uji batas bulan, timestamp tanpa partisi, FK tenant, GPS Point, duplicate key,
  penolakan UPDATE/DELETE/TRUNCATE pada parent/child, partisi baru, dan rollback.
- [x] Lengkapi device_health_log, alarm_log, holding_log, signal_log, battery_log,
  dan device_session melalui `20260911_0014`; diterapkan pada fsos, Alembic check bersih.
- [x] Tambahkan alarm_acknowledgment dan device_session_end append-only; uji tenant/actor,
  nilai sensor, waktu/duplikasi finalisasi, snapshot awal tetap utuh, trigger bukti,
  serta downgrade yang mempertahankan sensor berpartisi. Lima tes lulus.
- [x] Implementasikan pembacaan status efektif alarm/sesi dan API finalisasi
  memakai tabel bukti tambahan, termasuk validasi payload/status. Service dan HTTP
  baca/acknowledge/close tersedia dengan scope tenant, permission, validasi waktu
  serta retry tanpa mengubah bukti pertama. Reconnect dilacak terpisah di bawah.
- [x] Implementasikan dan uji status efektif alarm/sesi, snapshot impor, actor audit,
  penolakan tenant lain, permission mutasi terpisah, konflik waktu dan rollback.
- [x] Tambahkan daftar alarm/sesi internal dengan permission Read, filter perangkat,
  status efektif dan waktu, urutan timestamp/UUID serta pagination 1..100.
  Hasil daftar memakai proyeksi yang sama dengan detail, termasuk snapshot impor.
- [x] Verifikasi 66 tes dan Ruff: filter status sebelum/sesudah finalisasi, tenant,
  rentang waktu, pagination, validasi input, izin dicabut dan role runtime terbatas.
- [x] Tambahkan GET daftar/detail alarm telemetry dan POST acknowledgment dengan
  bearer, Alarm.Read/Acknowledge terpisah, filter status efektif dan pagination.
- [x] Verifikasi 26 tes terkait: scope tenant, permission dicabut, retry immutable,
  snapshot impor, filter waktu/status dan runtime role; perbarui dokumentasi frontend.
- [x] Tambahkan GET daftar/detail dan POST akhir sesi perangkat dengan bearer,
  DeviceSession.Read/Close terpisah, filter efektif dan bukti finalisasi immutable.
- [x] Sediakan CLI provisioning permission telemetry development dengan mode check,
  apply eksplisit, idempotency, audit dan penolakan pemulihan grant yang dicabut.
  Empat permission/grant diterapkan ke DEV_MAINTENANCE lokal; pengulangan membuat 0 row.
- [x] Verifikasi 25 tes terkait, Ruff dan pemeriksaan grant runtime lokal; perbarui
  kontrak frontend, changelog, event catalog dan runbook provisioning.
- [ ] Implementasikan ingestion/reconnect yang membuka session_id baru serta
  provisioning permission production dengan isolasi admin/secret yang sesuai.
- [ ] Jadwalkan pembuatan partisi ke depan, tentukan backfill/archive/retention,
  dan implementasikan ingestion MQTT/idempotency; belum ada penghapusan data otomatis.
- [x] Buat rolling check/ensure bulanan UTC, verifikasi batas partisi serta guard,
  exit code/laporan JSON; uji cakupan hilang, tahun kabisat dan guard invalid.
- [x] Siapkan enam bulan partisi fsos (September 2026â€“Februari 2027, 24 partisi);
  Alembic check bersih, task maintenance development harian/logon terdaftar.
- [x] Dokumentasikan runbook backfill dan target retensi draft; kebijakan saat ini
  mempertahankan semua bukti tanpa penghapusan otomatis.
- [ ] Implementasikan scheduler production/alert kegagalan, ekspor arsip dan uji restore;
  putuskan kebijakan pelepasan bukti serta retensi tipe yang belum ditentukan.
- [ ] Terapkan UUID, audit columns, version, soft delete, dan isolasi tenant.
  **Sebagian selesai:** repository kitchen memiliki scope tenant/actor, audit,
  soft delete dan update atomik berdasarkan expected_version. Modul lain,
  kebijakan query global/RLS serta integrasi autentikasi belum diterapkan.
- [x] Implementasikan dan uji KitchenRepository: actor/tenant aktif, penolakan
  akses lintas tenant, field audit dilindungi, version conflict, soft delete,
  pagination terbatas, dan rollback transaksi yang dikelola caller.
- [x] Uji upgrade/downgrade migrasi dan seed data development.
  Seed FSOS_DEV: 23 record fixture, tujuh master contoh dan enam aset registry;
  dua kali dijalankan pada fsos dengan created=23 lalu 0. Tes penolakan konflik,
  pencabutan izin, environment production, dan rollback lulus.
- [x] Tambahkan /api/v1/ready: PostgreSQL 18, PostGIS/pgcrypto, dan Alembic heads;
- [x] Tambahkan /api/v1/health/database untuk test koneksi database eksplisit dari frontend/devops;
  timeout, respons 503 tersanitasi, serta liveness terpisah. Diverifikasi pada fsos.
- [x] Uji readiness berhasil/gagal, timeout, extension hilang, revisi tidak cocok,
  envelope, dan dokumentasi 503; 15 tes API/readiness lulus.
- [ ] Perluas readiness dengan Redis/MQTT ketika menjadi dependensi runtime.

## P2 â€” Framework dan keamanan (docs/02, 10, 11, 16, 17)

- [x] Buat panduan frontend `backend/docs/frontend-api.md`: endpoint aktif,
  payload, response, error, header, auth/status, dan contoh integrasi.
- [x] Buat `backend/docs/event-catalog.md` dan `frontend-changelog.md`;
  bedakan event rencana dengan event runtime yang belum tersedia.
- [x] Simpan aturan pembaruan dokumentasi API/event pada `AGENTS.md`.
- [ ] Berkelanjutan: perbarui panduan frontend, OpenAPI, event catalog, dan changelog
  dalam setiap perubahan kontrak API/event; wajib sebelum menandai fitur selesai.
- [ ] Buat BaseEntity domain, interface repository, BaseService, pagination/filter/sort.
- [ ] Buat event bus dan worker dengan retry, idempotency, serta penanganan gagal.
- [x] Implementasikan endpoint login/refresh/logout dan /auth/me: access 15 menit,
  refresh 7 hari, bearer berbasis sid dan snapshot RBAC database aktif.
- [x] Terapkan migrasi 20260911_0017 dan grant runtime sesi pada fsos; Alembic
  check tanpa perbedaan. Seluruh 99 tes lulus termasuk dua refresh bersamaan.
- [x] Simpan hash refresh token, rotasi dan deteksi reuse dengan pencabutan
  keluarga sesi; logout per sesi dan resolver sid tersedia melalui service internal.
- [x] Hubungkan login/refresh/logout ke HTTP; commit sebelum token/401 reuse,
  error seragam, no-store, OpenAPI terstruktur dan limiter sementara per proses.
- [ ] Lengkapi audit persisten, limiter lintas worker, revokasi semua perangkat
  saat reset password, dan kebijakan retensi token; blacklist per-jti
  belum tersedia (pencabutan saat ini per keluarga sesi).
- [x] Implementasikan bcrypt cost 12 dan kebijakan 12 karakter sampai 72 byte UTF-8,
  tanpa truncation/trim, salt acak, verifikasi hash ketat dan wrapper async.
- [x] Implementasikan codec access JWT 15 menit: HS256 tetap, issuer/audience,
  claim wajib, tujuan access, UUID dan validasi waktu; tanpa secret bawaan.
- [x] Verifikasi 89 tes (23 primitive autentikasi), Ruff dan pip check bersih.
- [x] Hubungkan primitive password ke autentikasi akun internal: username per tenant,
  status actor/tenant, shared lock/recheck hash dan snapshot RBAC aktif.
- [x] Tambahkan bcrypt dummy untuk kredensial invalid dan resolusi access JWT
  ke actor/tenant aktif; permission operasi tetap diperiksa dari database.
- [x] Verifikasi suite 93 tes; empat kasus username invalid ditambahkan dan lima
  tes akun dijalankan ulang lulus (97 kasus tersedia), Ruff bersih.
- [x] Hubungkan autentikasi akun ke dependency current_account dan endpoint HTTP
  refresh/revoke; log action/outcome tersanitasi dan limiter 100/menit/IP per proses.
- [x] Verifikasi 103 tes; setelah tes CORS tambahan, 20 tes API/auth/readiness
  dijalankan ulang lulus (104 kasus tersedia). Ruff bersih.
- [ ] Lengkapi audit login persisten dan verifikasi mitigasi enumerasi/timing menyeluruh.
- [ ] Implementasikan RBAC/permission serta validasi tenant setiap akses.
- [ ] Buat seed role/permission dan bootstrap admin tanpa password bawaan.
  Seed role/permission development selesai; bootstrap admin manusia/production
  masih TODO. CLI bootstrap akun manusia development dengan password tersembunyi
  dan role terpilih tersedia; actor maintenance tetap tanpa password.
- [x] Sediakan CLI bootstrap manusia development dan --check: identitas unik,
  actor/tenant aktif, role tenant yang dipilih, bcrypt dan membership atomik;
  existing user/password/grant tidak diubah.
- [x] Verifikasi 113 tes dan Ruff; --check FSOS_DEV berhasil tanpa membuat akun
  contoh atau mengubah password actor maintenance.
- [ ] Tambahkan FK/validasi actor audit sesuai tenant; kolom created_by/updated_by/deleted_by
  saat ini masih UUID tanpa FK.
- [ ] Implementasikan API key device, OAuth2 client credentials, dan service identity.
- [ ] Terapkan rate limit human 100/min dan device 30/min berbasis Redis.
- [ ] Tambahkan audit login/logout/permission/rule serta log file berotasi.
- [ ] Tambahkan dependency current user, permission, repository, dan service.
- [ ] Pastikan seluruh endpoint bisnis memiliki auth, validasi, envelope,
  dokumentasi payload/parameter/rule/permission/error/example, serta pengujian.
- [ ] Putuskan kebijakan akses health dan dokumentasi pada production.

## P3 â€” Modul bisnis (docs/05, 09, 12â€“14, 17)

- [ ] Master data dan authentication.
- [ ] Device/digital twin: calibration, firmware lifecycle, heartbeat dan telemetry ingestion (docs/12).
- [ ] Telemetry: ingestion MQTT async, validasi payload, deduplikasi, event storage.
- [ ] Storage dan receiving: pemantauan kondisi dan penerimaan bahan.
- [ ] Production, packaging, QR, dan asset movement.
- [ ] Rule engine: konfigurasi, prioritas, versi, simulasi, dan execution log (docs/09).
- [ ] Holding time engine: start/update/finish/expired dan notifikasi (docs/14).
- [ ] Traceability graph: backward/forward traversal, timeline, passport,
  root cause, dan impact analysis (docs/13).
- [ ] Fleet: GPS, perjalanan, geofence, dan riwayat pengiriman.
- [ ] School receiving dan complaint.
- [ ] Food recall dan pelacakan paket terdampak.
- [ ] Notification melalui email/WhatsApp; outbox dashboard internal sudah aktif.
- [ ] Integrasi ERP MBG via REST API.
- [x] Integrasikan Google Routes API sebagai satu-satunya routing fleet untuk
  estimasi create/depart serta remaining distance/time.
- [ ] Analytics/AI lanjutan dan optimasi urutan multi-stop delivery.
- [ ] Setiap modul memiliki API, application, domain, infrastructure, schemas,
  dan tes repository/service/rule/API sesuai docs/17.

## P4 â€” Dashboard dan realtime (docs/15, 16)

- [ ] REST dashboard analytics; home/storage/fleet/holding/recall/notification counter sudah aktif.
- [ ] WebSocket dashboard/device/fleet/storage/holding/alarm dengan autentikasi.
- [ ] Redis cache dan distribusi event antarworker.
- [ ] Frontend Vue 3 serta integrasi peta dan alarm.
  Live tracking delivery sudah menampilkan marker armada/dapur/sekolah, rute Google,
  remaining distance/time dan ETA; realtime push dan visual alarm tetap TODO.

## P5 â€” Deployment dan operasional (docs/18)

- [ ] Siapkan Ubuntu, Gunicorn + uvicorn-worker, systemd/container, dan Nginx.
- [ ] Pasang/jalankan Redis dan uji koneksi; development/staging saat fitur integrasi dikerjakan.
- [ ] Pasang/jalankan Mosquitto dengan username/password, ACL, dan isolasi topic;
  development/staging saat telemetry dikerjakan.
- [ ] Buat konfigurasi Docker Compose bila deployment memakai Docker.
- [ ] Konfigurasi domain, HTTPS, secret production, firewall, dan monitoring.
- [ ] Siapkan CI untuk lint, unit, integration, API, dan migrasi.
- [ ] Uji isolasi tenant, beban telemetry, reconnect MQTT/WebSocket, dan multiworker.
- [ ] Siapkan backup harian database, mingguan file, dan arsip bulanan.
- [ ] Uji restore serta disaster recovery.

## Catatan keputusan

- Verifikasi instalasi: FastAPI 0.141.1, Pydantic 2.13.5, SQLAlchemy 2.0.52;
  `pip check` tanpa konflik; 4 tes API lulus; Ruff lulus; HTTP health dan Swagger
  mengembalikan 200 pada server Uvicorn lokal sementara (sudah dihentikan).
- Tes mengeluarkan 2 deprecation warning dari dependensi Starlette/httpx/AnyIO.
  Tidak menggagalkan tes; evaluasi migrasi test client saat memperbarui dependensi.

- Dokumen sumber masih berstatus Draft. Checklist ini tidak menyatakan seluruh
  FSOS sudah siap produksi setelah instalasi FastAPI.
- Untuk perbedaan envelope docs/02 dan docs/10 versus docs/16, fondasi memilih
  docs/16: `execution_time_ms` dan `correlation_id`.
- PostgreSQL lokal terverifikasi dengan PostGIS/pgcrypto dan schema
  tenant/kitchen/storage/zone/device/vehicle/driver/school/supplier/material/food/recipe
  beserta relasi supplier_material serta packaging_type/alarm_rule/holding_rule
  dan identity/RBAC; transaksi penerimaan serta produksi/paket tersedia
  serta pengiriman/penerimaan sekolah/konsumsi/keluhan/recall tersedia
  serta registry/relationship/movement dan operational event tersedia; empat sensor
  log berpartisi serta pesan MQTT ditambahkan pada revisi `20260911_0013`;
  seluruh schema telemetry docs/08 dilengkapi pada `20260911_0014`.
  Lima tes lulus (empat API dan satu integrasi database). Pembatasan query per tenant,
  optimistic locking, serta seed masih belum selesai.
- User mengonfirmasi Redis/Mosquitto ditunda ke tahap integrasi/deployment.
- SDK OpenAI ditunda sampai modul AI dikerjakan; saat ini konfigurasi API key
  tersedia dan integrasi HTTP dapat memakai httpx.














