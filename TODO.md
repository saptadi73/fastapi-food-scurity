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
- [ ] Lengkapi history revisi aturan immutable dan validasi DSL condition/action
  sebelum menyediakan perubahan/aktivasi aturan melalui API.
- [x] Uji upgrade/downgrade/upgrade pada database uji terpisah; periksa FK tenant,
  kode kitchen unik per tenant, koordinat, dan pelestarian extension saat downgrade.
- [ ] Siapkan role aplikasi dengan hak terbatas sebelum production (akun lokal saat ini superuser).
- [x] Buat ORM dan migrasi master data: tenant, kitchen, storage/zone, device,
  vehicle/driver, school, supplier, material, food item, recipe, packaging,
  alarm/holding rule, user/role/permission (docs/06).
- [ ] Buat migrasi digital asset, asset relationship, movement, operational
  event, produksi, paket, pengiriman, receiving, complaint, dan recall (docs/07).
- [x] Tahap penerimaan: receiving, raw_material_batch, receiving_item melalui
  `20260911_0007`; terapkan pada fsos dan verifikasi Alembic check.
- [x] Uji konsistensi header/supplier/batch, referensi tenant/operator/material,
  duplikasi batch/item, quantity, serta rollback yang mempertahankan master dan user.
- [x] Tahap produksi: production_batch, production_item, package melalui
  `20260911_0008`; terapkan pada fsos dan verifikasi Alembic check.
- [x] Uji relasi kitchen/menu/bahan/kemasan dalam tenant, jumlah bahan positif,
  kode/nomor paket unik, waktu produksi/holding, snapshot remaining negatif,
  serta rollback yang mempertahankan penerimaan bahan.
- [ ] Buat migrasi telemetry, index, dan partisi bulanan (docs/08).
- [ ] Terapkan UUID, audit columns, version, soft delete, dan isolasi tenant.
- [ ] Uji upgrade/downgrade migrasi dan seed data development.
- [ ] Tambahkan readiness terpisah yang memeriksa layanan pendukung.

## P2 — Framework dan keamanan (docs/02, 10, 11, 16, 17)

- [ ] Buat BaseEntity domain, interface repository, BaseService, pagination/filter/sort.
- [ ] Buat event bus dan worker dengan retry, idempotency, serta penanganan gagal.
- [ ] Implementasikan login JWT: access 15 menit, refresh 7 hari.
- [ ] Simpan dan rotasi refresh token; sediakan revoke, blacklist, dan logout.
- [ ] Implementasikan bcrypt cost 12 dan kebijakan panjang password.
- [ ] Implementasikan RBAC/permission serta validasi tenant setiap akses.
- [ ] Buat seed role/permission dan bootstrap admin tanpa password bawaan.
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
  pada revisi `20260911_0008`.
  Lima tes lulus (empat API dan satu integrasi database). Migrasi master data lainnya,
  pembatasan query per tenant, optimistic locking, serta seed masih belum selesai.
- User mengonfirmasi Redis/Mosquitto ditunda ke tahap integrasi/deployment.
- SDK OpenAI ditunda sampai modul AI dikerjakan; saat ini konfigurasi API key
  tersedia dan integrasi HTTP dapat memakai httpx.
