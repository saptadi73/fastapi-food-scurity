# Riwayat aturan dan DSL v1

Implementasi P1, 2026-09-11. Sumber kebutuhan:
[docs/09](../../docs/09_Rule_Engine_Architecture.md), terutama bagian 13–18.

## Riwayat database

Migrasi `20260911_0015` menambahkan `alarm_rule_revision` dan
`holding_rule_revision`. Setiap record memiliki UUID revision_id, tenant_id,
rule_id, version, snapshot JSONB lengkap termasuk audit, dan captured_at.
Pasangan tenant/rule/version unik dan rule harus berada dalam tenant yang sama.

Trigger menyimpan snapshot setelah INSERT/UPDATE aturan dalam transaksi yang
sama. UPDATE menaikkan version satu dan mengisi updated_at. Tenant, ID aturan,
created_at, serta created_by tidak dapat diganti. UPDATE yang tidak mengubah nilai
bisnis tetap menghasilkan revisi. Caller tetap harus menggunakan predicate
`WHERE version = expected_version`; kenaikan otomatis bukan pengganti pengecekan
konflik versi. updated_by harus berasal dari identitas aplikasi terverifikasi.

UPDATE/DELETE/TRUNCATE history dan hard delete/TRUNCATE aturan ditolak. Soft delete
aturan tetap berupa UPDATE sehingga tercatat sebagai revisi. Penonaktifan alarm
melalui enabled juga direkam. Trigger tidak otomatis mengisi actor pengguna.
Hak tulis history harus dibatasi pada role runtime sebelum production; akun owner
masih dapat melakukan DDL atau insert history langsung. Perlindungan ini bukan
tanda tangan kriptografis atau perlindungan dari administrator database.

Pembaruan 0016: [profil runtime](runtime-database-role.md) tidak mendapatkan
INSERT history langsung. Capture trigger memakai SECURITY DEFINER, target tabel
tetap, dan search_path terbatas; akses administrator/owner tetap terpisah.

Migrasi menyimpan snapshot kondisi terakhir setiap aturan lama dengan version
yang sudah dimilikinya. Riwayat sebelum migrasi tidak dapat direkonstruksi.
Upgrade mengunci tabel aturan selama pemasangan snapshot/trigger untuk mencegah
celah pencatatan. Downgrade menghapus history/trigger tambahan tetapi mempertahankan
aturan dan nilai version terakhirnya; gunakan hanya pada database uji.

## Kontrak validator internal

`validate_rule_dsl(condition, action)` di
`app/modules/master/domain/rule_dsl.py` mengembalikan None bila valid atau
RuleDSLValidationError bila invalid. Ini validator struktur, bukan evaluator
atau executor. Format JSON berikut adalah keputusan implementasi v1 karena
dokumen draft belum menetapkan grammar JSON.

```json
{
  "condition": {
    "all": [
      {"field": "temperature", "op": "gt", "value": 5},
      {"field": "duration_minutes", "op": "gte", "value": 15},
      {"field": "storage_type", "op": "eq", "value": "COLD_STORAGE"}
    ]
  },
  "action": {
    "dsl_version": 1,
    "steps": [
      {"type": "alarm", "code": "TEMP_HIGH", "severity": "HIGH"},
      {"type": "notification", "channel": "dashboard", "template": "temperature_high"}
    ]
  }
}
```

Nilai 5/15 di atas contoh dari desain, bukan default keamanan pangan.

| Kondisi | Kontrak |
| --- | --- |
| Node leaf | Tepat field, op, value; semuanya wajib dan tidak null |
| Node group | Tepat satu key all atau any; list 1–20 kondisi |
| Kompleksitas | Maksimum 100 node, kedalaman 8 (root dihitung 1) |
| Field numerik | temperature (Celsius setelah normalisasi ingestion), duration_minutes, humidity (%), remaining_minutes, speed (km/jam) |
| Operator numerik | eq, ne, gt, gte, lt, lte |
| Nilai numerik | int/float finite dalam -1e12..1e12, bukan boolean atau string angka |
| Field teks | storage_type, status |
| Operator teks | eq, ne |
| Nilai teks | String nonblank maksimal 200 karakter |

Key tambahan, field/path bebas, ekspresi Python/SQL, operator lain, dan nilai null
ditolak. Validator tidak menjalankan kode dari kondisi. Normalisasi unit,
semantik durasi, dan sumber nilai harus diimplementasikan evaluator/ingestion.

Action memiliki tepat `dsl_version` integer 1 dan `steps` list 1–10 object:

| type | Field tambahan wajib (string nonblank, maksimal 200 karakter) |
| --- | --- |
| alarm | code, severity; severity CRITICAL/HIGH/MEDIUM/LOW/INFO |
| notification | channel, template; channel dashboard/email/whatsapp/telegram |
| change_status | status |
| create_incident | code |
| create_recall | reason |
| discard_package | reason |
| create_audit | code |

Tidak ada parameter opsional atau nullable pada grammar ini. Tipe aksi tidak
berarti executor sudah tersedia. Keberadaan template, validitas transisi status,
izin recall/discard, dan entity target belum divalidasi oleh validator struktur.

## Batas implementasi

Validator sudah dipakai oleh service internal simpan/aktivasi dengan scope actor,
tenant dan permission database. Autentikasi HTTP/JWT serta endpoint manajemen
aturan belum dibuat. SQL langsung masih hanya memakai constraint JSON object lama;
data draft lama tidak ditafsir ulang atau diaktifkan oleh migrasi. DSL ini belum
merupakan payload HTTP frontend. Semua API aturan nantinya wajib melalui service.

Simulasi, evaluasi telemetry, executor, execution log, publikasi event, dan API
history tetap TODO. Tidak ada event runtime baru; snapshot revisi adalah data
audit internal, bukan pesan WebSocket.

## Service internal dan permission

`RuleService(session, trusted_scope, kind)` menerima kind `alarm` atau `holding`.
Caller memiliki transaksi serta bertanggung jawab memasok identitas terverifikasi;
ActorScope tidak boleh diambil langsung dari body/header tanpa autentikasi.
Service tidak commit/rollback dan tidak menjalankan action atau menerbitkan event.

| Method | Permission | Input/perilaku |
| --- | --- | --- |
| get(id) | AlarmRule.Read / HoldingRule.Read | Snapshot aturan aktif secara administratif (belum soft-deleted); alarm boleh enabled=false |
| history(id, offset=0, limit=20) | AlarmRule.Read / HoldingRule.Read | Revisi menurun, limit 1..100, hanya tenant yang sama |
| create(values) | AlarmRule.Write / HoldingRule.Write | Validasi seluruh definisi; alarm selalu enabled=false, version 1, audit actor otomatis |
| save(id, values, expected_version=...) | AlarmRule.Write / HoldingRule.Write | Penggantian definisi lengkap, bukan PATCH; alarm harus nonaktif |
| set_enabled(id, bool, expected_version=...) | AlarmRule.Activate | Hanya alarm; validasi ulang DSL saat enable; disable tetap boleh untuk DSL legacy invalid |

Nama permission peka huruf besar/kecil. Seed/grant permission belum dilakukan
otomatis pada database aplikasi; tanpa grant, operasi ditolak. Guard memeriksa
user/tenant aktif dan tidak soft-deleted, lalu rantai user_role/role/
role_permission/permission dalam tenant yang sama, semuanya tidak soft-deleted.
Role saat ini tidak memiliki kolom status aktif. Query menggunakan shared row
locks agar revocation bersamaan menunggu transaksi berjalan selesai.

Save/aktivasi mengunci row aturan dan membandingkan expected_version positif
(bukan boolean); UPDATE tetap memakai predicate version. Trigger 0015 menaikkan
version serta mencatat history. Aktivasi ke status yang sudah sama tidak menambah
revisi, tetapi tetap memeriksa permission dan expected_version. Enable yang sudah
true tetap memvalidasi DSL. Tidak ada metode hard delete atau restore.

`AlarmRuleInput` membutuhkan rule_code (1..50), rule_name (1..200), rule_category
(1..100), priority enum, condition object, action object. Semua wajib dan bukan
null; teks metadata di-trim. `HoldingRuleInput` membutuhkan food_category (1..100)
dan integer maximum_minutes > 0, warning_minutes >= 0, discard_minutes > 0,
dengan warning <= maximum <= discard. Holding tidak memiliki enabled pada schema.
Field tambahan termasuk actor/tenant/version/enabled ditolak. Threshold holding
serta field DSL divalidasi sebelum INSERT/UPDATE; detail semantik executor
(template, target entity, transisi bisnis) tetap pekerjaan engine.

Exception internal: InvalidActorError, PermissionDeniedError, RecordNotFoundError
(juga untuk tenant lain/soft delete), VersionConflictError, RuleStateError untuk
edit alarm aktif, Pydantic ValidationError untuk definisi tidak valid, serta
RuleDSLValidationError saat enable DSL tersimpan invalid. Error constraint unik
database diteruskan sebagai IntegrityError; caller harus rollback. Belum ada
pemetaan exception ini ke respons HTTP. Hasil berupa dict database, bukan DTO API.

Contoh alur internal (identitas dan permission harus sudah valid):

```python
async with session.begin():
    service = RuleService(session, trusted_scope, "alarm")
    draft = await service.create(definition)
    enabled = await service.set_enabled(
        draft["alarm_rule_id"], True, expected_version=draft["version"],
    )
```

Jaga transaksi singkat dan jangan membuka transaction kedua jika caller sudah
memiliki transaksi. Pengujian menggunakan data sementara dan rollback, sehingga
tidak membuat user/permission/aturan nyata pada fsos.
