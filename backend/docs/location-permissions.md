# Akses minimum master kitchen/storage/zone

Permission Read/Write awal: Kitchen.Read, Kitchen.Write, Storage.Read, Storage.Write,
StorageZone.Read dan StorageZone.Write. Sudah diterapkan ke role DEV_MAINTENANCE,
tenant FSOS_DEV lokal untuk memakai API master. Tidak membuat akun, password,
membership atau fixture bisnis. Role lain tetap memerlukan grant terpilih.

CLI development (ADMIN_DATABASE_URL) menggunakan pola administratif telemetry:

```powershell
.\venv\Scripts\python.exe backend/scripts/provision_location_permissions.py --tenant <tenant_uuid> --actor <actor_uuid> --role <role_uuid> --permission Kitchen.Read --permission Kitchen.Write --permission Storage.Read --permission Storage.Write --permission StorageZone.Read --permission StorageZone.Write
```

Default check tanpa penulisan; tambahkan --apply untuk membuat permission/grant
aktif yang belum ada. --permission dapat diulang untuk subset dari sembilan kode termasuk Delete di bawah. Tenant/actor harus aktif, role harus nondeleted dalam tenant. Kode duplikat,
permission di luar allowlist dan environment selain development ditolak. Permission
atau grant soft-deleted tidak dipulihkan; seluruh rencana divalidasi sebelum insert.
Grant yang sudah aktif tidak diganti UUID/audit/version. Transaksi dan advisory lock
per tenant menjaga operasi berulang; kegagalan rollback seluruh perubahan.

Koneksi admin adalah otoritas operator, UUID actor hanya identitas audit terverifikasi;
helper tidak boleh diekspos melalui endpoint runtime. Output JSON: mode check/apply,
tenant_id/role_id UUID string, permissions array string, missing_permissions/grants
(jumlah sebelum operasi), created_permissions/grants (0 pada check). Exit 0 sukses,
1 gagal dengan error_type/action tersanitasi, 2 argumen CLI invalid.

Profil database runtime telah diperbarui sebagai dependensi minimum fitur:
INSERT storage/storage_zone; UPDATE hanya definisi/audit/version yang diperlukan,
tanpa perubahan kitchen_id/storage_id induk, tenant, hard delete atau DDL.
Jalankan backend/scripts/provision_runtime_role.py dengan konfigurasi admin saat
memperbarui lingkungan development lain. Perubahan permission lokasi ini tidak menambah migrasi pada tahap 0017.
Untuk instalasi sekarang gunakan head 0022 dan [profil runtime terkini](runtime-database-role.md).

Frontend muat ulang /auth/me untuk snapshot permission terbaru. Endpoint mengecek
permission DB setiap request; Read/Write independen dan tidak memerlukan grant
AssetRegistry.Sync untuk sinkronisasi internal kitchen/storage.
Lihat [kontrak master](frontend-api.md#kontrak-master-kitchen-storage-zone).
Ini kebutuhan minimum modul, bukan perluasan seeding/provisioning umum.


## Permission Delete

Allowlist kini sembilan kode: Read, Write dan Delete untuk Kitchen, Storage, StorageZone.
Permission Kitchen.Delete, Storage.Delete, StorageZone.Delete telah ditambahkan
ke DEV_MAINTENANCE lokal. Gunakan --permission <kode.Delete> pada CLI yang sama;
check default, --apply eksplisit, revoked grant tetap tidak dipulihkan. Delete
independen dari Read/Write. Tidak ada membership/user/password baru.

Profil runtime mengizinkan UPDATE deleted_at/deleted_by pada tabel terkait untuk
soft delete. Tidak memberi privilege DELETE SQL. Kontrak respons dan proteksi
referensi: [soft delete](frontend-api.md#soft-delete-master-operasional).


## Akses sekolah

Allowlist lokasi bertambah School.Read, School.Write dan School.Delete (total 12 kode
untuk empat master). Ketiganya telah diprovision ke DEV_MAINTENANCE lokal; CLI dan
aturan check/apply/revoked grant tetap sama. Pilih --permission School.Read,
--permission School.Write dan --permission School.Delete sesuai kebutuhan.
Tidak membuat user/membership atau fixture sekolah.
Runtime memberi INSERT school serta UPDATE definisi/audit/version/deleted_at/deleted_by;
tidak mengizinkan perubahan tenant/kitchen_id, hard delete atau DDL. Profil telah
diterapkan di fsos tanpa migrasi. Frontend muat ulang /auth/me untuk permission.


## Akses kendaraan dan driver

Allowlist lokasi kini 18 kode untuk enam master: Kitchen, Storage, StorageZone,
School, Driver dan Vehicle masing-masing Read/Write/Delete. Enam kode Driver.* dan
Vehicle.* telah ditambahkan eksplisit ke DEV_MAINTENANCE lokal. Pilih setiap kode
melalui --permission pada CLI yang sama, default check dan --apply eksplisit.
Revoked grant tidak dipulihkan; tidak membuat user/membership atau fixture bisnis.
Runtime diberi INSERT driver/vehicle dan UPDATE definisi/audit/version/soft delete,
tanpa perubahan tenant/ID/hard delete. API vehicle boleh mengubah driver_id/gps_device
setelah validasi. Data GPS tetap memakai device_id internal; CRUD device belum tersedia.
