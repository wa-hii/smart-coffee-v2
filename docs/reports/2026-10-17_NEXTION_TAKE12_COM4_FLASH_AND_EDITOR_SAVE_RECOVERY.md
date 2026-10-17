# Sync firmware Take Data 12 halaman COM4 dan audit kerusakan HMI setelah Save

**Tanggal:** 17 Oktober 2026 WIB. **Status:** firmware ATmega2560 `take12-baseline60-20261017` berhasil dibangun, di-upload, di-verify, dan terdeteksi di COM4; satu receiver aktif. **Status HMI/TFT fisik:** pengguna menyatakan telah Compile + Debug berhasil dan flash TFT sendiri; jumlah halaman **TFT aktual belum dapat diverifikasi dari USB ATmega**. File HMI lokal yang dibuka dan disimpan ulang memang mempunyai kerusakan Page 3.

## 1. Bukti yang terpisah: flash TFT, proyek HMI, firmware MCU

- Pengguna sudah melakukan flash `.tft` melalui Nextion Editor setelah Compile/Debug berhasil. Peristiwa ini dilaporkan operator; `.tft` baru hasil compile tersebut tidak tersedia dalam folder proyek pada audit saat ini (yang ada di `nextion/.../build/` bertanggal 5 Oktober). Audit ini **tidak menganggap konten flash TFT dapat dibuktikan hanya dari file HMI yang tersimpan kemudian**.
- `RoastSense_RECOVERED_12P_34ac89d.HMI` lokal yang diedit dan Save ulang pukul 17:13, SHA256 `85076d236ea72af317aa2c731227abf51f74e926a6ce39394a349657c590dc5e`, mengandung **11 halaman dengan nama dan CRC valid**; entry `3.pa` yang mengarah ke `pDataRun` rusak (CRC gagal), sementara 11 halaman lain valid. Ini dapat menjelaskan Page List Editor berubah setelah Save/Reopen.
- HMI user lain `RoastSense_NX4827T043_011.HMI` juga berbeda dan memiliki 2 entri halaman rusak; **tidak digunakan untuk flashing/pemulihan**. Tidak ada file HMI lama yang ditimpa.
- **Perbaikan aman (append-only):** `RoastSense_12P_EDITOR_REPAIRED_SAFE_20261017.HMI` dengan SHA256 `4c117d6508506bb8a4a57331d47100b60b251849faa81e39dcd6a47c7a9a8c5a` (15.610.207 byte). `pDataRun` CRC-valid/Progress dari HMI referensi dimasukkan **di akhir file**, entry `3.pa` primer/backup diperbaiki, checksum direktori dihitung ulang. Hanya **14 byte** dalam seluruh file lama yang berubah (semuanya di direktori), sisanya tetap byte-identical. Gambar, font, serta 11 halaman hasil edit pengguna tidak berubah. Versi pertama pemulihan yang menulis di lokasi Page 3 rusak tidak aman karena menimpa resource gambar dan **sudah dihapus** (tidak di-commit).
- Kompilasi resmi HMI `RoastSense_12P_EDITOR_REPAIRED_SAFE_20261017.HMI` **belum dilakukan**; buka sebagai file baru di Editor, Compile/Debug, lalu bila diperlukan flash hasil `.tft` tersebut ke LCD. **Jangan menggunakan file HMI yang sudah rusak untuk compile berikutnya.**

## 2. QA struktural dan kontrak

- `python scripts/test_12_page_take_data_contract.py`: PASS, ke-12 page valid, termasuk pDataRun, tCycle, tTemp/tHum, jCycle Progress, Pause/Cancel, firmware mode 30/5/60.
- `python nextion/NX4827T043_011/tools/verify_nextion_atmega_contract.py --hmi nextion/NX4827T043_011/project/RoastSense_12P_EDITOR_REPAIRED_SAFE_20261017.HMI --editor-saved-asset-reference nextion/NX4827T043_011/project/RoastSense_RECOVERED_12P_34ac89d.HMI`: PASS 12 resource gambar **identik dengan HMI hasil Save pengguna** (bukan dicocokkan ke ekspor Figma lama), 12 halaman, 23 event punya handler di ATmega, dan Serial2 @ 9600 baud.
- Regresi `test_take30_contract`, `test_baseline_firmware_contract`, `test_acquisition_integrity`, `test_baseline_recording` PASS.
- Build `pio run -e mega2560`: PASS, 32.810 byte flash, 3.759 byte RAM. `IS_CALIBRATING_GAS_SENSOR=0` dan `USE_ON_DEVICE_INFERENCE=0` tetap berlaku.

## 3. Flash dan verifikasi COM4

- USB bridge FTDI FT232R `0403:6001`, USB serial `A10KMZQJA` pada COM4. Sebelum upload, staging file input di repo dan paket portable dipastikan kosong. Tiga listener Python yang berebut port dihentikan saat idle.
- `pio run -e mega2560 -t upload --upload-port COM4`: AVRDUDE `Device signature = 0x1e9801`, **32.810 byte ditulis dan diverifikasi**, PlatformIO SUCCESS.
- Serial read-only setelah boot menangkap:

```json
{"event":"FW_HELLO","protocol":"legacy-json.v1","build_id":"take12-baseline60-20261017","adc_channels":10,"data_cycles_total":30,"ai_cycles_total":5,"purge_s":25,"collect_s":5}
```

- I2C boot menemukan `0x44` dan **4/4 ADS1115** (`0x48` s.d. `0x4B`). Firmware masih mengeluarkan status **R0 belum terkalibrasi** karena EEPROM legacy: tidak dijalankan kalibrasi ulang atau penulisan EEPROM.
- Setelah dua proses portable sempat start hampir bersamaan, proses tersebut dihentikan pada kondisi tidak ada file staging. Receiver repo tunggal **PID 26872**, status `connected` pada **COM4@115200**. Tidak memulai Take Data atau Calibrate dari pengujian ini.

## 4. Batas dan urutan validasi fisik

1. Buka HMI baru `RoastSense_12P_EDITOR_REPAIRED_SAFE_20261017.HMI` di Nextion Editor. Pastikan daftar 12 halaman dengan `pDataRun` di ID 3 dan `pDataDone` di ID 4; Compile + Debug dan Save As TFT. Jika hasil Save/Reopen kembali menghilangkan halaman, hentikan proses dan kirim file/log (kemungkinan masalah serialisasi editor yang belum teratasi; jangan anggap QA biner sebagai pengganti compiler).
2. Jika TFT yang sudah diflash menunjukkan 12 halaman dan kontrol pDataRun berfungsi, tidak perlu reflash TFT tanpa sebab. Jika tidak, flash TFT baru hanya setelah **Compile + Debug PASS** dan periksa langsung pada LCD.
3. Uji fisik terawasi setelah mengonfirmasi LCD cocok: coba navigasi pTake, halaman pDataRun, Pause/Cancel, pDataDone; jangan mulai sesi 30 siklus hanya untuk verifikasi menu. Lakukan sesi fisik 30 siklus baru ketika alur HMI dinyatakan benar.
4. Periksa log dan CSV host setelah pengambilan 30 siklus berikutnya. **Tidak ada bukti keberhasilan E2E Nextion-ke-CSV untuk TFT baru** pada pekerjaan ini.
