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
| acknowledge | Alarm.Acknowledge | identifier UUID alarm; waktu dan actor diisi server |
| close_session | DeviceSession.Close | identifier UUID sesi, disconnected_at datetime bertimezone |

Permission mutasi mengizinkan hasil operasi dikembalikan tanpa perlu permission
Read terpisah. Permission baru ini belum ditambahkan ke seed DEV_MAINTENANCE;
seed tidak memperluas grant actor lama secara diam-diam. Provisioning permission
harus dilakukan eksplisit melalui jalur administratif yang sah.

Semua query membatasi tenant. Sumber yang hilang atau milik tenant lain menghasilkan
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
