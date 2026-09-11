# Akses minimum supplier dan bahan

Supplier.Read/Write, RawMaterial.Read/Write dan SupplierMaterial.Read/Write sudah
diberikan eksplisit ke DEV_MAINTENANCE, tenant FSOS_DEV lokal, sebagai dependensi
minimum API bisnis. Tidak membuat user/password/membership atau fixture transaksi.
Role lain tidak berubah. Frontend muat ulang /auth/me untuk snapshot permission.

CLI development menggunakan ADMIN_DATABASE_URL:

```powershell
.\venv\Scripts\python.exe backend/scripts/provision_supply_permissions.py --tenant <tenant_uuid> --actor <actor_uuid> --role <role_uuid> --permission Supplier.Read --permission Supplier.Write --permission RawMaterial.Read --permission RawMaterial.Write --permission SupplierMaterial.Read --permission SupplierMaterial.Write
```

Default check tanpa penulisan; --apply membuat permission/grant yang belum ada.
--permission dapat diulang untuk subset sembilan kode di atas, tanpa duplikat. Actor/tenant
harus aktif, role harus nondeleted dalam tenant. Permission/grant soft-deleted ditolak,
bukan dipulihkan. Kode di luar allowlist dan environment selain development ditolak.
Semua target diperiksa sebelum insert; transaksi dan advisory lock tenant menjaga
operasi berulang. Grant aktif tidak diganti UUID/audit/version.

Output JSON: mode, tenant_id, role_id, permissions, missing_permissions/grants
(jumlah sebelum operasi), created_permissions/grants. Exit 0 sukses, 1 gagal
tersanitasi (error_type/action), 2 argumen CLI invalid. Operator memakai koneksi admin;
actor UUID untuk audit bukan autentikasi admin HTTP. Helper tidak boleh diekspos publik.

Runtime kini mendapatkan INSERT supplier/raw_material/supplier_material serta UPDATE
kolom definisi/audit/version yang diperlukan. Tidak memberi hard delete/DDL/UPDATE
tenant. Satuan bahan dilindungi application service; tidak ada konversi satuan.
Profil diterapkan pada fsos tanpa migrasi dengan provision_runtime_role.py.

Tidak ada perluasan seed otomatis atau event permission.changed. Ini akses minimum
fitur supplier/bahan, bukan pekerjaan provisioning umum/production. Lihat
[kontrak frontend](frontend-api.md#kontrak-supplier-bahan-dan-relasi).


## Permission Delete

Allowlist kini sembilan kode: Read, Write dan Delete untuk Supplier, RawMaterial, SupplierMaterial.
Permission Supplier.Delete, RawMaterial.Delete, SupplierMaterial.Delete telah ditambahkan
ke DEV_MAINTENANCE lokal. Gunakan --permission <kode.Delete> pada CLI yang sama;
check default, --apply eksplisit, revoked grant tetap tidak dipulihkan. Delete
independen dari Read/Write. Tidak ada membership/user/password baru.

Profil runtime mengizinkan UPDATE deleted_at/deleted_by pada tabel terkait untuk
soft delete. Tidak memberi privilege DELETE SQL. Kontrak respons dan proteksi
referensi: [soft delete](frontend-api.md#soft-delete-master-operasional).
