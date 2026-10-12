# Arduino Mega 2560 ↔ Raspberry Pi 5 UART — BENCH TERISOLASI

**HASIL TESTBED 12 Oktober 2026: UART full-duplex
9600 baud pada hardware nyata PASS.**
Setelah operator menukar HV1→Mega D18 TX1
dan HV2→Mega D19 RX1, perbaikan parser
UART menghilangkan false-malformed akibat
timeout parsial; uji 30 s menangkap
28 heartbeat berurutan, 1 PONG,
0 malformed/gap/duplikasi.
USB Mega COM6 saat tes duplex mencatat
`PING ACK`. Detail QA:
`reports/2026-10-12_BENCH_TEST.md`.
Status ini hanya berlaku untuk
**Arduino Mega testbed ↔ Raspberry Pi 5**,
**bukan PCB custom atau AI produksi**.

**Tujuan:** uji UART testbed Arduino Mega 2560 melalui
level converter dua tegangan, tanpa firmware Smart Coffee PCB final.
**Status awal:** tes software & build saja; hasil bench fisik
dicatat pada laporan tersendiri, tidak disamakan dengan produksi.

## Topologi

```text
Laptop USB ─────── Mega 2560 (daya + upload/debug Serial 115200)
                        TX1 D18 ─── HV1 [translator] LV1 ─── GPIO15/RX pin10 Pi5
                        RX1 D19 ─── HV2 [translator] LV2 ─── GPIO14/TX pin8  Pi5
                        5V ──────── HV
                        GND ─────── GND ──────────────────── GND pin6 Pi
Pi PSU ──────────── Pi 5 3V3 pin1 ── LV (logic converter only)
```

TX/RX silang, GND bersama. **Jangan mencolok 5 V ke GPIO Pi**.
Saat wiring/perubahan jumper harus mematikan kedua perangkat,
termasuk USB Mega yang memasok daya dari laptop.
**Wajib** memeriksa pinout modul HV/LV, dan memastikan
tegangan LV1 menuju Pi RX tidak melebihi 3,3 V sebelum
tes live. Modul BSS138/pull-up generik dapat melemahkan
edge UART; mulai 9600 8N1, evaluasi sebelum baud tinggi.

Source board: `src/main.cpp`, PlatformIO proyek bench sendiri:
`pio run -d bench/mega_pi_uart`.
Hanya `Serial` USB debug 115200 dan `Serial1` 9600
yang digunakan. **Tidak ada operasi aktuator/sensor**.

### Upload hanya jika board Mega TESTBED terbukti benar

1. Pastikan Device Manager/PlatformIO menunjukkan
   board USB-serial **yang benar-benar Mega testbed**,
   tidak ada upload lain/Serial Monitor yang memiliki COM.
2. Setelah diidentifikasi, contoh perintah operator:

```powershell
pio run -d bench/mega_pi_uart -t upload --upload-port COM6
```

Jangan menjalankan perintah upload ke COM lain tanpa verifikasi.
Jangan mengubah `platformio.ini` di root proyek Smart Coffee.

### Pi 5

Target Pi terverifikasi: `/dev/ttyAMA0` (GPIO14/15).
Pi ini **tidak menggunakan `/dev/serial0`**
untuk pin 8/10, karena `serial0→ttyAMA10`
adalah debug header Pi 5. Sistem Pi ini sudah
mengaktifkan `dtparam=uart0=on` dan
`dtoverlay=uart0-pi5`; tidak perlu reboot.

Tes lokal tanpa port:

```bash
python3 bench/mega_pi_uart/pi/test_uart_bench.py
```

Tes serial baca saja **setelah keselamatan HV/LV diverifikasi**:

```bash
python3 bench/mega_pi_uart/pi/uart_bench.py --port /dev/ttyAMA0 \
  --baud 9600 --duration 20 --output /tmp/mega_uart_rx_01.json
```

Tes dua arah, setelah RX terbukti dan wiring Pi TX→Mega RX aman:

```bash
python3 bench/mega_pi_uart/pi/uart_bench.py --port /dev/ttyAMA0 \
  --baud 9600 --duration 20 --ping --output /tmp/mega_uart_bidir_01.json
```

Setelah berhasil, cek kestabilan selama durasi penuh:

```bash
python3 bench/mega_pi_uart/pi/uart_bench.py --port /dev/ttyAMA0 \
  --baud 9600 --duration 30 --ping --full-duration \
  --output /tmp/mega_uart_stability_01.json
```

Program membuka UART secara eksklusif dan menutupnya sesudah
durasi; keluaran JSON ditulis sekali (tidak menimpa).
`--ping` **hanya** mengirim perintah `PING,<nonce>`
yang dikembalikan sebagai PONG, tidak mengaktifkan aktuator.

Jika **tidak ada heartbeat sama sekali** meskipun USB laptop
menunjukkan Mega mengirim, diagnosis (dengan pengawasan laptop):

```bash
# Hanya satu perintah PING, tidak ada pengendalian aktuator
python3 bench/mega_pi_uart/pi/uart_bench.py --ping --probe-tx \
  --output /tmp/mega_uart_probe_tx01.json
```

Secara paralel lihat Serial USB Mega pada 115200,
cari teks `PING ACK`. Jika terlihat, jalur
Pi TX→Mega RX bekerja meski jalur balik RX Pi
belum bekerja. Jika tidak ada ACK, periksa
kedua arah, HV/LV, common GND, dan nomor pin.
Satu percobaan yang berhasil membutuhkan heartbeat baru
berurutan dan PONG nonce yang sama; penerimaan data
di-simulasikan pada QA offline, namun **hasil bench fisik**
harus dicatat dengan tanggal, port, baud, dan bukti.

Sumber:
- Raspberry Pi: https://www.raspberrypi.com/documentation/computers/configuration.html
- Raspberry Pi overlay `uart0-pi5`: https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README
- pySerial API: https://pyserial.readthedocs.io/en/latest/pyserial_api.html
