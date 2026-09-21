# Seed development

Status 2026-09-15: seed minimal `FSOS_DEV` sudah tersedia dan seed demo frontend
`FSOS_DEMO` sudah disiapkan melalui script terpisah.
Seed adalah fixture development, bukan bootstrap admin production atau data bisnis
nyata. Script hanya berjalan jika ENVIRONMENT tepat `development`.

## Baseline frontend tanpa transaksi

Untuk menyiapkan login dan master frontend tanpa receiving, stok transaksi, MO,
package, delivery, telemetry sample atau insiden, gunakan:

```powershell
.\venv\Scripts\python.exe backend\scripts\seed_demo_ready.py --masters-only --username frontend_admin
```

Mode ini cocok untuk menguji workflow dari awal. Login memakai tenant `FSOS_DEMO`,
username dari `--username`, dan password development `DemoFrontend123!`. Mode ini
tetap hanya boleh dijalankan pada environment development/testing dan bukan database
production.

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

## Seed demo frontend end-to-end

Script `backend/scripts/seed_demo_ready.py` membuat data demo yang lebih lengkap
untuk implementasi frontend dan integration test manual. Guard environment hanya
mengizinkan `development` atau `testing`; jangan jalankan pada production.

Data yang dibuat:

| Jenis | Isi |
| --- | --- |
| Tenant | `FSOS_DEMO` / FSOS Frontend Demo |
| User login | `frontend-admin` dengan password development `DemoFrontend123!` |
| Role/permission | Role `FRONTEND_ADMIN` dengan permission master, transaksi, dashboard, traceability, telemetry, notification |
| Master | Kitchen, cold/dry storage, zone/rak, supplier, dua raw material, school, driver, vehicle, device temperature/GPS, binding, food item, recipe, packaging type |
| Workflow | Receiving bahan, putaway, stock issue QC, production batch, package, delivery, school receiving, consumption |
| IoT | Temperature storage, temperature vehicle, GPS route dan alarm suhu demo |
| Incident | Complaint via package demo, report-ready traceability, recall, withdrawal evidence dan notification outbox |

ID dan kode penting untuk frontend:

| Kebutuhan frontend | Nilai demo |
| --- | --- |
| Login tenant | `FSOS_DEMO` lewat field `tenant`; `tenant_id` output JSON tetap tersedia |
| Username | `frontend-admin` |
| Password | `DemoFrontend123!` |
| Package scan | `PKG-2026-0001` |
| Production batch | `MO-2026-0001` |
| Vehicle | `VH-BOX-01` |
| School | `SCH-DEMO-01` |

Jalankan setelah migrasi dan runtime role:

```powershell
.\venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\venv\Scripts\python.exe backend\scripts\provision_runtime_role.py
.\venv\Scripts\python.exe backend\scripts\seed_demo_ready.py
```

Output JSON memuat `tenant_id`, username/password demo, jumlah record baru,
package_code, complaint_id dan recall_id. Pengulangan normal tidak membuat duplikat.
Script tidak menghapus data existing, tidak reset sequence dan tidak mengubah record
yang sudah ada.

Endpoint frontend yang langsung dapat dicoba setelah seed demo:

| Layar | Endpoint |
| --- | --- |
| Login | `POST /api/v1/auth/login` dengan `tenant=FSOS_DEMO` |
| Dashboard | `GET /dashboard/home`, `/dashboard/storage-temperatures`, `/dashboard/notifications` |
| Tracking | `GET /deliveries/{delivery_id}/tracking` dari daftar delivery |
| Complaint scan | `POST /complaints` dengan `package_code=PKG-2026-0001` dan school demo |
| Incident dashboard | `GET /complaints/reports` dan `GET /complaints/{complaint_id}/report` |
| Traceability | Gunakan asset UUID dari report untuk passport/impact |
| Recall | `GET /recalls`, `GET /recalls/{recall_id}`, withdrawal list |
| Notification | `GET /notifications`, mark sent/failed untuk item pending |

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
