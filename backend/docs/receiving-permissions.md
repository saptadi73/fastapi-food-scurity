# Permission transaksi receiving sampai konsumsi

Status 2026-09-15: allowlist `RECEIVING_PERMISSIONS` berisi 34 kode eksplisit pada
`app/core/database/receiving_permissions.py`. Nama helper historis tetap receiving;
aksesnya kini mencakup seluruh alur sampai konsumsi, complaint intake, recall dasar,
notification outbox, traceability read dan dashboard home. Permission Read dan aksi
terpisah; Write tidak otomatis memberikan Read, Complete atau permission master.

| Modul | Permission |
|---|---|
| Receiving | Receiving.Read, Receiving.Write, Receiving.Complete, Receiving.Cancel |
| Batch bahan | RawMaterialBatch.Read |
| Stok | Stock.Read, Stock.Putaway, Stock.Issue |
| Produksi | Production.Read, Production.Write, Production.Start, Production.Complete, Production.Cancel |
| Paket | Package.Read, Package.Write |
| Holding paket | Holding.Start, Holding.Update, Holding.Finish |
| Pengiriman | Delivery.Read, Delivery.Write, Delivery.Depart, Delivery.Complete, Delivery.Cancel |
| Penerimaan sekolah | SchoolReceiving.Read, SchoolReceiving.Write |
| Konsumsi | Consumption.Read, Consumption.Write |
| Complaint | Complaint.Read, Complaint.Write |
| Recall | Recall.Read, Recall.Execute |
| Traceability | Traceability.Read |
| Dashboard | Dashboard.Read |
| Telemetry ingestion | Telemetry.Ingest |
| Notification | Notification.Read, Notification.Dispatch |

## Penggunaan administratif development

Jalankan dari root dengan ADMIN_DATABASE_URL, ENVIRONMENT=development dan UUID
actor/tenant/role yang sudah ada. Contoh sintetis berikut hanya ilustrasi argumen;
ganti dengan ID lingkungan sendiri. Default memeriksa rencana, tidak menulis:

```powershell
.\venv\Scripts\python.exe backend/scripts/provision_receiving_permissions.py --tenant 77777777-7777-4777-8777-777777777777 --actor 88888888-8888-4888-8888-888888888888 --role 99999999-9999-4999-8999-999999999999 --permission SchoolReceiving.Read --permission SchoolReceiving.Write --permission Consumption.Read --permission Consumption.Write
```

Tambahkan `--apply` untuk membuat permission/grant yang belum ada. `--permission`
dapat diulang tanpa duplikat; wildcard tidak diterima. Actor/tenant harus aktif,
role nondeleted dan satu tenant. Permission atau grant revoked ditolak, bukan
dipulihkan. Pemeriksaan semua target dan penulisan terjadi satu transaksi dengan
advisory lock tenant. Grant aktif tidak diganti ID/audit/version.

Output JSON memuat mode, tenant_id, role_id, permissions, missing_permissions,
missing_grants, created_permissions, created_grants. Missing dihitung sebelum aksi.
Exit 0 sukses, 1 error tersanitasi, 2 argumen CLI invalid. CLI tidak membuat user,
password, role, user_role, data transaksi, atau event permission.changed. Role harus
sudah ditautkan ke pengguna lewat konfigurasi administratif yang sesuai.

Profil PostgreSQL fsos_runtime berbeda dari RBAC ini. Terapkan migrasi head 0031
kemudian [profil runtime](runtime-database-role.md) sebelum memakai service.
Provisioning profil tidak otomatis menambah permission aplikasi. Grant minimum
lokal telah diterapkan selama implementasi fitur; lingkungan lain perlu memeriksa
subset permission yang dibutuhkan. Tidak ada endpoint HTTP provisioning ini.

## Pemakaian frontend

Authorization bearer menentukan tenant dan actor; API memeriksa permission DB
pada setiap request. Frontend tidak mengirim tenant/operator sebagai pengganti
identitas sesi dan tidak memegang connection string administratif. Detail status,
expected_version, query/pagination dan contoh ada di [kontrak frontend](frontend-api.md).
SchoolReceiving/Consumption/Complaint/Recall/Notification/Traceability/Dashboard berlaku dalam tenant;
pembatasan user per sekolah belum tersedia. Bukti immutable tidak memiliki
permission Edit/Delete. Grant ini belum mengaktifkan provider email/WhatsApp,
retry worker atau subscription realtime.
