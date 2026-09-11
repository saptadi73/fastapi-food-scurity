# Sesi autentikasi dan refresh token

Status: SessionService terhubung ke endpoint HTTP login/refresh/logout dan
/auth/me dengan dependency bearer. [Kontrak frontend](frontend-api.md#kontrak-autentikasi-http). Memakai migrasi 20260911_0017.
Tidak ada akun/password manusia, refresh token atau secret nyata dibuat untuk
pengguna development. Primitive JWT tanpa sesi tetap tersedia untuk tes internal;
jalur SessionService.resolve_access menolak token tanpa sid.

## Penyimpanan dan izin

| Tabel | Isi |
| --- | --- |
| auth_session | session_id, tenant_id, user_id, created_at, expires_at, revoked_at nullable |
| refresh_token | token_id, tenant_id, session_id, token_hash SHA-256, created_at, used_at nullable |

FK gabungan menjaga pasangan user/tenant dan token/session/tenant. Token_hash unik
berupa 64 karakter hex. Expiry sesi harus setelah created_at. Index mendukung
pencarian per user dan session. Tabel ini menyimpan lifecycle autentikasi, bukan
telemetry append-only atau soft-deleted master. Tidak ada password/plaintext
refresh token maupun access JWT disimpan pada kedua tabel ini.

Refresh token opaque berbentuk UUID.token_acak; bagian acak memakai 48 byte dari
secrets.token_urlsafe. Hash dihitung atas seluruh string. Lookup memverifikasi
hash dengan compare_digest; mengetahui token_id saja tidak dapat mencabut sesi.
Token bukan JWT dan tidak membawa claim yang dipercaya aplikasi.

Runtime mendapat SELECT/INSERT pada kedua tabel, UPDATE(revoked_at) pada
session dan UPDATE(used_at) pada refresh_token. Tidak ada UPDATE identitas/hash,
DELETE/TRUNCATE/DDL baru. Profil provisioning mensyaratkan head 0017. Pembatasan
service bukan RLS; SQL langsung dengan credential database tetap memiliki grant
yang disebutkan. Revokasi monotonic dijaga service, bukan trigger immutable.

## Operasi internal

| Method | Input | Hasil / efek |
| --- | --- | --- |
| login | tenant_id UUID, username str, password str | Autentikasi akun; buat sesi 7 hari dan TokenPair |
| refresh | raw refresh token str | RefreshOutcome(status, tokens); rotasi atau penolakan |
| logout | raw refresh token str | bool; token valid mencabut satu keluarga sesi |
| resolve_access | access JWT str | ActorScope setelah JWT, akun/tenant dan sesi divalidasi |

TokenPair memuat access_token dan refresh_token sebagai SecretStr,
refresh_expires_at datetime aware, token_type='Bearer', expires_in=900. SecretStr
menyamarkan repr/log/serialisasi default; caller harus membuka secret hanya untuk
respons kepada pemegang sesi setelah commit. Router HTTP membuka kedua secret hanya untuk response sesudah commit.

Contoh bentuk hasil refresh internal (placeholder, bukan token nyata):

```json
{
  "status": "ROTATED",
  "tokens": {
    "access_token": "<ACCESS_JWT>",
    "refresh_token": "<OPAQUE_REFRESH_TOKEN>",
    "refresh_expires_at": "2026-09-18T10:00:00Z",
    "token_type": "Bearer",
    "expires_in": 900
  }
}
```

Status ROTATED memiliki TokenPair; INVALID dan REUSED memiliki tokens=null.
INVALID mencakup format/hash salah, sesi dicabut/kedaluwarsa atau akun/tenant
nonaktif. REUSED berarti token benar tetapi sudah pernah dipakai; seluruh keluarga
sesi dicabut, termasuk token baru yang pernah diterbitkan melalui keluarga itu.
Status ini internal; Router HTTP memberi penolakan seragam, bukan membocorkan
rincian validitas token kepada client. Login invalid memakai InvalidCredentialsError;
resolusi JWT invalid menggunakan InvalidAccessTokenError atau InvalidCredentialsError.

Login membentuk sesi baru dengan expiry absolut tujuh hari. Rotasi tidak memperpanjang
expiry keluarga; token lama ditandai used_at, token baru ditambahkan, dan access JWT
15 menit diterbitkan dengan sid=session_id. Role/permission token dibaca ulang dari
RBAC aktif pada refresh; permission operasi tetap diperiksa dari database.

resolve_access memerlukan sid, pasangan session/user/tenant yang cocok, akun dan
tenant aktif, sesi belum dicabut serta belum kedaluwarsa. Access token dapat ditolak
sebelum exp jika sesi dicabut atau expiry tujuh harinya telah lewat. Token tanpa sid
dari primitive codec tidak diterima oleh resolver sesi. AccountService.resolve_access
adalah helper tingkat rendah yang hanya memeriksa akun; endpoint HTTP memakai
resolver SessionService agar revokasi tidak dilewati.

Logout menerima bukti kepemilikan refresh token, termasuk token lama yang sudah
dipakai, dan mencabut sesi terkait. Pengulangan token valid mengembalikan True tanpa
mengganti revoked_at pertama. Token tidak valid mengembalikan False dan tidak
mengubah sesi. Tidak ada logout seluruh perangkat, reset password atau blacklist
per-jti pada tahap ini; revokasi dilakukan per keluarga melalui sid di database.

## Transaksi dan concurrency

Caller harus mengelola transaksi. Jangan mengirim token sebelum commit berhasil.
Login/refresh yang rollback harus membuang seluruh token hasil sementara.
Refresh REUSED mengubah database; jangan melempar error di dalam blok transaksi
yang membuat revokasinya ikut rollback. Contoh:

```python
async with factory() as db:
    async with db.begin():
        outcome = await SessionService(db, codec).refresh(raw_refresh_token)
# Commit sudah selesai. Baru petakan ROTATED atau penolakan ke respons.
```

Service tidak melakukan commit tersembunyi. Login/refresh mengunci akun/RBAC sebelum
sesi; refresh mengambil row lock sesi lalu membaca ulang used_at untuk menserialisasi
rotasi. Dua refresh bersamaan memakai token sama menghasilkan satu ROTATED dan satu
REUSED; sesudah keduanya commit, token pemenang juga ditolak karena sesi dicabut.
Client harus memakai satu permintaan refresh bersama (single-flight).
Retry token lama setelah respons rotasi hilang juga mencabut sesi; tidak ada grace
period atau pengembalian token baru yang sama. Client harus login kembali.

Logout menunggu operasi refresh pada sesi yang sama. Pemeriksaan akses mengambil
shared lock sehingga logout berlaku setelah transaksi operasi yang sudah mendapat
izin selesai; tidak membatalkan transaksi yang sedang berjalan.

## Deployment, frontend dan pekerjaan tersisa

Sesudah upgrade 0017 jalankan provision_runtime_role.py melalui ADMIN_DATABASE_URL.
API/service memakai DATABASE_URL. Tidak ada Redis/MQTT atau event baru. Schema dan
service kini terhubung ke login HTTP. Cookie/CSRF, rate limiting lintas worker,
audit persisten, bootstrap production dan cleanup sesi tetap perlu dibuat.
Bootstrap manusia development tersedia melalui [CLI administratif](human-bootstrap.md). Router
memiliki limiter sementara per proses serta log action/outcome tanpa secret. Pergantian password belum otomatis mencabut seluruh sesi.
Tidak ada penghapusan otomatis record token lama; jangan menghapus used token
sebelum kebijakan retensi selesai karena riwayat itu dipakai mendeteksi reuse.

## Verifikasi (2026-09-11)

99 tes lulus, Ruff bersih, Alembic check tidak menemukan perbedaan model/schema
pada database uji maupun fsos. Migrasi 0017 dan grant runtime sudah diterapkan di
fsos. Tes membuktikan rotasi/reuse, logout berulang, token salah/kedaluwarsa,
penolakan access tanpa sid, grant runtime serta dua transaksi refresh bersamaan
yang benar-benar commit revokasi. Upgrade/downgrade diuji melalui roundtrip schema.
Tidak ada sesi atau password fixture yang ditambahkan ke database aplikasi.
