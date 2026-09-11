# Bootstrap akun manusia development

Script backend/scripts/bootstrap_human.py membuat akun baru untuk login HTTP pada
tenant yang sudah ada. Bootstrap memakai ADMIN_DATABASE_URL, bukan koneksi runtime
API, dan hanya menerima ENVIRONMENT=development. Ini bukan endpoint signup publik
atau provisioning admin production. Tidak memerlukan migrasi maupun grant baru.

## Menjalankan pada FSOS_DEV

Dari root proyek di PowerShell interaktif:

```powershell
.\venv\Scripts\python.exe backend\scripts\bootstrap_human.py --tenant a492adf9-3a5b-501e-b4d5-ec48d54f657b --actor 9062c8ab-1713-5398-b4a1-06d3e9402b3a --role c24c4037-e242-5d8a-821c-06b2bcadb7d6
```

Perintah ini memilih tenant FSOS_DEV, actor audit dev-maintenance, dan role
DEV_MAINTENANCE yang sudah tersedia. Script menanyakan username, nama lengkap,
email, lalu password dua kali. Input password tidak ditampilkan. Jangan kirim
password ke chat; jangan menaruhnya pada argumen perintah, file contoh, atau URL.

Role contoh memiliki AssetRegistry.Sync, AlarmRule.Read/Write/Activate dan
HoldingRule.Read/Write. Ini bukan Administrator penuh dan tidak memberikan
Alarm.Read/Acknowledge atau DeviceSession.Read/Close. Pilih --role UUID lain bila
kebutuhan izin berbeda; role harus dibuat lebih dulu pada tenant yang sama.
Bootstrap tidak membuat role, permission atau wildcard admin otomatis.

Untuk pemeriksaan tanpa membuat akun, isi profil secara eksplisit dan gunakan
--check. Contoh data ilustratif berikut sudah diperiksa secara read-only pada fsos:

```powershell
.\venv\Scripts\python.exe backend\scripts\bootstrap_human.py --tenant a492adf9-3a5b-501e-b4d5-ec48d54f657b --actor 9062c8ab-1713-5398-b4a1-06d3e9402b3a --role c24c4037-e242-5d8a-821c-06b2bcadb7d6 --username operator-preview --fullname "Operator Preview" --email operator-preview@example.org --check
```

Hasil will_create=true berarti input siap saat diperiksa; **bukan akun sudah dibuat**.
Tidak ada prompt password atau insert pada mode ini. --check mengambil advisory/shared
lock sementara dan melepaskannya saat transaksi selesai. Operasi create memeriksa
ulang seluruh identitas dan role setelah password dimasukkan.

## Parameter

| Argumen | Required | Aturan |
| --- | --- | --- |
| --tenant | Ya | UUID tenant ACTIVE, belum soft-deleted |
| --actor | Ya | UUID user audit ACTIVE dalam tenant sama; operator harus berwenang memakai koneksi administratif |
| --role | Ya | UUID role tenant; dapat diulang, 1..100 role unik, tidak soft-deleted |
| --username | Tidak | Diprompt jika kosong; 1..100 karakter input; spasi ASCII tepi dipangkas, nonblank, tanpa kontrol/NUL/Unicode invalid |
| --fullname | Tidak | Diprompt jika kosong; 1..200 karakter, nonblank, tanpa kontrol/NUL/Unicode invalid |
| --email | Tidak | Diprompt jika kosong; sintaks email valid, maksimum 254 karakter; tidak mengirim email/verifikasi DNS |
| --check | Tidak | Pemeriksaan saja, tanpa password/insert |

Spasi ASCII di tepi username/nama dipangkas. Email dinormalisasi oleh validator.
Username/email diperiksa dengan lower(btrim(...)), sama dengan index database.
Identitas yang sama meskipun berbeda case/spasi atau akun lama soft-deleted tetap
menimbulkan konflik. Role tenant lain diperlakukan tidak tersedia.

Password mengikuti kebijakan bcrypt aplikasi: minimal 12 karakter, maksimum
72 byte UTF-8, tanpa NUL, tidak di-trim atau dipotong. Argumen --password sengaja
tidak tersedia. Input lewat pipe/non-interactive terminal ditolak pada tahap prompt,
dan fallback getpass yang akan menampilkan password juga ditolak. --check dengan
semua profil di argumen boleh dijalankan noninteraktif.

## Efek dan transaksi

Akun dibuat ACTIVE dengan UUID baru, hash bcrypt cost 12 serta version=1. Membership
user_role dibuat untuk role yang dipilih. created_by/updated_by pada user dan
membership berasal dari actor audit yang diminta. Actor tidak diverifikasi lewat
password: otoritas operasi berasal dari penggunaan ADMIN_DATABASE_URL oleh operator,
bukan public API atau permission actor secara otomatis.

User dan membership berada dalam satu transaksi; caller mengelola commit/rollback.
Advisory lock per tenant menserialisasi bootstrap, index unik tetap melindungi dari
penulisan lain. Hash dikerjakan sebelum lock; tidak ada lock DB ditahan saat pengguna
mengetik password. Akun existing tidak pernah diaktifkan ulang, diberi role tambahan
atau direset password-nya. Pengulangan nama/email yang sama gagal tanpa perubahan.

Tidak mengubah dev-maintenance atau tenant/role/permission yang sudah ada. Tidak
menerbitkan token atau membuat sesi login; setelah berhasil gunakan endpoint login.
Tidak mengirim email, event bus atau audit keamanan persisten. Record audit kolom
database tersedia; identitas operator administratif eksternal tetap tanggung jawab
operasional development.

## Output dan error

Mode --check: tenant_id, actor_id, username, fullname, email, roles (kode terurut),
dan will_create=true. Mode create: field profil yang sama ditambah user_id UUID dan
created=true, tanpa will_create. Password/hash tidak pernah dicetak; profil hasil
mengandung email/nama yang dimasukkan, jadi jangan membagikannya tanpa kebutuhan.

Exit 0 berarti check/create berhasil. Exit 1 untuk environment/input/kredensial
DB/role/aktor/konflik/password tidak cocok/pembatalan. Error JSON hanya error_type
dan petunjuk umum; ValidationError berisi field yang bermasalah tanpa nilai input.
Kesalahan sintaks CLI memakai argparse dengan exit 2. Jika koneksi terputus saat
commit, periksa keberadaan akun sebelum mengulang; konflik tidak berarti script
akan mereset akun. Tidak ada mode overwrite/upsert atau reset password.

## Login setelah bootstrap

Gunakan username dan password yang dimasukkan, serta tenant_id dari output:
POST /api/v1/auth/login. Setelah menerima token, GET /api/v1/auth/me dengan bearer
menampilkan user_id baru, tenant, role dan permission aktif dari database.
Payload/respons/error lengkap ada di [panduan frontend](frontend-api.md#kontrak-autentikasi-http).
Username/password PostgreSQL fsos_app bukan akun login frontend.

Bootstrap akun production, pembuatan role/permission baru, reset password dengan
revokasi semua sesi, invitation dan verifikasi email masih TODO. Script ini tidak
menandai keseluruhan pengelolaan akun selesai.

## Verifikasi (2026-09-11)

113 tes backend lulus; Ruff bersih. Bootstrap diuji untuk preview tanpa insert,
hash dan audit, membership role, login akun hasil bootstrap, konflik nama/email,
actor/tenant/role soft-deleted, role lintas tenant, rollback, production ditolak,
input invalid, password tidak cocok serta penolakan lewat fsos_runtime.
Mode --check lokal berhasil dengan will_create=true; operator-preview tidak
tercatat sebagai akun dan dev-maintenance tetap tanpa password. Akun manusia nyata
baru dibuat ketika operator menjalankan script dan memilih profil/password sendiri.
