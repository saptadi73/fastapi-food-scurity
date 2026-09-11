# Backend FSOS

Panduan instalasi, konfigurasi, migrasi, dan pengujian tersedia di
[README proyek](../README.md). Progres implementasi ada di [TODO](../TODO.md).

Entry point: `main:app`. Jalankan dari root proyek menggunakan
`venv\Scripts\python.exe -m uvicorn main:app --app-dir backend --reload`.

Dokumentasi operasional dan integrasi tersedia di [indeks backend](docs/README.md).
Kontrak aktif mencakup 120 operasi HTTP hingga penerimaan sekolah/konsumsi,
dengan schema `20260911_0022`. Desain modul yang belum tersedia tetap roadmap.
