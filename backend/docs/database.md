# Database development

PostgreSQL 18 lokal berjalan di localhost:5432. Database `fsos` yang disediakan
pengguna telah dihubungkan melalui `backend/.env`. Kredensial tidak dicatat di
dokumentasi. PostGIS dan pgcrypto aktif; revisi terkini adalah `20260911_0017`.

[Profil privilege fsos_runtime](runtime-database-role.md) sudah diprovisioning
sebagai grup NOLOGIN. Login fsos_app kini dipakai DATABASE_URL; migrasi/maintenance
memakai ADMIN_DATABASE_URL. Lihat [pemisahan koneksi](database-connections.md).
Migrasi 0016 memperketat capture history
aturan sehingga runtime tidak memerlukan INSERT langsung pada tabel history.

[Seed development](development-seed.md) sudah diterapkan pada tenant FSOS_DEV:
actor tanpa password login, role/permission service, tujuh master contoh, dan
enam aset registry. Pengulangan tidak menimpa data atau menggandakan fixture.

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
- Optimistic locking, audit actor, scope tenant, dan soft delete sudah tersedia
  melalui [KitchenRepository](repositories.md). Modul lain dan akses SQL langsung
  belum memperoleh perlindungan otomatis. Tidak ada endpoint CRUD publik pada tahap ini.

## Memeriksa koneksi dan migrasi

Migrasi 0015 menambahkan [riwayat revisi aturan](rule-versioning.md) alarm/holding
yang dicatat otomatis pada INSERT/UPDATE. History tidak boleh dimutasi atau
dihapus. Validator DSL sudah digunakan service simpan/aktivasi internal dengan
scope actor/tenant, permission database, dan pemeriksaan version; belum jalur API.

Endpoint `GET /api/v1/ready` melakukan pemeriksaan read-only PostgreSQL 18,
extension PostGIS/pgcrypto, dan kesamaan seluruh revisi database dengan Alembic
heads pada kode aplikasi. Respons 200 berarti semua pemeriksaan lulus; respons
503 berarti belum siap, termasuk konfigurasi kosong, koneksi gagal, timeout,
extension hilang, atau migrasi tidak sesuai. Respons menggunakan envelope API,
request ID, dan `Cache-Control: no-store`, tanpa URL, password, SQL, atau detail
exception. Endpoint tersedia di Swagger dan bersifat publik dengan status ringkas.

`READINESS_TIMEOUT_SECONDS` membatasi probe database, default 3 detik (lebih dari
0 hingga maksimal 30). Probe tidak menjalankan migrasi dan tidak menulis data.
Daftar heads dibaca dari direktori Alembic aplikasi serta di-cache selama proses
berjalan; restart aplikasi setelah memperbarui kode migrasi.

`GET /api/v1/health` tetap memeriksa proses saja dan tidak mengakses database.
Redis/MQTT belum menjadi dependensi runtime sehingga belum diperiksa. Readiness
tidak menguji seluruh constraint, hak tulis, partisi bulan mendatang, atau
kelengkapan fitur bisnis. Tambahkan pemeriksaan layanan saat integrasi diaktifkan.

Saat API berjalan, periksa dari PowerShell:

```powershell
Invoke-RestMethod http://localhost:8000/api/v1/ready
```

Tahap keempat belas melengkapi schema telemetry (docs/08):

- `device_health_log`, `alarm_log`, `holding_log`, `signal_log`, `battery_log`,
  dan `device_session` memakai UUID primary key, audit, waktu bertimezone,
  referensi tenant/device/package/pesan, serta index timeline. Enam tabel ini
  tidak dipartisi; docs/08 menetapkan partisi bulanan untuk empat sensor di bawah.
- Kolom tambahan UUID, device sumber pada signal/battery, recorded_at, dan
  mqtt_message_id memperjelas identitas serta asal bukti yang belum dirinci draft.
  recorded_at adalah waktu observasi; created_at adalah waktu penyimpanan.
- Asumsi satuan: signal wifi_signal/rssi dalam dBm, quality persen; battery dan
  percentage persen, voltage volt. Nilai nullable berarti tidak dilaporkan,
  bukan nol; setidaknya satu pengukuran signal/battery harus tersedia.
  Pada health, sensor/wifi/mqtt/gps/battery berupa label status subsistem.
  Kosakata status/severity dan pemetaan payload tetap perlu divalidasi parser/domain.
- Holding menyimpan snapshot menit; elapsed tidak negatif, remaining boleh
  negatif untuk paket melewati batas. Schema tidak menghitung holding time.
- Semua tabel baru menolak UPDATE/DELETE/TRUNCATE, termasuk soft delete.
  `alarm_log.acknowledged` merupakan snapshot awal. Acknowledgment setelahnya
  ditambahkan ke `alarm_acknowledgment`, sekali per alarm, dengan actor satu tenant
  dan acknowledged_at tidak sebelum recorded_at alarm. Status efektif adalah
  snapshot acknowledged OR keberadaan acknowledgment. Snapshot awal true tidak
  menerima acknowledgment tambahan.
- `device_session.disconnected_at` boleh diisi saat mengimpor sesi lengkap.
  Sesi terbuka ditutup dengan insert `device_session_end`, sekali per sesi;
  trigger menolak waktu sebelum connected_at dan sesi yang sudah lengkap sejak
  insert awal. Waktu akhir efektif adalah COALESCE(snapshot, session_end).
  IP memakai tipe INET (IPv4/IPv6). Reconnect membuat session_id baru.
- API pembacaan status efektif, acknowledgment, ingestion, pengelolaan reconnect,
  serta publisher event belum dibuat. Kedua tabel pendukung menjaga perubahan
  status sebagai bukti tambahan tanpa memperbarui bukti awal.
  [Service internal lifecycle](telemetry-lifecycle.md) sudah menyediakan pembacaan
  status efektif, acknowledgment dan close session dengan permission serta retry;
  belum tersedia sebagai endpoint HTTP.

Tahap ketiga belas menambahkan telemetry sensor berpartisi (docs/08):

- `temperature_log`, `humidity_log`, `gps_log`, `heartbeat_log` dipartisi RANGE
  berdasarkan `recorded_at` per bulan UTC. Partisi awal September–November 2026.
  Tidak ada default partition: timestamp di luar rentang yang disiapkan ditolak
  sampai partisi bulan tersebut dibuat, termasuk data backfill.
- Primary key setiap log adalah `(UUID log, recorded_at)` karena PostgreSQL
  mengharuskan kolom partition key tercakup pada primary/unique key. UUID tetap
  dibuat aplikasi; database hanya menolak pasangan UUID/waktu yang sama, bukan
  UUID sama pada waktu berbeda. Deduplikasi global/event retry tetap tugas ingestion.
- Device memakai `device.device_uuid` publik dengan FK gabungan tenant; GPS
  memakai vehicle_id, suhu dapat menunjuk storage_id. Semua referensi harus dalam
  tenant yang sama. Validasi penempatan aktual sensor/storage/vehicle masih TODO.
- GPS memiliki generated Point SRID 4326 dan index GiST. Index waktu, perangkat,
  storage/vehicle, dan referensi pesan tersedia untuk pencarian time series.
- Suhu menyimpan unit C/F/K tanpa ambang keamanan pangan bawaan. Humidity/battery
  adalah persen 0..100; GPS speed dalam km/jam, altitude meter, heading derajat,
  uptime detik, heap byte, wifi_signal dBm. Pemetaan unit ini perlu diikuti parser.
- `mqtt_message_log` menyimpan UUID internal pesan, tenant, topic, QoS 0..2,
  payload byte asli, received_at, dan snapshot processed. mqtt_message_id pada
  sensor merujuk UUID internal ini, bukan packet identifier MQTT yang bisa dipakai ulang.
- Seluruh bukti sensor/pesan append-only dengan trigger UPDATE/DELETE/TRUNCATE.
  Trigger row diwariskan ke partisi; trigger TRUNCATE dipasang juga di tiap child.
  processed adalah snapshot saat pencatatan, bukan flag antrean yang boleh diubah;
  status retry/worker memerlukan tabel terpisah pada tahap ingestion.
- Belum ada koneksi Mosquitto, parser ingestion, retention/archive, atau jadwal
  pembuatan partisi production. Maintenance development sudah dijadwalkan melalui
  [task Windows dan rolling check/ensure](telemetry-maintenance.md); fsos kini
  mencakup September 2026–Februari 2027. Tidak ada data yang dihapus otomatis.

Untuk menambah partisi, jalankan dari root proyek (aman diulang):

```powershell
.\venv\Scripts\python.exe backend\scripts\create_telemetry_partitions.py --start 2026-12 --months 3
```

Fungsi maintenance hanya membuat partisi empat tabel sensor dalam public schema,
memakai advisory lock, dan memasang guard TRUNCATE. Rentang dibatasi 1–24 bulan
per pemanggilan. Jalankan dengan role migrasi; API runtime tidak membutuhkan hak DDL.
Child partition dikecualikan dari Alembic autogenerate melalui introspeksi pg_inherits
agar tidak dianggap tabel aplikasi yang harus dihapus. Objek induk tetap diperiksa.

Referensi batasan PK dan partisi:
[PostgreSQL 18 table partitioning](https://www.postgresql.org/docs/18/ddl-partitioning.html).

Tahap kedua belas melengkapi operational event (docs/04 bagian 14, docs/08 bagian 14):

- `event_log`: event_uuid, tenant_id, event_type, entity_type, entity_uuid, payload
  JSONB objek, created_at bertimezone serta kolom audit standar. Index tersedia
  untuk timeline entity dan jenis event per tenant.
- event_uuid adalah identitas event global: pengulangan UUID ditolak. Ini belum
  menyediakan retry idempotent, deduplikasi payload, atau dispatch exactly-once;
  producer harus mempertahankan UUID yang sama untuk retry dan menangani konflik.
- entity_uuid menunjuk identitas entity sumber (bukan UUID registry). Referensi
  polimorfik ini belum memiliki FK sumber; validasi keberadaan/type/tenant entity
  wajib pada publisher aplikasi. Payload baru divalidasi bentuk objek JSON,
  bukan schema semantik tiap event.
- Trigger menolak UPDATE/DELETE/TRUNCATE dan insert soft-deleted ditolak constraint.
  Koreksi dicatat sebagai event baru. Pemilik database tetap dapat mengubah DDL;
  gunakan role runtime terbatas pada deployment.
- created_at mencatat waktu pencatatan event. Event bus, transactional outbox,
  worker, retry, validasi payload, serta pencatatan otomatis dari transaksi belum
  diimplementasikan. Penambahan schema tidak berarti semua transaksi sudah menerbitkan event.
- Uji mencakup UUID duplikat, tenant invalid, bentuk payload, trigger riwayat,
  beberapa event untuk satu entity, dan rollback yang mempertahankan graph/movement.

Tahap kesebelas menambahkan registry dan graph (docs/07, 12, 13):

- `digital_asset`: asset_uuid, tenant, asset_type, entity_uuid sumber, code, name,
  status, audit/version. Satu representasi per tenant/type/entity dan kode unik
  per tenant/type. UUID registry berbeda dari UUID entity sumber.
- `entity_uuid` merupakan referensi polimorfik, belum memiliki FK ke tabel sumber.
  [Adapter sumber dan backfill](asset-registry.md) sudah memvalidasi tenant/type
  serta menyinkronkan registry dalam transaksi caller. KitchenRepository sudah
  terhubung; jalur tulis modul lain/SQL langsung belum otomatis menyinkronkan.
  Backfill tenant development FSOS_DEV sudah dijalankan melalui seed;
  tenant lain memerlukan provisioning dan backfill tersendiri.
- `asset_relationship`: parent/child adalah UUID registry, relationship_type
  mengikuti docs/13. FK menolak relasi lintas tenant; self-edge dan edge duplikat
  ditolak. Graph traversal, deteksi siklus multilangkah, dan aturan pasangan jenis
  aset belum diimplementasikan.
- `asset_movement`: referensi registry dan asset_type harus cocok dalam tenant;
  movement_type mengikuti docs/07. from/to_location adalah UUID registry lokasi,
  boleh NULL untuk asal/tujuan yang belum diketahui. Operator opsional mendukung
  event sistem; jika diisi harus user dalam tenant yang sama.
- Riwayat movement append-only: trigger PostgreSQL menolak UPDATE, DELETE,
  soft-delete, dan TRUNCATE dengan SQLSTATE 55000. Insert dengan deleted_at/deleted_by
  juga ditolak. Koreksi perlu event baru. AuditMixin tetap menyediakan kolom standar,
  tetapi updated_at/version tidak diperbarui setelah insert pada tabel ini.
- Trigger berlaku pada SQL normal, bukan batas terhadap administrator yang dapat
  menonaktifkan trigger atau menghapus tabel. Role runtime terbatas tetap diperlukan.
  Downgrade oleh administrator menghapus trigger dan tabel khusus rollback migrasi.
- Index timeline tersedia pada tenant/asset/movement_time. Event producer,
  idempotency berbasis event ID, pembatasan tipe lokasi, dan history perubahan
  relationship masih TODO. Tabel ini belum menjalankan traceability engine.

Tahap kesepuluh menambahkan konsumsi, keluhan, dan recall (docs/07):

- `consumption`: UUID, tenant, paket, consumed_at bertimezone, snapshot sisa menit,
  safe nullable, audit/version. Pemetaan draft memakai satu catatan konsumsi final
  per paket. Konsumsi parsial/multi-porsi memerlukan model tambahan pada tahap domain.
- Nilai safe tidak otomatis true dan tidak dihitung database. NULL berarti belum
  dinilai; remaining_minutes bisa negatif untuk merekam kejadian setelah expiry.
  Riwayat aktual tidak ditolak hanya karena hasil akhirnya tidak aman.
- `complaint`: UUID, tenant, paket, sekolah pelapor, description wajib tidak kosong,
  reported_at, audit/version. Paket dan sekolah harus dalam tenant yang sama.
  Beberapa laporan terhadap satu paket diperbolehkan.
- Sekolah pada complaint belum diwajibkan memiliki school_receiving: laporan dapat
  dicatat sebelum dokumen penerimaan tersedia. Verifikasi pelapor dan kecocokan
  bukti penerimaan adalah workflow investigasi, bukan klaim yang dijamin FK saat ini.
- `recall`: UUID, tenant, batch produksi, reason wajib, started_at, completed_at
  opsional, audit/version. Waktu selesai tidak boleh mendahului mulai. Beberapa
  kasus recall per batch dapat dicatat; aturan kasus aktif ditangani domain nanti.
- Penyimpanan recall belum mengubah status paket, menghitung dampak, mengirim
  notifikasi, atau menjalankan penarikan. Permission Recall.Execute, workflow,
  daftar paket terdampak, dan audit immutable masih TODO.
- Tes memastikan referensi valid, satu consumption final per paket, waktu/alasan
  wajib, serta rollback tahap kesepuluh yang mempertahankan tabel pengiriman.

Tahap kesembilan menambahkan pengiriman dan penerimaan sekolah (docs/07):

- `delivery`: UUID, tenant, vehicle/driver (UUID sesuai nama field draft), waktu
  berangkat/tiba bertimezone, status awal CREATED, audit/version. Waktu tiba
  memerlukan waktu berangkat dan tidak boleh lebih awal.
- `delivery_item`: UUID, tenant, delivery, package, serta sekolah tujuan. Paket
  hanya muncul sekali dalam satu delivery. FK memastikan semua referensi satu tenant.
- `school_receiving`: UUID, tenant, delivery, school, package, received_time,
  temperature, accepted, photo, audit/version. FK gabungan mengharuskan paket dan
  sekolah cocok dengan manifest delivery. Satu hasil penerimaan per paket/delivery.
- Sekolah tujuan dan delivery pada penerimaan merupakan penambahan terhadap
  draft untuk menjamin konsistensi manifest. Nama school/package mengikuti docs/07.
- Driver pada delivery merupakan penugasan perjalanan; tidak harus sama dengan
  driver default master vehicle. Ketersediaan driver/armada tetap validasi domain.
- `accepted=NULL` berarti belum diperiksa, bukan diterima otomatis. Photo adalah
  referensi file/URL, bukan isi gambar; upload, validasi, dan akses file belum dibuat.
- Pengiriman ulang paket pada perjalanan berbeda tidak diblokir schema. Pencegahan
  pengiriman aktif bersamaan, status/expiry paket, kronologi penerimaan terhadap
  perjalanan, otorisasi penerima, dan event movement tetap tugas application/domain.
- Verifikasi rollback hanya pada database uji; tabel produksi dan paket tetap ada.

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

Koneksi runtime lokal menggunakan fsos_app dengan hak terbatas. Koneksi admin
lokal masih memakai owner superuser; production membutuhkan owner migrasi khusus
dan isolasi secret administratif dari proses API.

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

## Sesi autentikasi (0017)

Migrasi 20260911_0017 menambahkan auth_session dan refresh_token, FK tenant/user/session,
index lookup serta hash token unik. Hanya hash refresh disimpan, bukan plaintext.
Profil runtime sudah diperluas untuk operasi sesi terbatas. Rincian lifecycle,
rotasi bersamaan, revokasi dan kontrak transaksi ada di [panduan sesi](refresh-sessions.md).
Upgrade/downgrade masuk pengujian roundtrip pada database terpisah.
