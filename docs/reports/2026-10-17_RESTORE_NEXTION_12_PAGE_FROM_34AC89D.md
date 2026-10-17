# Pemulihan HMI 12 halaman dari 34ac89d dan sinkronisasi firmware

**Tanggal:** 17 Oktober 2026. **Status:** restore byte-identical, QA kontrak serta build ATmega2560 PASS secara offline. **Nextion Editor Compile serta flashing TFT/ATmega BELUM dilakukan.**

## Sumber HMI dan perlindungan perubahan lokal

- Commit sumber: `34ac89d93b4772dadd2fe5008c8d00bac8e138e9` (6 Okt 2026), file `nextion/NX4827T043_011/project/RoastSense_NX4827T043_011_COMPILE_READY.HMI`.
- SHA-256 sumber dan file hasil: `b481a5ae498badedcc8395908f1c75132442a3e134a67bd43043c3ed6c505188` (15.359.762 byte). Biner disalin **langsung dari Git** tanpa mengubah gambar, warna, font, komponen atau event.
- Hasil pemulihan **di file baru**: `nextion/NX4827T043_011/project/RoastSense_RECOVERED_12P_34ac89d.HMI`.
- Semua HMI lain, termasuk `RoastSense_NX4827T043_011.HMI` yang memiliki edit lokal dan `RoastSense_NX4827T043_011_COMPILE_READY.HMI` yang pernah diperbaiki, **tidak ditimpa**. Oleh sebab itu, warna yang diubah setelah commit sumber tidak otomatis terbawa ke file pemulihan; tetap tersimpan pada salinan kerja sebelumnya.

## Daftar halaman yang diverifikasi

| ID | Nama HMI | Fungsi |
|---:|---|---|
| 0 | pSplash | Splash |
| 1 | pHome | Menu |
| 2 | pTake | Pilih kopi/roast/batch dan mulai |
| 3 | pDataRun | Progress akuisisi, Pause/Cancel |
| 4 | pDataDone | Selesai |
| 5 | pTest | Memulai AI Test |
| 6 | pTestRun | Proses AI Test |
| 7 | pResult | Hasil AI Test |
| 8 | pCal | Baseline udara bersih |
| 9 | pSettings | Pengaturan |
| 10 | pHistory | Riwayat |
| 11 | pAlert | Peringatan |

## Integrasi firmware saat ini

- `src/main.cpp`: dikembalikan ke `pTake → pDataRun → pDataDone` untuk Take Data **30 siklus × (25 detik purging + 5 detik collecting)**. `pDataRun` kembali mengupdate `tSample`, `tCycle`, `jCycle.val`, `tPhase`, `tRemain`, `tTemp`, `tHum`, serta rotasi 10 kanal `tSensors`; event `EVT:DATA_PAUSE` dan `EVT:DATA_CANCEL` aktif kembali di halaman 3. Pemulihan layar independen saat akuisisi juga menuju pDataRun.
- AI Test **tetap 5 siklus**, inferensi on-device tetap nonaktif (N/A). Menu Calibrate tetap merekam baseline ADC **60 sampel @ 1 Hz** tanpa menulis ulang R0 EEPROM. Format USB serial/CSV dan aplikasi receiver auto-COM tidak berubah.
- Build ID firmware baru: `take12-baseline60-20261017`; firmware ini **baru di-build, belum di-flash**. Alat di COM4 pada sesi sebelumnya masih memakai `take11-baseline60-20261016` sampai dilakukan flashing terawasi dan dikonfirmasi FW_HELLO.
- Penggantian tipe komponen pada halaman 3 **tidak diperlukan** untuk HMI sumber: `jCycle` sudah Progress, `tTemp/tHum` Text.

## QA

- `python scripts/test_12_page_take_data_contract.py`: PASS, mengunci identitas file HMI dan source firmware 12 halaman.
- `python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py --hmi nextion/NX4827T043_011/project/RoastSense_RECOVERED_12P_34ac89d.HMI`: PASS 12 aset Figma, 12 halaman, 23 event, semua handler, Serial2 9600, tipe `jCycle` Progress.
- `python scripts/test_take30_contract.py`, `python scripts/test_baseline_firmware_contract.py`, `python scripts/test_acquisition_integrity.py`, `python scripts/test_baseline_recording.py`, `python scripts/test_usb_autodetect.py`: PASS.
- `pio run -e mega2560`: SUCCESS, flash **32.810 byte**, RAM **3.759 byte**. Peringatan pustaka upstream non-blocking.

## Langkah sebelum deploy pada alat

1. Buka **file pemulihan bernama `RoastSense_RECOVERED_12P_34ac89d.HMI`** di Nextion Editor. Pastikan terlihat 12 halaman dan warna sesuai tujuan; karena ini snapshot lama, bandingkan warna manual terbaru sebelum mengedit apa pun. Klik Compile dan simpan lognya. **Kompilasi GUI belum dikonfirmasi otomatis.**
2. Jangan upload TFT bila Compile belum sukses. Setelah berhasil, uji event Start/Pause/Cancel secara aman dan kesesuaian tombol Nextion. Ketika siap, sesuaikan firmware fisik dengan build ID baru pada ATmega melalui flashing yang diminta/diizinkan secara terpisah, lalu verifikasi FW_HELLO serta satu sesi akuisisi terawasi.
3. Jangan menjalankan pengambilan data ketika versi HMI/firmware tidak sinkron. Tidak ada alasan untuk mengubah/memigrasikan CSV historis atau melakukan R0 re-calibration hanya untuk pemulihan navigasi layar.
