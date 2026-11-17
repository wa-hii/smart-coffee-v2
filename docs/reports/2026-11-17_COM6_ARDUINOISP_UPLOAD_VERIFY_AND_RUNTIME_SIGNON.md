# Upload ArduinoISP ke Mega CH340 COM6 dan verifikasi runtime STK500v1

**Tanggal:** 17 November 2026 WIB
**Branch:** `wahyu`
**Persetujuan:** operator menjawab **"ya lakukan"** terhadap permintaan
spesifik menimpa sketch Mega **COM6** dengan ArduinoISP, setelah diberi tahu
bahwa hasil readback sketch lama COM6 all-FF tidak dapat dipercaya sebagai backup.
Persetujuan ini **bukan** persetujuan menghapus atau mem-flash PCB E-Nose target.

## 1. Identitas dan preflight

- **COM6 programmer:** CH340 `VID:PID=1A86:7523`, Arduino Mega 2560.
- **COM11 target:** FT232RL `VID:PID=0403:6001`,
  serial `A10KNJBLA`, terhubung ke PCB custom ATmega2560 kedua.
- `lcd_acquisition_service.py` untuk identitas FT232RL target
  ditemukan berjalan dan **tidak dihentikan**.
- Sumber resmi ArduinoISP dalam folder privat
  `private/com12_arduino_isp/vendor/ArduinoISP.ino` telah
  diverifikasi SHA256:
  `9d6318e03dce7c12825fed3abe82a6c8a6d16842d2b38d64b278c37844d011e2`.
- Firmware hasil build untuk Mega COM6:
  `private/com6_mega_isp/build/mega_as_isp/firmware.hex`,
  SHA256 `fd40f224c2aa009afa3606d0931305a4f5df46f405a15d43775aa68afb35f408`.
- Wrapper `diagnostics/com12_arduinoisp/src/main.cpp` menetapkan
  **RESET target D10**, SPI hardware **D50–D52**, dan
  UART programmer **19200 baud**.

## 2. Upload yang benar-benar dilakukan

Perintah:

```text
pio run -c scripts/platformio_com6_arduinoisp.ini -e mega_as_isp -t upload
```

Output nyata:

```text
Using manually specified: COM6
Device signature = 0x1e9801 (probably m2560)
avrdude: writing flash (5406 bytes)
avrdude: 5406 bytes of flash written
avrdude: verifying flash memory against ... firmware.hex
avrdude: 5406 bytes of flash verified
avrdude done.
SUCCESS
```

**Kesimpulan:** sketch ArduinoISP berhasil ditulis ke
**Mega COM6** dan AVRDUDE melaporkan verifikasi Flash PASS.
**Tidak ada firmware PCB target COM11 yang disentuh.**
Flash aplikasi lama Mega COM6 telah diganti sesuai izin,
dan tidak ada backup sketch lamanya yang tervalidasi.

## 3. Uji firmware ArduinoISP berjalan (bukan hanya Flash)

Setelah upload dilakukan tes `scripts/com6_arduinoisp_runtime_check.py`,
yang membaca identitas USB COM6, membuka UART **19200 baud**
tanpa membuka COM11, menunggu bootloader selesai, kemudian
mengirim **hanya** perintah `STK_GET_SYNC + CRC_EOP`:

```text
TX: 30 20
RX: 14 10
status: ARDUINOISP_SIGNON_PASS
arduinoisp_stk500v1_runtime_verified: true
isp_target_entered_programming_mode: false
target_flash_written: false
target_eeprom_written: false
```

Balasan `14 10` merupakan `STK_INSYNC` dan `STK_OK`
sesuai fungsi sign-on pada source resmi.
Ini mengonfirmasi **sketch ArduinoISP berjalan melalui UART COM6**.
Skrip tidak mengirim perintah masuk programming mode,
perintah baca signature target, erase atau tulis memory.
Log dan hasil disimpan privat pada
`private/com6_mega_isp/arduinoisp_signon_*/result.json`.

QA mock `scripts/test_com6_arduinoisp_runtime_check.py`: PASS.
QA pemisahan port dan fail-closed `scripts/test_com6_mega_isp.py`: PASS.

## 4. Gerbang tindakan berikutnya

**Programmer COM6 READY. PCB target belum teruji.**

Sebelum mengakses ISP target, operator perlu:

1. Menghentikan proses akuisisi/receiver COM11 secara terawasi
   (tidak dilakukan dalam sesi ini).
2. Dengan seluruh sumber daya mati, memasang jumper
   dari Mega COM6: D10 → RESET target, D51 → MOSI,
   D50 → MISO, D52 → SCK, GND → GND.
   Titik target harus berdasarkan skematik/label PCB,
   tidak menebak kaki IC.
3. Memastikan power path aman; jangan menyatukan
   5 V USB programmer dan 5 V supply custom
   tanpa verifikasi, pastikan level logika kompatibel.
   Perhatikan kemungkinan **auto-reset programmer**
   ketika COM6 dibuka, yang dapat menghalangi
   protokol `stk500v1` saat target terpasang.
4. Setelah operator menyatakan wiring dan daya benar,
   jalankan pemeriksaan signature target **read-only**
   menggunakan `scripts/com6_isp_target_signature.py`
   pada COM6 `-c stk500v1 -b 19200`.
5. Jika signature target `0x1e9801` terbaca,
   backup Flash + EEPROM + fuse/lockbits
   PCB kedua dan verifikasi pemulihannya.
   Baru kemudian dapat dipertimbangkan
   upload firmware diagnostik atau produksi
   dengan izin terpisah.

## 5. Status akhir

| Komponen | Status |
|---|---|
| Identitas USB Mega programmer COM6 | PASS |
| Sketch ArduinoISP resmi SHA-pinned | PASS |
| Build ArduinoISP untuk COM6 | PASS |
| Flash ke programmer COM6 | **PASS** |
| AVRDUDE readback/verify Flash COM6 | **PASS** |
| STK500v1 runtime sign-on COM6 | **PASS** |
| Koneksi fisik ISP ke PCB target | **UNVERIFIED** |
| Signature MCU E-Nose PCB kedua | **NOT RUN** |
| Backup Flash/EEPROM PCB target | **NOT RUN** |
| Flash/RF500 pada PCB target | **NOT RUN** |
| Receiver COM11 | Dibiarkan berjalan |

Catatan: COM6 adalah **programmer yang siap digunakan**,
bukan bukti bahwa kerusakan UART0 atau Nextion pada PCB target
telah terselesaikan.
