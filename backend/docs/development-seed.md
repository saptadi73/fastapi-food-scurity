# Seed development

Status 2026-09-11: sudah diterapkan pada database lokal fsos, tenant `FSOS_DEV`.
Seed adalah fixture development, bukan bootstrap admin production atau data bisnis
nyata. Script hanya berjalan jika ENVIRONMENT tepat `development`.

## Data yang dibuat

| Jenis | Isi |
| --- | --- |
| Tenant | FSOS_DEV / FSOS Development |
| Actor | dev-maintenance, email contoh dev-maintenance@example.invalid, ACTIVE |
| Role | DEV_MAINTENANCE |
| Permission | AssetRegistry.Sync, AlarmRule.Read/Write/Activate, HoldingRule.Read/Write |
| Master | Satu kitchen, storage, storage zone, device, supplier, raw material, school |
| Registry | Enam aset dari master yang memiliki adapter (storage zone belum ada adapter) |

Fixture membuat total 23 record tenant/actor/RBAC/master, di luar enam record
registry. Tidak membuat alarm aktif, sampel telemetry, receiving, produksi,
pengiriman, complaint, recall, atau transaksi palsu. Field suhu/holding yang tidak
diberikan tetap kosong; tidak menetapkan ambang keamanan pangan contoh sebagai default.

Actor pemeliharaan tidak diberi password (`password_hash` awal NULL). Actor ini
dipakai CLI/service administratif melalui akses database tepercaya, **bukan akun
login frontend**. Endpoint login/JWT kini tersedia dan menolak actor tanpa
password/credential autentikasi yang sah dengan 401. Bootstrap akun
manusia development dengan password pilihan pengguna tersedia melalui
[panduan CLI](human-bootstrap.md); bootstrap admin production tetap pekerjaan P2.

ID fixture menggunakan UUID v5 deterministik pada namespace proyek agar stabil
ketika seed diulang. UUID ini bukan secret atau token autentikasi:

- Tenant: `a492adf9-3a5b-501e-b4d5-ec48d54f657b`.
- Actor: `9062c8ab-1713-5398-b4a1-06d3e9402b3a`.

## Menjalankan

Migrasi head harus sudah terpasang. Dari root proyek:

```powershell
.\venv\Scripts\python.exe backend\scripts\seed_development.py
```

Script menggunakan ADMIN_DATABASE_URL dari konfigurasi lokal. Hasil JSON berisi
tenant_id, actor_id, created (record fixture baru), serta registry_processed per
tipe aset. Pengulangan normal menghasilkan created=0. registry_processed menghitung
sumber yang diperiksa, bukan jumlah aset baru. Exit 0 berarti commit berhasil,
exit 1 berarti gagal dengan error_type tanpa membocorkan URL/password.

Seluruh fixture dan backfill tenant berada dalam satu transaksi dengan advisory
lock antarproses seed. Kegagalan rollback seluruh seed. Record existing tidak
ditimpa: nama, kapasitas, dan konfigurasi yang sudah diubah tetap dipertahankan.
Registry mengikuti proyeksi sumber terkini melalui service sync.

Script menolak ID fixture yang identitasnya berubah, record soft-deleted, actor/
tenant nonaktif, serta grant/role yang hilang atau dicabut pada instalasi yang
actornya sudah tersedia. Script tidak memulihkan izin secara diam-diam. Benturan
kode/email dengan record lain menyebabkan transaksi gagal, bukan mengambil alih
record tersebut. Hard delete fixture master dapat menyebabkan seed membuatnya
lagi; script ini bukan mekanisme reset data atau penghapusan environment.

ENVIRONMENT adalah guard operasional, bukan pembatas akses database; tetap jangan
arahkan seed ke database production. Tidak ada script reset/drop/delete otomatis.

## Backfill registry lokal

Seed sudah memindai seluruh 15 tipe sumber pada tenant FSOS_DEV dan menyimpan
enam aset yang tersedia. Contoh mengulang satu tipe setelah perubahan sumber:

```powershell
.\venv\Scripts\python.exe backend\scripts\backfill_asset_registry.py --tenant a492adf9-3a5b-501e-b4d5-ec48d54f657b --actor 9062c8ab-1713-5398-b4a1-06d3e9402b3a --asset-type KITCHEN
```

Tenant lain tidak otomatis diberi actor/grant atau di-backfill. Seed development
tidak menggantikan provisioning identitas production. Script CLI backfill terpisah
commit per batch; berbeda dari seed yang membungkus keseluruhan fixture/backfill
dalam satu transaksi. Lihat [panduan registry](asset-registry.md).

Verifikasi: seed pertama pada fsos membuat 23 fixture, pengulangan membuat 0;
enam aset registry tetap tersedia. Tes PostgreSQL mencakup pengulangan tanpa
perubahan UUID/version, pelestarian nama yang diedit, penolakan grant soft/hard
deleted dan actor nonaktif, penolakan environment production, serta rollback.
