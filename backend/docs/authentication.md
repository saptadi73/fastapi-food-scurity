# Fondasi autentikasi manusia

Status 2026-09-11: primitive password, codec access JWT, autentikasi akun dan
resolusi identitas access token melalui database tersedia sebagai service internal.
Penyimpanan/rotasi refresh dan revokasi sesi tersedia melalui [SessionService](refresh-sessions.md).
Endpoint login/refresh/logout dan /auth/me kini tersedia bersama dependency current_account.
Kontrak lengkap ada di [panduan frontend](frontend-api.md#kontrak-autentikasi-http).
[Bootstrap akun manusia development](human-bootstrap.md) tersedia melalui CLI
administratif; provisioning production dan audit persisten tetap TODO.
Tidak ada akun yang diberi password atau secret JWT yang diubah pada tahap ini.
Actor dev-maintenance tetap tanpa password. API aktif tetap health dan readiness.

## Password

Modul authentication/infrastructure/passwords.py menyediakan hash_password dan
verify_password, serta wrapper async hash_password_async/verify_password_async.
Wrapper async memindahkan pekerjaan bcrypt ke thread agar tidak memblokir event
loop. Caller HTTP nantinya tetap memerlukan rate limit dan pembatasan concurrency.

| Aturan | Implementasi |
| --- | --- |
| Algoritma | bcrypt, prefix 2b, cost 12 sesuai docs/11 |
| Minimum | 12 karakter Unicode; keputusan implementasi karena draft belum menetapkan panjang |
| Maksimum | 72 byte UTF-8, bukan 72 karakter; input berlebih ditolak tanpa dipotong |
| Transformasi | Tidak trim, lowercase atau normalisasi; spasi bagian dari password |
| Input invalid | Tipe selain str, UTF-8 tidak valid, NUL, terlalu pendek/panjang ditolak |
| Hash baru | Salt acak setiap pemanggilan; plaintext tidak disimpan/dicetak |
| Verifikasi | bool; password salah/invalid, hash kosong/malformed atau selain 2b cost 12 menghasilkan False |

Hashing invalid menghasilkan ValueError tanpa menyertakan nilai password.
Format hash sengaja dibatasi pada format yang dibuat aplikasi. Migrasi hash lama
atau cost lain belum tersedia; tidak ada fallback ke password plaintext.
Primitive verify_password bukan alur login lengkap. AccountService di bawah
menambahkan query akun per tenant, error seragam, dummy hash dan validasi
actor/tenant aktif; integrasi HTTP, rate limit, audit dan pengujian timing menyeluruh
masih diperlukan. verify_password sendiri
tidak menjamin waktu respons seragam untuk input atau hash invalid.

Batas 72 byte menghindari truncation pada versi bcrypt lama dan ValueError pada
bcrypt 5. Detail library: [bcrypt resmi](https://pypi.org/project/bcrypt/).

## Access JWT

AccessTokenCodec menerima SecretStr secara eksplisit; secret minimal 32 byte UTF-8,
tanpa default atau fallback. Panjang tersebut bukan bukti entropy: deployment
harus memasok secret acak kriptografis. Codec dihubungkan ke Settings/routes melalui codec_dependency. JWT_SECRET kosong
atau lifetime konfigurasi selain 15 menit/7 hari menghasilkan HTTP 503. Secret
acak development sudah disimpan pada .env lokal yang diabaikan Git.
Secret tidak diletakkan di frontend, token atau dokumentasi contoh.

issue(user_id, tenant_id, roles=[...], permissions=[...]) hanya boleh dipanggil
setelah autentikasi dan pembacaan RBAC database oleh caller tepercaya. Mengirim UUID
atau role/permission dari browser langsung ke method ini bukan autentikasi.

| Claim/header | Nilai / aturan |
| --- | --- |
| alg / typ | HS256 / JWT; allowlist tetap, tidak dipilih dari permintaan token |
| iss / aud | fsos / fsos-api; audience harus string tunggal |
| sub / tenant | UUID canonical lowercase user dan tenant |
| jti | UUID baru setiap penerbitan |
| iat / nbf | Integer Unix seconds UTC, waktu penerbitan yang sama |
| exp | iat + 900 detik; access token tepat 15 menit |
| token_type | access; refresh ditolak oleh decoder ini |
| role / permission | Snapshot list string, maks 100 item per list, tiap string nonblank maks 100 karakter |

Penerbitan mengurutkan dan menghapus duplikasi role/permission. Total token dibatasi
16.384 karakter. Seluruh claim di atas wajib. Decoder memeriksa signature, issuer,
audience, expiration, nbf/iat masa depan, tipe timestamp, UUID, tujuan dan durasi.
Tidak ada clock leeway. Algoritma none/selain HS256, typ lain atau critical header
nonkosong ditolak. Library digunakan dengan algorithms=['HS256'] dan required
claims eksplisit: [referensi PyJWT](https://pyjwt.readthedocs.io/en/stable/api.html).

Hasil decode adalah AccessIdentity(user_id: UUID, tenant_id: UUID, token_id: UUID,
expires_at: int). Role/permission snapshot tidak dikembalikan sebagai otorisasi;
service tetap harus memeriksa actor/tenant dan permission aktif dari database.
Signature valid tidak membuktikan akun masih aktif atau token belum dicabut.
Semua kegagalan decode menghasilkan InvalidAccessTokenError dengan pesan seragam
Invalid or expired access token; raw token/claim tidak dimasukkan ke pesan error.

JWT ditandatangani, bukan dienkripsi; jangan memasukkan password atau data sensitif
ke claim. Refresh token 7 hari, rotasi/reuse detection dan logout per sesi kini tersedia
melalui SessionService. Audit dan blacklist per-jti belum diimplementasikan. Codec ini tidak
memproduksi refresh token dan tidak boleh dianggap alur login lengkap.

## Frontend dan kontrak

POST /api/v1/auth/login, /auth/refresh, /auth/logout dan GET /api/v1/auth/me sudah
aktif. JSON input, response envelope terstruktur, status error, permission,
header, contoh dan perilaku retry dijelaskan di [panduan frontend](frontend-api.md#kontrak-autentikasi-http).
Tidak ada cookie otomatis. Secret/password tidak boleh dimasukkan ke URL atau log.

Dependency current_account memvalidasi bearer melalui SessionService.resolve_access,
memeriksa sid dan membaca RBAC terkini dalam transaksi. Scope dependency adalah
function: transaksi ditutup sebelum respons terkirim. Endpoint bisnis berikutnya
harus memeriksa permission yang diperlukan; adanya current_account bukan izin
untuk semua operasi. Jangan memanggil db.begin() lagi di dalam transaksi dependency.

POST mengelola transaksi eksplisit. Refresh memetakan outcome ke 401 hanya sesudah
commit sehingga revokasi reuse bertahan. Kesalahan database/configuration menjadi
503 tersanitasi. Log operasional mencatat action/outcome/request_id tanpa secret;
ini belum audit keamanan persisten. Limiter sementara per proses 100 request/menit
per IP mencakup semua auth route; limiter Redis lintas worker masih TODO.

## Verifikasi

89 tes backend lulus, termasuk 23 tes primitive autentikasi: password salah,
spasi dipertahankan, salt unik, batas byte/Unicode, hash invalid/cost salah,
claim hilang, signature salah, algoritma none/HS512, issuer/audience/tujuan salah,
timestamp invalid/expired/masa depan dan identitas UUID invalid. Ruff dan pip check
bersih. Migrasi/service/permission runtime juga diuji pada database terpisah.
Tes ini belum mencakup login HTTP, refresh/revoke atau mitigasi brute force.

## Autentikasi akun dan resolusi identitas

AccountService(session).authenticate(tenant_id, username, password) menerima UUID
tenant, username string nonblank 1..100 karakter, tanpa NUL/Unicode invalid, dan password
plaintext sesuai kebijakan
password. Username dicocokkan memakai PostgreSQL lower(btrim(...)), sama dengan
index unik akun: tidak membedakan case dan mengabaikan spasi ASCII di tepi.
Login email belum didukung. Password tidak di-trim atau dinormalisasi.

Query hanya menerima user/tenant ACTIVE dan belum soft-deleted dalam tenant yang
diminta. Hasil AuthenticatedAccount berisi user_id dan tenant_id (UUID), roles dan
permissions (tuple string terurut tanpa duplikasi). Role/membership/grant/permission
yang soft-deleted dikecualikan. Akun tanpa role/permission masih dapat diautentikasi
namun tidak mendapat hak operasi. Tidak ada password/hash dalam hasil.

Untuk akun tidak ada/nonaktif, hash kosong/rusak atau password invalid, wrapper
verify_login_password_async tetap menjalankan bcrypt cost 12 menggunakan dummy
hash publik yang tidak terhubung ke akun. Ini mengurangi perbedaan biaya hash,
bukan jaminan waktu respons identik karena query database dan jalur input berbeda.
Rate limit, pembatasan concurrency, audit serta pemetaan error HTTP tetap diperlukan.
Semua kegagalan kredensial menghasilkan InvalidCredentialsError('Invalid credentials')
tanpa membedakan akun tidak ditemukan, tenant salah atau password salah.

Bcrypt berjalan pada thread sebelum mengambil lock. Setelah password cocok,
service membaca ulang user/tenant dengan shared lock, termasuk membandingkan hash
terkini untuk menolak perubahan password selama verifikasi. RBAC juga dibaca dengan
shared lock. Caller mengelola transaksi singkat dan melakukan commit/rollback;
service tidak menyimpan password, membuat user, atau mencatat waktu login.

Contoh internal setelah konfigurasi secret codec oleh aplikasi:

```python
async with session.begin():
    account = await AccountService(session).authenticate(tenant_id, username, password)
    access_token = codec.issue(
        account.user_id, account.tenant_id,
        roles=list(account.roles), permissions=list(account.permissions),
    )
```

Contoh ini primitive internal; endpoint publik yang tersedia memakai SessionService
dan router HTTP yang juga menangani transaksi, rate limit dan error. Penerbitan token dilakukan eksplisit oleh
caller setelah autentikasi; method authenticate sendiri tidak mengembalikan token.

resolve_access(token, codec) memvalidasi JWT lalu memeriksa user/tenant aktif dari
database dengan shared lock; hasilnya ActorScope(tenant_id, actor_id). Token invalid
menghasilkan InvalidAccessTokenError, akun nonaktif/hilang menghasilkan
InvalidCredentialsError. Caller masih wajib require_permission untuk setiap
operasi: snapshot role/permission dalam token tidak dipercaya sebagai izin terkini.
Pencabutan permission berlaku ketika operasi memeriksa RBAC meskipun token lama
masih valid. AccountService.resolve_access tidak memeriksa sesi; router HTTP memakai SessionService.resolve_access yang memeriksa sid dan pencabutan. Mengganti password belum mencabut access JWT lama;
validitas signature tetap berlaku sampai exp kecuali akun/tenant dinonaktifkan.

AccountService menggunakan DATABASE_URL runtime dan grant baca/locking yang sudah ada.
Tidak ada password akun nyata yang dibuat; router HTTP kini memakai SessionService.
Tidak ada event login diterbitkan; sesi/refresh kini dikelola SessionService. Account dev-maintenance pada fsos tetap tanpa password.
Tes hanya memasang hash pada fixture database terpisah dan me-rollback seluruhnya.

## Verifikasi autentikasi akun

Suite backend: 93 tes lulus. Sesudah penambahan empat kasus username invalid,
lima tes akun dijalankan ulang dan lulus (termasuk integrasi database); total
cakupan kini 97 kasus. Ruff bersih. Tes mencakup akun tanpa password, kredensial
salah, tenant lain, case/spasi username, dummy bcrypt, akun/tenant nonaktif atau
soft-deleted, snapshot grant dicabut, role runtime, dan hash berubah selama bcrypt.
Simulasi perubahan hash bukan stress test transaksi paralel. Seluruh fixture
password di-rollback pada database uji, bukan ditulis ke akun fsos.

## Verifikasi HTTP

Suite 103 tes lulus; sesudah penambahan tes CORS untuk 429, 20 tes HTTP/auth/readiness
dijalankan ulang dan lulus (104 kasus tersedia). Pengujian mencakup alur login,
refresh, commit revokasi pada 401 reuse, logout berulang, akun nonaktif, limiter,
CORS, OpenAPI, validasi tersanitasi dan kegagalan commit tanpa membocorkan token.
Readiness lokal 200, actor tanpa password dan /me tanpa bearer sama-sama 401.
Tidak ada sesi autentikasi fixture di fsos. Restart proses API lama untuk memuat
route dan JWT_SECRET lokal yang baru; bootstrap akun manusia development tersedia melalui CLI; password dipilih operator di terminal.
