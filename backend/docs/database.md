# Database development

PostgreSQL 18 lokal berjalan di localhost:5432. Database `fsos` yang disediakan
pengguna telah dihubungkan melalui `backend/.env`. Kredensial tidak dicatat di
dokumentasi. PostGIS dan pgcrypto aktif; revisi terkini adalah `20260911_0008`.

## Schema awal

- `tenant`: UUID `tenant_id`, kode unik, nama, status.
- `kitchen`: UUID `kitchen_id`, FK tenant dengan ON DELETE RESTRICT, kode unik
  dalam tenant, nama, latitude/longitude, alamat, kapasitas, status.
- Keduanya memiliki created/updated/deleted timestamp dan actor UUID serta version.
- `location` kitchen adalah generated Point SRID 4326 dari longitude/latitude,
  dengan index GiST. Koordinat harus berpasangan dan dalam rentang geografis valid.
- Audit actor masih UUID tanpa FK; validasi actor sesuai tenant masih TODO. `updated_at`
  diperbarui oleh SQLAlchemy saat ORM melakukan update; raw SQL harus mengisinya.
- UUID dibuat aplikasi. Kode tetap unik setelah soft delete agar identitas tidak
  dipakai ulang. Validasi status/rule bisnis akan ditambahkan pada domain.
- Composite unique `(tenant_id, kitchen_id)` disediakan untuk FK modul berikutnya.
  Ini belum menggantikan otorisasi tenant pada query/API.
- Kolom version tersedia, tetapi optimistic locking dan soft-delete repository
  belum diimplementasikan. Tidak ada endpoint CRUD publik pada tahap ini.

## Memeriksa koneksi dan migrasi

Tahap kedelapan menambahkan produksi dan paket (docs/07):

- `production_batch`: UUID, tenant, batch_code unik per tenant, kitchen/menu
  (FK kitchen/food_item), started_at, finished_at, holding_started_at,
  holding_expired_at, status awal CREATED, audit/version. Waktu selesai memerlukan
  waktu mulai dan tidak boleh lebih awal; demikian pula pasangan waktu holding.
- `production_item`: hubungan batch produksi dengan batch bahan pada tenant yang
  sama, quantity Numeric(14,6) positif/bukan NaN, dan satuan snapshot. Satu baris
  menyimpan total bahan dari satu batch bahan dalam satu batch produksi.
- `package`: UUID, tenant, kode unik per tenant, batch produksi, nomor urut positif
  unik dalam batch, jenis kemasan opsional, remaining_minutes, expired_at, status,
  audit/version. Jenis kemasan jika diisi harus dari tenant yang sama.
- `remaining_minutes` merupakan snapshot nullable dan dapat negatif setelah
  expiry. Tidak ada timer, keputusan aman/tidak aman, atau perhitungan expiry
  otomatis pada schema ini. Engine akan memperbaruinya melalui event.
- Nama `kitchen` dan `menu` mengikuti field draft docs/07; keduanya UUID. Field
  tambahan `uom` pada item dan `package_type_id` pada paket memperjelas satuan
  pemakaian serta jenis kemasan.
- FK menjamin referensi satu tenant, bukan izin pemakaian stok. Validasi bahan
  diterima/belum kedaluwarsa, saldo dan reservasi stok, kecocokan resep, perpindahan
  stok antar-kitchen, snapshot versi resep/policy, serta state machine tetap TODO.
- Produksi dan paket tidak dapat dihapus melalui cascade. Downgrade hanya untuk
  migrasi development; verifikasi rollback dilakukan di database uji terpisah.

Tahap ketujuh menambahkan transaksi penerimaan bahan (docs/07):

- `receiving`: UUID, tenant, supplier, kitchen penerima, operator (FK app_user),
  received_at bertimezone, status awal CREATED, serta audit/version.
- `raw_material_batch`: UUID, tenant, master raw material, receiving, supplier,
  batch_code, expired_date opsional, status, QR opsional, audit/version. Kode batch
  dan QR unik per tenant. QR masih identifier; gambar/tautan QR belum dibuat.
- `receiving_item`: UUID, tenant, receiving, batch, quantity Numeric(14,6), satuan,
  temperature opsional, accepted nullable, dan audit/version. Quantity wajib positif
  dan bukan NaN. `accepted=NULL` berarti belum diperiksa, bukan diterima otomatis.
- Keputusan tambahan terhadap field draft: kitchen penerima dan master material
  wajib agar batch dapat ditelusuri; satuan item disimpan sebagai snapshot transaksi.
  Satu batch berasal dari satu penerimaan dan memiliki satu receiving_item.
- FK gabungan memastikan operator/kitchen/supplier/material berada dalam tenant
  yang sama; supplier batch harus sama dengan supplier header; item harus menunjuk
  batch pada header yang sama. Data yang masih direferensikan tidak dapat dihapus fisik.
- Tidak dipaksakan FK ke katalog supplier_material: pemasok aktual dicatat pada
  transaksi, sedangkan persetujuan pemasok dan pemeriksaan penerimaan adalah aturan domain.
- Pemeriksaan status operator/izin, kedaluwarsa bahan, suhu penerimaan, konversi
  satuan, transaksi atomik header–batch–item, API, dan event movement belum dibuat.
  Tabel movement serta produksi/distribusi masih langkah selanjutnya.

Tahap keenam menambahkan schema identity/RBAC dalam modul authentication:

- `app_user` (pemetaan entity User docs/06): UUID, tenant, username, fullname,
  email, password_hash opsional, status awal INACTIVE, dan kolom audit/version.
  Nama tabel menghindari ambiguitas dengan identitas USER PostgreSQL.
- Username/email unik per tenant melalui index `lower(btrim(...))` yang
  mengabaikan case dan spasi tepi. Ini mencegah duplikasi tanpa mengubah teks yang
  tersimpan; service login harus memakai normalisasi yang sama dan identitas tenant.
- `role` dan `permission` scoped per tenant, memiliki UUID, kode unik per tenant,
  label/deskripsi dan kolom audit. Kode role/permission bersifat case-sensitive.
- `user_role` dan `role_permission` mendukung relasi banyak-ke-banyak dengan UUID,
  audit, pasangan unik, serta composite FK yang menolak relasi lintas tenant.
  Master yang masih direferensikan tidak dapat dihapus fisik (ON DELETE RESTRICT).
- Tidak ada user/admin/password atau pemberian izin yang di-seed. `password_hash`
  disediakan sebagai tempat hash, bukan input password plaintext. ORM menunda
  pemuatannya (`deferred`), tetapi ini bukan mekanisme redaksi respons; schema
  respons API nantinya harus mengecualikan field ini secara eksplisit.
- Hash bcrypt cost 12, aktivasi akun, login/JWT/refresh, seed permission, query
  akses tenant, pengecualian soft-deleted user/role/grant, dan validasi format email
  belum diimplementasikan. Tabel relasi belum berarti enforcement RBAC aktif.
- Tes mencakup duplikasi identitas, referensi/pasangan RBAC tidak valid, status
  awal akun, serta downgrade revisi keenam yang mempertahankan master rule/kemasan.

Tahap kelima menambahkan:

- `packaging_type`: UUID, tenant, code unik per tenant, name, material, volume.
  Keputusan satuan untuk field `volume` yang belum ditetapkan docs/06 adalah mL;
  Numeric(12,3), boleh NULL bila belum diketahui, tetapi jika diisi wajib positif
  dan bukan NaN.
- `alarm_rule`: UUID, tenant, kode/nama/kategori, priority, condition/action JSONB,
  enabled default false, serta kolom audit/version. Prioritas sesuai docs/09:
  CRITICAL, HIGH, MEDIUM, LOW, INFO. Condition/action wajib objek tidak kosong.
  Bentuk ini belum memvalidasi DSL atau mengeksekusi rule; engine dan validasi
  semantik belum diimplementasikan. Contoh kategori docs/06 tidak di-seed.
- `holding_rule`: UUID, tenant, food_category unik per tenant, maximum_minutes,
  warning_minutes, discard_minutes, dan kolom audit/version. Tidak ada nilai
  ambang default maupun seed kebijakan keamanan pangan.
- Pemetaan waktu: maximum_minutes adalah durasi total sejak cooking finished;
  warning_minutes adalah sisa waktu sebelum expiry mengikuti docs/14, dalam
  rentang 0..maximum. Draft belum menjelaskan discard_minutes, sehingga tahap ini
  memetakannya sebagai durasi total sejak titik awal yang sama dan >= maximum.
  Ini konfigurasi waktu pembuangan terjadwal, bukan larangan membuang lebih awal
  akibat insiden. Tidak berarti makanan aman setelah maximum tercapai.
- Riwayat revisi aturan immutable yang diminta docs/09 belum tersedia; kolom
  version/audit bukan pengganti history. API perubahan/aktivasi rule, critical
  threshold, pemilihan policy, dan timer engine masih TODO.
- Tes memastikan referensi tenant dan batas nilai valid, serta rollback revisi
  kelima mempertahankan supplier, recipe, dan relasi pemasok–bahan.

Tahap keempat menambahkan:

- `supplier`: UUID, tenant, kode unik per tenant, nama, telepon/email opsional, status.
- `raw_material`: UUID, tenant, kode/nama bahan, kategori, satuan, jenis penyimpanan,
  rekomendasi suhu min/max, maksimum jam penyimpanan, status.
- `food_item`: UUID, tenant, kode/nama menu, kategori, satuan, holding limit, status.
- `recipe`: satu baris bahan per menu, dengan quantity Numeric(14,6) positif dan satuan
  wajib. Pasangan menu–bahan unik dalam tenant; foreign key gabungan mencegah
  penggunaan master dari tenant lain.
- `supplier_material`: tabel penghubung ber-UUID dan kolom audit untuk beberapa
  pemasok per bahan dan beberapa bahan per pemasok. Ini keputusan pemetaan relasi
  Supplier→Raw Material pada draft docs/06 yang belum menentukan kardinalitas.
  Relasi lintas tenant dan pasangan duplikat ditolak.
- Semua tabel memiliki kolom audit. Batas suhu menolak min > max; waktu menolak
  nilai negatif. Nilai batas boleh NULL ketika belum dikonfigurasi, bukan berarti aman
  atau tidak terbatas. Tidak ada nilai ambang keamanan pangan yang ditetapkan di schema.
- Kode master tetap unik setelah soft delete. Relasi/resep yang diaktifkan kembali
  menggunakan baris lama; pengelolaan soft delete serta versi resep masih pekerjaan domain.
- Konversi satuan, ukuran hasil resep, validasi email, kategori/status, serta
  pemilihan supplier pada batch penerimaan belum diimplementasikan. Tabel pemasok–bahan
  adalah katalog, bukan bukti pemasok aktual suatu batch.
- Uji roundtrip memverifikasi downgrade revisi keempat mempertahankan data fleet
  dan master tahap sebelumnya. Database utama hanya di-upgrade.

Tahap ketiga menambahkan:

- `driver`: UUID, tenant, kode unik per tenant, nama, telepon opsional, dan status.
- `vehicle`: UUID, tenant, kode/plat unik per tenant, tipe, kapasitas nonnegatif,
  GPS device dan driver opsional, status, serta Point PostGIS SRID 4326/index GiST.
- `school`: UUID, tenant, kitchen penanggung jawab, kode unik per tenant, nama,
  alamat, jumlah siswa nonnegatif, status, dan koordinat berpasangan. Point sekolah
  dihitung dari longitude/latitude dan diberi index GiST.
- Semua tabel memiliki kolom audit. Foreign key gabungan menolak relasi
  vehicle–driver, vehicle–device, serta school–kitchen lintas tenant.
- Keputusan pemetaan draft docs/06: satu school memiliki satu kitchen penanggung
  jawab saat ini; `vehicle.driver_id` adalah penugasan driver saat ini. Riwayat dan
  penugasan per perjalanan akan dibuat pada modul distribusi/fleet, bukan di tabel ini.
- `gps_device` mereferensikan `device_id` internal. Validasi tipe perangkat GPS,
  normalisasi plat, kapasitas beserta satuannya, dan aturan penugasan tetap tugas
  application/domain. FK saat ini hanya menjamin keberadaan dan kesamaan tenant.
- Downgrade revisi ketiga menghapus vehicle/school/driver saja; data master tahap
  sebelumnya dipertahankan. Pengujian rollback hanya dilakukan di database uji.

Tahap kedua menambahkan:

- `storage`: kitchen pemilik, kode unik per kitchen, nama, jenis, rentang suhu,
  status, dan lokasi PostGIS Point SRID 4326 dengan index GiST.
- `storage_zone`: storage pemilik dan kode zone unik per storage.
- `device`: identitas internal `device_id` dan identitas publik `device_uuid`
  (keduanya UUID), nama, jenis, firmware/hardware, topic MQTT, status, last_online.
- Ketiganya memiliki kolom audit dan tenant_id. Foreign key gabungan memastikan
  storage–kitchen, zone–storage, serta device–zone berada dalam tenant yang sama.
- Device boleh belum memiliki zone saat registrasi. Tenant tetap wajib valid.
  `device_uuid` unik global; status awal REGISTERED. Kolom `mqtt_topic` masih metadata,
  belum menjamin otorisasi topic atau mengaktifkan koneksi broker.
- Rentang suhu menolak min > max; batas boleh kosong saat belum dikonfigurasi.
  Tidak ada ambang keamanan pangan yang di-hardcode. Jenis/status serta transisi
  bisnis akan divalidasi oleh domain pada implementasi API berikutnya.
- Nama field device mengikuti ERD docs/06. Field tambahan digital twin docs/12
  (lifecycle, health, calibration, dan sebagainya) tetap pekerjaan tahap berikutnya.
- Downgrade revisi kedua hanya menghapus device/zone/storage. Data tenant/kitchen
  tetap ada; perilaku ini telah diuji pada database khusus pengujian.

Dari root proyek:

```powershell
.\venv\Scripts\python.exe backend\scripts\check_database.py
.\venv\Scripts\python.exe -m alembic -c backend\alembic.ini current
.\venv\Scripts\python.exe -m alembic -c backend\alembic.ini upgrade head
.\venv\Scripts\python.exe -m alembic -c backend\alembic.ini check
```

Pemeriksa database bersifat read-only dan tidak mencetak URL/password. Status
`database_prerequisites_ready` memeriksa versi 18 dan extension, bukan kelengkapan
modul bisnis. Respons juga menampilkan revisi migrasi yang terpasang.

Alembic mengecualikan `spatial_ref_sys` dari autogenerate karena tabel tersebut
milik PostGIS. Migrasi aplikasi tidak membuat atau menghapus extension.

## Provisioning untuk instalasi baru

Untuk database lokal yang saat ini tersedia, langkah ini sudah selesai.
Jika membuat lingkungan baru, script berikut membuat role/database bernama fsos
dan extension. Jalankan sebagai administrator PostgreSQL:

```powershell
& 'C:\Program Files\PostgreSQL\18\bin\psql.exe' -X -h localhost -p 5432 -U postgres -d postgres -f backend\scripts\provision_database.sql
```

psql meminta password role baru secara interaktif melalui `\password`. Jika role
atau database sudah ada, script tidak mengganti password atau ownership-nya.
Pastikan database target memang milik aplikasi. Untuk database dengan nama/user
lain yang sudah ada, administrator cukup menjalankan `enable_extensions.sql`
pada database target, kemudian mengisi `.env` dan menerapkan Alembic.

User lokal yang diberikan saat ini memiliki hak superuser. Gunakan role aplikasi
terbatas dan pisahkan provisioning administratif pada deployment production.

## Tes integrasi

Tes integrasi membutuhkan database **kosong dan khusus pengujian**, dengan nama
diawali `fsos_test`, serta extension PostGIS dan pgcrypto sudah aktif. Tes ini
melakukan upgrade, memasukkan data uji, downgrade yang menghapus tabel master,
lalu upgrade ulang. Jangan arahkan ke database aplikasi.

```powershell
$env:FSOS_TEST_DATABASE_URL='postgresql+asyncpg://TEST_USER:TEST_PASSWORD@localhost:5432/fsos_test'
.\venv\Scripts\python.exe -m pytest -c backend\pyproject.toml backend\tests -q
Remove-Item Env:FSOS_TEST_DATABASE_URL
```

Verifikasi awal menggunakan cluster PostgreSQL sementara di `.postgres-test/`
pada port 55432. Cluster ini diabaikan Git dan sudah dihentikan setelah pengujian.
Database utama fsos tidak pernah di-downgrade dalam verifikasi tersebut.

Referensi: [psql PostgreSQL 18](https://www.postgresql.org/docs/18/app-psql.html)
dan [Alembic async migrations](https://alembic.sqlalchemy.org/en/latest/cookbook.html#using-asyncio-with-alembic).
