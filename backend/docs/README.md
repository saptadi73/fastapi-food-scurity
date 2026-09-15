# Indeks dokumentasi backend

Status 2026-09-15: **165 operasi HTTP aktif**, 70 operasi CRUD untuk empat belas
master, Alembic head `20260915_0032`. Dokumen desain `docs/01`?`docs/18` adalah
acuan arsitektur/roadmap; kontrak aktif diverifikasi dari router, schema dan tes.

| Kebutuhan | Dokumen |
|---|---|
| Instalasi dan menjalankan API | [README proyek](../../README.md) |
| Endpoint/payload/error/auth/pagination | [Kontrak frontend](frontend-api.md) |
| Riwayat perubahan kontrak | [Changelog frontend](frontend-changelog.md) |
| Seed demo frontend | [Seed development](development-seed.md#seed-demo-frontend-end-to-end) |
| Event, producer/consumer dan status transport | [Event catalog](event-catalog.md) |
| Migrasi dan integritas database | [Database](database.md) |
| Pool runtime/admin | [Koneksi database](database-connections.md) |
| Hak PostgreSQL service | [Role runtime](runtime-database-role.md) |
| JWT, sesi dan refresh | [Autentikasi](authentication.md), [sesi refresh](refresh-sessions.md) |
| Akun manusia development | [Bootstrap manusia](human-bootstrap.md) |
| Permission master | [Lokasi](location-permissions.md), [supply/menu/kemasan](supply-permissions.md) |
| Permission alur transaksi | [Receiving sampai konsumsi](receiving-permissions.md) |
| Registry dan rekonsiliasi | [Digital asset](asset-registry.md) |
| Telemetry/maintenance/rule | [Lifecycle](telemetry-lifecycle.md), [maintenance](telemetry-maintenance.md), [versioning](rule-versioning.md) |
| Status pekerjaan tersisa | [TODO](../../TODO.md) |

## Alur bisnis yang dapat diintegrasikan

| Tahap | Kontrak | Batas utama |
|---|---|---|
| Empat belas master | [Matriks CRUD](frontend-api.md#cakupan-crud-dan-status-modul) | Administrasi tenant/user/role belum CRUD HTTP |
| Penerimaan bahan | [Receiving](frontend-api.md#kontrak-receiving-dan-batch-bahan) | Complete keputusan inspeksi sebelum putaway |
| Stok | [Putaway/saldo](frontend-api.md#stok-batch-bahan-dan-putaway) | Transfer/adjustment/reversal belum tersedia |
| Produksi | [Batch produksi](frontend-api.md#kontrak-transaksi-produksi) | Snapshot resep dan issue stok atomik |
| Pengemasan/holding | [Paket dan timer](frontend-api.md#kontrak-kemasan-paket-dan-holding) | QR payload tersedia; cetak label/scheduler expiry belum tersedia |
| Pengiriman | [Manifest dan perjalanan](frontend-api.md#kontrak-pengiriman) | Complete mencatat arrival, bukan acceptance sekolah; GPS/per-stop belum tersedia |
| Sekolah/konsumsi | [Penerimaan dan finalisasi](frontend-api.md#kontrak-penerimaan-sekolah-dan-konsumsi) | Bukti immutable; safe hanya snapshot holding; koreksi/backdated belum tersedia |
| Complaint | [Keluhan paket](frontend-api.md#kontrak-complaint-intake) | Intake immutable dengan scan/foto dan report insiden; recall otomatis belum tersedia |
| Recall | [Recall dasar](frontend-api.md#kontrak-recall-dasar) | Start/execute/withdrawal/close; notifikasi belum otomatis |
| Notification | [Notification outbox](frontend-api.md#kontrak-notification-outbox) | Outbox dashboard internal; provider email/WhatsApp belum otomatis |
| Traceability | [Traceability read](frontend-api.md#kontrak-traceability-read) | Graph/passport/impact read-only; repair/replay belum tersedia |
| Dashboard | [Dashboard read](frontend-api.md#kontrak-dashboard-read) | Counter tenant, suhu storage dan notification outbox read-only; realtime/cache/analytics belum tersedia |

Status utama paket: CREATED -> PACKAGED -> RELEASED -> ALLOCATED -> IN_TRANSIT
-> DELIVERED -> RECEIVED -> CONSUMED/DISCARDED. Penolakan sekolah menghasilkan
REJECTED. Cancel manifest CREATED mengembalikan paket RELEASED atau EXPIRED sesuai
deadline. Status dan expected_version paket harus dimuat ulang setelah aksi.
Lihat kontrak per tahap untuk transisi discard/expiry dan validasi lengkap.

Investigasi mendalam, ingestion telemetry,
evaluator alarm dan notifikasi otomatis masih TODO. Event bisnis yang tersedia
tersimpan di PostgreSQL; belum ada subscription MQTT/WebSocket/SSE frontend.
