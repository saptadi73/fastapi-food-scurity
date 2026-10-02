# Exhibition / live demo runbook

Skrip ini dibuat khusus untuk demo pameran (exhibition) dan latihan berulang,
terpisah dari seed development (`FSOS_DEV`) dan seed frontend (`FSOS_DEMO`).
Seed dan flow demo tetap ditujukan untuk environment development/testing.
`demo_cleanup.py` adalah pengecualian terkontrol: tidak memerlukan perubahan
`ENVIRONMENT`, hanya mengizinkan tenant disposable `FSOS_EXPO`, dan tetap wajib
menggunakan `--confirm`.

## Dua tenant terpisah (disarankan)

`seed_exhibition_masters.py` dan `seed_exhibition_incident.py` menerima
`--tenant-code` (deterministik, tidak bentrok ID antar tenant). Disarankan pakai
dua tenant terpisah supaya reset demo live tidak pernah menghapus skenario
insiden yang sudah jadi, dan sebaliknya:

| Tenant | Untuk apa | Direset dengan `demo_cleanup.py`? |
| --- | --- | --- |
| `FSOS_EXPO` (default) | Demo live end-to-end (`demo_live_flow.py`), boleh diulang berkali-kali | Ya, bebas direset antar sesi |
| `FSOS_EXPO_INCIDENT` | Skenario insiden/recall yang SUDAH JADI, cukup dibuka-tutup untuk demo traceability | Tidak perlu direset; jangan panggil `demo_cleanup.py` dengan tenant ini kecuali sengaja mau membuat ulang skenario |

Kalau Anda tetap ingin satu tenant saja (lebih simpel, cukup untuk latihan
sendiri), lewati saja `--tenant-code` dan biarkan default `FSOS_EXPO` dipakai
keduanya — skrip tetap idempotent dan aman dijalankan bersamaan di satu tenant.

## Login demo

Dibuat oleh `seed_exhibition_masters.py` untuk setiap tenant yang di-seed
(`FSOS_EXPO` maupun `FSOS_EXPO_INCIDENT`). Isi kode tenant sesuai tenant yang dipakai.

| Tenant | Role | Username | Password |
| --- | --- | --- | --- |
| `FSOS_EXPO` / `FSOS_EXPO_INCIDENT` | `ADMIN` | `expo-admin` | `ExpoDemo123!` |
| `FSOS_EXPO` / `FSOS_EXPO_INCIDENT` | `GURU` | `guru-sd-expo-01` | `GuruExpo123!` |
| `FSOS_EXPO` / `FSOS_EXPO_INCIDENT` | `OPERATOR_SEKOLAH` | `operator-sd-expo-01` | `OperatorExpo123!` |

Username admin mengikuti `--username` bila seed dijalankan dengan flag tersebut.
Kredensial ini khusus demo; jangan dipakai pada tenant atau server production.
Output JSON seed juga mencetak `roles` dan `role_passwords` sebagai pengingat.

## Urutan sebelum hari-H

```powershell
.\venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\venv\Scripts\python.exe backend\scripts\provision_runtime_role.py

# Tenant untuk demo live (reset bebas antar sesi)
.\venv\Scripts\python.exe backend\scripts\seed_exhibition_masters.py --tenant-code FSOS_EXPO

# Tenant terpisah khusus skenario insiden (jangan direset)
.\venv\Scripts\python.exe backend\scripts\seed_exhibition_masters.py --tenant-code FSOS_EXPO_INCIDENT
.\venv\Scripts\python.exe backend\scripts\seed_exhibition_incident.py --tenant-code FSOS_EXPO_INCIDENT
```

Di Linux/server, jika `backend/.env` memakai `ENVIRONMENT=production`, gunakan
`ENVIRONMENT=development` hanya pada command seed berikut; file `.env` tidak perlu
diubah. Master dan incident harus memakai `--tenant-code` yang sama:

```bash
ENVIRONMENT=development python backend/scripts/seed_exhibition_masters.py \
  --tenant-code FSOS_EXPO

ENVIRONMENT=development python backend/scripts/seed_exhibition_masters.py \
  --tenant-code FSOS_EXPO_INCIDENT
ENVIRONMENT=development python backend/scripts/seed_exhibition_incident.py \
  --tenant-code FSOS_EXPO_INCIDENT
```

Jangan langsung menjalankan `seed_exhibition_incident.py` pada tenant yang belum
di-seed master. Script incident membutuhkan kitchen, school, menu, packaging
type, dan master lain dari tenant yang sama. Jika muncul `Kitchen not found; run
seed_exhibition_masters.py first (matching --tenant-code)`, jalankan command
master untuk tenant tersebut terlebih dahulu; jangan mengganti ke tenant lain.

**Selalu jalankan `alembic upgrade head` dulu dan periksa hasilnya** (lihat
troubleshooting di bawah) — seed exhibition memakai tabel `UserLocationAssignment`
dan `SignatureEvidence` yang baru ada sejak migrasi `20260924_0036`/`0037`.
Tanpa migrasi ini, seed akan gagal atau role GURU/OPERATOR_SEKOLAH tidak bisa
menandatangani penerimaan.

`seed_exhibition_masters.py` membuat login demo (`expo-admin` /
`ExpoDemo123!` pada tenant yang dipilih), satu dapur, cold/dry storage, tiga
pemasok, enam bahan baku (dua bahan punya lebih dari satu sumber pemasok),
empat sekolah terdaftar (jumlah siswa bervariasi), satu armada + sopir, dua
jenis kemasan, dan tiga menu dengan resep. Tidak ada transaksi (receiving,
produksi, pengiriman) di skrip ini — harus dijalankan sekali per tenant_code
yang dipakai, termasuk untuk tenant insiden.

## Menjalankan server backend secara lokal

```powershell
c:/projek/fastapi-Food-Security/venv/Scripts/python.exe -m uvicorn main:app --app-dir backend --port 8001 --reload
```

Entrypoint FastAPI ada di `backend/main.py` (bukan `backend/app/main.py`).
Dengan `--app-dir backend`, module yang dipanggil uvicorn adalah **`main:app`**,
bukan `app.main:app` — kesalahan ini menghasilkan
`ModuleNotFoundError`/`Could not import module "app.main"`.

## Konvensi role registrasi user

Role bersifat bebas per-tenant (`role_code` string), bukan enum tetap. Skrip
`seed_exhibition_masters.py` membuat konvensi contoh untuk didemokan:

| role_code | Untuk siapa | Hak akses |
| --- | --- | --- |
| `ADMIN` | `expo-admin` / `ExpoDemo123!` | Akses penuh, sama seperti `EXPO_ADMIN` |
| `GURU` | `guru-sd-expo-01` / `GuruExpo123!` | `SchoolReceiving.Sign`, `Signature.Verify`, `Complaint.*`, ditugaskan (assignment) ke `SCH-EXPO-01` |
| `OPERATOR_SEKOLAH` | `operator-sd-expo-01` / `OperatorExpo123!` | `SchoolReceiving.Write/Read`, `Consumption.*`, `Complaint.*`, ditugaskan ke `SCH-EXPO-01` |

Password sengaja dibedakan per role (bukan satu password untuk semua) supaya
salah ketik username saat demo tidak diam-diam berhasil login sebagai role lain.

Tidak ada login siswa (`SISWA`); siswa hanya data penerima (`School.student_count`),
bukan akun pengguna. `GURU` di atas adalah pihak yang menandatangani (digital
signature) saat kemasan diterima di sekolah — endpoint
`POST /signatures/targets/school_receiving/{id}` mensyaratkan penanda tangan
punya `UserLocationAssignment` aktif ke sekolah tujuan.

`seed_exhibition_incident.py` membangun DI ATAS master yang sama satu skenario
insiden siap investigasi (bukan untuk dijalankan live): satu batch produksi,
empat kemasan ke empat sekolah, satu complaint `CONTAMINATION` berseverity
`HIGH` dan status `OPEN`, satu recall yang sudah dieksekusi, serta satu bukti
penarikan fisik. Status `OPEN` sengaja dipertahankan agar scan kemasan lain dari
batch `MO-INCIDENT-001` memunculkan warning. Gunakan ini untuk demo
traceability/forward-impact secara instan tanpa menjalankan seluruh alur di
depan audiens.

Setelah seed, scan `PKG-INCIDENT-001` untuk complaint asal dan
`PKG-INCIDENT-002` sampai `PKG-INCIDENT-004` untuk menunjukkan alert lintas
kemasan pada batch yang sama. Buka `GET /complaints/{complaint_id}/batch-impact`
untuk melihat seluruh kemasan, delivery, sekolah tujuan, penerimaan, dan status
konsumsi. Output JSON seed sekarang mencetak `complaint_id`, metadata incident,
kode kemasan, serta `demo_endpoints` agar presenter tidak perlu mencari UUID.

Seed tidak membuat foto atau tanda tangan palsu. Untuk mendemokan evidence,
unggah foto nyata lewat `POST /uploads/complaint-photo`, buat complaint melalui
alur UI, lalu capture tanda tangan melalui
`POST /signatures/targets/complaint/{complaint_id}`. Complaint seed tetap dapat
dipakai untuk demo warning dan batch-impact tanpa evidence tersebut.

Jika seed pernah dijalankan sebelum metadata incident tersedia, jalankan ulang
perintah yang sama. Skrip akan merekonsiliasi complaint deterministik miliknya
ke `CONTAMINATION`/`HIGH`/`OPEN` tanpa menghapus transaksi dan tanpa menimpa
referensi foto atau signature yang sudah ada. Output `reconciled: 1` berarti
record lama diperbarui; eksekusi berikutnya menghasilkan `reconciled: 0`.

## Saat demo live (alur utama, dijalankan di depan audiens)

```powershell
.\venv\Scripts\python.exe backend\scripts\demo_live_flow.py --tenant FSOS_EXPO --run-tag sesi1
```

Jika `FSOS_EXPO` harus sudah berisi transaksi sampai pengiriman aktif sebelum
frontend dibuka, gunakan mode persiapan berikut:

```powershell
.\venv\Scripts\python.exe backend\scripts\demo_live_flow.py `
  --base-url https://api.foodsecurity.online/api/v1 `
  --tenant FSOS_EXPO `
  --run-tag ready1 `
  --stop-after-depart
```

Mode ini membuat receiving, putaway, produksi, kemasan, manifest, dan
keberangkatan armada melalui REST API nyata, lalu berhenti saat delivery
`IN_TRANSIT`. Data akan muncul pada Penerimaan Bahan, Batch Produksi, Paket & QR,
Pengiriman Aktif, dan Live Tracking Delivery. Arrival, penerimaan sekolah, dan
konsumsi dilanjutkan dari frontend. Jangan memakai `run-tag` yang sama dua kali;
gunakan tag baru atau jalankan cleanup tenant demo terlebih dahulu.

Tanpa `--stop-after-depart`, skrip mempertahankan perilaku end-to-end lama dan
melanjutkan delivery sampai penerimaan sekolah serta konsumsi.

Skrip ini memanggil REST API sungguhan (login lalu POST/GET) sehingga semua
aturan bisnis nyata ikut teruji dan terlihat:

1. Penerimaan bahan (dua pemasok berbeda) dan pencetakan/penampilan QR batch.
2. Putaway ke storage sesuai tipe bahan.
3. Batch produksi dibuat, lalu dimulai dengan "scan" QR batch bahan sebagai
   sumber stok (mengurangi stok otomatis), lalu diselesaikan.
4. Kemasan dibuat dan holding time dimulai; QR kemasan ditampilkan. Kemasan
   lalu dirilis (`POST /packages/{id}/holding/finish` dengan `outcome=RELEASED`)
   karena manifest hanya menerima kemasan `RELEASED` yang belum kedaluwarsa.
5. Manifest pengiriman ke salah satu sekolah terdaftar.
6. **Cek "belum sampai"**: script mencoba mencatat penerimaan sekolah SEBELUM
   armada berangkat, lalu SAAT masih `IN_TRANSIT` — keduanya harus ditolak API
   (`409 Completed delivery and matching package/school manifest required`).
7. Armada berangkat lalu tiba (`depart` -> `complete`).
8. **Cek holding time**: script menampilkan `remaining_minutes` dan
   `timer_status` kemasan tepat sebelum penerimaan sekolah dicatat.
9. Penerimaan sekolah dan konsumsi dicatat; ringkasan akhir menampilkan kode
   produksi, kode/QR kemasan, sekolah tujuan, dan traceability passport
   (jumlah parent/child/movement) dari asset kemasan tersebut.

## Siapa dan di mana saat investigasi insiden

`GET /complaints/{id}/report` sekarang menyertakan `school_receivings[].received_by`
(nama/jabatan penanda tangan dari `signer_snapshot`, jika signature sudah
diambil lewat `POST /signatures/targets/school_receiving/{id}`) dan
`school_address`/`school_name` pada `current_location` serta setiap baris
`delivery_manifest`/`school_receivings`. Tanpa signature yang diambil,
`received_by` bernilai `null` — untuk demo insiden, jalankan capture signature
memakai akun `GURU` sebelum membuka laporan komplain agar "diterima oleh
siapa" terlihat, bukan hanya status `accepted` boolean.

Jalankan ulang dengan `--run-tag` berbeda (mis. `sesi2`) untuk mengulang tanpa
bentrok kode unik, atau reset dulu (lihat di bawah).

## Reset antar sesi demo

Jika reset dilakukan dari frontend, login sebagai `ADMIN` pada tenant `FSOS_EXPO`
lalu panggil `POST /api/v1/demo/reset` dari menu reset demo. Endpoint mengambil
tenant dari bearer session dan menolak tenant selain `FSOS_EXPO`; tidak perlu
masuk server atau menjalankan script. Frontend sebaiknya meminta konfirmasi
destruktif dan me-refresh dashboard setelah respons `200`.

Reset tidak lagi memerlukan perubahan `ENVIRONMENT` di `backend/.env`; server
dengan `ENVIRONMENT=production` (atau nilai lain) tetap bisa menjalankan reset
langsung tanpa mengedit `.env` dan tanpa restart API. Pengaman yang berlaku:

- `--confirm` wajib; tanpa flag ini argparse langsung menolak dan tidak ada koneksi DB.
- Hanya tenant `FSOS_EXPO` yang diterima (default `--tenant-code`). Tenant lain,
  termasuk `FSOS_EXPO_INCIDENT`, `FSOS_DEV` dan `FSOS_DEMO`, ditolak sebelum
  koneksi database dibuka.
- Seluruh penghapusan berjalan dalam satu transaksi memakai `ADMIN_DATABASE_URL`;
  bila satu langkah gagal, tidak ada data yang terhapus sebagian.

Windows (root proyek):

```powershell
.\venv\Scripts\python.exe backend\scripts\demo_cleanup.py --confirm
```

Linux/server (root proyek, venv aktif):

```bash
python backend/scripts/demo_cleanup.py --confirm
```

`--tenant-code FSOS_EXPO` boleh ditulis eksplisit, hasilnya sama. Contoh output
sukses (exit code 0, dipersingkat; output asli memuat semua tabel transaksi):

```json
{
  "tenant_code": "FSOS_EXPO",
  "tenant_id": "00000000-0000-0000-0000-000000000000",
  "removed": {"consumption": 1, "school_receiving": 1, "delivery": 1, "package": 1, "receiving": 2, "digital_asset": 7, "event_log": 20}
}
```

Output gagal (exit code 1) berbentuk `{"error_type": ..., "detail": ...}`, mis.
`demo_cleanup.py only permits the dedicated demo tenant FSOS_EXPO; refusing to
reset another tenant` atau `Tenant FSOS_EXPO not found; nothing to reset`
(jalankan `seed_exhibition_masters.py --tenant-code FSOS_EXPO` dulu).

Menghapus HANYA data transaksi tenant `FSOS_EXPO`:
receiving, batch, stok, produksi, kemasan, pengiriman, penerimaan sekolah,
konsumsi, komplain, recall/withdrawal, serta registry/movement/event terkait).
Master (dapur, storage, pemasok, bahan, sekolah, armada, menu, resep, login,
assignment lokasi user) tidak disentuh, sehingga seed master tidak perlu diulang.
Setelah reset tenant live,
langsung lanjut `demo_live_flow.py --tenant FSOS_EXPO` untuk sesi berikutnya;
tenant insiden tidak perlu disentuh sama sekali antar sesi. Untuk membuat ulang
skenario insiden, jalankan ulang `seed_exhibition_incident.py --tenant-code
FSOS_EXPO_INCIDENT` (idempotent) — bukan `demo_cleanup.py`.

## Menu/bahan yang dipakai skrip live

`demo_live_flow.py` secara default memakai menu `MENU-EXPO-UTAMA` (Nasi Ayam
Sayur Expo) dengan bahan `RM-EXPO-BERAS` (dari `SUP-EXPO-01`) dan
`RM-EXPO-AYAM` (dari `SUP-EXPO-02`), dikirim ke sekolah `SCH-EXPO-01`. Semua
argumen bisa diganti lewat flag CLI (`--menu-code`, `--material-codes`,
`--supplier-codes`, `--school-code`, `--vehicle-code`, `--planned-quantity`,
dll) untuk variasi antar sesi demo.

## Troubleshooting yang sudah pernah terjadi

| Gejala | Penyebab | Solusi |
| --- | --- | --- |
| `alembic -c backend\alembic.ini ...` gagal `No 'script_location' key found in configuration` | `%(here)s` di `backend/alembic.ini` tidak ter-resolve saat dipanggil dari root lewat `-c` | `cd backend` dulu lalu jalankan `python -m alembic <perintah>` tanpa `-c` |
| `alembic current` menunjukkan revisi lebih lama dari `alembic heads` | Migrasi belum diterapkan ke database (mis. `20260924_0036/0037/0038` belum jalan) | `cd backend; python -m alembic upgrade head`, lalu cek ulang `alembic current` sampai sama dengan `heads` |
| `ModuleNotFoundError: No module named 'pythonjsonlogger'` saat start uvicorn | Dependency di `requirements/base.txt`/`dev.txt` belum ter-install di venv | `pip install -r backend\requirements\dev.txt` (atau minimal `pip install python-json-logger`) |
| `Could not import module "app.main"` saat start uvicorn dengan `--app-dir backend` | Salah nama module; entrypoint adalah `backend/main.py`, bukan `backend/app/main.py` | Pakai `main:app`, bukan `app.main:app` |
| `seed_exhibition_incident.py` gagal `Kitchen not found` | Master tenant incident belum dibuat, atau `--tenant-code` berbeda antara dua script | Jalankan `ENVIRONMENT=development python backend/scripts/seed_exhibition_masters.py --tenant-code FSOS_EXPO_INCIDENT`, lalu ulangi seed incident dengan tenant code yang sama |
| `demo_cleanup.py` menolak karena environment bukan development | Versi skrip lama masih memakai guard `ENVIRONMENT` | Tarik versi terbaru; jangan mengubah `ENVIRONMENT` di `.env` server hanya untuk reset demo |
| `provision_runtime_role.py` keluar `{"error_type": "ValueError", ...}` | Head database berbeda dari `PROFILE_REVISION` profil grant | `alembic upgrade head`, lalu jalankan ulang; `detail` menampilkan revisi yang diharapkan dan aktual |
| `demo_live_flow.py` gagal `POST /deliveries -> 409 Package must be released and unexpired for dispatch` | Versi skrip lama tidak merilis kemasan (`holding/finish` `RELEASED`) sebelum manifest | Tarik versi terbaru; jalankan `demo_cleanup.py --confirm` atau pakai `--run-tag` baru karena run gagal sudah membuat receiving/produksi/kemasan |

Sebelum hari-H, jalankan urutan berikut sekali untuk memastikan lingkungan
siap tanpa kejutan di atas panggung:

```powershell
cd backend
python -m alembic current
python -m alembic heads
# Kalau current != heads:
python -m alembic upgrade head
cd ..
pip install -r backend\requirements\dev.txt
```
