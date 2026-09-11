# Repository dan transaksi

Status 2026-09-11: implementasi pertama untuk kitchen, belum framework lengkap
untuk seluruh modul. Tidak ada migrasi baru; memakai kolom audit/schema yang ada.

`ActorScope(tenant_id, actor_id)` adalah konteks internal bertipe UUID, yang harus
berasal dari identitas terverifikasi application service. Jangan mengambil tenant
atau actor langsung dari request body. Autentikasi dan permission RBAC belum
diimplementasikan; keberadaan scope bukan bukti pengguna sudah login.

`KitchenRepository(session, scope)` menyediakan:

| Method | Perilaku |
| --- | --- |
| `get(id)` | Satu kitchen tenant aktif, menyembunyikan soft-deleted record |
| `list(offset=0, limit=20)` | Scope yang sama, limit 1..100, urut created_at lalu UUID |
| `create(values)` | UUID baru, tenant/actor dari scope, version 1 |
| `update(id, values, expected_version=...)` | UPDATE atomik dengan predicate tenant, id, deleted_at null, dan version |
| `soft_delete(id, expected_version=...)` | Mengisi deleted_at/deleted_by, bukan DELETE SQL |

Setiap operasi memeriksa user dan tenant aktif serta belum dihapus. SELECT FOR
SHARE menahan perubahan pada actor/tenant selama transaksi; transaksi aplikasi
harus singkat. Gunakan satu session per unit of work, jangan berbagi session
antar-task yang berjalan bersamaan. Repository tidak commit atau rollback.

Field yang boleh ditulis: kitchen_code, kitchen_name, latitude, longitude,
address, capacity, status. ID/tenant/audit/version/deleted fields dan computed
location tidak dapat disisipkan melalui values. Validasi tipe/domain tetap tugas
schema/service; constraint database tetap berlaku. Belum ada validasi transisi
status, otorisasi role, atau pengecekan referensi ke kitchen yang soft-deleted.

Create/update/soft delete kitchen kini juga menyinkronkan registry digital asset
dalam transaksi yang sama; lihat [kontrak registry](asset-registry.md). Jika sync
gagal, caller wajib rollback seluruh transaksi sumber beserta registry.

Update dan soft delete menaikkan version satu serta mengisi updated_by/updated_at;
created_by/created_at dipertahankan. Pembaca menerima snapshot dict hasil Core SQL,
bukan entity ORM yang bisa diubah lalu di-flush tanpa melalui repository.
Hasil ini belum DTO frontend: antara lain geometry/Decimal perlu schema serialisasi.

Record tenant lain, hilang, atau soft-deleted menghasilkan RecordNotFoundError
yang sama. Record masih terlihat dengan version berbeda menghasilkan
VersionConflictError; caller harus memuat ulang sebelum menawarkan retry.
Actor/tenant tidak valid menghasilkan InvalidActorError. Belum ada HTTP mapping.
IntegrityError database diteruskan; application service harus rollback transaksi
gagal. Tidak ada hard delete atau restore pada repository ini.

Contoh application service internal (scope harus sudah diverifikasi):

```python
async with session.begin():
    repository = KitchenRepository(session, trusted_scope)
    kitchen = await repository.get(kitchen_id)
    result = await repository.update(
        kitchen_id, {"kitchen_name": "Kitchen Baru"},
        expected_version=kitchen["version"],
    )
```

Jangan membungkus contoh ini di dalam transaksi yang sudah terbuka tanpa mengatur
unit of work terlebih dahulu. Auth dependency nanti harus berbagi pengelolaan
transaksi yang konsisten dengan service.

Perlindungan ini berlaku pada jalur KitchenRepository. Raw SQL, session ORM umum,
dan modul lain belum otomatis dibatasi; ini bukan PostgreSQL RLS. Seluruh API
bisnis harus memakai repository yang sesuai serta permission sebelum dibuka.
Actor audit pada schema umum belum memiliki FK; validasi repository tidak
menggantikan pekerjaan tersebut. Tabel bukti immutable tidak boleh menggunakan
pola update/soft delete kitchen. Publisher/outbox belum diimplementasikan.

Tes repository memerlukan database uji `fsos_test*` dengan migrasi head terpasang,
membuat data dalam transaksi dan rollback setelah verifikasi. Tes version saat
ini mensimulasikan editor membawa version lama; bukan stress test paralel.
