# SOP Bench Tahap 1 — Firmware, Nextion, Sensor dan Akuisisi

**Status:** DRAF untuk persetujuan operator perangkat. **Revisi:** 9 Oktober 2026. **Jangan menafsirkan file ini sebagai izin otomatis mengoperasikan hardware.**

## 1. Tujuan dan ruang lingkup

Memvalidasi alur **sensor gas/SHT30 → ATmega2560 → USB Serial 115200 → autosave CSV**, layar Nextion melalui `Serial2` 9600, transisi 5 × (purging 25 s + collecting 5 s), respons valve/pompa dan keselamatan gagal. Protokol UART langsung ke Raspberry Pi 5 masih Tahap 7, **tidak diuji dalam SOP ini**.

**Dua tingkat izin:**

- **Tingkat A — observasi pasif:** membaca status proses, log yang ada dan **CSV final**, memeriksa file hash, menjalankan QA offline. Tidak membuka COM5, mengirim perintah, menyentuh EEPROM, atau memodifikasi alat. Tingkat ini sudah dipakai dalam audit 9 Oktober.
- **Tingkat B — pengujian aktif:** operator wajib menyetujui sesi maintenance berikut batas tindakan satu per satu: menjalankan UI Nextion dan valve/pompa, memindahkan kepemilikan COM5, restart/power-cycle, flashing, upload TFT, dan/atau kalibrasi/EEPROM. **Flashing, upload TFT, dan kalibrasi merupakan persetujuan terpisah**, tidak otomatis diizinkan hanya karena SOP dibaca.

## 2. Prasyarat keselamatan sebelum tingkat B

1. Operator hadir di alat dan dapat memutus catu daya dengan aman; identitas perangkat dan koneksi sensor/driver aktuator sudah dikonfirmasi pada skematik/wiring.
2. Periksa tegangan catu, GND, polaritas driver solenoid, daya dan temperatur komponen; selang, pompa, chamber, serta saluran gas dalam keadaan aman.
3. Uji menggunakan udara bersih dan sampel yang diizinkan; jangan memasukkan gas berbahaya, konsentrasi ekstrem, atau memodifikasi jalur gas saat alat menyala.
4. Pastikan apakah ada pengambilan data aktif. **COM5 hanya boleh dimiliki satu proses**. Jika listener masih aktif, **jangan membuka port kedua**, jangan menghentikannya, dan jangan flashing sampai run berakhir dan operator mengizinkan window maintenance.
5. Simpan cadangan konfigurasi dan versi firmware/HMI yang benar-benar terpasang jika tersedia; nilai kalibrasi EEPROM jangan diubah tanpa prosedur serta backup yang relevan.
6. Tinjau status `platformio.ini` milik operator (COM5) tanpa menimpa perubahan lokal.

**Perintah yang dilarang selama SOP normal:** `#pin_scan;` (selalu dinonaktifkan), serta pengoperasian `#valve_on/off/test;` pada firmware produksi tanpa build khusus dan izin operator.

## 3. Prosedur dan matriks bukti

| ID | Pemeriksaan | Prosedur dan bukti yang diperlukan | Kriteria penerimaan |
|---|---|---|---|
| B01 | Inventaris firmware/port | Catat identitas board, versi firmware yang **terverifikasi pada alat**, baud, pemilik COM5 dan kondisi HMI | Identitas dan konfigurasi jelas; tidak ada proses berebut port |
| B02 | Ketersediaan ADC/SHT30 | Operator konfirmasi 4× ADS1115 (0x48–0x4B), 10 kanal, SHT30; ukur bila perlu | Tidak ada kanal hilang, null terus-menerus, saturasi atau nilai tidak masuk akal |
| B03 | Akuisisi normal 5 siklus | Operator memulai **satu** run aman melalui Nextion sesuai izin; amati fisik posisi valve/pompa dan catat waktu aktual memakai jam/logic analyzer | Alur 25 s purge → 5 s collect ×5 terbukti **secara fisik**, bukan cuma dari CSV |
| B04 | Penyimpanan host | Biarkan listener normal memiliki COM5; periksa log `ACQ_START/ACQ_COMPLETE` dan file CSV **setelah finalisasi** | CSV valid, 5 siklus benar, tidak overwrite, event tidak menjadi sensor |
| B05 | Timing serial | Jalankan `bench_stage1_passive_qa.py` pada CSV final; cocokkan trace dengan pengukuran valve terpisah | Interval sensor dan event konsisten; toleransi timing fisik disepakati sebelum penilaian |
| B06 | Nextion dan UI | Operator uji alur menu pHome→pTake→pDataRun→pDataDone dan pTest→pTestRun→pResult; periksa tombol pause/cancel; **jangan menekan CAL** | Navigasi, progres, hasil N/A dan kendali berhenti masuk akal; 12 halaman siap diverifikasi |
| B07 | Negatif dan fail-safe | Dengan SOP khusus: uji stop/pause/resume, reset/reconnect dan kegagalan sensor terkontrol **tanpa hot-unplug I2C saat alat hidup** | Valve masuk posisi aman, tidak ada data palsu, run parsial ditahan |
| B08 | Recovery/rollback | Operator pastikan catu, listener, port dan firmware kembali ke konfigurasi semula; review log | Tidak ada proses menguasai port secara ganda dan tidak ada file mentah terhapus |

Jangan mengukur durasi valve hanya berdasarkan `millis()`: bukti firmware berbeda dari bukti penggerak/arus koil dan perpindahan fluida nyata. Ambang akurasi fisik (misalnya deviasi yang diperbolehkan dari 25 s dan 5 s) harus ditetapkan sebelum bench test aktif.

## 4. Prosedur tingkat A yang bisa dijalankan tanpa mengganggu perangkat

Dari root proyek:

    powershell -NoProfile -ExecutionPolicy Bypass -File scripts/status_lcd_autosave.ps1
    python scripts/bench_stage1_passive_qa.py --file data/raw/NAMA_FILE_FINAL.csv
    python scripts/test_bench_stage1_passive_qa.py

Jalankan `bench_stage1_passive_qa.py` **hanya pada CSV final**; alat akan menolak path staging dan incomplete. Uji ini tidak pernah membuka COM5 dan tidak mengubah data. PASS berarti integritas **rekaman** valid, bukan bukti versi firmware, kalibrasi, atau posisi valve.

## 5. Kondisi berhenti dan keputusan GO/NO-GO

**Hentikan pengujian aktif** jika muncul panas/bau tidak normal, valve bergerak di luar perintah, ketidakjelasan port/versi, power tidak stabil, error bus I2C berat, CSV berisiko tertimpa, atau alat tidak dapat kembali ke kondisi aman. Penghentian dilakukan oleh operator sesuai pemutus daya dan prosedur perangkat.

Laporan tiap pengujian mencatat tanggal, operator, foto/skema jika diperlukan, versi firmware/HMI, observasi fisik, file CSV final beserta SHA256, keluaran QA, dan status **PASS/FAIL/BLOCKED/NOT RUN**. Tahap 1 hanya boleh ditutup sebagai **hardware verified** setelah B01–B08 yang relevan benar-benar terbukti.

**Persetujuan yang belum tercatat:** operator, waktu bench, izin uji aktif, akses eksklusif COM5, SOP valve, flashing/upload TFT, kalibrasi EEPROM, serta bukti skematik board. Sampai dipenuhi, hanya tingkat A boleh dijalankan.
