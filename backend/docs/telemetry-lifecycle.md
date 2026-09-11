# Status efektif alarm dan sesi perangkat

Status 2026-09-11: service internal tersedia; tidak ada endpoint HTTP baru,
WebSocket, MQTT consumer, atau reconnect handler. Memakai tabel migrasi 0014
tanpa perubahan schema. [API frontend](frontend-api.md) tetap hanya menyediakan
health dan readiness.

## Permission dan operasi

`TelemetryLifecycleService(session, trusted_scope)` memerlukan actor/tenant aktif
dan permission melalui RBAC database. Caller harus menyediakan identitas yang
sudah diverifikasi; UUID actor dari body/header bukan autentikasi.

| Method | Permission | Input |
| --- | --- | --- |
| get_alarm | Alarm.Read | identifier UUID alarm |
| get_session | DeviceSession.Read | identifier UUID sesi |
| list_alarms | Alarm.Read | Filter perangkat/status efektif/waktu, offset dan limit |
| list_sessions | DeviceSession.Read | Filter perangkat/status efektif/waktu, offset dan limit |
| acknowledge | Alarm.Acknowledge | identifier UUID alarm; waktu dan actor diisi server |
| close_session | DeviceSession.Close | identifier UUID sesi, disconnected_at datetime bertimezone |

Permission mutasi mengizinkan hasil operasi dikembalikan tanpa perlu permission
Read terpisah. Permission baru ini belum ditambahkan ke seed DEV_MAINTENANCE;
seed tidak memperluas grant actor lama secara diam-diam. Provisioning permission
harus dilakukan eksplisit melalui jalur administratif yang sah.

Semua query membatasi tenant. Pada operasi detail/finalisasi, sumber yang hilang atau milik tenant lain menghasilkan
RecordNotFoundError yang sama. Akses tetap memungkinkan pembacaan bukti perangkat
lama meskipun device kemudian dinonaktifkan; permission actor/tenant tetap diperiksa.

## Hasil get_alarm dan acknowledge

Hasil berupa dict kolom `alarm_log` ditambah:

| Field tambahan | Tipe internal | Makna |
| --- | --- | --- |
| effective_acknowledged | bool | snapshot acknowledged OR bukti acknowledgment tersedia |
| acknowledgment_id | UUID atau None | UUID bukti tambahan |
| acknowledged_at | datetime atau None | Waktu acknowledgment yang dicatat service |
| acknowledged_by | UUID atau None | Actor yang pertama mencatat acknowledgment |

Field asli `acknowledged` tidak diubah. Setelah acknowledge pada alarm baru,
acknowledged tetap false tetapi effective_acknowledged menjadi true. Jika snapshot
impor sudah acknowledged=true, hasil efektif true dan field bukti tambahan dapat
tetap None. Service tidak mengarang waktu/actor yang tidak tersedia pada snapshot.

Acknowledge mengunci parent alarm, memeriksa status efektif, lalu insert satu
alarm_acknowledgment. acknowledged_at/recorded_at memakai waktu UTC server dan
actor/audit berasal dari scope. Waktu observasi alarm yang masih di masa depan
ditolak sebelum insert baru. Retry setelah berhasil mengembalikan bukti pertama
tanpa menambah row atau mengganti actor/waktu, termasuk bila caller berikutnya
actor lain yang memiliki permission. Tidak memerlukan expected_version karena
parent immutable.

## Hasil get_session dan close_session

Hasil berupa dict kolom `device_session` ditambah:

| Field tambahan | Tipe internal | Makna |
| --- | --- | --- |
| effective_disconnected_at | datetime atau None | COALESCE(snapshot disconnected_at, bukti akhir sesi) |
| is_open | bool | true jika waktu akhir efektif belum ada |
| session_end_id | UUID atau None | UUID bukti tambahan, None untuk snapshot sesi lengkap |

`disconnected_at` asli pada sesi terbuka tetap None setelah close_session;
effective_disconnected_at berasal dari device_session_end. Input disconnected_at
wajib datetime aware (tidak menerima string langsung pada service Python),
dinormalisasi ke UTC dan tidak boleh sebelum connected_at. Penutupan baru juga
tidak boleh memakai waktu masa depan. Parsing ISO 8601 untuk HTTP nantinya tugas schema API.

Service mengunci parent sesi lalu insert bukti akhir; created_by/updated_by berasal
dari scope dan recorded_at adalah waktu penerimaan server. Retry dengan waktu
yang sama mengembalikan bukti yang ada. Retry dengan waktu berbeda menghasilkan
CompletionConflictError, termasuk bila sesi berasal dari snapshot impor yang
sudah lengkap. Tidak ada update/delete terhadap parent atau bukti tambahan.

## Transaksi dan batas implementasi

Caller memiliki commit/rollback. Gunakan transaksi singkat dan satu session per
unit of work; kegagalan harus me-rollback seluruh transaksi. Lock parent
menserialisasi finalisasi service untuk record yang sama. Constraint unik dan
trigger database tetap menjadi perlindungan terakhir untuk writer lain. Belum
ada stress test paralel atau delivery exactly-once dari broker.

InvalidActorError/PermissionDeniedError menandai masalah identitas/izin;
RecordNotFoundError menandai record tidak terlihat; ValueError menandai input waktu
invalid; CompletionConflictError menandai konflik waktu akhir. Belum ada pemetaan
HTTP untuk exception ini. Dict service bukan DTO JSON frontend: timestamp/UUID
perlu serialisasi schema. Tidak ada payload POST/PATCH HTTP yang dapat dipanggil sekarang.

Reconnect harus membuat session_id baru. Penutupan sesi tidak menandai device
offline secara global karena perangkat dapat memiliki sesi lain. Membuka sesi,
mendeteksi sesi kedaluwarsa, korelasi broker reconnect, daftar/pagination alarm/sesi,
API berautentikasi dan event publication tetap TODO. Tidak ada event runtime baru.

Contoh internal setelah otorisasi identitas:

```python
async with session.begin():
    service = TelemetryLifecycleService(session, trusted_scope)
    alarm = await service.acknowledge(alarm_id)
    ended = await service.close_session(session_id, disconnected_at=observed_end_time)
```

Tes PostgreSQL mencakup permission read/mutasi terpisah, tenant lain, snapshot impor,
hasil efektif, retry identik, konflik waktu, timestamp naive/masa depan/terlalu awal,
actor audit, jumlah bukti tunggal, serta rollback seluruh fixture. Tes menggunakan
database terpisah; tidak membuat alarm/sesi palsu pada fsos.

## Daftar alarm dan sesi (service internal)

Dua method daftar memakai proyeksi JOIN yang sama dengan detail/finalisasi; bukan
query terpisah yang hanya membaca status snapshot lama. Tidak membutuhkan migrasi,
perubahan grant fsos_runtime, Redis atau MQTT. Tidak ada method/path HTTP, header
Authorization, request JSON browser atau status code HTTP baru pada tahap ini.

| Parameter | Tipe / default | Validasi dan arti |
| --- | --- | --- |
| device_uuid | UUID atau None; default None | UUID publik device, bukan device_id internal; tanpa filter jika None |
| acknowledged | bool atau None; default None | Khusus list_alarms; memfilter effective_acknowledged |
| is_open | bool atau None; default None | Khusus list_sessions; memfilter apakah waktu akhir efektif masih kosong |
| since | datetime aware atau None | Batas awal inklusif |
| until | datetime aware atau None | Batas akhir eksklusif; harus lebih besar dari since jika keduanya diisi |
| offset | int; default 0 | Minimal 0; boolean bukan integer yang diterima |
| limit | int; default 20 | 1..100; boolean ditolak |

Alarm difilter dan diurutkan berdasarkan recorded_at; sesi memakai connected_at,
bukan recorded_at atau disconnected_at. Timestamp harus datetime Python bertimezone;
string ISO 8601 belum diparsing oleh service. Offset zona berbeda tetap dibandingkan
sebagai waktu absolut. Nilai bool 0/1 atau string "false" bukan filter yang valid.
Perangkat tidak ditemukan atau milik tenant lain menghasilkan daftar kosong tanpa
membocorkan keberadaannya. Filter perangkat tidak memerlukan status device aktif.
Actor/tenant tetap harus aktif dan permission Read belum dicabut.

Urutan terbaru dahulu: timestamp DESC lalu UUID alarm/session DESC sebagai pemutus
urutan jika waktu sama. Filter diterapkan sebelum pagination. Tiap halaman mengambil
satu record tambahan untuk menentukan next_offset tanpa query COUNT seluruh tabel.

Contoh pemanggilan internal (trusted_scope berasal dari autentikasi caller):

```python
from datetime import UTC, datetime

async with session.begin():
    service = TelemetryLifecycleService(session, trusted_scope)
    alarms = await service.list_alarms(
        acknowledged=False,
        since=datetime(2026, 9, 1, tzinfo=UTC),
        until=datetime(2026, 10, 1, tzinfo=UTC),
        offset=0, limit=20,
    )
    sessions = await service.list_sessions(is_open=True, limit=20)
```

Hasil adalah dict internal, tanpa envelope HTTP:

| Field hasil | Tipe / makna |
| --- | --- |
| items | list[dict]; setiap item identik dengan hasil get_alarm atau get_session pada keadaan data yang sama |
| offset | int offset yang diminta |
| limit | int batas yang diminta |
| next_offset | int posisi halaman berikut bila ada; None jika halaman terakhir/kosong |

Contoh hasil kosong yang lengkap: {"items": [], "offset": 0, "limit": 20,
"next_offset": null}. UUID/datetime dalam item masih objek Python; serialisasi API
akan ditentukan saat endpoint dibuat. Field tambahan item dijelaskan pada bagian
hasil detail di atas. acknowledged asli dapat tetap false meskipun filter
acknowledged=True, karena filter memakai bukti acknowledgment tambahan. Sesi
is_open=False bisa memiliki disconnected_at asli None karena waktu akhir efektif
berasal dari device_session_end. Metadata acknowledgment impor tetap None jika
bukti waktu/actor tidak tersedia; tidak diisi dengan nilai buatan.

Parameter invalid menghasilkan ValueError. Actor/tenant tidak aktif menghasilkan
InvalidActorError; izin Read tidak ada/dicabut menghasilkan PermissionDeniedError.
Permission mutasi tidak otomatis memberi hak daftar. Error ini belum dipetakan
ke respons HTTP. Tidak ada insert bukti, perubahan snapshot/version, commit
internal, publisher, atau event baru akibat membaca daftar.

Pagination offset bukan snapshot lintas halaman: penambahan alarm/sesi atau
acknowledgment/penutupan saat pengguna berpindah halaman dapat menggeser hasil.
Untuk refresh dashboard nantinya, muat ulang dari offset 0 dan deduplikasi UUID.
Tidak tersedia total count, cursor snapshot, arbitrary sort atau pencarian bebas.
Offset besar dapat lebih mahal; kinerja data production belum diuji beban.

## Verifikasi daftar (2026-09-11)

Seluruh 66 tes lulus, Ruff bersih. Tes PostgreSQL memeriksa daftar/detail identik,
status sebelum/sesudah acknowledgment/close termasuk snapshot impor, urutan UUID
saat timestamp sama, batas since inklusif/until eksklusif, halaman terakhir/kosong,
filter tenant/perangkat, izin Read tidak ada/dicabut dan akses fsos_runtime.
Parameter invalid diuji tanpa akses database. Bukti tambahan tetap satu per
finalisasi; pembacaan tidak menambah bukti. Fixture hanya dibuat pada database
uji terpisah, lalu rollback; tidak ada alarm/sesi contoh ditambahkan ke fsos.
