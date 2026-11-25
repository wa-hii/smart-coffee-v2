# 25 Nov 2026 — ATmega eks COM3: USB FT232RL disconnect setiap transisi ~25 detik

## Status: HARDWARE DIAGNOSIS / STOP DATA COLLECTION

Host: `enose-v3@enose-pi5`, Pi 5; FT232RL A10KN6X9 (bekas Windows
COM3 A10KN6X9A), symlink
`/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KN6X9-if00-port0`.
Firmware RF30 dari commit `37095d0f` (build
`take30-ai30-rfhost-20261110`), listener RF500 dari commit `91c86686`.

## Bukti dari tiga percobaan Take Data gagal

- L-GRB B30 mulai 20:55:36; kernel USB disconnect 20:56:01;
  CSV incomplete 24 / 900.
- L-MING B32 mulai 21:00:24; kernel USB disconnect 21:00:49;
  CSV incomplete 25 / 900.
- L-MING B27 mulai 21:09:44; kernel USB disconnect 21:10:09;
  CSV incomplete 24 / 900.
- Kernel `usb 3-1: USB disconnect` dan `ftdi_sio ttyUSB0:
  FTDI ... now disconnected`, kemudian re-enumerasi serial yang
  sama A10KN6X9. Pada percobaan ketiga berulang tepat 30 detik:
  21:10:09, 21:10:39, 21:11:09, ... 21:19:09.
- Bahkan ketika listener RF500 **tidak membuka port** dan
  supervisor hanya menunggu FTDI, disconnection 30 detik tetap
  terjadi. Penjelasan berbasis parsing data/model AI/two serial
  consumers tidak sesuai bukti ini.
- Pi `vcgencmd get_throttled = 0x0`; USB
  `power/control=on`, `runtime_status=active`; ModemManager dan
  brltty tidak aktif. Status Pi ini **tidak mengukur** tegangan
  pada FT232R, PCB MCU, valve, L293DD, atau rail eksternal.

## Korelasi dengan firmware

Firmware 30 siklus berjalan dalam setiap siklus
25 s PURGING (solenoid OFF via setPurging()), 5 s COLLECTING
(solenoid ON via setCollecting()). L293DD IN3 = pin10 MCU,
IN4 = pin11 MCU, driver menghubungkan OUT3/OUT4 ke kumparan
valve. Waktu USB disconnect tepat sekitar 25 s setelah start,
lalu berulang 30 s meski receiver Pi mati.

**Hipotesis utama, belum terbukti secara elektrik:**
perubahan beban induktif valve atau ground/supply/noise
menjatuhkan koneksi FT232RL; kabel, konektor, backfeed, dan
kerusakan USB bridge masih kandidat.

Source `actuator.cpp` menyebut Festo MHE2-MS1H-3/2G-M7.
Datasheet Festo untuk part **196131** menyatakan **24 V DC**
dan 5.0 W pada fase arus awal, 1.25 W fase tahan.
Sebelum menentukan tegangan suplai, verifikasi bahwa komponen
fisik betul tipe/part number ini. Source driver L293DD
memiliki logic dan load supply terpisah serta clamp diodes
internal. Skematik PCB custom, VBUS USB vs catu eksternal,
decoupling aktual, dan titik ground **belum tersedia**.

Referensi pabrikan:
- Festo datasheet: https://ftp.festo.com/Public/PNEUMATIC/SOFTWARE_SERVICE/Datasheet/EN_GB/196131.pdf
- STMicro L293D/DD: https://www.st.com/en/motor-drivers/l293d.html

## Prosedur isolasi aman (memerlukan operator onsite)

1. Hentikan dari tombol **Cancel** di Nextion (firmware:
   `EVT:DATA_CANCEL` memanggil `stopAcquisition()`,
   `actuator.stop()`). **Jangan jalankan Take Data baru**.
   Jika tidak bisa dihentikan, matikan catu PCB dengan prosedur
   aman setelah memastikan aktuator tidak membahayakan;
   jangan lepas kabel/coil live.
2. Amati kernel menggunakan
   `sudo journalctl -k -f | grep --line-buffered -Ei 'usb 3-1|ftdi|ttyUSB0'`
   saat idle selama sedikitnya 90 s. Jika siklus disconnect
   berhenti tepat saat Cancel, hubungan kejadian dengan state
   mesin semakin kuat. Jika terus berlanjut walau PCB benar-benar
   idle, periksa jalur USB/konektor/PSU/bridge secara terpisah.
3. Dengan semua daya dimatikan sesuai urutan aman, foto sisi
   atas/bawah PCB dan label voltage/rating valve/adapter;
   inspect solder FT232R dan USB-B, konektor DC, kabel
   valve/solenoid, koneksi GND, L293DD, fuse/protection.
   Verifikasi model valve fisik sebelum menetapkan 24 V.
4. Dengan teknisi dan alat ukur yang layak, inspeksi
   suplai pada VSS (logic), VS (load) L293DD, rail 5V MCU,
   ground, VBUS FT232R, dan tegangan coil **saat pergantian
   phase**. Scope sesuai untuk menangkap droop/noise transien.
   Jangan menggabungkan rail USB VBUS dan 5V eksternal atau
   menambah dioda pada H-bridge tanpa skema.
5. Periksa decoupling dan integritas driver, proteksi spike,
   isolasi routing high-current vs USB, lalu uji dengan kabel
   USB-B data yang telah diketahui baik dan port Pi lain.
   Lakukan hanya setelah memutus semua catu dan memastikan
   wiring aman.
6. Lanjutkan dengan uji idle >=90 s dan SATU uji terawasi
   ketika supply/driver dinyatakan aman. Harus tidak ada
   disconnect saat transisi, semua 900 baris tervalidasi,
   dan `ACQ_COMPLETE`. Tiga file incomplete tidak boleh
   digunakan sebagai training.

## Gerbang lain yang belum lulus

Pada boot fisik COM3 23 Nov, ADS1115 `0/4` dan SHT30
tidak terdeteksi (laporan
`2026-11-23_COM3_COMMIT_37095D0F_RF30_FLASH_VERIFIED_SENSOR_I2C_MISSING.md`).
Meskipun beberapa frame ADC baru terlihat, jangan
menganggap sensor siap sebelum verifikasi ulang semua
sensor dan nilainya secara independen.

**Yang TIDAK dilakukan:** tidak mengubah firmware MCU,
EEPROM, Nextion, adaptor, USB power sysfs, fungsi valve,
atau menjalankan test fisik baru. Diagnosis SSH read-only
belum bisa mengukur atau memperbaiki rangkaian listrik fisik.
