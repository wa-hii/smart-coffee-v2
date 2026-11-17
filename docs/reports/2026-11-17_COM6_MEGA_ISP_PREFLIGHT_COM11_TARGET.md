# Persiapan pemrograman PCB E-Nose kedua via Arduino Mega CH340 COM6

**Tanggal pengujian:** 17 November 2026 (WIB).
**Branch:** `wahyu`.
**Status:** preflight dan build PASS, **belum ada upload ke COM6 atau flashing target COM11**.

## 1. Identitas port dan status sistem

- **COM6 (programmer):** `USB-SERIAL CH340`, VID:PID `1A86:7523`.
  AVRDUDE read-only `-p m2560 -c wiring -P COM6 -b 115200 -n -v`
  berhasil, exit 0, signature **`0x1e9801`**. Ini MCU **Mega programmer**,
  **bukan signature ATmega target**.
- **COM11 (target E-Nose):** FT232RL VID:PID `0403:6001`,
  serial `A10KNJBLA`. Pada pemeriksaan awal terdapat proses
  `lcd_acquisition_service.py --port auto --usb-serial A10KNJBLA`
  yang masih berjalan. Proses tersebut **tidak dihentikan**;
  port COM11 **tidak dibuka** selama sesi ini.
- Hanya identitas USB tersedia saat ini. Belum ada bukti kabel
  SPI/RESET antara Mega COM6 dan PCB target sudah terpasang.
  Tidak boleh menyimpulkan komunikasi ISP target berhasil
  hanya karena COM6 memiliki bootloader yang berfungsi.

## 2. Firmware ArduinoISP untuk COM6 — build saja

Sumber resmi ArduinoISP yang sudah diverifikasi SHA-256:
`9d6318e03dce7c12825fed3abe82a6c8a6d16842d2b38d64b278c37844d011e2`
tersimpan secara privat pada
`private/com12_arduino_isp/vendor/ArduinoISP.ino`.
Wrapper C++ yang ada pada
`diagnostics/com12_arduinoisp/src/main.cpp`
memverifikasi **RESET D10**, SPI hardware Mega **D50–D52**
dan **19200 baud** untuk protokol programmer setelah di-upload.

File konfigurasi khusus port baru:
`scripts/platformio_com6_arduinoisp.ini`.
Perintah yang **sudah dijalankan**:

```text
pio run -c scripts/platformio_com6_arduinoisp.ini -e mega_as_isp
SUCCESS
Flash = 5406 byte
RAM global = 482 byte
```

**Tidak menjalankan `-t upload`.**
Upload ArduinoISP akan **menggantikan sketch yang sedang ada
pada Arduino Mega COM6**, bukan mengubah PCB E-Nose.
Konfigurasi `upload_port = COM6`; COM11 tidak pernah
menjadi port upload ArduinoISP.

## 3. Pemeriksaan backup sketch lama Mega COM6

Percobaan baca-saja:
`python scripts/com6_mega_isp_backup_programmer.py`.

```text
avrdude read-only exit = 0
backup_verified = false
error = ALL_FF_READBACK_NOT_RECOVERABLE
flash_written = false
eeprom_written = false
```

Log dan hasil baca disimpan di:
`private/com6_mega_isp/programmer_original_20261117_175125_486138/`
(di-ignore Git). Hasil pembacaan Flash yang seluruhnya `FF`
**tidak dapat digunakan sebagai backup yang dapat dipulihkan**.
Hal ini tidak membuktikan Flash fisik memang kosong karena
bootloader bisa membatasi pembacaan.

Karena tidak ada backup sketch Mega COM6 yang tepercaya,
**upload ke COM6 memerlukan izin jelas untuk menimpa sketch
yang sudah ada.** Jangan menyamakan izin menguji signature
COM6 dengan izin menulis firmware target.

## 4. Jalur SPI/ISP yang harus diverifikasi secara fisik

Matikan catu daya saat memasang jumper. Gunakan skematik atau
label header PCB target, jangan menebak pin kemasan ATmega.

| Arduino Mega COM6 (programmer) | PCB E-Nose ATmega2560 (target) |
|---|---|
| D10 | RESET target |
| D51 / MOSI | MOSI target |
| D50 / MISO | MISO target |
| D52 / SCK | SCK target |
| GND | GND target |

Jangan menyatukan **5 V USB Mega COM6** dan **5 V PSU custom PCB
target** secara langsung tanpa verifikasi power path dan backfeed.
Pastikan catu target sesuai dan sinyal SPI 5 V kompatibel.
Perhatikan bahwa ArduinoISP pada Mega memerlukan
`-c stk500v1 -P COM6 -b 19200` **setelah sketch ArduinoISP
berhasil dipasang**. Baud ini berbeda dari bootloader Mega
COM6 sendiri (`wiring/115200`).

Pemeriksaan target read-only telah dibuat:
`scripts/com6_isp_target_signature.py`, dengan guard
`--arduinoisp-installed`, `--wiring-verified` dan
`--receiver-stopped`. Skrip juga memeriksa proses receiver
Windows; bila masih aktif, **STOP**. Script mengizinkan
COM11 USB dicabut saat ISP untuk menghindari masalah
backfeed, tetapi tidak menoleransi COM11 dengan identitas
USB berbeda.

**Skrip ini belum dijalankan terhadap hardware target**
karena koneksi ISP fisik dan izin upload Mega belum tersedia.
Simulasi jalur fail-closed telah PASS.

## 5. Tahap berikutnya dan batas

1. Operator menyatakan secara eksplisit bahwa
   **sketch lama Arduino Mega COM6 boleh ditimpa** meski
   backup readback tidak valid.
2. Operator menegaskan status kabel ISP
   antarboard dan power path aman. Jika jumper sudah
   terpasang, pastikan proses akuisisi/receiver
   dihentikan secara terawasi sebelum uji target.
3. Upload **ArduinoISP hanya ke COM6**, verify.
4. Baca signature **target PCB kedua** via `stk500v1/19200`,
   kemudian baca Flash/EEPROM/fuse dan validasi backup.
   Pada ATmega2560 periksa keterbatasan alamat ISP
   untuk >128 KiB; jangan mengasumsikan backup lengkap
   hanya dari exit code.
5. Setelah bukti pemulihan/backup cukup dan ada
   izin khusus, pilih firmware diagnosis UART–Nextion
   atau RF30 untuk langkah berikutnya.

**Tidak ada penulisan Flash/EEPROM COM6 maupun COM11,
tidak ada reset MCU target, dan tidak ada kontrol pompa/valve
dalam pemeriksaan ini.**
