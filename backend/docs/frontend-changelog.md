# Perubahan kontrak frontend

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

## 2026-09-11 — Pemisahan koneksi API dan admin

- API/readiness/backfill memakai pool DATABASE_URL; migrasi, seed, provisioning
  serta maintenance memakai pool ADMIN_DATABASE_URL tanpa fallback ke runtime.
- Bootstrap lokal fsos_app menghasilkan secret tanpa mencetaknya, memverifikasi
  hak runtime, dan memperbarui konfigurasi lokal. Akun ini bukan login frontend.
- Tidak ada endpoint, payload, respons HTTP, atau event runtime baru.
  Proses backend yang sudah berjalan perlu restart agar konfigurasi baru terbaca.

## 2026-09-11 — Profil privilege runtime database

- Migrasi 0016 memperketat fungsi capture history aturan; grup fsos_runtime
  membatasi akses DML/DDL untuk service yang tersedia.
- Tidak ada endpoint, payload/respons HTTP, login frontend, atau event baru.
  NOLOGIN adalah atribut role PostgreSQL, bukan status akun aplikasi.
- Koneksi lokal belum dialihkan; pemisahan login/secret API dan maintenance
  tetap tahap berikutnya sebelum production.

## 2026-09-11 — Rolling maintenance partisi

- CLI check/ensure memeriksa batas UTC dan guard append-only; fsos disiapkan untuk
  enam bulan (24 partisi). Task development berjalan harian dan saat logon.
- Tidak ada endpoint, response/payload HTTP atau event baru. Readiness HTTP tidak
  berubah; hasil maintenance tersedia sebagai laporan administratif lokal.
- Retensi draft didokumentasikan, seluruh bukti tetap disimpan; arsip/penghapusan
  otomatis belum diimplementasikan. 21 tes terkait dan Alembic check lulus.

## 2026-09-11 — Status efektif dan finalisasi telemetry internal

- Service baru: get_alarm, get_session, acknowledge, close_session dengan permission
  Alarm.Read/Acknowledge dan DeviceSession.Read/Close. Belum diberikan oleh seed.
- Acknowledgment berulang mempertahankan bukti pertama; penutupan ulang dengan
  waktu berbeda ditolak. Parent telemetry tetap immutable.
- Tidak ada endpoint, payload HTTP, atau event runtime baru. Frontend menunggu
  API autentikasi dan schema respons; detail status efektif ada di telemetry-lifecycle.md.
- Verifikasi: 45 tes terkait lulus, termasuk permission, tenant, retry, konflik,
  validasi waktu dan rollback; tidak ada data telemetry baru pada fsos.

## 2026-09-11 — Seed development dan backfill lokal

- Tenant FSOS_DEV, actor pemeliharaan tanpa password, role/permission dan master
  contoh ditambahkan; registry sumber contoh sudah di-backfill.
- Tidak ada perubahan endpoint, payload, respons HTTP, maupun event runtime.
  Fixture belum tersedia lewat CRUD frontend dan actor seed bukan akun login.
- Verifikasi: 44 tes terkait lulus; seed dijalankan dua kali pada fsos,
  created berturut-turut 23 dan 0, dengan enam aset registry.

## 2026-09-11 — Adapter dan backfill registry

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

## 2026-09-11 — Riwayat aturan dan validator DSL internal

- Migrasi 0015 menambahkan snapshot alarm/holding rule yang immutable.
- Validator DSL v1 tersedia untuk struktur condition/action; integrasi ke
  service simpan/aktivasi, evaluator, dan API masih belum tersedia.
- Kontrak frontend tidak berubah. Tidak ada endpoint atau event runtime baru.
- Tindakan frontend: gunakan dokumen rule-versioning untuk memahami rancangan;
  jangan memanggil route manajemen aturan sebelum statusnya menjadi aktif.

## 2026-09-11 — Service simpan/aktivasi aturan

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

## 2026-09-11 — Dokumentasi awal, aplikasi 0.1.0

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

## 2026-09-11 — Fondasi repository kitchen

- Internal: tenant/actor scope, audit, soft delete, serta optimistic concurrency
  menggunakan expected_version ditambahkan pada repository kitchen.
- Kontrak frontend: tidak ada endpoint/payload/respons baru atau perubahan HTTP.
  Belum ada pemetaan exception repository ke respons API bisnis.
- Event: tidak ada publisher baru; operasi repository belum menerbitkan event.
- Tindakan frontend: belum perlu perubahan. Form kitchen menunggu API berautentikasi.
- Verifikasi: tes PostgreSQL mencakup akses lintas tenant, actor/tenant tidak aktif,
  version lama, audit, soft delete, pembatasan field, pagination dan rollback.
