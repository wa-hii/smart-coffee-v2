# Tahap 7 — G2 guarded USB RX PCB custom, 13 Oktober 2026

**Target:** PCB custom ATmega2560 Smart Coffee E-Nose v2
yang terhubung USB Type-B → USB-A Raspberry Pi 5 (FT232R).
**Bukan** testbed Arduino Mega 2560 Serial1↔Pi GPIO.

## Keputusan keselamatan dan persetujuan

Operator/pembuat PCB menyatakan 13 Oktober bahwa
**PCB custom sudah aman** dan meminta pekerjaan dilanjutkan.
Ini merupakan **konfirmasi pembuat perangkat atas desainnya**,
**bukan pengukuran independen** terhadap rail 5 V,
arus balik, atau skematik VBUS.

Pra-syarat operasional dari SOP tetap penting saat membuka
USB serial: **alat harus IDLE, ada pengawas fisik yang dapat
segera memutus daya jika diperlukan, dan operator menerima
risiko DTR/RTS atau auto-reset MCU**. Kondisi tiga hal itu
**belum dikonfirmasi secara eksplisit** dalam sesi ini.
**G2 serial port open NOT RUN**. Pengujian G3 dengan
Nextion dan pompa/valve tidak termasuk izin ini.

## Preflight read-only yang terverifikasi

| Item | Hasil |
|---|---|
| SSH Pi | `enose-v3@enose-pi5` PASS |
| USB bridge | FT232R VID:PID `0403:6001`, serial `A10KMM3S` |
| Stable port | `/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0` → `ttyUSB0` |
| Port owner saat snapshot | tidak ditemukan oleh `fuser` |
| ModemManager/getty | inactive |
| Pi undervoltage indication | `vcgencmd get_throttled` = `0x0` |
| Source firmware host | `Serial.begin(115200)`, data/event JSON |
| Source firmware HMI | `Serial2` 9600 untuk Nextion |
| Source firmware boot | `actuator.begin()` memanggil `stop()`, tetapi versi terpasang belum diverifikasi |
| Komunikasi fisik via FT232R | **NOT RUN** |

USB descriptor yang telah diaudit: `Bus Powered`, `MaxPower=90mA`
(nilai deklarasi, bukan hasil pengukuran arus PCB).
Penilaian independen VBUS/backfeed tetap belum selesai;
status tersebut jangan diubah menjadi PASS berbasis
data descriptor.

## Perangkat lunak probe yang disiapkan

`scripts/stage7_usb_readonly_probe.py` dibuat khusus
untuk G2. Fitur:

- Port **hanya** FT232R dengan path by-id yang tetap,
  baud **115200 8N1**, maksimal **30 detik**.
- `exclusive=True`, sebelum membuka port set
  `dtr=False`, `rts=False`. Karena implementasi driver
  dapat memicu perubahan kontrol saat `open()`,
  ini **bukan jaminan zero-reset**.
- Tidak ada kode `write()`, perintah ke MCU,
  HMI, aktuator, kalibrasi, atau inferensi AI.
- Parser stream inkremental berdasarkan LF, tahan
  fragmentasi `read()`/timeout, limit 4096 byte
  tiap baris; menolak duplikasi kunci JSON dan
  angka nonfinite. Tidak mengasumsikan setiap
  baris berisi sensor; pesan boot, I2C, warn,
  event, sensor dipisahkan menurut skema.
- Output berisi **agregat frame/hash/preview metadata**,
  tidak menyimpan payload sensor mentah; evidence
  menggunakan mode create-once agar tidak menimpa.
- Tiga token perizinan CLI untuk G2, status IDLE,
  dan kehadiran pengawas fisik. Tes default tanpa
  token **menolak membuka tty**.

Regresi tanpa port:
`scripts/test_stage7_usb_readonly_probe.py`
**PASS di Windows dan Pi**. Mock pySerial membuktikan
DTR/RTS diset false sebelum `open`, exclusive,
max read size 128, close di `finally`,
dan menggagalkan panggilan `write()`.
Tes fragmen byte, oversized, no-overwrite, dan
penolakan port lain/baud/durasi/izin juga PASS.
File skrip sudah disalin ke
`~/smart-coffee-stage7/scripts/` di Pi.

## Perintah tahap G2 nanti (BELUM dijalankan)

**Jangan eksekusi** sampai operator memastikan
alat IDLE dan pengawas fisik siap menghentikan alat
jika reset, dengan izin eksplisit untuk pembukaan
port USB read-only. Perintah berikut untuk
pelaksanaan oleh engineering setelah persetujuan:

```bash
cd ~/smart-coffee-stage7
.venv/bin/python scripts/stage7_usb_readonly_probe.py \
  --port /dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0 \
  --duration 12 \
  --acknowledgment I_APPROVE_CUSTOM_PCB_USB_RX_G2 \
  --idle I_CONFIRM_IDLE \
  --supervised I_AM_ONSITE \
  --output results/pi_stage7/custom_pcb_usb_g2_first_run.json
```

Program **tidak menulis ke serial** tetapi
tetap berisiko reset ketika port dibuka.
G3 dan rilis model Tahap 10 **tidak otomatis
diotorisasi** bila G2 berhasil.

## Hasil dan blocker

- Source audit USB firmware: **PASS sebagai bukti source**.
- Pi USB enumerasi/kepemilikan: **PASS saat pemeriksaan**.
- G2 parser/mock dan deploy Pi: **PASS**.
- **G2 live UART: NOT RUN**; jangan klaim E2E
  perangkat fisik sampai ada evidence.
- **G3 akuisisi Nextion/aktuator: NOT RUN**.
- **AI release: NO-GO**, menunggu validasi prospektif.
