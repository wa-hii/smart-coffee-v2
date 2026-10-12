# Laporan UART Hardware Bench Arduino Mega 2560 → Raspberry Pi 5

## Addendum: DIAGNOSIS SELESAI — 12 Oktober 2026

**Hasil akhir testbed UART fisik: PASS_BIDIRECTIONAL,
9600 baud, 8N1**. Status awal FAIL/INCONCLUSIVE
di bawah adalah **riwayat pemeriksaan sebelum
penukaran jumper dan perbaikan parser**, bukan
status terakhir.

### 1. Koreksi wiring operator

Operator melaporkan sebelum perbaikan
`HV1→Mega D19`, `HV2→Mega D18`.
Kontrak resmi ATmega2560 Arduino Mega menggunakan
`D18=TX1` dan `D19=RX1`. Operator menukar jumper
menjadi:

| Jalur | Koneksi yang bekerja pada testbed |
|---|---|
| Mega D18 **TX1** → Pi RX | D18 → HV1 ↔ LV1 → GPIO15 Pi, pin fisik 10 |
| Pi TX → Mega D19 **RX1** | GPIO14 Pi, pin fisik 8 → LV2 ↔ HV2 → D19 |
| Tegangan | HV 5 V Mega, LV 3,3 V Pi; GND bersama sesuai instruksi operator |

**Catatan QA:** tidak ada alat ukur atau foto skema
yang diverifikasi independen; klaim jalur
tegangan aman secara elektrik tidak otomatis
dibuktikan hanya oleh keberhasilan komunikasi.

### 2. Bug software ditemukan dan diperbaiki

Pengujian awal setelah jumper ditukar menunjukkan
**40 frame malformed dalam 20 detik** meskipun
UART aktif. `uart_raw_diagnostic.py` kemudian
membaca 256 byte RX pada Pi yang berisi
JSON heartbeat ASCII utuh dengan pemisah
`\r\n`, urutan naik `seq=1509, 1510, 1511`.
Ini mengonfirmasi UART receive **fisik sudah
berjalan pada 9600 baud**.

Akar penyebab *false negative* pengujian adalah
validator lama memanggil pySerial
`read_until(b"\n")` dengan **timeout 0,5 s**
sementara heartbeat dikirim tiap **1 s**.
Setiap periode kosong dapat mengembalikan
potongan baris yang tidak berakhir newline;
program lama salah menghitungnya sebagai
frame rusak (bukan menunggu pesan lengkap).

Perbaikan `pi/uart_bench.py`: gunakan
`LineFramer` yang membaca chunk pendek,
**menumpuk byte hingga newline**, membatasi
memori per frame 256 byte, mengabaikan
baris parsial awal ketika port mulai dibuka,
dan menangani overlong frame tanpa
memecahnya jadi banyak JSON error.
`pi/test_uart_bench.py` sekarang menguji
fragmentasi satu byte/berlapis, CRLF,
overlong recovery, dan nonce allowlist.
Semua regresi offline lulus di Windows
dan Raspberry Pi.

### 3. Hasil nyata setelah perbaikan

| Pengujian | Hasil Pi / bukti |
|---|---|
| Raw UART setelah kabel ditukar | **256 byte** cuplikan heartbeat ASCII 9600 valid |
| RX-only dengan parser baru | **PASS_RX_ONLY**: 5 heartbeat, 0 malformed, 0 gap, 0 duplicate, 0 timestamp error |
| Duplex pertama setelah parser | RX 19/19 baik, `PING` terkirim, belum ada PONG (riwayat gagal) |
| Duplex saat debug USB laptop berjalan bersamaan | **PASS_BIDIRECTIONAL**: RX 5 heartbeat, 1 PONG dengan nonce benar, 0 error |
| Monitor USB Mega COM6 bersamaan | **29 heartbeat, 1 PING ACK**, memverifikasi Pi→Mega benar-benar masuk `Serial1` |
| Stabilitas duplex selama 30 detik | **PASS_BIDIRECTIONAL**: **28 heartbeat**, 1 PONG, 0 malformed/gap/duplicate/uptime errors |
| Aktuator/pompa/valve, EEPROM, kalibrasi, model AI | **TIDAK DIJALANKAN**; firmware bench tidak memiliki perintah tersebut |

Pada 30 detik, pembaca membuka UART ketika
Mega sudah mengirim; protokol sync membuang
fragmen pesan pertama sampai newline,
sehingga jumlah 28 tidak otomatis berarti
2 paket hilang. **Tidak ada gap** dalam
sequence heartbeat yang tercatat
(seq 105 s.d. 132).

Evidence lengkap tetap ada pada Pi:
`/home/enose-v3/mega_uart_bench/results/`.
Ringkasan serta checksum SHA256 dari hasil
Pi disimpan dalam
`bench/mega_pi_uart/evidence/2026-10-12_after_swap_summary.json`.
Monitor USB laptop:
`bench/mega_pi_uart/evidence/mega_usb_monitor_after_swap.json`.

### Keputusan akhir

- **PASS hardware testbed:** komunikasi UART
  full-duplex Arduino Mega D18/D19 ↔ Pi GPIO14/15
  melalui level converter, **9600 8N1**.
- **PASS software:** framing robust, validasi
  seq/time, nonce PING/PONG, bounded buffering.
- **Belum diuji:** 115200 baud pada level
  converter ini, data sensor A0, kualitas
  power/gelombang secara elektrikal,
  PCB custom Smart Coffee, Nextion, AI
  prospektif dan E2E produksi.
- **Tidak perlu** flash ulang Mega, mengubah
  `config.txt`, atau mengganti
  `/dev/serial0`. Untuk GPIO14/15
  Pi 5 ini tetap `/dev/ttyAMA0`.

---

**Tanggal:** 12 Oktober 2026.
**Status saat tes pertama (historis):** Arduino firmware upload dan USB debug **PASS**,
Raspberry Pi UART GPIO **FAIL/INCONCLUSIVE — 0 frame**.
**End-to-end dua arah pada tes pertama: BELUM BERHASIL.**

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
