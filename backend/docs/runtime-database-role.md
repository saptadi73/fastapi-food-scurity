# Role database runtime

Profil `fsos_runtime` adalah grup privilege PostgreSQL **NOLOGIN**, bukan user
frontend atau role RBAC aplikasi. Profil disiapkan untuk service yang sudah
diimplementasikan. DATABASE_URL lokal kini memakai login fsos_app dengan membership
fsos_runtime. Migrasi, seed dan maintenance memakai ADMIN_DATABASE_URL terpisah.
Lihat [panduan koneksi](database-connections.md) untuk bootstrap dan pengelolaan secret.

Sudah diterapkan pada fsos bersama migrasi 0016 pada 2026-09-11. Seluruh 53 tes
lulus pada database uji, dan Alembic check fsos tidak menemukan perubahan schema.

## Hak yang diberikan

| Objek | Privilege |
| --- | --- |
| Database/schema | CONNECT database, USAGE schema public |
| Tabel aplikasi yang dikenal ORM | SELECT |
| alembic_version | SELECT saja |
| kitchen, storage, storage_zone, school, driver, vehicle, supplier, raw_material, supplier_material, digital_asset, alarm_rule, holding_rule | INSERT, UPDATE pada daftar kolom yang dibutuhkan service |
| alarm_acknowledgment, device_session_end | INSERT |
| auth_session, refresh_token | SELECT/INSERT; UPDATE hanya revoked_at atau used_at masing-masing |
| Tabel sumber registry, actor/tenant/RBAC, alarm_log, device_session | UPDATE(version) untuk kebutuhan SELECT FOR UPDATE/SHARE |
| History revisi aturan | SELECT; INSERT hanya melalui fungsi trigger yang diperketat |

Tidak ada hak CREATE schema/tabel, TEMP, ALTER/DROP, TRUNCATE, DELETE, TRIGGER,
pengelolaan role, superuser, replication, atau BYPASSRLS. Runtime tidak dapat
mengeksekusi fungsi pembuat partisi. Raw telemetry ingestion belum mendapat
INSERT; perlu tinjauan grant saat modul ingestion siap. Hak baru tidak diwariskan
otomatis ke tabel masa depan melalui ALTER DEFAULT PRIVILEGES.

PostgreSQL memerlukan UPDATE setidaknya satu kolom untuk locking reads. Karena
itu UPDATE(version) diberikan tanpa mengizinkan perubahan role_id, permission_id,
status user, password, atau identitas tenant melalui UPDATE. Pada bukti immutable,
trigger tetap menolak UPDATE apa pun. Pada tabel mutable, SQL langsung bisa
mengubah version; ini konsekuensi izin locking, bukan permission bisnis.
[Referensi SELECT PostgreSQL 18](https://www.postgresql.org/docs/18/sql-select.html).

## Fungsi history yang diperketat

Migrasi 0016 mengubah fsos_capture_rule_revision menjadi SECURITY DEFINER dengan
search_path `pg_catalog, pg_temp`. Target INSERT ditulis eksplisit untuk
alarm_rule_revision dan holding_rule_revision. Fungsi menolak sumber selain tabel
public.alarm_rule/public.holding_rule dan operasi selain INSERT/UPDATE; tidak lagi
memilih tabel berdasarkan argumen trigger dinamis. Hak EXECUTE PUBLIC dicabut.

Fungsi berjalan sebagai owner migrasi agar service tidak perlu INSERT history
langsung. Owner lokal saat ini superuser; production harus memakai owner migrasi
terpisah yang hanya memiliki objek aplikasi. SQL fungsi tidak menjalankan payload
DSL atau input pengguna. Profil runtime tidak mendapat hak membuat/mengganti trigger.
[Panduan keamanan SECURITY DEFINER](https://www.postgresql.org/docs/18/sql-createfunction.html).

## Provisioning

Setelah migrasi 0017, jalankan dengan koneksi administratif dari root proyek:

```powershell
.\venv\Scripts\python.exe -m alembic upgrade head
.\venv\Scripts\python.exe backend\scripts\provision_runtime_role.py
```

Provisioning dalam satu transaksi, aman diulang untuk role yang ditandai
`FSOS managed runtime role v1`. Role nama sama yang tidak memiliki marker, atribut
berlebihan, LOGIN, atau keanggotaan ke role lain akan ditolak. Profil mengatur
ulang grant langsung pada tabel yang dikenal termasuk grant per kolom. Jangan
memberi privilege tambahan manual pada grup ini; gunakan profil yang ditinjau.

Untuk memastikan pembatasan efektif, CREATE public schema dan CREATE/TEMP database
dicabut dari PUBLIC, dan EXECUTE fungsi maintenance dicabut dari PUBLIC. Ini
berlaku pada database target, sehingga login lain yang bergantung pada grant PUBLIC
tersebut memerlukan grant administratif eksplisit. Owner/superuser lokal tetap
bisa menjalankan migrasi dan maintenance.

Script mensyaratkan head tepat 0017 sebagai pagar peninjauan. Saat schema/service
berubah, tinjau serta perbarui profil dan tes sebelum provisioning ulang. Script
tidak memberikan LOGIN, mengubah password, mengubah ownership objek, memberi
membership kepada user existing, atau mengalihkan DATABASE_URL.

## Pemisahan koneksi runtime dan admin

Pemisahan sudah diterapkan pada development: fsos_app memakai grant grup NOLOGIN
fsos_runtime dan koneksi owner dipakai hanya pada jalur administratif. Script
configure_runtime_login.py membuat login dan mengalihkan konfigurasi lokal setelah
verifikasi. provision_runtime_role.py sendiri hanya mengelola profil grant.

Tes grant memakai SET LOCAL ROLE pada database terpisah. Koneksi fsos_app lokal
juga telah diverifikasi langsung: readiness berhasil, backfill registry berjalan,
dan password salah gagal terhubung. Seluruh 55 tes lulus. Task partisi melalui
koneksi administratif selesai dengan LastTaskResult=0. Production masih memerlukan
isolasi secret dari proses API, owner migrasi khusus dan pengujian TLS/deployment.

## Batas keamanan dan frontend

Ini pembatasan capability koneksi database, bukan isolasi row antar-tenant.
SELECT pada tabel aplikasi tetap lintas tenant dari SQL langsung. Service harus
menjalankan scope dan permission; PostgreSQL RLS serta audit actor menyeluruh
masih TODO. Role tidak melindungi database dari owner/admin yang bisa mengubah DDL.

Tidak ada endpoint, payload, respons, token atau event baru untuk frontend.
Nama fsos_runtime tidak dipakai pada header Authorization atau form login.
Frontend tidak boleh menerima connection string PostgreSQL. Endpoint health/ready
tetap memakai kontrak yang sudah didokumentasikan.

Tes membuktikan service kitchen/registry/aturan berjalan dengan role runtime,
history tercatat meskipun INSERT history langsung ditolak, serta penolakan DDL,
TEMP, disable trigger, truncate, hard delete, perubahan user/grant dan maintenance.
Upgrade/downgrade fungsi diuji pada database terpisah. Profil belum menyatakan
seluruh konfigurasi production sudah selesai.

## Perluasan profil sesi (0017)

Profil grant diperbarui dan diprovisioning ulang setelah migrasi sesi. Runtime
mendapat INSERT auth_session/refresh_token serta UPDATE hanya kolom revokasi atau
pemakaian; tidak mendapat hak mengubah user/tenant, hash atau waktu expiry sesi.
Grant ini tidak membuat endpoint login. Lihat [sesi refresh](refresh-sessions.md).


Master lokasi: profil runtime kini memberi INSERT storage/storage_zone dan UPDATE
kolom definisi/audit/version. Parent kitchen_id pada storage dan storage_id pada zone
tidak diberi UPDATE. API mempertahankan induk dan memeriksa tenant/parent aktif.
Perubahan telah diterapkan pada fsos tanpa migrasi; tidak menambah hak delete/DDL.

Supplier/bahan: profil kini memberi INSERT serta UPDATE definisi/audit/version
supplier, raw_material dan supplier_material. Referensi tenant dan parent aktif
diperiksa service; perubahan uom bahan ditolak service. Tidak ada hak delete/DDL baru.


Soft delete master: UPDATE deleted_at/deleted_by kini diberikan pada storage,
storage_zone, supplier, raw_material dan supplier_material (kitchen sudah tersedia).
Service mengisi audit/version dan memeriksa referensi sebelum menandai terhapus.
Tidak ada privilege DELETE SQL baru, cascade atau DDL. Grant sudah diterapkan pada
fsos sebagai dependensi API DELETE; schema tetap 0017 tanpa migrasi.

School kini mendapatkan INSERT dan UPDATE kolom definisi/audit/version termasuk
soft delete, tanpa UPDATE kitchen_id/tenant_id atau hard delete. Ini dependensi
minimum CRUD sekolah dan sudah diterapkan pada fsos.

Driver/vehicle kini memiliki INSERT dan UPDATE definisi/audit/version termasuk
soft delete. Vehicle.driver_id/gps_device boleh diubah setelah pemeriksaan service;
tenant/ID tetap dilindungi. Tidak ada privilege DELETE SQL/DDL atau INSERT GPS log baru.
