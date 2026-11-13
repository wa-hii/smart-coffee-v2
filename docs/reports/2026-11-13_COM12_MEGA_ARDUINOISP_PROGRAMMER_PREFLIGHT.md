# Persiapan Arduino Mega 2560 CH340 COM12 sebagai ISP untuk PCB E-Nose kedua

**Tanggal:** 13 November 2026 WIB
**Branch:** `wahyu`
**Ruang lingkup:** identifikasi board programmer, pengujian bootloader read-only,
backup programmer secara read-only, penyiapan dan kompilasi ArduinoISP resmi.
**TIDAK ADA upload atau penulisan firmware pada Mega COM12 maupun PCB COM11.**

## 1. Identitas perangkat dan bukti

Windows mendeteksi dua port yang **harus dipisahkan**:

| Port | USB | Fungsi | Pembuktian |
|---|---|---|---|
| COM12 | CH340, VID:PID `1A86:7523`; tidak memiliki serial number unik yang dilaporkan | **Arduino Mega 2560 programmer** | AVRDUDE `wiring/115200` membaca signature **`0x1e9801`**, exit 0 |
| COM11 | FT232RL VID:PID `0403:6001`, serial `A10KNJBLA` | **PCB E-Nose kedua TARGET** | USB PASS, bootloader MCU sebelumnya timeout |

Signature yang sudah terbaca adalah dari **COM12**, BUKAN dari
ATmega2560 target COM11. Tidak ada receiver maupun programmer aktif
yang mengunci port saat pemeriksaan awal. Tidak ditemukan perangkat
USBasp/Atmel-ICE lain.

Skrip preflight:
`scripts/com12_mega_isp_preflight.py` membedakan dua port
berdasarkan VID/PID, identitas FTDI target, dan menggunakan AVRDUDE
`-p m2560 -c wiring -P COM12 -b 115200 -n -v`.
Hasil `MEGA2560_BOOTLOADER_PASS` disimpan di
`private/com12_arduino_isp/bootloader_probe_*/`.
Seluruh output privat dilindungi `private/.gitignore`.

## 2. Pemeriksaan Flash/EEPROM Arduino COM12 sebelum mengganti sketch

`scripts/com12_mega_isp_backup_programmer.py` melakukan
pembacaan read-only `flash:r` dan `eeprom:r` menggunakan
bootloader COM12. AVRDUDE mengembalikan exit 0 dan
signature `0x1e9801`, tetapi pembacaan Flash tidak
berisi data non-`FF`: validasi menghasilkan
`ALL_FF_READBACK_NOT_RECOVERABLE`.

**Keputusan:** hasil ini **BUKAN backup sketch lama COM12
yang dapat dipulihkan**. Bisa saja aplikasi kosong
atau pembacaan dibatasi bootloader/lock bits;
jangan menyimpulkan isi Flash lama benar-benar kosong
tanpa verifikasi mandiri.
Tidak ada data Mega COM12 yang ditimpa.
Lokasi privat:
`private/com12_arduino_isp/programmer_original_20261113_203757_269532/`.

Karena sketch lama tidak dapat dicadangkan secara meyakinkan,
**upload ArduinoISP ke COM12 memerlukan persetujuan eksplisit
operator bahwa sketch Arduino Mega COM12 boleh diganti**.
Ini *berbeda* dari izin flashing PCB E-Nose COM11.

## 3. ArduinoISP resmi dan build

Skrip `scripts/fetch_com12_arduinoisp_official.py`
mengambil kode sketch resmi Arduino Examples (lisensi BSD),
memastikan SHA-256:
`9d6318e03dce7c12825fed3abe82a6c8a6d16842d2b38d64b278c37844d011e2`,
dan menyimpannya di lokasi Git-ignore
`private/com12_arduino_isp/vendor/ArduinoISP.ino`.

Wrapper `diagnostics/com12_arduinoisp/src/main.cpp` memakai
source resmi tersebut, memaksa kompilasi C++ dengan
assert pin untuk **RESET D10**, SPI hardware **D50/D51/D52**,
serta **19200 baud**. Wrapper ini dibuat karena preprocessor
`.ino` PlatformIO sempat memunculkan peringatan redefinisi
makro ketika file resmi dikompilasi langsung. Setelah
dibangun melalui wrapper, peringatan tersebut hilang.

Konfigurasi `scripts/platformio_com12_arduinoisp.ini`
khusus environment `mega_as_isp`: target MCU ATmega2560,
sketch ArduinoISP, `upload_protocol=wiring`,
`upload_port=COM12` dan baud upload 115200.
`monitor_speed=19200` adalah baud **programmer
ArduinoISP setelah sketch terpasang**, berbeda dari
baud bootloader COM12 ketika upload.

Perintah yang **sudah** dijalankan:

```text
python scripts/fetch_com12_arduinoisp_official.py
pio run -c scripts/platformio_com12_arduinoisp.ini -e mega_as_isp

SUCCESS
Program: 5406 byte (2,1% kapasitas aplikasi)
RAM: 482 byte (5,9%)
```

**Belum dijalankan:** `-t upload`.
Setelah operator mengizinkan penimpaan sketch COM12,
sketch ArduinoISP dapat di-upload ke **COM12 SAJA**.
Perintah programmer **setelah sketch ArduinoISP berhasil
terpasang** memakai `-c stk500v1 -P COM12 -b 19200`,
BUKAN `-c wiring` dan bukan COM11.

## 4. Kabel ISP yang perlu operator pasang secara fisik

**Matikan semua catu daya sebelum memasang jumper.**
Gunakan skematik/label asli PCB untuk menemukan
header/test point ISP target; jangan menebak kaki
ATmega TQFP yang berdekatan.

| Arduino Mega 2560 COM12 (programmer) | PCB E-Nose kedua (target) |
|---|---|
| D10 | RESET ATmega2560 target |
| D51 / MOSI / COPI | MOSI / COPI target |
| D50 / MISO / CIPO | MISO / CIPO target |
| D52 / SCK | SCK target |
| GND | GND target |

**D53 (SS) bukan RESET target.**
Untuk SPI juga dapat memakai pin ICSP programmer
yang **benar-benar milik ATmega2560**, bukan
ICSP khusus chip USB pada board tertentu.

Arduino Mega mendapat daya dari USB COM12,
sedangkan PCB target memakai supply custom 5 V.
Jangan menyatukan jalur **5 V USB programmer**
dan **5 V custom target** secara langsung tanpa
analisis pembagian daya/backfeed terlebih dahulu.
**GND wajib bersama.** Pastikan target sudah
memiliki 5 V yang benar sebelum sinyal SPI
diberikan, dan tegangan logika kedua perangkat
kompatibel. Jika kabel USB COM11 pada PCB target
menyebabkan backfeed atau auto-reset,
putuskan USB target saat prosedur ISP
setelah memastikan catu target independen.

Tutorial resmi:
https://support.arduino.cc/hc/en-us/articles/4841602539164-Burn-the-bootloader-on-UNO-Mega-and-classic-Nano-using-another-Arduino

## 5. Tahap setelah operator melakukan pengkabelan

Skrip `scripts/com12_mega_isp_target_signature.py`
terkunci **fail-closed** bila tidak diberi
`--wiring-verified`. Setelah sketch ArduinoISP
**berhasil di-upload** ke Mega COM12,
operator memverifikasi wiring, dan catu dinyatakan aman,
jalankan:

```text
python scripts/com12_mega_isp_target_signature.py --wiring-verified
```

Skrip hanya memakai AVRDUDE:
`-p m2560 -c stk500v1 -P COM12 -b 19200 -n -v`
dengan timeout. Ia membaca signature **target SPI**,
**tidak** menulis Flash, EEPROM, fuse atau lockbits.
Jika `0x1e9801` terbaca, target PCB kedua baru
teridentifikasi secara hardware. Setelah itu perlu
backup **Flash dan EEPROM asli target** disertai
fuse/lockbit read-only dan verifikasi hash/scope
sebelum memilih langkah upload.

**Peringatan khusus ATmega2560:** Flash 256 KiB
memerlukan pengalamatan di atas 128 KiB.
Sketch ArduinoISP/STK500v1 tertentu mempunyai
keterbatasan pengalamatan 16-bit. Jangan menyatakan
backup penuh valid hanya karena AVRDUDE exit 0;
uji alamat di atas batas 128 KiB atau gunakan
programmer yang mendukung extended address.
Jika original Flash target tidak dapat dipulihkan
secara andal, **STOP sebelum erase/upload**.

Setelah signature/backup dan izin khusus,
barulah putuskan apakah akan memakai firmware
diagnostik UART–Nextion atau produksi RF30.
Tidak diperbolehkan langsung meng-upload SVM30
PCB lama atau mem-flash RF500 tanpa validasi.

## 6. Status akhir

| Tahapan | Status |
|---|---|
| Arduino Mega CH340 COM12 terdeteksi | PASS |
| Bootloader MCU programmer COM12 | **PASS — 0x1e9801** |
| Sketch ArduinoISP resmi SHA-pinned | PASS |
| Build ArduinoISP melalui wrapper | **PASS (compile-only)** |
| Backup sketch COM12 yang recoverable | **FAIL: hasil all-FF, tidak dapat dipercaya** |
| Upload ArduinoISP ke COM12 | **NOT RUN — perlu izin overwrite** |
| Kabel ISP Mega → PCB kedua | **Belum terkonfirmasi terpasang** |
| Signature MCU target E-Nose | **NOT RUN** |
| Backup & flash target PCB kedua | **NOT RUN** |
| Nextion pHome dan RF500 live | **BELUM terverifikasi / tetap ditahan** |

Seluruh perubahan pengguna di CSV dan HMI tidak disentuh.
