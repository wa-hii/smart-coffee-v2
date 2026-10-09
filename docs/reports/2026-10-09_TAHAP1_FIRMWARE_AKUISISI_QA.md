# Tahap 1 — Audit dan penguatan firmware, Nextion, dan akuisisi

**Tanggal:** 9 Oktober 2026

**Branch:** `wahyu`

**Baseline awal:** `9146eaf`; perubahan lokal `platformio.ini` tetap dipertahankan dan tidak di-commit.

**Status:** P0 pengamanan offline **PASS**; keseluruhan Tahap 1 **SEBAGIAN / PERLU UJI HARDWARE**.

## 1. Hasil audit dan tindakan

| Risiko | Temuan kode sebelum perubahan | Perbaikan pada milestone ini |
|---|---|---|
| Salah fase pada sampel batas | `adsCallback` membaca ADC, menjalankan transisi fase, baru mengirim sampel yang berlabel fase baru. | **Baca → kirim frame dengan fase/siklus saat dibaca → proses transisi.** Status/sampel selalu memakai fase lama sampai pembacaan selesai. |
| Sampel terakhir tidak tersimpan | `ACQ_COMPLETE` bisa dikeluarkan sebelum `printJsonData` pada callback yang sama; listener menutup file saat COMPLETE. | Frame sampel akhir dikirim **sebelum** `ACQ_COMPLETE`. Tidak ada frame `idle` dari callback akuisisi. |
| Label bocor pada AI_TEST | Event `ACQ_START` selalu membawa `sample_id`, roast, origin, batch, filename dari pilihan pTake sebelumnya. | **Mode `ai_test` kini label-free**; mode `labeled_data` tetap mengirim metadata agar autosave kompatibel. |
| Pemindaian GPIO tidak aman | `#pin_scan;` mengubah mode dan menggerakkan banyak pin, termasuk D19/RX1 dan D20/SDA I2C. | Perintah mengembalikan `PIN_SCAN_DISABLED` dan kode pemindaian destruktif dihapus. |
| Penggerakan valve debug | `#valve_on/off/test;` dapat menggerakkan valve dari host serial tanpa mode bench khusus. | Flag `ENABLE_MANUAL_ACTUATOR_TESTS=0` secara default; perlu build khusus dan SOP terotorisasi untuk mengaktifkan command. |
| Perintah serial `#start;` | Dapat memulai state machine walau ADC tidak seluruhnya terdeteksi. | Ditolak jika `sensorsReady` atau `allAdcAvailable()` gagal, seperti pada logika start Nextion. |
| `#scan;` I2C saat akuisisi | Bisa memblokir tugas dan mengganggu bus sensor pada sesi aktif. | Hanya dijalankan ketika MCU dalam status IDLE. |

Perubahan ini tidak menyentuh desain Nextion, konfigurasi pin, konfigurasi EEPROM, pemetaan ADC, durasi nominal 25/5 detik, model AI, maupun data mentah.

## 2. Verifikasi offline dan interpretasi

Pengujian wajib:

    pio run -e mega2560 -e nextion_test
    python scripts/test_stage1_firmware_contract.py
    python scripts/test_stage0_contract.py
    python scripts/test_acquisition_suite.py
    python scripts/validate_b32_acquisition.py
    python scripts/audit_b32_dataset.py
    python scripts/test_feature_pipeline.py
    python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py
    python -m compileall -q scripts
    git diff --check

Pengujian tambahan parser event Nextion pada host C++:

    g++ -std=c++17 -I src test/nextion_event_parser_test.cpp -o .pio/test_nextion_event_parser_stage1.exe
    .pio/test_nextion_event_parser_stage1.exe

**Rekap hasil akhir: PASS seluruh tes offline di atas.** Firmware `mega2560` memakai RAM statis **3.698/8.192 byte (45,1%)** dan flash **34.444/253.952 byte (13,6%)**; `nextion_test` RAM **541/8.192**, flash **5.062/253.952**. Validator B32–B35 **86/86 PASS**; B32 khusus **18/18 PASS**. Kontrak HMI **12 halaman, 23 event PASS**; parser event C++ host juga **PASS**.

Peringatan dari pustaka bawaan EEPROM/TaskScheduler dan metode Pillow `getdata` yang deprecated tetap dicatat sebagai pekerjaan pemeliharaan, bukan kegagalan build.

`test_stage1_firmware_contract.py` memeriksa urutan di implementasi C++ secara statis dan menjalankan simulasi **1 Hz ideal**: 5 × (25 sampel purging + 5 sampel collecting) = **150 frame**, dengan frame kelima collecting pada siklus 5 muncul tepat sebelum COMPLETE. Hasil simulasi bukan pembuktian jadwal aktual `TaskScheduler` atau latensi sensor/serial.

Regresi listener menguji kondisi `ai_test` tanpa ground truth diabaikan untuk CSV labeled, COMPLETE duplikat tidak menimpa file, dan STOP mempertahankan data parsial; pengujian tidak membuka COM5.

**Tinjauan manual penting:** pengiriman serial sinkron masih memiliki latensi, `showNextionPage` memakai penundaan, dan operasi I2C/Nextion dapat menyebabkan jitter pada callback sampling. Pembalikan urutan frame–transisi memperbaiki atribusi secara logis tetapi **belum membuktikan akurasi waktu, perpindahan gas, atau jumlah frame riil**. Perlu pengukuran timing GPIO/event dan trace serial di perangkat.

## 3. Pekerjaan hardware/operasional yang masih terbuka

1. Ukur **waktu fase sebenarnya**, jumlah frame, keterlambatan UART USB, dan hubungan sampel dengan posisi valve menggunakan alat fisik, lalu validasi bahwa data CSV cocok dengan perubahan firmware.
2. Uji kegagalan sensor/ADS1115, pembacaan SHT30 null dan retry, recovery I2C, saturasi serta stabilisasi R0/RL. Validasi kalibrasi/EEPROM tanpa perubahan tidak sengaja.
3. Uji keselamatan pompa/valve dalam mode START, STOP, pause/resume, reset MCU, power loss dan error Nextion. Pause selama collecting mengubah keadaan valve, sehingga efek transien gas saat resume memerlukan penilaian khusus.
4. Uji konektivitas Nextion pada HMI/TFT nyata, 12 halaman, event, reboot selama akuisisi dan serial disconnect/reconnect; cek kompatibilitas `labeled_data` autosave pada COM5 setelah update firmware.
5. Implementasi transport ke Raspberry Pi (UART/USB), skema protokol versi 1, session ID, ACK dan hasil inferensi dua arah **tetap ruang lingkup Tahap 7**, bukan bagian perubahan ini.

**Batas keselamatan:** build offline **bukan** izin flashing. Pengujian di atas memerlukan SOP yang disetujui, penjadwalan COM5 agar tidak mengganggu autosave, backup firmware, dan prosedur rollback. Jangan menganggap `#valve_*` sudah siap digunakan tanpa mengaktifkan flag pada build bench khusus.

## 4. Keputusan QA

- **PASS offline (bersyarat):** kompilasi firmware, regresi payload/CSV, pengujian kontrak firmware, simulasi urutan frame dan verifikasi HMI offline.
- **NO-GO hardware/E2E:** belum ada bukti timing/aktuator/serial langsung, pelaksanaan bench test, maupun pengujian Raspberry Pi.
- **Berikutnya:** tutup checklist hardware Tahap 1 jika SOP dan alat siap; sementara itu pekerjaan Tahap 2 dapat dimulai secara read-only tanpa mengklaim kesiapan hardware.

Identitas commit milestone tercatat pada riwayat Git branch `wahyu`; laporan hanya menyebut pengujian yang benar-benar dijalankan.
