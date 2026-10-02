"""Generate the FSOS operator manual as a dependency-free DOCX file."""

from __future__ import annotations

import struct
from datetime import date
from pathlib import Path
from xml.sax.saxutils import escape
from zipfile import ZIP_DEFLATED, ZipFile


ROOT = Path(__file__).resolve().parents[2]
OUTPUT = ROOT / "backend" / "docs" / "FSOS-Manual-Pengguna-dan-Panduan-Demo.docx"
FLOW_IMAGE = Path.home() / "Downloads" / "flow_fsos.png"
MOCKUP_IMAGE = Path.home() / "Downloads" / "mockup_fsos.png"


def x(value: object) -> str:
    return escape(str(value), {'"': '&quot;'})


def run(text: str, *, bold=False, color=None, size=None, code=False) -> str:
    props = []
    if bold:
        props.append('<w:b/>')
    if color:
        props.append(f'<w:color w:val="{color}"/>')
    if size:
        props.append(f'<w:sz w:val="{size}"/><w:szCs w:val="{size}"/>')
    if code:
        props.append('<w:rFonts w:ascii="Consolas" w:hAnsi="Consolas"/>')
    return f'<w:r><w:rPr>{"".join(props)}</w:rPr><w:t xml:space="preserve">{x(text)}</w:t></w:r>'


def p(text='', *, style=None, bold=False, color=None, size=None, align=None,
      before=0, after=100, keep=False, code=False) -> str:
    ppr = []
    if style:
        ppr.append(f'<w:pStyle w:val="{style}"/>')
    if align:
        ppr.append(f'<w:jc w:val="{align}"/>')
    if before or after:
        ppr.append(f'<w:spacing w:before="{before}" w:after="{after}"/>')
    if keep:
        ppr.append('<w:keepNext/>')
    return f'<w:p><w:pPr>{"".join(ppr)}</w:pPr>{run(text, bold=bold, color=color, size=size, code=code)}</w:p>'


def bullet(text: str, level=0) -> str:
    return (f'<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="{level}"/>'
            f'<w:numId w:val="1"/></w:numPr><w:spacing w:after="60"/></w:pPr>{run(text)}</w:p>')


def numbered(text: str, level=0) -> str:
    return (f'<w:p><w:pPr><w:pStyle w:val="ListParagraph"/><w:numPr><w:ilvl w:val="{level}"/>'
            f'<w:numId w:val="2"/></w:numPr><w:spacing w:after="70"/></w:pPr>{run(text)}</w:p>')


def note(title: str, text: str, color='E8F5EE') -> str:
    return table([[title, text]], widths=[1800, 6900], header=False, fill=color)


def table(rows, *, widths=None, header=True, fill=None) -> str:
    widths = widths or [int(9000 / len(rows[0]))] * len(rows[0])
    grid = ''.join(f'<w:gridCol w:w="{width}"/>' for width in widths)
    tr_xml = []
    for row_index, row in enumerate(rows):
        cells = []
        for index, value in enumerate(row):
            shade = '0C3B5D' if header and row_index == 0 else fill
            tcpr = [f'<w:tcW w:w="{widths[index]}" w:type="dxa"/>']
            if shade:
                tcpr.append(f'<w:shd w:fill="{shade}"/>')
            text_color = 'FFFFFF' if header and row_index == 0 else None
            cells.append(f'<w:tc><w:tcPr>{"".join(tcpr)}</w:tcPr>'
                         f'{p(str(value), bold=header and row_index == 0, color=text_color, after=40)}</w:tc>')
        tr_xml.append(f'<w:tr>{"".join(cells)}</w:tr>')
    return (f'<w:tbl><w:tblPr><w:tblW w:w="9000" w:type="dxa"/>'
            f'<w:tblBorders><w:top w:val="single" w:sz="4" w:color="B8C4CC"/>'
            f'<w:left w:val="single" w:sz="4" w:color="B8C4CC"/>'
            f'<w:bottom w:val="single" w:sz="4" w:color="B8C4CC"/>'
            f'<w:right w:val="single" w:sz="4" w:color="B8C4CC"/>'
            f'<w:insideH w:val="single" w:sz="4" w:color="DDE4E8"/>'
            f'<w:insideV w:val="single" w:sz="4" w:color="DDE4E8"/>'
            f'</w:tblBorders></w:tblPr><w:tblGrid>{grid}</w:tblGrid>{"".join(tr_xml)}</w:tbl>')


def heading(text: str, level=1) -> str:
    return p(text, style=f'Heading{level}', before=180 if level == 1 else 100, after=90, keep=True)


def page_break() -> str:
    return '<w:p><w:r><w:br w:type="page"/></w:r></w:p>'


def image_size(path: Path) -> tuple[int, int]:
    data = path.read_bytes()
    if data[:8] != b'\x89PNG\r\n\x1a\n':
        return 1200, 675
    return struct.unpack('>II', data[16:24])


def image_xml(rel_id: str, path: Path, doc_pr: int, max_width_in=6.7) -> str:
    width, height = image_size(path)
    cx = int(max_width_in * 914400)
    cy = int(cx * height / width)
    return f'''<w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:drawing>
<wp:inline distT="0" distB="0" distL="0" distR="0"><wp:extent cx="{cx}" cy="{cy}"/>
<wp:docPr id="{doc_pr}" name="{x(path.name)}"/><wp:cNvGraphicFramePr/>
<a:graphic xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/picture">
<pic:pic xmlns:pic="http://schemas.openxmlformats.org/drawingml/2006/picture"><pic:nvPicPr><pic:cNvPr id="0" name="{x(path.name)}"/><pic:cNvPicPr/></pic:nvPicPr>
<pic:blipFill><a:blip r:embed="{rel_id}"/><a:stretch><a:fillRect/></a:stretch></pic:blipFill>
<pic:spPr><a:xfrm><a:off x="0" y="0"/><a:ext cx="{cx}" cy="{cy}"/></a:xfrm><a:prstGeom prst="rect"><a:avLst/></a:prstGeom></pic:spPr>
</pic:pic></a:graphicData></a:graphic></wp:inline></w:drawing></w:r></w:p>'''


def build_body(images: list[tuple[str, Path]]) -> str:
    out = []
    out += [
        p('FOOD SAFETY AND TRACEABILITY MANAGEMENT SYSTEM', bold=True, color='0C3B5D', size=34,
          align='center', before=1200, after=180),
        p('Manual Pengguna dan Panduan Demo FSOS', bold=True, color='0A8F67', size=28, align='center', after=300),
        p('Receiving • Storage • IoT • Produksi • Holding • Packaging • Delivery • Penerimaan Sekolah • Incident',
          color='425466', size=19, align='center', after=500),
        table([['Dokumen', 'Manual operasional dan runbook demo'], ['Versi', '1.0'],
               ['Tanggal', '2 Oktober 2026'], ['Cakupan', 'Frontend web dan proses operasional FSOS']],
              widths=[2500, 6500], header=False, fill='F3F7F8'),
        p('Dokumen ini ditujukan untuk administrator tenant, operator dapur, petugas gudang, petugas produksi, '
          'petugas distribusi, guru/operator sekolah, dan presenter demo.', align='center', before=500),
        page_break(),
        heading('Kontrol dokumen', 1),
        table([['Elemen', 'Keterangan'], ['Pemilik proses', 'Tim Food Safety / Administrator FSOS'],
               ['Klasifikasi', 'Panduan operasional'], ['Sumber kebenaran teknis', 'OpenAPI backend dan dokumentasi frontend API'],
               ['Pembaruan', 'Perbarui bersama perubahan alur, permission, endpoint, atau tampilan frontend']],
              widths=[2500, 6500]),
        heading('Cara menggunakan manual', 2),
        bullet('Ikuti Bab 3 untuk menyiapkan master data sebelum transaksi pertama.'),
        bullet('Ikuti Bab 4–11 untuk alur operasional end-to-end.'),
        bullet('Gunakan Bab 12 untuk insiden, complaint, traceability, dan recall.'),
        bullet('Gunakan Bab 14–15 untuk demo FSOS_EXPO dan FSOS_EXPO_INCIDENT.'),
        note('PENTING', 'Nama tombol dapat mengikuti bahasa UI terbaru. Validasi server tetap menjadi keputusan akhir; '
             'UI tidak menggantikan SOP keamanan pangan organisasi.', 'FFF3CD'),
        heading('Daftar isi', 1),
        '<w:p><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText xml:space="preserve"> TOC \\o "1-3" \\h \\z \\u </w:instrText></w:r><w:r><w:fldChar w:fldCharType="separate"/></w:r><w:r><w:t>Klik kanan lalu pilih Update Field di Microsoft Word.</w:t></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p>',
        page_break(),
        heading('1. Gambaran umum sistem', 1),
        p('FSOS mencatat rantai keamanan makanan dari bahan diterima sampai makanan diterima sekolah. Setiap batch '
          'bahan, proses produksi, kemasan, perjalanan, penerimaan, dan kejadian insiden dapat ditelusuri.'),
        table([['Tahap', 'Tujuan utama', 'Menu frontend'],
               ['Receiving', 'Mencatat supplier, suhu, jumlah, kedaluwarsa, kondisi, foto, QR', 'Penerimaan Bahan'],
               ['Storage', 'Putaway batch ke storage/rak dan menjaga stok', 'Penerimaan/Pengeluaran Bahan'],
               ['IoT', 'Monitoring suhu storage, food probe, GPS dan suhu box', 'Monitor Suhu / Binding MQTT'],
               ['Produksi', 'Mengeluarkan bahan, cooking, suhu inti, holding', 'Batch Produksi'],
               ['Packaging', 'Membuat kemasan, QR, suhu awal, holding', 'Paket & QR'],
               ['Delivery', 'Manifest, armada, tujuan, ETA, GPS', 'Pengiriman Aktif / Live Tracking'],
               ['School', 'Scan penerimaan, suhu, kondisi, tanda tangan', 'Penerimaan Sekolah'],
               ['Incident', 'Complaint, batch impact, recall, withdrawal', 'Keluhan / Recall / Cek Kemasan']],
              widths=[1400, 4700, 2900]),
    ]
    if images:
        out += [heading('Alur bisnis referensi', 2), image_xml(images[0][0], images[0][1], 1),
                p('Gambar 1. Alur Food Safety and Traceability Management System.', align='center', color='667788')]
    out += [
        heading('2. Login, tenant, role, dan keamanan', 1),
        numbered('Buka URL frontend resmi organisasi.'),
        numbered('Masukkan tenant code, username, dan password dari administrator.'),
        numbered('Pastikan tenant yang tampil sesuai konteks kerja sebelum membuat transaksi.'),
        numbered('Logout setelah penggunaan pada perangkat bersama.'),
        table([['Peran contoh', 'Aktivitas'], ['ADMIN', 'Master data, user, konfigurasi, seluruh proses tenant'],
               ['Operator dapur/gudang', 'Receiving, putaway, pengeluaran bahan, produksi, packaging'],
               ['Petugas distribusi', 'Manifest, departure, live tracking, completion'],
               ['Operator sekolah', 'Penerimaan, suhu, kondisi, konsumsi'],
               ['Guru/penanggung jawab', 'Tanda tangan penerimaan/complaint sesuai assignment sekolah']],
              widths=[2500, 6500]),
        note('KEAMANAN', 'Jangan berbagi password, access token, QR sensitif, atau API key. Permission UI hanya '
             'membantu navigasi; backend selalu memvalidasi tenant, role, permission, version, dan status.', 'FDECEC'),
        heading('3. Persiapan master data', 1),
        p('Isi master dengan urutan berikut agar pilihan parent dan referensi tersedia.'),
        numbered('Dapur: kode, nama, alamat, latitude, longitude, kapasitas, status ACTIVE.'),
        numbered('Storage: pilih dapur, isi kode/nama, tipe COLD_STORAGE, FREEZER, atau DRY_STORAGE, ambang suhu, dan koordinat bila diperlukan.'),
        numbered('Zona/rak storage: pilih storage induk dan isi kode/nama zona.'),
        numbered('Supplier dan bahan baku: isi identitas supplier; bahan berisi kategori, UOM, tipe storage, suhu rekomendasi, dan batas simpan.'),
        numbered('Relasi supplier–material: hubungkan setiap supplier dengan bahan yang boleh dipasok.'),
        numbered('Menu dan resep: buat menu, kategori makanan, UOM, holding limit; tambahkan komposisi bahan dan quantity.'),
        numbered('Jenis kemasan: kode, nama, material, dan volume.'),
        numbered('Sekolah: pilih dapur pemasok, isi kode/nama, alamat, jumlah siswa, latitude, longitude, status ACTIVE.'),
        numbered('Driver dan kendaraan: buat driver, lalu kendaraan beserta plat, tipe, kapasitas, dan driver.'),
        numbered('User dan role: daftarkan operator, role, jabatan, serta assignment dapur/sekolah.'),
        table([['Pemeriksaan master', 'Kriteria lulus'], ['Koordinat', 'Dapur dan seluruh sekolah memiliki latitude/longitude valid'],
               ['Storage', 'Minimal satu storage sesuai kebutuhan bahan dan zona/rak'],
               ['Resep', 'Seluruh bahan resep tersedia dan UOM benar'], ['Armada', 'Kendaraan ACTIVE dan memiliki driver'],
               ['Sekolah', 'ACTIVE, terkait dapur, koordinat dan alamat lengkap']], widths=[2800, 6200]),
        heading('4. Device IoT dan binding MQTT', 1),
        heading('4.1 Jenis device', 2),
        table([['Device', 'Penggunaan', 'Binding'], ['TEMPERATURE', 'Suhu chiller/freezer/dry storage', 'Device ke storage/zone'],
               ['FOOD_TEMPERATURE', 'Food probe on-demand untuk field suhu manual', 'Tanpa zone; topic/event/sensor food probe'],
               ['GPS', 'Posisi armada', 'Device ke kendaraan'], ['Suhu box mobil', 'Temperatur cold box perjalanan', 'Device/telemetry delivery']],
              widths=[2200, 4200, 2600]),
        heading('4.2 Binding MQTT', 2),
        numbered('Buka Binding MQTT Device.'),
        numbered('Pilih topic tersimpan lalu pilih event terbaru yang payload-nya valid.'),
        numbered('Pilih device existing untuk mencegah duplikasi, atau buat device bila belum tersedia.'),
        numbered('Pilih selector event dan selector sensor yang tepat. Contoh payload temperature memakai temperature_c; sensor dapat membedakan kanal.'),
        numbered('Untuk GPS, lanjutkan binding device ke kendaraan pada Master Data → Binding GPS Armada.'),
        numbered('Pastikan last online dan jumlah event bertambah. Binding tidak mengubah firmware/device MQTT.'),
        note('FOOD PROBE', 'Food probe tidak ditampilkan sebagai storage monitor. Nilainya hanya diambil ketika operator '
             'menekan Ambil dari sensor pada receiving, selesai masak, packaging, atau penerimaan sekolah.', 'E8F5EE'),
        heading('5. Receiving bahan baku dan pengukuran suhu', 1),
        numbered('Buka Penerimaan Bahan lalu pilih Terima Bahan.'),
        numbered('Pilih dapur dan supplier; isi tanggal/waktu penerimaan.'),
        numbered('Tambahkan item: bahan, batch code, jumlah, UOM, expired date, kondisi, dan foto inspeksi.'),
        numbered('Isi suhu manual atau pilih Thermo Makanan lalu tekan Ambil dari sensor. Periksa angka, waktu sampel, usia, dan device sebelum menerima nilai.'),
        numbered('Simpan receiving berstatus CREATED; periksa kembali seluruh item.'),
        numbered('Complete receiving dan tentukan accepted/rejected per item. Sistem membuat raw material batch dan QR.'),
        numbered('Cetak label QR dan tempel pada bahan/lot fisik.'),
        table([['Validasi', 'Tindakan'], ['Suhu tidak sesuai', 'Tahan bahan, catat kondisi/foto, ikuti keputusan QA'],
               ['Kedaluwarsa/tanggal tidak valid', 'Tolak atau koreksi sebelum complete'], ['QR gagal dipindai', 'Gunakan payload/UUID resmi, jangan membuat QR manual'],
               ['Foto gagal', 'Pastikan JPEG/PNG/WebP dan ukuran sesuai batas upload']], widths=[2800, 6200]),
        heading('6. Putaway, stok, FEFO/FIFO, dan pengeluaran', 1),
        numbered('Setelah receiving accepted, pilih batch lalu lakukan putaway.'),
        numbered('Pilih storage dan zone/rak yang sesuai; isi quantity. Storage utama ditetapkan pada tahap ini.'),
        numbered('Gunakan daftar bahan untuk pencarian jenis/nama/batch. Prioritaskan FEFO untuk bahan ber-expiry; gunakan FIFO bila expiry setara/tidak relevan.'),
        numbered('Saat produksi dimulai, scan QR bahan. Sistem mengisi batch, storage, version, dan stok yang tersedia.'),
        numbered('Jika batch belum memiliki storage, pilih dari storage aktif yang sesuai sebelum issue; jangan menebak UUID.'),
        numbered('Konfirmasi quantity issue dan periksa stok tersisa.'),
        heading('7. Monitoring suhu storage', 1),
        numbered('Buka Monitor Suhu.'),
        numbered('Periksa Storage Terpantau, Dalam Batas, Di Luar Batas, dan Tanpa Data.'),
        numbered('Klik/lihat card storage untuk suhu terbaru, ambang, waktu pembaruan, dan status OK/LOW/HIGH/NO_DATA.'),
        numbered('Jika NO_DATA, periksa device ACTIVE, zone binding, topic/event selector, consumer MQTT, dan timestamp log.'),
        numbered('Jika di luar batas, buka Alarm dan lakukan acknowledgment sesuai SOP setelah tindakan korektif.'),
        note('CATATAN', 'Daftar monitor berasal dari master storage aktif, bukan master device. Karena itu storage tanpa '
             'device tetap dapat muncul sebagai NO_DATA.', 'EAF2F8'),
        heading('8. Produksi, cooking, dan holding', 1),
        numbered('Buka Batch Produksi dan buat manufacturing order: kode MO, dapur, menu, planned quantity.'),
        numbered('Tekan Mulai, scan seluruh QR bahan, cek storage, stok, version, required quantity, lalu konfirmasi.'),
        numbered('Sistem mengurangi stok secara atomik dan mencatat started_at.'),
        numbered('Saat masak selesai, isi actual quantity dan suhu inti. Nilai dapat diambil dari food probe lalu dikonfirmasi operator.'),
        numbered('Complete produksi. Sistem mencatat finished_at, holding_started_at, holding policy, dan expiry holding.'),
        numbered('Pantau SAFE/WARNING/EXPIRED. Produk melewati batas harus mengikuti discard/QA policy.'),
        heading('9. Packaging dan QR kemasan', 1),
        numbered('Buka Paket & QR dan pilih batch produksi COMPLETED.'),
        numbered('Pilih jenis kemasan, isi package code, nomor, quantity, dan suhu awal packaging.'),
        numbered('Gunakan food probe bila tersedia; operator tetap mengonfirmasi suhu.'),
        numbered('Start holding package lalu release untuk distribusi sesuai status yang diizinkan.'),
        numbered('Cetak label QR kemasan. Satu QR harus merujuk satu package resmi.'),
        heading('10. Manifest, departure, dan live tracking', 1),
        numbered('Buka Pengiriman Aktif dan buat manifest: dapur, kendaraan, driver, package, sekolah tujuan.'),
        numbered('Pastikan koordinat dapur/sekolah terisi agar Google Routes dapat menghitung jarak, durasi, dan ETA.'),
        numbered('Lakukan loading/scan kemasan dan tekan Berangkat. Status menjadi IN_TRANSIT.'),
        numbered('Buka Live Tracking Delivery dan pilih delivery.'),
        numbered('Peta menampilkan Dapur asal, sekolah tujuan, rute, dan ikon mobil pada GPS terbaru.'),
        numbered('Klik marker dapur/sekolah untuk nama, kode, alamat, koordinat; klik mobil untuk status dan waktu GPS.'),
        numbered('Periksa sisa jarak, durasi, ETA, riwayat GPS, serta event enter/exit geofence.'),
        numbered('Setelah tiba, complete delivery. Jangan mencatat penerimaan sebelum delivery COMPLETED.'),
        table([['Masalah tracking', 'Pemeriksaan'], ['Tidak ada GPS', 'Device GPS ACTIVE, binding kendaraan, topic, event, latitude/longitude, consumer'],
               ['Jarak tidak sesuai', 'Koordinat dapur/sekolah dan posisi GPS; Google Routes API aktif'],
               ['Marker salah', 'Master koordinat tenant dan manifest sekolah'], ['ETA tidak berubah', 'Timestamp GPS terbaru dan routing response']], widths=[2700, 6300]),
        heading('11. Penerimaan sekolah dan konsumsi', 1),
        numbered('Buka Penerimaan Sekolah lalu scan QR kemasan.'),
        numbered('Periksa warning incident batch sebelum melanjutkan.'),
        numbered('Pastikan delivery COMPLETED dan package–school sesuai manifest.'),
        numbered('Isi jumlah diterima, kondisi, accepted/rejected, suhu makanan, foto/catatan bila diperlukan.'),
        numbered('Ambil suhu dari food probe atau isi manual, lalu konfirmasi.'),
        numbered('Simpan penerimaan dan capture tanda tangan digital oleh user yang memiliki assignment sekolah.'),
        numbered('Catat konsumsi/discard dengan quantity dan catatan; jangan lanjut jika warning incident/recall aktif.'),
        heading('12. Traceability, incident, complaint, dan recall', 1),
        heading('12.1 Scan dan laporan incident', 2),
        numbered('Buka Cek Kemasan lalu scan QR/package code.'),
        numbered('Jika incident aktif, kartu warning menampilkan penyebab, severity, batch, dampak, recall, dan tindakan wajib.'),
        numbered('Tahan penerimaan/konsumsi; isolasi kemasan; buka laporan dampak batch.'),
        numbered('Untuk kejadian baru tekan Laporkan insiden makanan, pilih kategori/severity, isi deskripsi, sekolah, foto, lalu kirim.'),
        numbered('Capture tanda tangan pelapor bila diwajibkan.'),
        heading('12.2 Kategori incident', 2),
        table([['Kategori', 'Contoh'], ['DAMAGE', 'Kemasan bocor/rusak'], ['CONTAMINATION', 'Bau/warna/benda asing'],
               ['PARASITE', 'Parasit'], ['ANIMAL', 'Hewan/serangga'], ['ILLNESS', 'Keluhan sakit'],
               ['EXPIRED', 'Kedaluwarsa/holding habis'], ['TEMPERATURE', 'Suhu tidak sesuai'], ['OTHER', 'Kejadian lain']],
              widths=[2400, 6600]),
        heading('12.3 Laporan dampak dan recall', 2),
        bullet('Menu Keluhan menampilkan complaint dan laporan lengkap: package, batch produksi, bahan, lokasi, delivery, receipt, consumption, signature.'),
        bullet('Batch impact menampilkan seluruh kemasan satu production batch dan sekolah tujuannya.'),
        bullet('Recall digunakan untuk menarik output batch; eksekusi menandai package nonterminal sebagai RECALLED.'),
        bullet('Withdrawal mencatat penarikan fisik, quantity, kondisi, waktu, dan bukti foto.'),
        note('LARANGAN', 'Kemasan dengan warning aktif tidak boleh diterima atau dikonsumsi hanya karena kondisi visual tampak baik. '
             'Ikuti investigasi, recall, dan keputusan petugas berwenang.', 'FDECEC'),
        heading('13. Checklist operasional harian', 1),
        table([['Waktu', 'Checklist'], ['Awal shift', 'Login tenant benar; device online; storage temperature; alarm terbuka; food probe tersedia'],
               ['Receiving', 'Supplier/bahan benar; suhu; expiry; kondisi; foto; accepted; QR; putaway'],
               ['Produksi', 'MO/menu; scan bahan; FEFO/FIFO; stok; suhu inti; holding'],
               ['Distribusi', 'Package QR; suhu; manifest; armada/driver; GPS; tujuan; departure'],
               ['Sekolah', 'Warning incident; delivery completed; scan; quantity; suhu; kondisi; signature'],
               ['Akhir shift', 'Alarm/incident; delivery belum selesai; holding warning; stok; logout']], widths=[2000, 7000]),
        page_break(),
        heading('14. Panduan demo FSOS_EXPO', 1),
        p('FSOS_EXPO adalah tenant demo live yang boleh di-reset. Master dipertahankan; transaksi dapat dibuat ulang.'),
        heading('14.1 Tujuan', 2),
        bullet('Mendemokan alur nyata dari receiving sampai delivery/penerimaan melalui frontend/API aktif.'),
        bullet('Mendemokan live tracking dengan delivery ditinggalkan IN_TRANSIT.'),
        bullet('Boleh di-cleanup antar sesi oleh ADMIN tenant FSOS_EXPO.'),
        heading('14.2 Persiapan', 2),
        numbered('Administrator memastikan migrasi database terbaru, backend/frontend aktif, dan master exhibition sudah tersedia.'),
        numbered('Login menggunakan tenant FSOS_EXPO dan akun demo yang diberikan administrator. Password tidak dicantumkan dalam manual.'),
        numbered('Pastikan kitchen, storage, supplier, bahan, menu/resep, packaging, sekolah, kendaraan, driver, serta device tersedia.'),
        numbered('Untuk demo sampai delivery aktif, jalankan demo_live_flow.py dengan --tenant FSOS_EXPO --run-tag unik --stop-after-depart terhadap base URL resmi.'),
        numbered('Login ulang/refresh frontend. Periksa receiving, batch produksi, package, dan delivery IN_TRANSIT.'),
        heading('14.3 Skenario presentasi live', 2),
        table([['Urutan', 'Halaman', 'Narasi'], ['1', 'Dashboard', 'Ringkasan tenant dan status operasi'],
               ['2', 'Penerimaan Bahan', 'Batch bahan, suhu, QR, storage'], ['3', 'Batch Produksi', 'Bahan terpakai, cooking, holding'],
               ['4', 'Paket & QR', 'Kemasan dan label'], ['5', 'Pengiriman Aktif', 'Manifest dan status IN_TRANSIT'],
               ['6', 'Live Tracking', 'Rute, mobil, jarak, durasi, ETA, geofence'],
               ['7', 'Penerimaan Sekolah', 'Complete delivery lalu scan, suhu, signature'],
               ['8', 'Traceability', 'Telusuri asal bahan sampai sekolah']], widths=[900, 2500, 5600]),
        heading('14.4 Reset', 2),
        bullet('Tombol Reset demo hanya terlihat untuk ADMIN yang login pada tenant_code FSOS_EXPO.'),
        bullet('Reset menghapus transaksi demo tetapi mempertahankan master, user, dan tenant.'),
        bullet('Baca dialog, ketik phrase konfirmasi, dan jangan reset saat presenter/operator lain sedang memakai tenant.'),
        bullet('FSOS_EXPO_INCIDENT tidak menampilkan tombol reset dan backend menolak cleanup tenant tersebut.'),
        page_break(),
        heading('15. Panduan demo FSOS_EXPO_INCIDENT', 1),
        p('FSOS_EXPO_INCIDENT adalah tenant skenario incident/recall yang sudah jadi dan tidak boleh di-reset untuk latihan biasa.'),
        heading('15.1 Data skenario', 2),
        table([['Objek', 'Data demo'], ['Production batch', 'MO-INCIDENT-001'],
               ['Kemasan', 'PKG-INCIDENT-001 sampai PKG-INCIDENT-004'],
               ['Incident', 'CONTAMINATION, HIGH, OPEN; bau tidak sedap sebelum dibagikan'],
               ['Dampak', '4 kemasan, 4 delivery, 3 diterima, 1 dikonsumsi'],
               ['Recall', 'Package nonterminal ditarik; withdrawal fisik tersedia']], widths=[2600, 6400]),
        heading('15.2 Urutan demonstrasi', 2),
        numbered('Login ke FSOS_EXPO_INCIDENT dengan akun demo dari administrator.'),
        numbered('Buka Keluhan dan tampilkan complaint aktif serta laporan batch impact.'),
        numbered('Scan PKG-INCIDENT-001 untuk menunjukkan sumber complaint.'),
        numbered('Scan PKG-INCIDENT-002 atau 004 untuk menunjukkan warning lintas kemasan batch yang sama.'),
        numbered('Jelaskan penyebab, batch MO-INCIDENT-001, severity, status recall, jumlah tujuan, receipt, consumption, dan tindakan wajib.'),
        numbered('Buka Recall untuk menunjukkan penarikan serta withdrawal fisik.'),
        numbered('Buka traceability untuk menelusuri bahan INCIDENT-BERAS-001 dan INCIDENT-AYAM-001 sampai sekolah.'),
        heading('15.3 Hal yang tidak dilakukan', 2),
        bullet('Jangan menekan cleanup/reset pada tenant incident.'),
        bullet('Jangan mengubah status complaint/recall demo tanpa rencana pemulihan.'),
        bullet('Jangan memakai data incident sebagai data produksi nyata.'),
        bullet('Foto/signature demo harus dicapture lewat endpoint/UI resmi; seed tidak membuat evidence palsu.'),
        heading('16. Troubleshooting cepat', 1),
        table([['Gejala', 'Penyebab umum', 'Tindakan'],
               ['Data kosong', 'Login tenant salah atau filter/status', 'Periksa tenant code, logout/login, reset filter, refresh'],
               ['401 refresh', 'Sesi kedaluwarsa/revoked', 'Login ulang; periksa konfigurasi domain/token'],
               ['403', 'Role/permission/tenant tidak sesuai', 'Periksa role dan assignment; jangan bypass backend'],
               ['QR tidak ditemukan', 'QR tenant lain/kode salah', 'Scan QR resmi atau package/batch identifier tenant aktif'],
               ['Storage NO_DATA', 'Belum ada telemetry terikat', 'Periksa device, zone, topic/event, consumer dan timestamp'],
               ['Food probe gagal', 'Device type/zone/freshness salah', 'FOOD_TEMPERATURE, zone null, ACTIVE, sampel <= maximum age'],
               ['GPS tidak bergerak', 'Binding kendaraan/topic salah', 'Cek event MQTT, device GPS, vehicle binding, delivery'],
               ['Route salah', 'Koordinat master salah', 'Koreksi latitude/longitude dapur/sekolah dan cek Google Routes'],
               ['Receipt ditolak', 'Delivery belum COMPLETED/manifes mismatch', 'Selesaikan delivery dan scan package tujuan yang tepat'],
               ['Tombol reset salah tenant', 'Frontend/backend belum versi terbaru', 'Deploy keduanya, logout/login; hanya FSOS_EXPO ADMIN']],
              widths=[2100, 3000, 3900]),
        heading('17. Eskalasi dan bukti yang disiapkan', 1),
        bullet('Tenant code, menu, waktu kejadian, dan langkah reproduksi.'),
        bullet('Request ID/correlation ID dari respons API; jangan kirim access token/password.'),
        bullet('Kode batch/package/delivery/device dan screenshot tanpa data pribadi sensitif.'),
        bullet('Status backend health/database, browser console, serta timestamp MQTT bila terkait IoT.'),
        heading('18. Ringkasan status kritis', 1),
        table([['Domain', 'Status penting'], ['Receiving', 'CREATED → COMPLETED/CANCELLED; item accepted/rejected'],
               ['Raw batch', 'ACCEPTED dan stok tersedia; expiry untuk FEFO'], ['Production', 'CREATED → RUNNING → COMPLETED'],
               ['Package', 'PACKAGED/RELEASED/DELIVERED/RECEIVED/CONSUMED atau RECALLED/DISCARDED'],
               ['Delivery', 'CREATED → IN_TRANSIT → COMPLETED'], ['Incident', 'OPEN/INVESTIGATING; severity LOW–CRITICAL'],
               ['Recall', 'OPEN/EXECUTED/COMPLETED pada ringkasan scan'], ['Temperature', 'OK/LOW/HIGH/NO_DATA']],
              widths=[2300, 6700]),
    ]
    if len(images) > 1:
        out += [page_break(), heading('Lampiran A. Referensi tampilan awal', 1), image_xml(images[1][0], images[1][1], 2),
                p('Gambar 2. Mockup referensi dashboard dan alur mobile.', align='center', color='667788')]
    out += [
        heading('Lampiran B. Referensi teknis internal', 1),
        bullet('backend/docs/frontend-api.md — kontrak endpoint aktif.'),
        bullet('backend/docs/exhibition-demo.md — runbook exhibition dan command server.'),
        bullet('backend/docs/event-catalog.md — event, producer, consumer, ordering, retry/replay.'),
        bullet('vue-food-security/docs/frontend-api.md — salinan kontrak untuk tim frontend.'),
        p('Akhir dokumen', bold=True, color='0A8F67', align='center', before=500),
    ]
    return ''.join(out)


def generate() -> Path:
    images = []
    for index, path in enumerate((FLOW_IMAGE, MOCKUP_IMAGE), start=1):
        if path.is_file():
            images.append((f'rIdImage{index}', path))

    body = build_body(images)
    document = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:document xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"
 xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships"
 xmlns:wp="http://schemas.openxmlformats.org/drawingml/2006/wordprocessingDrawing"
 xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main">
<w:body>{body}<w:sectPr><w:headerReference w:type="default" r:id="rIdHeader"/>
<w:footerReference w:type="default" r:id="rIdFooter"/><w:pgSz w:w="11906" w:h="16838"/>
<w:pgMar w:top="1080" w:right="1080" w:bottom="1080" w:left="1080" w:header="500" w:footer="500"/>
</w:sectPr></w:body></w:document>'''

    styles = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:styles xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:style w:type="paragraph" w:default="1" w:styleId="Normal"><w:name w:val="Normal"/><w:rPr><w:rFonts w:ascii="Aptos" w:hAnsi="Aptos"/><w:sz w:val="21"/></w:rPr><w:pPr><w:spacing w:after="100" w:line="276" w:lineRule="auto"/></w:pPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading1"><w:name w:val="heading 1"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:pageBreakBefore/><w:spacing w:before="180" w:after="120"/><w:outlineLvl w:val="0"/></w:pPr><w:rPr><w:b/><w:color w:val="0C3B5D"/><w:sz w:val="30"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading2"><w:name w:val="heading 2"/><w:basedOn w:val="Normal"/><w:next w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:spacing w:before="160" w:after="90"/><w:outlineLvl w:val="1"/></w:pPr><w:rPr><w:b/><w:color w:val="0A8F67"/><w:sz w:val="25"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="Heading3"><w:name w:val="heading 3"/><w:basedOn w:val="Normal"/><w:qFormat/><w:pPr><w:keepNext/><w:outlineLvl w:val="2"/></w:pPr><w:rPr><w:b/><w:color w:val="425466"/><w:sz w:val="22"/></w:rPr></w:style>
<w:style w:type="paragraph" w:styleId="ListParagraph"><w:name w:val="List Paragraph"/><w:basedOn w:val="Normal"/><w:pPr><w:ind w:left="540" w:hanging="280"/></w:pPr></w:style>
</w:styles>'''
    numbering = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<w:numbering xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main">
<w:abstractNum w:abstractNumId="1"><w:multiLevelType w:val="multilevel"/><w:lvl w:ilvl="0"><w:numFmt w:val="bullet"/><w:lvlText w:val="•"/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="540"/></w:tabs><w:ind w:left="540" w:hanging="280"/></w:pPr></w:lvl></w:abstractNum>
<w:abstractNum w:abstractNumId="2"><w:multiLevelType w:val="multilevel"/><w:lvl w:ilvl="0"><w:start w:val="1"/><w:numFmt w:val="decimal"/><w:lvlText w:val="%1."/><w:lvlJc w:val="left"/><w:pPr><w:tabs><w:tab w:val="num" w:pos="540"/></w:tabs><w:ind w:left="540" w:hanging="280"/></w:pPr></w:lvl></w:abstractNum>
<w:num w:numId="1"><w:abstractNumId w:val="1"/></w:num><w:num w:numId="2"><w:abstractNumId w:val="2"/></w:num></w:numbering>'''
    header = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:hdr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="right"/><w:pBdr><w:bottom w:val="single" w:sz="6" w:color="0A8F67"/></w:pBdr></w:pPr><w:r><w:rPr><w:b/><w:color w:val="0C3B5D"/></w:rPr><w:t>FSOS • Manual Pengguna</w:t></w:r></w:p></w:hdr>'''
    footer = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?><w:ftr xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"><w:p><w:pPr><w:jc w:val="center"/></w:pPr><w:r><w:t>FSOS • 2 Oktober 2026 • Halaman </w:t></w:r><w:r><w:fldChar w:fldCharType="begin"/></w:r><w:r><w:instrText> PAGE </w:instrText></w:r><w:r><w:fldChar w:fldCharType="end"/></w:r></w:p></w:ftr>'''
    rels = ['<Relationship Id="rIdStyles" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>',
            '<Relationship Id="rIdNumbering" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/numbering" Target="numbering.xml"/>',
            '<Relationship Id="rIdHeader" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/header" Target="header1.xml"/>',
            '<Relationship Id="rIdFooter" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/footer" Target="footer1.xml"/>']
    for index, (rel_id, _) in enumerate(images, start=1):
        rels.append(f'<Relationship Id="{rel_id}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/image" Target="media/image{index}.png"/>')
    document_rels = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                     '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
                     + ''.join(rels) + '</Relationships>')
    content_types = ['<Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
                     '<Default Extension="xml" ContentType="application/xml"/>',
                     '<Override PartName="/word/document.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.document.main+xml"/>',
                     '<Override PartName="/word/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.styles+xml"/>',
                     '<Override PartName="/word/numbering.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.numbering+xml"/>',
                     '<Override PartName="/word/header1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.header+xml"/>',
                     '<Override PartName="/word/footer1.xml" ContentType="application/vnd.openxmlformats-officedocument.wordprocessingml.footer+xml"/>']
    if images:
        content_types.append('<Default Extension="png" ContentType="image/png"/>')
    types_xml = ('<?xml version="1.0" encoding="UTF-8" standalone="yes"?>'
                 '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">'
                 + ''.join(content_types) + '</Types>')
    package_rels = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
<Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="word/document.xml"/>
</Relationships>'''

    OUTPUT.parent.mkdir(parents=True, exist_ok=True)
    with ZipFile(OUTPUT, 'w', ZIP_DEFLATED) as archive:
        archive.writestr('[Content_Types].xml', types_xml)
        archive.writestr('_rels/.rels', package_rels)
        archive.writestr('word/document.xml', document)
        archive.writestr('word/styles.xml', styles)
        archive.writestr('word/numbering.xml', numbering)
        archive.writestr('word/header1.xml', header)
        archive.writestr('word/footer1.xml', footer)
        archive.writestr('word/_rels/document.xml.rels', document_rels)
        for index, (_, path) in enumerate(images, start=1):
            archive.write(path, f'word/media/image{index}.png')
    with ZipFile(OUTPUT) as archive:
        bad_file = archive.testzip()
        if bad_file:
            raise RuntimeError(f'Invalid DOCX entry: {bad_file}')
    return OUTPUT


if __name__ == '__main__':
    result = generate()
    print(f'Generated {result} ({result.stat().st_size} bytes)')
