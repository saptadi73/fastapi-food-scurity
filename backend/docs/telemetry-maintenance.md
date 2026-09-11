# Maintenance partisi dan retensi telemetry

Status 2026-09-11: rolling maintenance dan pemeriksaan partisi sudah tersedia.
Database fsos memiliki cakupan September 2026–Februari 2027: 24 partisi untuk
temperature/humidity/GPS/heartbeat. Tidak ada data dihapus, diarsipkan, atau
dipindahkan oleh maintenance ini. Tidak memerlukan migrasi schema baru.

## CLI pemeriksaan dan pembuatan

Dari root proyek:

```powershell
.\venv\Scripts\python.exe backend\scripts\maintain_telemetry_partitions.py --check --months 6
.\venv\Scripts\python.exe backend\scripts\maintain_telemetry_partitions.py --ensure --months 6 --report-file backend\logs\partitions.json
```

Pilih tepat satu mode. `--check` memeriksa catalog PostgreSQL tanpa DDL;
`--ensure` memanggil fungsi maintenance migrasi 0013 lalu memeriksa hasilnya.
Default start adalah hari pertama bulan UTC saat dijalankan, bukan tanggal lokal
Windows. `--months` 1..24, default 6 (bulan berjalan dan lima bulan berikutnya).
`--start YYYY-MM` dapat dipakai untuk kebutuhan backfill historis.

Pemeriksaan mencakup nama partisi standar, relasi ke parent public yang benar,
batas FROM/TO tepat bulan UTC, serta trigger UPDATE/DELETE/TRUNCATE yang aktif dan
menunjuk fungsi penolakan bukti pada parent/child. Ini tidak memeriksa isi fungsi,
hak role runtime, volume data, indeks lain, atau ruang disk. Trigger replica-only
dianggap tidak melindungi operasi normal. Format batas yang tidak dikenali
dilaporkan tidak siap, bukan dianggap valid.

| Exit | Arti |
| --- | --- |
| 0 | Cakupan yang diminta dan guard siap |
| 2 | Pemeriksaan selesai tetapi ada issue; ensure me-rollback DDL pada transaksi itu |
| 1 | Kegagalan koneksi/DDL/input operasional, dengan error_type tersanitasi |

JSON berisi ready, start, months, expected_partitions, issues, mode dan checked_at;
kegagalan exception dapat hanya berisi ready=false, error_type dan checked_at.
Reason issue: missing_partition, unexpected_bounds, missing_or_disabled_guard.
Mode ensure memakai lock_timeout 5 detik dan statement_timeout 30 detik per
statement. Tidak otomatis memperbaiki batas partisi salah atau mengaktifkan guard
yang dinonaktifkan. Investigasi issue sebelum memakai DDL perbaikan administratif.

Contoh hasil:

```json
{
  "ready": true,
  "start": "2026-09",
  "months": 6,
  "expected_partitions": 24,
  "issues": [],
  "mode": "ensure",
  "checked_at": "2026-09-11T02:48:24+00:00"
}
```

## Tugas development Windows

Task `FSOS-Telemetry-Partitions-Development` sudah didaftarkan pada komputer ini.
Menjalankan venv pythonw.exe dan CLI ensure enam bulan setiap hari pukul 08:00
waktu lokal, serta ketika user pemilik task logon. Task berjalan tersembunyi
dengan hak user biasa, hanya saat user tersebut login; tidak menyimpan password.
StartWhenAvailable aktif, instance tumpang tindih diabaikan, batas runtime 5 menit.
Ini bukan scheduler production yang tetap berjalan tanpa sesi user.

File registrasi dapat dijalankan untuk setup ulang pada mesin development:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File backend\scripts\register_partition_task.ps1
Get-ScheduledTaskInfo -TaskName FSOS-Telemetry-Partitions-Development
Get-Content backend\logs\partitions.json
```

Bypass hanya berlaku pada proses tersebut, tidak mengubah execution policy sistem.
Task existing dengan executable/arguments berbeda ditolak, tidak ditimpa.
Jika sama, script mempertahankan task; tidak merekonsiliasi perubahan manual
pada trigger/settings. Folder proyek atau venv yang dipindahkan memerlukan
peninjauan dan registrasi task ulang.

Laporan JSON ditimpa setiap run yang dapat menulis file. Periksa LastTaskResult,
ready/issues dan checked_at; laporan lama tidak membuktikan run terbaru berhasil.
File log diabaikan Git. Tidak ada alert email/WhatsApp otomatis saat task gagal.
Task memakai backend/.env; batasi akses file itu karena akun lokal masih memiliki
hak database luas. Saat production, gunakan role maintenance terpisah dan scheduler
server (belum diimplementasikan), bukan menyalin task development begitu saja.

## Backfill historis

1. Tentukan rentang bulan dari recorded_at asli dalam UTC.
2. Jalankan ensure dengan --start dan --months yang sesuai; periksa ready=true.
3. Import melalui ingestion tervalidasi ketika modulnya tersedia, dengan identitas
   pesan/event stabil. Jangan menggeser timestamp agar masuk partisi yang sudah ada.
4. Uji jumlah record, timestamp minimum/maksimum, tenant dan duplikasi setelah import.

Tidak ada default partition. Data di luar rentang yang disiapkan tetap ditolak.
Global deduplication masih pekerjaan ingestion; PK UUID+recorded_at hanya mencegah
pasangan identik, bukan UUID sama pada timestamp lain.

## Retensi dan arsip

Target berikut berasal dari docs/08 bagian 22, yang masih berstatus draft:

| Data | Target retensi draft |
| --- | --- |
| Temperature | 1 tahun |
| GPS | 1 tahun |
| Heartbeat | 6 bulan |
| Alarm | 5 tahun |
| Recall | Permanen |
| Humidity dan jenis lainnya | Belum ditentukan dokumen |

Saat ini kebijakan operasional adalah **mempertahankan seluruh bukti**. Target
draft tidak mengaktifkan DROP/DELETE otomatis. Dokumen juga mewajibkan bukti tidak
dihapus; kebijakan pemindahan arsip dan akses ulang harus disepakati sebelum data
dikeluarkan dari database online. Jangan menganggap usia data sebagai izin menghapus.

Runbook persiapan arsip: pilih partisi yang seluruh rentang waktunya melewati
cutoff; pastikan tidak terkait investigasi/recall berjalan; ekspor secara konsisten
beserta manifest schema, tenant/rentang waktu, jumlah row dan checksum; verifikasi
checksum serta restore/query pada database terpisah; tetapkan penyimpanan cadangan
dan jalur pencarian bukti sebelum mempertimbangkan pelepasan partisi online.
Script ekspor/restore, media arsip, kebijakan data investigasi, cutoff humidity,
dan proses persetujuan pelepasan belum dibuat. Maintenance saat ini hanya membuat
partisi dan memeriksa guard, tanpa DETACH/DROP/DELETE/TRUNCATE.

## Frontend dan pengujian

Tidak ada endpoint HTTP atau event runtime baru. `/api/v1/ready` masih memeriksa
database/extension/revisi, bukan cakupan partisi; dashboard belum dapat membaca
laporan maintenance melalui API. CLI/admin harus memantau hasil task terpisah.

21 tes terkait lulus, termasuk lintas tahun/tahun kabisat, input invalid, cakupan
hilang, ensure berulang, batas bulan salah, serta guard dinonaktifkan pada database
uji. Pemeriksaan fsos setelah ensure melaporkan 24 partisi siap dan Alembic check
tanpa perubahan schema.

## Koneksi administratif

Script create/maintain partitions dan task Windows kini mengambil
ADMIN_DATABASE_URL dari konfigurasi backend, bukan pool runtime DATABASE_URL.
Task lokal sudah dijalankan ulang setelah pemisahan dan selesai LastTaskResult=0.
Lihat [panduan koneksi](database-connections.md) untuk konfigurasi deployment.
