# B6: Preflight COM5 Windows untuk uji standalone SVM30 ATmega2560

**Tanggal:** 11 November 2026, WIB. **Branch:** `wahyu`.
**Status:** **NO-GO / Tidak melakukan flashing atau pembukaan serial**.

## Tujuan

Menindaklanjuti permintaan B6 pada folder
`D:\ENOSE\smart-coffee-v2-hardware\smart-coffee-v2-hardware`,
setelah operator melaporkan **COM5** sekarang terhubung ke PCB ATmega.
Ini **tidak otomatis** membuktikan MCU siap diprogram maupun
memverifikasi identitas firmware di chip.

## Hasil pemeriksaan pasif Windows

- `serial.tools.list_ports` mendeteksi
  **COM5 / USB Serial Port (FTDI VID:PID 0403:6001,
  serial `A10KMM3SA`)**.
- Windows PnP mengonfirmasi
  `FTDIBUS\VID_0403+PID_6001+A10KMM3SA\0000` dengan
  status **OK**. Ini hanya identitas adaptor FTDI,
  **bukan read-back chip ATmega**.
- Identitas ini berbeda dari FT232R **`A10KNJBL`** yang
  sebelumnya ada di Raspberry Pi 5; perlu konfirmasi
  pemetaan kabel ke PCB custom yang dimaksud.
- Proses aktif **PID 14628 `pythonw.exe`** menjalankan
  `scripts/lcd_acquisition_service.py --port auto --baud 115200`
  sejak sekitar **04:09 WIB**.
- `logs/acquisition_service.status.json` mencatat
  **`state: connected, port: COM5, baud: 115200, pid: 14628`**,
  diperbarui **15:16:23 WIB**.
- Ekor `logs/acquisition_service.log` mencatat
  **`USB detected -> COM5`, `Membuka COM5`,
  `CONNECTED COM5` pukul 15:16:23 WIB**. Tidak ada
  bukti rekaman baru dari cuplikan log tersebut, namun
  listener tetap hidup dan mungkin memegang port.
  Proses **tidak dihentikan paksa** karena bisa saja
  mengganggu penerimaan akuisisi yang sedang berlangsung.
- `platformio.ini` lokal berisi **COM4**, tetapi
  file itu adalah perubahan pengguna dan **tidak disentuh**.
  Profil `svm30_standalone` memakai file konfigurasi
  terpisah tanpa `upload_port`.

## Firmware dan model

- `private/embedded_svm30_model.h` tersedia, koefisien
  model SHA-pinned `final_svm.joblib`:
  `d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33`.
- Image kandidat lokal `private/svm30_standalone_firmware.hex`
  berukuran **140.676 byte Intel HEX**. SHA-256
  cocok dengan manifest:
  `6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2`.
- Manifest masih `COMPILE_ONLY_NOT_FLASHED`.
  **Bukti ini bukan verifikasi firmware yang sudah
  terpasang di ATmega.**
- Tidak ada backup Flash MCU/EEPROM yang sudah
  diverifikasi untuk perangkat COM5. Belum ada bukti
  programmer ISP/bootloader, jalur reset, dan SOP PSU/VBUS
  untuk FT232R `A10KMM3SA`.

## Preflight otomatis tanpa membuka serial

Ditambahkan:

- `scripts/svm30_b6_preflight.py` untuk memeriksa
  PnP port, status receiver, checksum image/model,
  dan *manual safety gates*. Tidak membuka COM5,
  tidak menulis UART, tidak mem-flash, tidak menghentikan
  listener dan tidak me-reset MCU.
- `scripts/test_svm30_b6_preflight.py` menguji
  **8 gerbang NO-GO**, termasuk bila penerima COM5
  aktif atau tidak pasti.
- Hasil snapshot JSON privat tersimpan pada
  `private/svm30_b6_preflight_20261111_1600.json`;
  file diabaikan Git.

**Output pada 11 November 2026: `NO_GO`**, dengan blockers:

```text
COM5_RECEIVER_ACTIVE_OR_UNKNOWN
NEXTION_BOOT_NOT_VERIFIED
NO_VERIFIED_FLASH_EEPROM_BACKUP
PROGRAMMER_POWER_SOP_NOT_VERIFIED
SPECIFIC_UPLOAD_APPROVAL_MISSING
```

## Langkah B6 berikutnya (belum dieksekusi)

1. Operator **mengonfirmasi kondisi fisik terbaru**
   Nextion: harus benar-benar masuk `pHome`, tidak
   terus tertahan pada `Initializing Systems`.
   Periksa pompa/dinamo sesuai desain, valve OFF di IDLE
   dan tidak ada panas/daya tidak normal.
2. Pastikan COM5 FT232R `A10KMM3SA` memang kabel
   UART pemrograman ATmega custom yang tepat,
   bukan FTDI alat lain. Tinjau wiring DTR/reset,
   bootloader/ISP, supply dan ground sebelum upload.
3. Jika receiver **benar-benar IDLE** dan operator
   menyetujui, akhiri `lcd_acquisition_service.py`
   **secara terkontrol**, tanpa merusak partial CSV.
   Jangan membuka COM5 kedua saat receiver masih
   memilikinya.
4. **Backup dan verifikasi Flash/EEPROM dan fuses**
   lewat jalur programmer yang tervalidasi. Tidak
   menggunakan perintah erase/flash untuk backup.
   Simpan image dan hash di `private/`. Jika
   tidak ada akses backup, hentikan proses.
5. Validasi checksum kandidat firmware dan mapping
   `Serial2` Nextion. Flash **hanya setelah persetujuan
   spesifik SOP dan prosedur rollback terverifikasi**;
   jangan memakai perintah upload default COM4.
6. Sesudah cold boot benar-benar masuk `pHome`,
   jalankan satu AI TEST 30 siklus terawasi,
   pastikan hasil Light/Medium/Dark tampil di
   `pResult`. Ukur latency, stack peak dan
   uji cancel/fail-safe sebelum klaim B6 PASS.

**Sampai ini dipenuhi, B6 tetap NO-GO; tidak ada
pengubahan firmware fisik, EEPROM, TFT, port, atau aktuator.**

## Addendum — Operator mengonfirmasi Nextion sudah di pHome

Pada sesi lanjutan, operator secara eksplisit menyampaikan:
**`sudah masuk ke halaman utama pHome`** saat PCB terhubung
melalui COM5. Ini merupakan bukti pengamatan langsung dari
operator bahwa Nextion tidak lagi stuck pada layar
`Initializing Systems`, **bukan** bukti telemetri/firmware
version read-back, stabilitas boot berulang, atau kesiapan flashing.

Pemeriksaan pasif diperbarui dengan
`--operator-reported-phome` dan menghasilkan snapshot privat
`private/svm30_b6_preflight_phome_20261111.json`.
Pemeriksaan ini tetap **tidak membuka COM5**, menghentikan
receiver, melakukan reset, atau flashing.

**NO_GO: empat gerbang masih terbuka:**

```text
COM5_RECEIVER_ACTIVE_OR_UNKNOWN
NO_VERIFIED_FLASH_EEPROM_BACKUP
PROGRAMMER_POWER_SOP_NOT_VERIFIED
SPECIFIC_UPLOAD_APPROVAL_MISSING
```

Receiver `pythonw.exe` PID 14628 tetap hidup dengan
`state=connected` pada COM5. Folder `data/raw/.incoming`
tidak berisi file parsial saat pemeriksaan, dan log
receiver terakhir memperlihatkan `CONNECTED COM5`
15:16:23 WIB. Tidak adanya file parsial **bukan jaminan**
bahwa alat sedang IDLE sepanjang waktu.

**Keputusan:** pengamatan `pHome` dari operator memperbarui
status boot yang sebelumnya belum diketahui. Jangan
menafsirkannya sebagai izin melepas kepemilikan COM5,
melakukan DTR reset, membaca firmware, atau mengunggah
SVM30. Tahap berikutnya harus memastikan alat benar-benar
IDLE tanpa run aktif, mendapat izin terpisah untuk
menutup receiver secara aman dan membaca backup Flash/EEPROM,
memastikan jalur bootloader/ISP di PCB custom, serta
menyetujui prosedur rollback sebelum flashing.
