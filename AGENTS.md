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
