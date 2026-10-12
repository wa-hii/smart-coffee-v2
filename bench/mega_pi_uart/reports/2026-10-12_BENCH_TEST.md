# Laporan UART Hardware Bench Arduino Mega 2560 → Raspberry Pi 5

**Tanggal:** 12 Oktober 2026.
**Status:** Arduino firmware upload dan USB debug **PASS**,
Raspberry Pi UART GPIO **FAIL/INCONCLUSIVE — 0 frame**.
**End-to-end dua arah: BELUM BERHASIL.**

## 1. Ruang lingkup

Testbed sementara **board Arduino Mega 2560** dipakai
untuk protokol UART dengan Raspberry Pi 5; berbeda dari
PCB custom ATmega yang tetap menjadi hardware target
Smart Coffee E-Nose. Testbed memakai USB laptop sebagai
daya/upload/debug; Pi memakai PSU sendiri; UART data
melewati level converter HV=5 V/LV=3,3 V yang
dipasang operator pada breadboard. **Tidak ada foto
rinci/pengukuran LV1/HV1/ground yang diterima**;
keselamatan dan kebenaran jalur analog **belum
terverifikasi independen**.

Firmware isolasi di `bench/mega_pi_uart/src/main.cpp`,
build terpisah melalui PlatformIO
`bench/mega_pi_uart/platformio.ini`.
Port Mega di laptop `COM6` **USB-SERIAL CH340**
VID:PID 1A86:7523 (bukan COM5).
USB debug `Serial` 115200;
link GPIO `Serial1` 9600 pada D18 TX1/D19 RX1.
Pi port `/dev/ttyAMA0` GPIO14 TXD/GPIO15 RXD.

## 2. Riset best practice

- Raspberry Pi UART GPIO menggunakan level 3,3 V;
  jangan memasukkan TX 5 V Mega langsung ke Pi.
- Pada Pi 5, debug UART default ada di header
  khusus; untuk GPIO14/15 setup ini telah
  mengaktifkan `dtoverlay=uart0-pi5` dan
  `dtparam=uart0=on`. Alias `/dev/serial0`
  mengarah ke **ttyAMA10**, bukan GPIO14/15.
- Level converter BSS138 bidirectional lazim
  untuk I²C/open-drain. Ia dapat dipakai
  prototipe UART berbaud rendah dengan kabel
  pendek, tetapi kualitas edge harus diperiksa,
  terutama jika diberi pull-up lemah. Untuk
  produksi gunakan translator push-pull/UART
  yang sesuai atau IC dual-supply bus transceiver.
- Software Pi memakai pySerial dengan bounded
  `read_until`, timeout, POSIX `exclusive`,
  pemeriksaan nomor urut dan uptime, serta
  protokol PING dengan nonce; hanya boleh
  mengirim `PING,<nonce>` ketika diminta.

Sumber primer:
- https://www.raspberrypi.com/documentation/computers/configuration.html
- https://github.com/raspberrypi/firmware/blob/master/boot/overlays/README
- https://pyserial.readthedocs.io/en/latest/pyserial_api.html

## 3. Bukti aktual

| Tahap | Tindakan | Bukti/status |
|---|---|---|
| Build | `pio run -d bench/mega_pi_uart` | **SUCCESS**, RAM 402 B/8 KB, flash 3212 B/248 KB |
| Upload | `pio run -d bench/mega_pi_uart -t upload --upload-port COM6` | **SUCCESS**, ATmega2560 signature `0x1e9801`, 3212 bytes flash verified |
| USB Debug Mega | Baca `COM6` 115200, tidak menulis | **PASS**, `MEGA_PI_UART_BENCH_V1 READY`, HEARTBEAT 1–5 |
| Konfigurasi Pi | SSH read-only, pinctrl 14/15 | **PASS**: `ttyAMA0` tersedia, TXD0/RXD0, getty inactive, port tanpa owner |
| Data Mega→Pi | `uart_bench.py` 9600 RX-only selama 20 detik | **FAIL/INCONCLUSIVE**, 0 heartbeat, 0 byte/baris valid |
| Data Pi→Mega | Satu diagnostic `PING` dari Pi, USB debug Mega pada saat sama | **FAIL/INCONCLUSIVE**, Pi `ping_sent=true`, 0 PONG; Mega `PING ACK_COUNT=0` |
| Catu Pi | `vcgencmd get_throttled` | `0x0` saat pemeriksaan |
| Safety | Firmware bench tidak menyentuh pompa/valve/EEPROM/sensor | **PASS static** |
| AI/Smart Coffee | Firmware utama dan model tidak dipakai | **NOT RUN** |

Firmware sketch **berjalan dengan benar** pada
Mega melalui USB debug, sehingga diagnosis
terkuat saat ini: **jalur fisik UART/level
converter/GND/pinout**, bukan source firmware
tidak berjalan. Kondisi hardware tidak
memungkinkan penyimpulan penyebab tunggal
tanpa inspeksi di lokasi. Jangan mengklaim
bahwa level shifter rusak; belum diuji.

## 4. Daftar pemeriksaan operator untuk memperbaiki blocker

**MATIKAN DAYA MEGA DAN RASPBERRY PI SEBELUM
MEMINDAH JUMPER.** Laptop USB Mega juga dapat
memberi daya; lepaskan sesuai SOP bench,
jangan menyentuh jumper saat powered.

1. Verifikasi sumber HV=5 V **Mega**, LV=3,3 V
   **Pi**, satu GND bersama Mega–converter–Pi
   dan tidak ada short HV/LV.
2. Pastikan benar-benar memakai **Serial1 Mega**:
   TX1 **D18** ke HV1, RX1 **D19** dari HV2
   (bukan D1/D0, D16/D17, atau label IC pin fisik).
3. Pastikan **pasangan kanal yang sama**:
   HV1↔LV1 ke Pi **GPIO15 (pin fisik 10)**,
   HV2↔LV2 ke Pi **GPIO14 (pin fisik 8)**.
   Jangan tertukar TX→TX atau RX→RX.
4. Periksa tipe modul, orientation pin header,
   sambungan breadboard/baris rail,
   serta posisi VCC/GND. Rail breadboard
   bisa terputus di tengah.
5. Sebelum menghubungkan ulang Pi RX,
   operator berkompeten ukur output LV1
   ketika idle; tidak boleh lebih dari 3,3 V.
   Pengukuran DC **tidak membuktikan edge/timing
   UART 9600**; untuk diagnosis pulsa yang
   tepat gunakan osiloskop/logic analyzer
   bertingkat tegangan sesuai.
6. Setelah wiring terkoreksi dan tegangan aman,
   tes **RX-only 20 detik** lebih dahulu;
   harapkan ≥3 heartbeat berurutan, malformed=0,
   gap=0. Baru tes `--ping` PONG.
7. Bila tetap 0 byte, foto breadboard dan
   label HV/LV modul, identitas pin Mega/Pi,
   atau hasil pengukuran level dibutuhkan.
   Jangan menganggap pengaturan baud Pi
   salah karena sudah 9600 ketika diuji.

## 5. Kode/command

Laptop (sudah dilakukan, **tidak perlu upload
ulang tanpa alasan**):

```powershell
pio run -d bench/mega_pi_uart
pio run -d bench/mega_pi_uart -t upload --upload-port COM6
```

Raspberry Pi (script terkirim ke
`/home/enose-v3/mega_uart_bench/pi/`):

```bash
cd ~/mega_uart_bench
~/smart-coffee-stage7/.venv/bin/python pi/test_uart_bench.py

# Setelah wiring & tegangan aman:
~/smart-coffee-stage7/.venv/bin/python pi/uart_bench.py \
  --duration 20 --output results/uart_rx_run02.json

# Hanya setelah RX PASS & wiring Pi TX terverifikasi:
~/smart-coffee-stage7/.venv/bin/python pi/uart_bench.py \
  --duration 20 --ping --output results/uart_duplex_run02.json
```

Pilih nama output baru, jangan menimpa
evidence sebelumnya. Program berhenti sendiri
setelah maksimal 20 detik; menghentikan
lebih awal dengan Ctrl+C dapat menyebabkan
JSON final tidak tertulis.

**Batas:** ini adalah pengujian UART testbed,
bukan deployment Nextion/AI/kopi
atau validasi PCB custom.
