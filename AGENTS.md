# Instruksi proyek

## Dokumentasi integrasi frontend

Pengguna mewajibkan dokumentasi endpoint lengkap dan terus diperbarui.
Setiap perubahan endpoint, request/response, error, auth/permission, pagination,
atau perilaku yang memengaruhi frontend harus memperbarui
`backend/docs/frontend-api.md` dalam perubahan yang sama.

- Catat method/path, tujuan, status implementasi, auth/permission, header,
  path/query parameter, payload (termasuk jika tidak ada), tipe/required/nullable,
  validasi, contoh request, respons sukses/error, dan efek samping/event.
- Selaraskan dokumentasi Markdown dengan route, schemas, OpenAPI dan tes.
  Verifikasi contoh terhadap perilaku aktual; jangan menjadikan desain draft
  atau keberadaan tabel sebagai bukti endpoint sudah tersedia.
- Setiap event baru/berubah memperbarui `backend/docs/event-catalog.md`:
  status, trigger, producer, consumer, transport/channel, versi/payload,
  tenant/auth, ordering, deduplikasi/retry/replay, serta contoh.
  Tandai hal yang belum diimplementasikan sebagai rencana, bukan kontrak aktif.
- Catat perubahan kontrak dan dampak frontend di
  `backend/docs/frontend-changelog.md`, lalu perbarui `TODO.md`.
- Jangan menaruh kredensial atau data pribadi nyata dalam contoh.

Pekerjaan API/event belum selesai sebelum dokumentasi terkait diperbarui.


## Prioritas implementasi pengguna

Dahulukan modul utama proses bisnis menurut bagian "Prioritas kerja aktif" di
TODO.md: master operasional, receiving/stok, produksi, packaging/holding,
pengiriman, penerimaan sekolah/konsumsi, complaint/recall dan pendukung bisnis.
Implementasikan traceability, movement dan aturan bisnis bersama alur terkait.

Jangan memilih perluasan tes, deploy production, seeding tambahan, provisioning
umum atau penyempurnaan infrastruktur sebagai pekerjaan berikutnya selama modul
bisnis utama masih belum selesai, kecuali dependensi minimum fitur yang dikerjakan.
Pemeriksaan terarah untuk kebenaran fitur, auth/tenant dan integritas transaksi tetap
dilakukan sebagai bagian implementasi. Dokumentasi frontend/event tetap wajib
langsung diperbarui bersama perubahan kontrak. Jangan menandai schema sebagai
penyelesaian fitur bisnis atau menunda modul demi pengulangan tes yang tidak perlu.
