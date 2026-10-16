# Nextion Take Data: 30 siklus × (25 s purging + 5 s collecting)

**Status:** implementasi kode dan QA offline PASS; **belum di-flash atau diuji pada alat fisik**. Tombol Take Data tetap menggunakan alur Nextion → ATmega2560 → listener USB serial → CSV, tanpa perintah manual `#start;`.

- Mode `LABELED_DATA` (Take Data): **30 siklus**, masing-masing purging 25 detik + collecting 5 detik; durasi nominal **900 detik/15 menit** (tidak termasuk overhead). Nominal 900 baris sensor pada 1 Hz, dapat berbeda karena scheduler/timing; validator menguji indeks kontigu dan toleransi jumlah sampel per fase.
- Mode `AI_TEST`: **tetap 5 siklus**, sehingga tidak memperpanjang G3 atau mengubah kesiapan AI (`N/A`).
- Firmware build ID baru: `take30-ai5-20261016`; metadata `ACQ_START` mencantumkan `cycles_total=30` untuk data dan `5` untuk AI.
- `lcd_acquisition_service.py` hanya memulai sesi label bila menerima kontrak 30/25/5. `ACQ_COMPLETE` harus 30 siklus, penghitung sampel cocok dengan frame yang diterima, dan `validate_file(..., expected_cycles=30)` lulus sebelum CSV final diterbitkan. Akuisisi yang terputus tetap masuk `data/raw/incomplete/`.
- `validate_file(path)` default tetap memvalidasi **5 siklus** untuk data historis. `validate_file(path, expected_cycles=30)` digunakan hanya untuk kontrak baru, sehingga file lama tidak ditafsirkan ulang.

## QA offline

`python scripts/test_acquisition_integrity.py` PASS. `python scripts/test_take30_contract.py` PASS, mencakup 5 siklus lama, 30 siklus valid secara sintetis, dan 29 siklus yang harus ditolak. `pio run -e mega2560` SUCCESS. Test umum seluruh folder B32+ belum PASS karena file data lokal lain telah berubah; tidak ada perubahan pada data tersebut.

## Sebelum pengambilan fisik

1. Backup firmware saat ini dan cek alat aman/IDLE. **Flashing memerlukan persetujuan operator** dan prosedur hardware terawasi; perubahan kode saja tidak mengubah firmware yang sedang berjalan pada PCB.
2. Setelah persetujuan, flash build baru pada ATmega, lalu pastikan FW_HELLO/build ID atau ACQ_START menunjukkan `take30-ai5-20261016` dan `cycles_total=30` pada Take Data. Periksa juga tampilan jumlah siklus/ETA di Nextion.
3. Pastikan hanya satu listener memakai port serial USB dan jalankan `python scripts/lcd_acquisition_service.py --port COM5 --baud 115200 --verbose` pada laptop (ganti port sesuai sistem). Listener harus sudah berjalan **sebelum** START dari LCD.
4. Uji fisik terawasi dengan udara kontrol terlebih dahulu; amati valve, pump, suhu, frame sensor, fase 25/5 detik, penghentian aman, dan file CSV setelah 30 siklus. Jangan menggunakan hasil uji ini untuk melatih/mempromosikan AI sebelum provenance dan QC selesai.

**Batas:** kode/firmware build bukan bukti perangkat sudah diuji. File HMI lokal dan `platformio.ini` yang dimodifikasi pengguna tidak ikut commit.
