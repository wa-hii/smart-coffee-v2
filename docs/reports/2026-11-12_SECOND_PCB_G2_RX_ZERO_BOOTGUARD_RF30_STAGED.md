# PCB kedua — probe serial 8 detik, hardening startup RF30 dan staging Pi

**Tanggal:** 12 November 2026 (WIB)

**Target:** PCB custom ATmega2560 kedua melalui FT232R `A10KNJBL` di Raspberry Pi 5; Nextion dilaporkan tetap pada `Initializing Systems`, alat dalam IDLE.

## 1. Pengujian live yang diizinkan

Operator menyetujui **satu pembacaan serial singkat** setelah mengonfirmasi alat IDLE. Sebelum port dibuka:

- SSH melalui Tailscale berhasil; adaptor by-id `usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0` menunjuk `/dev/ttyUSB0`.
- `fuser` tidak menemukan proses pemegang port, `get_throttled=0x0`.
- Skrip `stage7_usb_readonly_probe.py` telah lolos uji mock `test_stage7_usb_readonly_probe.py` yang menguji DTR/RTS false sebelum open, akses eksklusif dan larangan `write()`.
- Pembacaan dilakukan **sekali**, maksimal 8 detik pada 115200 baud, dalam mode pasif tanpa perintah MCU/Nextion dan tanpa model AI.

### Bukti hasil

| Parameter | Hasil |
|---|---|
| Status probe | `SERIAL_DATA_INCONCLUSIVE` (exit code 2) |
| Port serial | Berhasil dibuka; tertutup lagi setelah pengujian |
| Data RX | **0 byte** |
| Baris/event JSON | **0** |
| Perintah UART TX | **0 byte** |
| Akuisisi, pompa/valve, flash/EEPROM | **Tidak dipicu oleh software pengujian** |
| DTR / reset hardware | DTR/RTS disetel false sebelum open; kemungkinan pulsa/reset dari driver/hardware tidak dapat dikesampingkan |

Bukti tersimpan pada Pi:
`/home/enose-v3/smart-coffee-stage7/g2_20261111/pcb2_20261112_passive_08s.json`.

Sesudah pengujian, SSH Pi tetap berhasil, `throttled=0x0`, adaptor tetap di `ttyUSB0`; journal kernel boot tidak mencatat `disconnect` atau `xHCI dead` baru. Ini hanya menegaskan **endpoint USB dapat dibuka tanpa insiden yang terdeteksi pada pengujian ini**, tidak membuktikan jalur TX MCU, versi firmware, atau validitas 900 sampel.

**Diagnosis:** Nol byte tidak membedakan firmware yang tidak mengirim saat IDLE, MCU tertahan sebelum `Serial.begin()`, firmware lain, koneksi UART TX/RX yang salah/putus, atau masalah kelistrikan. Nextion yang tertahan juga belum membuktikan salah satu penyebab tersebut. **Tidak dilakukan pengulangan serial-open.**

## 2. Hardening kandidat firmware RF30 — source only

Pada build `ENABLE_PI_RF30_RETURN=1`, fungsi `setup()` kini:

- Menginisialisasi `Wire` dan mengaktifkan timeout transaksi I²C 25 ms sebelum `sensors.begin()`.
- Tidak menjalankan scan penuh 126 alamat I²C saat boot; fitur scan manual masih ada, dan build default lama tetap mempertahankan perilaku sebelumnya.
- Tidak mengubah mapping sensor, interval 30 siklus, komunikasi Nextion `Serial2` 9600, bentuk pesan AI RF30, EEPROM maupun layout HMI.

Langkah ini mengurangi peluang boot terhambat pada full scan I²C, **tetapi tidak membuktikan penyebab `Initializing Systems` pada PCB kedua maupun menjamin firmware baru bisa boot di PCB tersebut**.

### Verifikasi offline

- `pio run -c scripts/platformio_rf30_bench.ini -e rf30_return_bench`: **PASS**, Flash **35.770 B**, global SRAM **3.917 B**.
- `pio run -c scripts/platformio_svm30_standalone.ini -e svm30_standalone`: **PASS**, Flash 50.006 B dan SRAM global 4.189 B.
- `pio run -e mega2560 -e nextion_test`: **PASS** kedua environment.
- `test_rf30_boot_guard.py`, `test_prepare_rf30_second_pcb_candidate.py`, `test_stage7_usb_readonly_probe.py`, firmware Stage 1, RF30 result contract, 30-cycle timing, bridge, validation fitur, replay dan kontrak Nextion: **PASS offline**.

## 3. Image khusus PCB kedua: kandidat, bukan firmware terpasang

File lokal privat dan tidak masuk Git:

`private/rf30_second_pcb_candidate/20261112_rf30_bootguard_v1/`

Berisi `rf30_pi_return_candidate.hex` dan `image_manifest.json`. SHA-256 HEX:

`26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`

Alamat payload Flash **0–35769**, seluruhnya pada area aplikasi (batas 253952 byte), build ID `take30-ai30-rfhost-20261110`. Manifest menyatakan `new_pcb_firmware_identified=false`, `new_pcb_flash_backup_verified=false` dan `firmware_uploaded=false`.

Salinan dipindahkan via SCP ke folder staging Pi yang terpisah:

`/home/enose-v3/smart-coffee-stage7/rf30_staging/second_pcb_20261112_bootguard_v1/`

Hash SHA-256 file HEX di Pi **identik** dengan lokal. Transfer tersebut hanya menulis file ke storage Pi; tidak membuka port serial dan tidak menulis Flash/EEPROM MCU. Model RF500 asli dengan hash yang sudah di-pin tetap tersedia dalam staging terpisah.

## 4. Keputusan akhir dan blocker

| Gerbang | Keputusan |
|---|---|
| SSH / FT232R enumerasi | PASS selama pemeriksaan |
| Satu serial-open 8 detik | PASS untuk open/close tanpa gangguan kernel baru; **RX tidak tersedia (0 byte)** |
| Versi firmware MCU kedua | **UNKNOWN** |
| `pSplash → pHome` pada Nextion kedua | **Belum berhasil menurut laporan operator** |
| Backup asli Flash+EEPROM MCU kedua | **BELUM ADA** |
| Programmer/bootloader/reset pin PCB kedua | **BELUM DIVERIFIKASI** |
| Kandidat RF30 + model Pi | **PASS build / offline staging** |
| Firmware fisik, 900-sampel live, ACK dan LCD RF500 | **NOT RUN / BLOCKED** |

**Jangan flash image ini sekarang.** Backup SVM30/COM5 tanggal 11 November berasal dari **PCB lain** sehingga tidak dapat dianggap rollback untuk PCB kedua. Pi belum memiliki `avrdude` dalam PATH dan jalur bootloader yang benar belum dibuktikan. Percobaan lain untuk membuka/reset port tanpa verifikasi kabel dan catu daya berpotensi mengulangi kegagalan xHCI historis.

### Urutan menuju uji E2E

1. Inspeksi onsite saat aman: suplai Pi/PCB/Nextion, ground, VBUS/backfeed, TX/RX FT232R ↔ UART0, DTR ↔ RESET, serta Nextion ↔ UART2. Pastikan tidak ada aktuator aktif/komponen terlalu panas.
2. Dengan prosedur daya dan programmer/bootloader yang diverifikasi, lakukan **readback-only Flash+EEPROM khusus PCB kedua** dan validasi signature/hash/rollback; jangan menulis EEPROM.
3. Hanya setelah image cocok dengan wiring, backup sah, dan persetujuan flashing spesifik, tulis serta verifikasi aplikasi RF30 satu kali dengan operator onsite. Pertahankan rollback PCB kedua.
4. Konfirmasi `pHome`, `FW_HELLO`, sensor/aktuator, 30 siklus/900 sampel dan balasan `AI_RESULT_ACK` nyata sebelum mengklaim RF500 E2E; lakukan evaluasi prediksi pada kopi LIGHT/MEDIUM/DARK di PCB baru. Karena model menggunakan tiga fitur ADC absolut, validasi ulang lintas PCB sangat penting.

**Tidak ada flashing, penulisan EEPROM atau upload HMI dalam milestone ini.**
