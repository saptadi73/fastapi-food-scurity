# Registry digital asset

Status 2026-09-11: adapter sumber, service sinkronisasi, backfill administratif,
rekonsiliasi laporan sumber, dan integrasi transaksi KitchenRepository tersedia. Tidak ada endpoint baru,
publisher event, atau traversal graph. Tidak memerlukan migrasi baru.

## Pemetaan sumber

`entity_uuid` adalah primary key tabel sumber, bukan UUID registry. Khusus DEVICE,
gunakan device_id internal; device_uuid publik dipakai telemetry, bukan adapter ini.
Tipe aset peka huruf besar/kecil dan dibatasi daftar berikut.

| asset_type | Tabel / primary key | Sumber name |
| --- | --- | --- |
| SUPPLIER | supplier / supplier_id | supplier_name |
| KITCHEN | kitchen / kitchen_id | kitchen_name |
| STORAGE | storage / storage_id | storage_name |
| VEHICLE | vehicle / vehicle_id | plate_number |
| SCHOOL | school / school_id | school_name |
| DEVICE | device / device_id | device_name |
| RAW_MATERIAL | raw_material / raw_material_id | material_name |
| RAW_MATERIAL_BATCH | raw_material_batch / raw_material_batch_id | batch_code |
| PRODUCTION_BATCH | production_batch / production_batch_id | batch_code |
| PACKAGE | package / package_id | package_code |
| DELIVERY | delivery / delivery_id | Tipe + UUID |
| RECEIVING | receiving / receiving_id | Tipe + UUID |
| CONSUMPTION | consumption / consumption_id | Tipe + UUID |
| COMPLAINT | complaint / complaint_id | Tipe + UUID |
| RECALL | recall / recall_id | Tipe + UUID |

Jenis lain tidak diterima sampai adapter dan tes ditambahkan. Status disalin dari
sumber; tabel tanpa status menggunakan RECORDED. Adapter tidak menyimpulkan
keamanan pangan dari data sumber.

Registry baru memakai UUID baru untuk asset_uuid dan string entity_uuid untuk
code. Ini menghindari benturan kode bisnis yang hanya unik dalam kitchen atau
supplier. Label manusia tersimpan di name. Registry lama mempertahankan code dan
asset_uuid, sehingga referensi graph/movement tidak berpindah identitas.

## Service dan transaksi

`RegistryService(session, trusted_scope)` menyediakan:

| Method | Input | Hasil |
| --- | --- | --- |
| sync | asset_type, entity_id | Dict record registry |
| reconcile | asset_type, after_id UUID registry opsional, limit 1..200 (default 100) | Satu halaman hasil pemeriksaan; rincian di bawah |
| backfill | asset_type, after_id opsional, limit 1..200 (default 100) | processed dan last_id; last_id null bila tidak ada sumber |

Ketiga operasi memerlukan actor/tenant aktif dan permission `AssetRegistry.Sync`
melalui rantai RBAC yang belum soft-deleted. Permission tidak diberikan otomatis.
Tipe tidak dikenal menghasilkan ValueError; sumber tidak ada atau tenant berbeda
menghasilkan RecordNotFoundError. Error actor/permission mengikuti guard internal.
Belum ada pemetaan error HTTP atau request body frontend.

Adapter mengunci sumber lalu registry dalam transaksi caller. Pendaftaran pertama
untuk sumber yang sama terserialisasi. Identitas dipilih berdasarkan tenant/type/
entity; caller tidak bisa memasok nama, status, atau identitas registry arbitrer.
Jika field proyeksi sama, hasil tidak berubah dan version tidak bertambah.
Jika berubah, name/status/deleted_at/deleted_by disinkronkan, version bertambah
satu, updated_by diisi actor penyinkron dan updated_at diisi waktu database.

Sumber soft-deleted tetap dapat diregistrasi untuk kebutuhan riwayat; registry
menyalin deleted_at/deleted_by tanpa menghapus graph/movement. Jika sumber dipulihkan,
sync berikutnya menyalin kondisi tersebut. Actor deleted_by berasal dari sumber,
bukan diganti oleh actor backfill. Audit sumber tetap memerlukan validasi pada
jalur tulis sumber. Nama terlalu panjang/data invalid atau konflik code registry
ditolak constraint database; tidak dipotong atau ditimpa secara diam-diam.

KitchenRepository kini memanggil primitive internal `sync_source` setelah create,
update dan soft_delete. Otorisasi jalur domain berasal dari pemeriksaan kitchen;
tidak memerlukan permission backfill tambahan. Primitive tersebut bukan API dan
tidak melakukan autentikasi sendiri, seperti akses SQL internal. Service modul
lain wajib mengotorisasi lalu melakukan write sumber dan sync dalam satu transaksi.
Untuk ORM pending changes, flush sumber terlebih dahulu.

Tidak ada commit/rollback di adapter/service/repository. Caller harus rollback
seluruh unit of work jika salah satu langkah gagal, dan tidak boleh menangkap
error sync lalu commit perubahan sumber saja. Gunakan transaksi singkat;
multi-entity sinkronisasi harus memakai urutan lock konsisten untuk mengurangi
deadlock. Aplikasi tetap harus menangani retry transaksi bila terjadi deadlock.

## Backfill administratif

Dari root proyek, isi UUID tenant dan actor yang sudah memiliki permission:

```powershell
.\venv\Scripts\python.exe backend\scripts\backfill_asset_registry.py --tenant TENANT_UUID --actor ACTOR_UUID --asset-type KITCHEN --batch-size 100
```

Placeholder UUID harus diganti. Script memakai DATABASE_URL lokal tanpa mencetak
URL/password. Script tidak membuat user atau memberi permission. Tiap batch commit
sendiri, cursor berdasarkan UUID sumber; kegagalan me-rollback batch berjalan,
batch sebelumnya tetap tersimpan. Aman dijalankan ulang dari awal, termasuk setelah
gagal. `processed` menghitung sumber yang diperiksa, bukan jumlah insert baru.

Contoh output sukses: `{"processed": 12, "asset_type": "KITCHEN"}`.
Exit 0 berarti scan selesai, exit 1 berarti gagal dengan error_type tersanitasi.
Untuk sumber yang ditambah/diubah selama scan, ulangi backfill; cursor bukan snapshot
global dan dapat melewatkan insert baru dengan UUID sebelum posisi cursor.

Backfill sudah dijalankan pada tenant FSOS_DEV melalui [seed development](development-seed.md)
dengan actor/permission khusus development; tenant lain belum otomatis diproses.
Tidak ada penjadwalan otomatis. Script tidak menghapus registry yatim; raw SQL yang
menghapus sumber atau mengubah identitas dapat membuat referensi registry tidak
valid karena belum ada FK polimorfik. Rekonsiliasi di bawah mendeteksi sumber
hilang; pemulihan sumber dan kebijakan penghapusannya memerlukan penanganan operator.

## Batas integrasi

Sinkronisasi otomatis baru terhubung ke KitchenRepository. Adapter seluruh tipe
tersedia, tetapi service tulis modul lain harus dihubungkan saat diimplementasikan.
SQL langsung tidak otomatis memicu sync. Belum ada API registry, event deduplication,
graph builder/traversal, atau publisher. Tes mencakup seluruh adapter dengan sumber
nyata, scope, permission, retry identik, pagination, perubahan, soft delete serta
rollback transaksi. Ini belum stress test writer paralel.

## Rekonsiliasi registry (laporan tanpa mutasi)

RegistryService.reconcile memeriksa satu tipe/tenant per halaman dengan permission
AssetRegistry.Sync yang sama. Jalur ini memakai DATABASE_URL runtime dan tidak
memerlukan grant baru atau migrasi. Pemeriksaan mencakup registry soft-deleted.
Source dicocokkan lewat tenant_id dan primary key adapter; UUID yang hanya ada
pada tenant atau tipe lain dilaporkan SOURCE_MISSING tanpa membuka data tersebut.

```powershell
.\venv\Scripts\python.exe backend\scripts\reconcile_asset_registry.py --tenant TENANT_UUID --actor ACTOR_UUID --asset-type KITCHEN --batch-size 100
```

Ganti placeholder dengan UUID actor/tenant yang berwenang. --after menerima UUID
asset_uuid dari next_cursor halaman sebelumnya, bukan UUID sumber untuk backfill.
Input limit harus integer 1..200; tipe aset mengikuti tabel adapter di atas.
Tidak ada request HTTP, payload frontend, JWT, atau endpoint baru.

Contoh hasil satu halaman (UUID ilustratif):

```json
{
  "asset_type": "KITCHEN",
  "processed": 1,
  "issue_count": 1,
  "items": [
    {
      "asset_uuid": "11111111-1111-4111-8111-111111111111",
      "entity_uuid": "22222222-2222-4222-8222-222222222222",
      "version": 2,
      "state": "SOURCE_MISSING",
      "changed_fields": [],
      "source_deleted": null
    }
  ],
  "last_id": "11111111-1111-4111-8111-111111111111",
  "next_cursor": null
}
```

| Field | Tipe / arti |
| --- | --- |
| asset_type | String tipe yang diminta |
| processed | Integer jumlah registry yang diperiksa pada halaman ini |
| issue_count | Integer jumlah SOURCE_MISSING + PROJECTION_MISMATCH pada halaman |
| items | Array hasil; kosong bila tidak ada record setelah cursor |
| items[].asset_uuid / entity_uuid | UUID registry / UUID sumber yang disimpan registry |
| items[].version | Integer versi registry saat diperiksa; tidak ditambah oleh scan |
| items[].state | IN_SYNC, SOURCE_MISSING, atau PROJECTION_MISMATCH |
| items[].changed_fields | Array nama field berbeda: name, status, deleted_at, deleted_by; kosong untuk missing/in-sync |
| items[].source_deleted | Boolean kondisi soft delete sumber; null jika sumber tidak ditemukan |
| last_id | UUID registry terakhir pada halaman, null jika kosong |
| next_cursor | UUID untuk --after bila masih ada halaman, selain itu null |

IN_SYNC berarti proyeksi sesuai sumber pada saat query, bukan jaminan keamanan
pangan. PROJECTION_MISMATCH membandingkan empat field proyeksi yang sama dengan
sync; code dan identitas registry lama memang dipertahankan dan tidak dibandingkan.
Tabel tanpa status memakai RECORDED; label fallback mengikuti adapter. Sumber
soft-deleted masih ditemukan dan bukan SOURCE_MISSING.

Exit 0: halaman bersih. Exit 2: halaman memiliki temuan. Exit 1: gagal dengan
JSON error_type tersanitasi (misalnya PermissionDeniedError atau InvalidActorError).
Kesalahan sintaks argumen CLI memakai pesan argparse dan exit 2 tanpa laporan JSON.
Selalu periksa next_cursor; exit 0 tidak menyatakan seluruh registry bersih jika
masih ada halaman. Tidak ada hitungan total lintas halaman atau semua tenant.

Setiap halaman memakai satu statement JOIN untuk snapshot data registry/sumber.
Guard actor/permission tetap mengambil shared lock dalam transaksi singkat.
Tidak ada INSERT/UPDATE/DELETE, perubahan version/audit, penghapusan graph/movement,
atau event yang diterbitkan. Laporan tidak dipersist sebagai bukti insiden.
Pagination UUID bukan snapshot global: insert/perubahan selama scan dapat terlewat;
ulangi scan setelah aktivitas tulis selesai bila membutuhkan hasil konsisten.

Tindak lanjut operator:

1. Untuk PROJECTION_MISMATCH, periksa sumber lalu jalankan sync/backfill resmi;
   sumber dibaca ulang dan dikunci pada transaksi sinkronisasi.
2. Untuk SOURCE_MISSING, investigasi import, tenant/type/UUID dan pemulihan sumber.
   Jangan menghapus registry yang mungkin masih dirujuk graph atau movement.
3. Jalankan rekonsiliasi kembali setelah perbaikan. Sumber yang belum memiliki
   registry tidak terdeteksi oleh scan ini; gunakan backfill untuk arah tersebut.

Otomatisasi pemulihan sumber, scheduler rekonsiliasi, endpoint laporan dan
notifikasi belum tersedia.

## Verifikasi rekonsiliasi (2026-09-11)

Seluruh 56 tes lulus, termasuk proyeksi pada 15 adapter, permission dicabut/actor
nonaktif, lintas tenant/tipe, sumber hilang, soft delete, pagination, validasi input,
pelestarian record registry dan eksekusi dengan grant fsos_runtime. Ruff bersih.
Scan development FSOS_DEV melalui koneksi runtime mencakup 15 tipe: enam registry
diperiksa, issue_count=0. Ini hanya keadaan tenant tersebut saat scan, bukan
sertifikasi integritas seluruh database atau penilaian keamanan pangan.
