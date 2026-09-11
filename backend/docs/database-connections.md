# Koneksi runtime dan administratif

Konfigurasi memisahkan dua pool SQLAlchemy:

| Konfigurasi | Pemakai | Kebutuhan |
| --- | --- | --- |
| DATABASE_URL | API, readiness, check_database, CLI backfill/reconcile registry | Login aplikasi dengan grant fsos_runtime |
| ADMIN_DATABASE_URL | Alembic online/offline, seed, provisioning role, create/maintain partitions | Owner/migration credential terpisah |

Pool dibuat secara lazy dan ditutup terpisah. Jalur administratif **tidak fallback**
ke DATABASE_URL ketika ADMIN_DATABASE_URL kosong. API tidak perlu membuat pool admin
untuk health/readiness atau service bisnis. Kedua URL tetap memakai driver
postgresql+asyncpg. Schema saat ini revisi 0022 (hingga penerimaan sekolah dan konsumsi).

## Bootstrap development lokal

Dari root proyek, setelah role/profile migrasi 0022 tersedia:

```powershell
.\venv\Scripts\python.exe backend\scripts\configure_runtime_login.py
```

Script khusus ENVIRONMENT=development ini membaca backend/.env langsung dan menolak
override DATABASE_URL/ADMIN_DATABASE_URL/ENVIRONMENT dari environment shell agar
file lokal tidak diarahkan ke database lain tanpa sengaja.

Urutannya:

1. Pilih ADMIN_DATABASE_URL atau, pada instalasi lama, DATABASE_URL owner yang ada.
2. Provisioning ulang profil fsos_runtime sesuai revisi 0022.
3. Buat login fsos_app dengan secret acak 48 byte dari generator kriptografis,
   disimpan PostgreSQL sebagai SCRAM-SHA-256. LOGIN bukan superuser, owner objek,
   pembuat database/role, replication, atau BYPASSRLS. Membership hanya fsos_runtime.
4. Simpan calon konfigurasi ke backend/.env.runtime.pending sebelum transaksi
   pembuatan login commit. File ini diabaikan Git dan memuat secret; jangan dibagikan.
5. Verifikasi koneksi fsos_app, akses baca schema, serta penolakan capability
   CREATE/TEMP/insert history langsung/maintenance.
6. Ganti backend/.env secara atomik: DATABASE_URL memakai fsos_app,
   ADMIN_DATABASE_URL mempertahankan koneksi owner. Secret tidak dicetak ke output.

Pengulangan memakai secret tersimpan dan tidak merotasinya. Role nama sama yang
tidak memiliki marker pengelolaan, atribut berlebihan, kepemilikan objek, atau
membership administratif ditolak. Bila proses terhenti sesudah commit role tetapi
sebelum mengganti .env, pending file dapat dipakai pada pengulangan; jangan menghapusnya
sebelum investigasi. Bila secret tidak cocok atau konfigurasi konflik, script gagal
tanpa mereset password akun existing. Error output hanya error_type dan petunjuk umum.

Script tidak membuat akun login frontend. fsos_app adalah kredensial server
PostgreSQL, bukan JWT, API key device, atau user tabel app_user.

## Verifikasi dan penggunaan harian

```powershell
.\venv\Scripts\python.exe backend\scripts\check_database.py
.\venv\Scripts\python.exe -m alembic check
.\venv\Scripts\python.exe backend\scripts\maintain_telemetry_partitions.py --check --months 6
```

Perintah pertama memeriksa jalur runtime; dua berikutnya memakai admin. Task
Windows partisi tetap menggunakan script yang sama, tetapi kini mengambil
ADMIN_DATABASE_URL. CLI backfill menggunakan runtime karena service sudah memiliki
grant registry yang diperlukan dan masih memeriksa actor/permission aplikasi.

Restart proses API/worker setelah perubahan konfigurasi; Settings dan engine
di-cache pada proses berjalan. Jangan menganggap proses lama otomatis berpindah
credential hanya karena file .env sudah berubah. Periksa readiness setelah restart.

## Production

Pada development, kedua secret berada dalam satu file .env lokal. Ini memisahkan
koneksi database, **bukan isolasi secret dari proses yang bisa membaca file itu**.
Production harus memberikan hanya DATABASE_URL kepada proses API, tanpa file .env
administratif yang bisa dibaca API. Berikan ADMIN_DATABASE_URL hanya kepada job
migrasi/provisioning/maintenance melalui mekanisme secret deployment.

Owner lokal lama masih superuser; production perlu owner migrasi khusus dengan
hak hanya pada objek aplikasi, TLS/kebijakan pg_hba yang sesuai, rotasi secret dan
pengujian deploy. Bootstrap otomatis ini bukan provisioning production. Profil
runtime tetap bukan RLS; query scope tenant dan RBAC service wajib dipertahankan.

## Frontend

Tidak ada perubahan endpoint, payload, response, atau event. Jangan menyalin
DATABASE_URL/ADMIN_DATABASE_URL ke variabel frontend, browser storage, atau repo.
User dev-maintenance tetap actor internal tanpa password login. Dokumentasi
[API frontend](frontend-api.md) tetap menjadi daftar endpoint yang dapat dipanggil.

## Riwayat verifikasi pemisahan koneksi (2026-09-11)

Konfigurasi fsos sudah dialihkan ke fsos_app; bootstrap ulang tidak mereset password.
Seluruh 55 tes lulus. Readiness mengembalikan 200, backfill registry berhasil melalui
runtime, seed dan Alembic check berhasil melalui admin, dan task partisi selesai
LastTaskResult=0 dengan 24 partisi siap. Password salah gagal terhubung (driver
melaporkan kode koneksi umum 08003); aturan host lokal memakai SCRAM-SHA-256.
Pengujian ini belum mencakup TLS atau isolasi secret production.
