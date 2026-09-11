# Perubahan kontrak frontend

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
