# Percobaan alternatif COM11 FT232RL onboard: tidak ada jalur flash yang merespons

**Tanggal:** 13 November 2026, 17.29–17.33 WIB.
**PCB:** ATmega2560 kedua, FT232RL onboard, Windows COM11,
USB VID:PID `0403:6001`, serial `A10KNJBLA`.
**Branch:** `wahyu`.

## Tujuan

Atas permintaan operator untuk mencoba skema pemrograman lain,
dilakukan percobaan **baca-saja** alternatif bootloader UART.
Tidak mengaktifkan pompa, valve, Nextion, inferensi live,
atau menulis Flash/EEPROM.

## Preflight

- Deteksi port COM11 dengan identitas USB FT232R onboard cocok.
- Tidak ditemukan proses `lcd_acquisition_service.py` atau
  `avrdude.exe` aktif yang memegang port.
- Folder `data/raw/.incoming` kosong.
- Windows PnP hanya menampilkan USB Serial Converter dan
  USB Serial Port FTDI terkait; **tidak ada ISP USB
  programmer** yang dapat digunakan.
- RF30 kandidat privat memiliki hash sebelumnya yang terverifikasi,
  `26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6`.
- Probe standar `wiring/115200` pada 13 November pukul 17.10
  sebelumnya timeout dengan protokol STK500v2.

## Varian programmer alternatif yang benar-benar diuji

Kode: `scripts/com11_alternative_bootloader_probe.py`.
Sebelum mengakses AVRDUDE, skrip melakukan preflight identitas
COM11 secara ketat. Semua perintah memakai `-n -v`,
dibatasi **14 detik/profil**.

| Profil | Baud | Perilaku | Signature |
|---|---:|---|---|
| `wiring` (pengujian sebelumnya) | 115200 | `stk500v2_ReceiveMessage(): timeout` | Tidak ada |
| `arduino` (alternatif STK500v1) | 115200 | `TIMEOUT_KILLED` | Tidak ada |
| `wiring` (alternatif baud) | 57600 | `TIMEOUT_KILLED` | Tidak ada |

Hasil varian baru:
`NO_ALTERNATE_BOOTLOADER_SIGNATURE_NO_FLASH`,
exit code 3, **0 signature terkonfirmasi**.

Log asli dan manifest privat:
`private/com11_second_pcb_deployment/alternative_probe_20261113_172944_002239/`.

## Probe RX-only Windows

Kode: `scripts/com11_uart_readonly_diagnostic.py`.
Port COM11 dibuka **sekali** dengan DTR/RTS disetel
false sebelum `open()`, pada 115200 baud selama
8 detik, tanpa pemanggilan `write()`.
Pulsa DTR sesaat akibat implementasi driver/hardware
**tidak dapat dikesampingkan**.

```text
status: RX_ZERO_BYTES_INCONCLUSIVE
duration_s: 8.0
rx_bytes: 0
uart_tx_bytes: 0
fw_hello_seen: false
mcu_signature_verified: false
flash_written: false
eeprom_written: false
```

Log privat: `private/com11_second_pcb_deployment/rx_readonly_20261113_173150_393685/`.

Nol byte saat idle **tidak membuktikan chip rusak**:
firmware yang terpasang mungkin tidak mengirim data saat
idle, mungkin tertahan pada boot/sensor, TX/RX tidak
terhubung sebagaimana diharapkan, atau voltase/clock/reset
belum sesuai. Hasil ini hanya menambah bukti bahwa
firmware MCU belum dapat diidentifikasi melalui COM11.

## Penjelasan batas FT232RL dan metode ISP

FT232RL onboard **terlihat sebagai USB–UART**, bukan bukti
bahwa jalur SPI programming terhubung. Dokumentasi AVRDUDE
memungkinkan FT232R digunakan untuk bitbang programming
**hanya jika sinyal FT232R memang dirutekan secara fisik**
ke pin SPI/RESET yang diperlukan:
https://avrdude.readthedocs.io/en/latest/5-Programmer_Specific_Information.html

Tidak ada bukti net FT232RL ke MOSI/MISO/SCK/RESET
atau perangkat USBasp/Atmel-ICE dalam koneksi fisik
saat ini. Mengganti `-c` menjadi `ft232r` atau
`usbasp` tanpa jalur yang sesuai **bukan**
cara untuk membuat hardware ISP secara software.

## Langkah yang masih memerlukan koneksi hardware

1. Saat alat aman dan tidak mengambil data, periksa
   skematik/continuity jalur DTR# FT232RL ke RESET
   ATmega, TXD/RXD0, ground, catu dan clock.
2. Jika tidak ada bootloader/auto-reset, siapkan
   **programmer ISP** (USBasp/Atmel-ICE/AVRISP)
   dan sambungkan **MISO, MOSI, SCK, RESET, GND**,
   serta VTref/VCC sesuai catu target dan dokumentasi
   programmer. Jangan menghubungkan VCC dari dua
   sumber yang bertentangan.
3. Verifikasi signature ATmega2560 `0x1e9801`,
   buat backup Flash dan EEPROM **PCB kedua**,
   kemudian upload aplikasi RF30 dan verify.
   Jangan memakai backup PCB COM5 lama.
4. Kembalikan USB FT232RL ke Pi 5, validasi `pHome`,
   900 sampel, roast dan `AI_RESULT_ACK`
   secara end-to-end.

## QA dan status

`test_com11_alternative_bootloader_probe.py` dan
`test_com11_uart_readonly_diagnostic.py` PASS pada
simulasi no-write; pengujian firmware/upload penuh
masih BLOCKED sampai ada programmer yang dapat
berkomunikasi dengan MCU fisik.

**Status akhir: NO-GO UNTUK FLASH MELALUI KOMUNIKASI SAAT INI.**
Tidak ada operasi Flash/EEPROM. Port USB COM11
masih terdeteksi pada akhir pemeriksaan; tidak ada
programmer ISP baru. Masalah ini memerlukan perubahan/
verifikasi koneksi fisik, bukan sekadar penyesuaian
software atau baud rate.
