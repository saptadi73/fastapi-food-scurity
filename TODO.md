# TODO — Food Safety Operating System

Checklist instalasi dan roadmap berdasarkan docs/01–18. Tanggal awal: 2026-09-11.
`[x]` berarti telah tersedia dan diperiksa; `[ ]` berarti belum selesai.
Paket yang terpasang tidak berarti fitur bisnis sudah diimplementasikan.

## P0 — Fondasi instalasi FastAPI

- [x] Perbaiki dan verifikasi venv Python 3.11 beserta pip.
- [x] Baca kebutuhan stack, struktur, framework, keamanan, API, dan deployment.
- [x] Buat folder backend sesuai docs/03 dan titik masuk FastAPI.
- [x] Siapkan requirements development dan production Linux.
- [x] Selesaikan instalasi dependensi dan simpan versi aktual untuk Windows Python 3.11.
- [x] Siapkan `.env.example`, `.env` lokal, dan `.gitignore`.
- [x] Siapkan SQLAlchemy async session dan konfigurasi Alembic (belum schema).
- [x] Siapkan endpoint `/api/v1/health`, Swagger, ReDoc, dan OpenAPI.
- [x] Terapkan envelope API docs/16, request ID, error handler, dan CORS.
- [x] Siapkan JSON logging console.
- [x] Verifikasi pip check, tes API, lint, dan startup server HTTP.
- [x] Tulis panduan menjalankan aplikasi pada Windows di README.

## P1 — Layanan dan database (docs/04, 06–08, 18)

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
- [x] Uji relasi vehicle–driver/GPS dan school–kitchen dalam tenant yang sama,
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
- [ ] Integrasikan autentikasi HTTP, seed permission dan endpoint manajemen aturan;
  validasi semantik executor (template/target/transisi) sebelum menjalankan action.
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
  **Status: schema selesai.** Receiving hingga recall melalui revisi 0007–0010;
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
- [x] Implementasikan rekonsiliasi registry per tenant/type: laporan sumber hilang,
  proyeksi berbeda, pagination UUID dan CLI tanpa mutasi bukti. Dokumentasikan
  payload hasil, izin, exit code, batas scan dan tindak lanjut operator.
- [x] Verifikasi 56 tes dan Ruff; scan runtime FSOS_DEV untuk 15 tipe memeriksa
  enam registry dengan issue_count=0, tanpa perubahan data.
- [ ] Implementasikan pemulihan sumber hilang setelah investigasi, scheduler/alert
  rekonsiliasi serta endpoint laporan berautentikasi.
- [ ] Implementasikan event idempotency, pembangunan relationship dan traversal graph.
- [x] Buat migrasi telemetry, index, dan partisi bulanan (docs/08).
  **Status: schema selesai** melalui revisi 0013–0014, termasuk health/alarm/holding/
  signal/battery/device_session. Ingestion dan engine tetap dilacak terpisah.
- [x] Terapkan `20260911_0013`: empat sensor log berpartisi bulanan UTC serta
  mqtt_message_log; index timeline/GIS, FK tenant/device/pesan, dan bukti append-only.
- [x] Siapkan 12 partisi awal (September–November 2026) dan script maintenance
  create_telemetry_partitions.py untuk menambah bulan secara idempotent.
- [x] Uji batas bulan, timestamp tanpa partisi, FK tenant, GPS Point, duplicate key,
  penolakan UPDATE/DELETE/TRUNCATE pada parent/child, partisi baru, dan rollback.
- [x] Lengkapi device_health_log, alarm_log, holding_log, signal_log, battery_log,
  dan device_session melalui `20260911_0014`; diterapkan pada fsos, Alembic check bersih.
- [x] Tambahkan alarm_acknowledgment dan device_session_end append-only; uji tenant/actor,
  nilai sensor, waktu/duplikasi finalisasi, snapshot awal tetap utuh, trigger bukti,
  serta downgrade yang mempertahankan sensor berpartisi. Lima tes lulus.
- [ ] Implementasikan pembacaan status efektif alarm/sesi dan API finalisasi
  memakai tabel bukti tambahan, termasuk validasi payload/status serta reconnect.
  **Sebagian selesai:** service baca/acknowledge/close tersedia dengan scope tenant,
  permission, validasi waktu serta retry tanpa mengubah bukti pertama.
- [x] Implementasikan dan uji status efektif alarm/sesi, snapshot impor, actor audit,
  penolakan tenant lain, permission mutasi terpisah, konflik waktu dan rollback.
- [x] Tambahkan daftar alarm/sesi internal dengan permission Read, filter perangkat,
  status efektif dan waktu, urutan timestamp/UUID serta pagination 1..100.
  Hasil daftar memakai proyeksi yang sama dengan detail, termasuk snapshot impor.
- [x] Verifikasi 66 tes dan Ruff: filter status sebelum/sesudah finalisasi, tenant,
  rentang waktu, pagination, validasi input, izin dicabut dan role runtime terbatas.
- [ ] Tambahkan API daftar/finalisasi berautentikasi, provisioning permission telemetry,
  serta ingestion/reconnect yang membuka session_id baru.
- [ ] Jadwalkan pembuatan partisi ke depan, tentukan backfill/archive/retention,
  dan implementasikan ingestion MQTT/idempotency; belum ada penghapusan data otomatis.
- [x] Buat rolling check/ensure bulanan UTC, verifikasi batas partisi serta guard,
  exit code/laporan JSON; uji cakupan hilang, tahun kabisat dan guard invalid.
- [x] Siapkan enam bulan partisi fsos (September 2026–Februari 2027, 24 partisi);
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
- [x] Tambahkan `/api/v1/ready`: PostgreSQL 18, PostGIS/pgcrypto, dan Alembic heads;
  timeout, respons 503 tersanitasi, serta liveness terpisah. Diverifikasi pada fsos.
- [x] Uji readiness berhasil/gagal, timeout, extension hilang, revisi tidak cocok,
  envelope, dan dokumentasi 503; 15 tes API/readiness lulus.
- [ ] Perluas readiness dengan Redis/MQTT ketika menjadi dependensi runtime.

## P2 — Framework dan keamanan (docs/02, 10, 11, 16, 17)

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

## P3 — Modul bisnis (docs/05, 09, 12–14, 17)

- [ ] Master data dan authentication.
- [ ] Device/digital twin: registry, binding, calibration, firmware, heartbeat (docs/12).
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
- [ ] Notification melalui email/WhatsApp.
- [ ] Integrasi ERP MBG via REST API.
- [ ] Analytics/AI dan Google Maps setelah kebutuhan API serta secret tersedia.
- [ ] Setiap modul memiliki API, application, domain, infrastructure, schemas,
  dan tes repository/service/rule/API sesuai docs/17.

## P4 — Dashboard dan realtime (docs/15, 16)

- [ ] REST dashboard untuk home/storage/fleet/holding/analytics.
- [ ] WebSocket dashboard/device/fleet/storage/holding/alarm dengan autentikasi.
- [ ] Redis cache dan distribusi event antarworker.
- [ ] Frontend Vue 3 serta integrasi peta dan alarm.

## P5 — Deployment dan operasional (docs/18)

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
