# Provisioning permission telemetry development

Status 2026-09-11: CLI tersedia dan telah diterapkan pada role DEV_MAINTENANCE,
tenant FSOS_DEV di database lokal. Empat permission dan empat grant dibuat;
pengulangan menghasilkan created_permissions=0 dan created_grants=0.
Tidak membuat user, password, membership, alarm atau sesi perangkat contoh.

## Ruang lingkup

`backend/scripts/provision_telemetry_permissions.py` memakai ADMIN_DATABASE_URL,
bukan koneksi runtime. Hanya ENVIRONMENT=development diterima. Ini jalur administratif
untuk operator yang sudah memiliki akses koneksi admin; UUID actor hanya identitas
audit yang harus aktif dalam tenant, bukan autentikasi atau grant admin HTTP.
Jangan panggil helper ini dari endpoint publik/runtime. Isolasi admin/secret production
serta provisioning production tetap TODO.

Permission allowlist: Alarm.Read, Alarm.Acknowledge, DeviceSession.Read,
DeviceSession.Close. Operator harus memilih setiap permission secara eksplisit;
tidak ada wildcard atau grant seluruh permission otomatis. Satu role yang ada dan
nondeleted dalam tenant dipilih per pemanggilan. Akun anggota role menerima grant
tersebut jika membership/akun/tenant masih aktif. Role lain tidak berubah.

Default hanya pemeriksaan tanpa penulisan; --apply menambahkan permission/grant
aktif yang belum ada dalam satu transaksi. Permission atau grant yang soft-deleted
menghasilkan TelemetryGrantConflictError, bukan dipulihkan. Actor/tenant nonaktif,
role tenant lain/hilang/deleted, permission tidak dikenal atau duplikat ditolak.
Advisory lock per tenant menserialisasi CLI ini; constraint unik tetap melindungi
writer lain. Kegagalan menggagalkan seluruh transaksi. Tidak ada perubahan seed
PERMISSIONS atau pelebaran akses database fsos_runtime.

## Penggunaan dari root proyek

Ganti placeholder UUID dengan tenant, actor audit dan role yang benar. Periksa dahulu:

```powershell
.\venv\Scripts\python.exe backend/scripts/provision_telemetry_permissions.py --tenant <tenant_uuid> --actor <actor_uuid> --role <role_uuid> --permission Alarm.Read --permission Alarm.Acknowledge --permission DeviceSession.Read --permission DeviceSession.Close
```

Perintah yang sama dengan --apply di akhir menulis hasil. --permission dapat diulang
untuk subset allowlist; --tenant/--actor/--role masing-masing UUID wajib.
Tidak perlu mengirim password atau DATABASE_URL ke chat/argumen command line.

Respons stdout JSON (bukan envelope HTTP); exit 0 bila berhasil, exit 1 untuk
kegagalan proses, exit 2 untuk argumen CLI yang tidak valid. Field hasil:

| Field | Tipe | Makna |
| --- | --- | --- |
| mode | check/apply | Mode operasi |
| tenant_id, role_id | UUID string | Target terverifikasi |
| permissions | array string | Kode terpilih diurutkan |
| missing_permissions, missing_grants | integer | Jumlah yang belum ada sebelum operasi |
| created_permissions, created_grants | integer | Jumlah dibuat, selalu 0 pada check |

Contoh hasil awal apply (UUID ilustrasi):

```json
{
  "mode": "apply",
  "tenant_id": "11111111-1111-4111-8111-111111111111",
  "role_id": "22222222-2222-4222-8222-222222222222",
  "permissions": ["Alarm.Acknowledge", "Alarm.Read", "DeviceSession.Close", "DeviceSession.Read"],
  "missing_permissions": 4,
  "missing_grants": 4,
  "created_permissions": 4,
  "created_grants": 4
}
```

Error stdout hanya error_type dan action tersanitasi; tidak mencetak SQL/credential.
Gunakan check untuk memeriksa target, jangan memakai apply untuk mengembalikan grant
yang dicabut. Pengulangan aktif tidak mengganti UUID, actor, version atau audit lama.

## Dampak frontend dan verifikasi

Tidak menambah endpoint admin. GET /auth/me membaca ulang snapshot permission;
frontend muat ulang /auth/me setelah provisioning. Otorisasi API juga membaca grant
DB setiap request sehingga token akses valid tidak perlu diganti hanya untuk grant.
403 tetap mungkin pada role lain atau membership/permission dicabut.
Kontrak [alarm](frontend-api.md#kontrak-alarm-telemetry-http) dan
[sesi perangkat](frontend-api.md#kontrak-sesi-perangkat-http) menjelaskan hak masing-masing.

Tes database mencakup check tanpa mutasi, allowlist, actor/tenant/role invalid,
production ditolak, apply berulang, audit, revoked permission/grant ditolak,
rollback dan penolakan INSERT permission oleh runtime role. API sesi diuji memakai
grant dari helper ini. Tidak ada event permission.changed yang diterbitkan.
