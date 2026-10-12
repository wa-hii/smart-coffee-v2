# Tahap 7 — Verifikasi topologi UART Raspberry Pi 5 (read-only)

### Addendum konfigurasi catu daya aktual

Operator mengonfirmasi **ATmega memakai adaptor
daya eksternal terpisah dari adaptor Raspberry
Pi**, sambil tetap tersambung USB langsung
untuk komunikasi. Informasi ini mengonfirmasi
dua catu, **bukan** isolasi USB VBUS,
ketiadaan backfeed, maupun aman-tidaknya
mode reset DTR pada papan custom FT232R.
Belum ada skematik/foto power PCB yang
memastikan sumber 5 V ATmega berasal dari
jack DC/VIN atau masukan langsung rail 5 V.

**G0 tetap PARTIAL/BLOCKED; G2/G3 NOT RUN**.
Audit jalur suplai/USB dan pengamatan fisik
menjadi prasyarat uji serial read-only.
Rincian checklist operator di
`docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`.

## Rekonsiliasi klarifikasi wiring operator (12 Oktober 2026)

Operator selanjutnya memperjelas koneksi sebenarnya:
**USB port ATmega ↔ kabel USB ↔ USB port Pi 5**.
Tidak ada GPIO Pi atau TTL RX/TX eksternal yang
digunakan. Oleh karena itu jalur native
`ttyAMA0` yang ditemukan sebelumnya **tidak
digunakan** untuk komunikasi host saat ini.
FT232R `ttyUSB0` kemungkinan besar menjadi
USB-serial bridge papan ATmega yang terkoneksi;
identitas PCB fisik tetap perlu dikaitkan
melalui foto/skematik operator. Tidak ada alasan
mengubah Serial1 atau mengalihkan Nextion Serial2.

**Status G0 daya USB VBUS/backfeed: BELUM
TERVERIFIKASI**. Kabel sudah terpasang menurut
operator, tetapi ini tidak menggantikan
persetujuan keselamatan kelistrikan.
**Port serial tidak dibuka**. G2/G3 tidak
dijalankan. SOP relevan kini
`docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`,
bukan SOP TTL/GPIO.

**QA setelah koreksi jalur USB:**
`python scripts/test_stage7_usb_contract.py`
PASS untuk Serial UART0 115200,
Nextion Serial2 9600, Serial1 tidak aktif,
dan larangan membuka tty tanpa izin.
`test_stage0_contract.py`,
`test_stage1_firmware_contract.py`,
`test_stage7_uart_preflight.py`,
`test_stage7_bridge.py` dan
`test_stage7_pi_adapter.py` PASS.
Verifier HMI **12 halaman/23 event PASS**,
PlatformIO mega2560/nextion_test **2/2 SUCCESS**,
`compileall` dan `git diff --check` PASS.
Nomor pin TQFP-100 USART2 dalam
`nextion/NX4827T043_011/ATMEGA2560_USART2_WIRING.txt`
juga dikoreksi menjadi PH0/RXD2 pin 12,
PH1/TXD2 pin 13; perlu verifikasi
skematik PCB jika dipakai untuk kerja fisik.
Tidak ada live serial test, flash,
ataupun perintah aktuator.

**Tanggal:** 12 Oktober 2026.

**Konteks:** pengguna menyatakan Pi sudah
terkoneksi ke UART ATmega2560, tetapi
belum memberi jenis konektor, pin, rangkaian
penyesuaian tegangan, atau izin membuka port.

## Pemeriksaan lapangan melalui SSH

SSH `enose-v3@enose-pi5` melalui Tailscale
meminta autentikasi ulang dan kemudian berhasil.
Dengan perintah **read-only** diperoleh:

- Pi 5 Model B Rev 1.1, kernel
  `6.18.50+rpt-rpi-2712`, `throttled=0x0`.
- USB FTDI FT232R `0403:6001` terenumerasi
  sebagai `/dev/ttyUSB0`,
  by-id `usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0`.
  Tidak otomatis membuktikan kabel FT232 TTL
  terhubung ATmega.
- Native Pi UART `/dev/ttyAMA0` tersedia.
  `pinctrl get 14` → `GPIO14 = TXD0`,
  `pinctrl get 15` → `GPIO15 = RXD0`.
  Config Pi: `dtparam=uart0=on`,
  `dtoverlay=uart0-pi5`.
- `/dev/serial0` mengarah ke **ttyAMA10**
  (debug), jadi salah apabila diasumsikan
  alias GPIO14/15 di Pi 5 ini.
- `/proc/cmdline`: console aktif `tty1`,
  tidak ditemukan `console=ttyAMA0`.
  serial-getty ttyAMA0, ttyAMA10, ttyUSB0
  tidak aktif.
- `fuser` tidak menemukan proses
  pemilik port pada saat pemeriksaan,
  tidak menjamin bebas pada waktu lain.
- Unit test `scripts/test_stage7_uart_preflight.py`
  **PASS offline di Windows dan Pi**,
  script inventaris nyata **berjalan di Pi**,
  tidak membuka /dev/tty apa pun.

## Review firmware

Source yang diperiksa: `src/main.cpp`,
`inference.cpp`, `nextion_transport.cpp`.
`Serial.begin(115200)` adalah output
akuisisi, sedangkan Nextion memakai Serial2
9600. **Tidak ditemukan pengiriman data
via Serial1 di source aktif.**
Jika kabel dipasang ke RX1/TX1
(header Mega D19/D18), firmware aktif
yang di-repo **belum siap** mengeluarkan
frame ke kanal tersebut. Hardware aktual
dan kesamaan firmware terpasang belum
dibuktikan.

## Keputusan

### Pembaruan berdasarkan konfirmasi operator

Operator mengidentifikasi **jalur FT232 USB-to-TTL
(`/dev/ttyUSB0`)** sebagai sambungan saat ini.
Jenis USART ATmega di ujung kabel dan level
tegangan sambungan langsung **belum diketahui**.
Sehingga ketidakpastian *jalur FT232 vs GPIO*
sekarang **terjawab: FT232**, tetapi bukti
elektrik dan link payload masih terbuka.
Dokumentasi repo tidak memuat skematik PCB
ATmega/FT232 yang cukup untuk menyelesaikan
audit pin dan VCCIO dari jarak jauh.

**G0: BLOCKED (butuh inspeksi operator fisik).**
**G1: kabel dinyatakan telah terpasang oleh
operator, namun belum terverifikasi aman.**
**G2/G3: NOT AUTHORIZED/NOT RUN.** Tidak
ada pembukaan ttyUSB0, loopback UART,
frame read, flash, perubahan config, atau
aksi aktuator. Checklist bukti G0:
`docs/STAGE7_UART_ATMEGA_PI5_SOP.md`.

**Penyempurnaan berdasarkan penjelasan USB langsung:**
referensi SOP G0 yang berlaku sekarang adalah
`docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`.
Pilihan USART ATmega sebagai koneksi host
**Serial/UART0 (source firmware)** sudah
ditemukan; tidak diperlukan pin Serial1.
Sambungan fisik di dalam USB-serial PCB
dan jalur daya masih memerlukan bukti.

| Gerbang | Hasil |
|---|---|
| SSH / topologi port / config Pi | **PASS read-only** |
| FT232R driver dan by-id | **PASS enumerasi** |
| GPIO14/15 ALT UART | **PASS pinmux read-only** |
| Wiring UART ATmega dan tegangan | **UNVERIFIED** |
| Pilihan jalur FT232 vs native GPIO | **FT232 dikonfirmasi operator** |
| Serial payload, baud pada kabel | **NOT TESTED** |
| Output Serial1 firmware | **NOT IMPLEMENTED dalam repo** |
| UART→Nextion, kontrol aktuator | **NOT TESTED / NO ACTION** |
| Model final | **NO-GO** |

## QA yang benar-benar dijalankan

| Pemeriksaan | Hasil |
|---|---|
| `python scripts/test_stage7_uart_preflight.py` di Windows dan Pi | **PASS**, inventarisasi GPIO/tty pasif |
| `python scripts/stage7_uart_preflight.py` langsung pada Pi | **PASS**, menghasilkan dua kandidat jalur tanpa membuka port |
| `test_stage7_pi_adapter.py`, `test_stage7_bridge.py`, `test_stage7_pi_preflight.py` | **PASS offline** |
| `test_stage6_release_gate.py`, `test_stage5_validation.py`, `test_stage4_model_benchmark.py` | **PASS** |
| Regresi Stage0–3 dan audit provenance | **PASS** |
| `test_acquisition_suite.py` | **89/89 PASS**, validitas struktur CSV lokal |
| Nextion contract | **12 halaman, 23 event PASS** |
| `pio run -e mega2560 -e nextion_test` | **2/2 SUCCESS**, tanpa flash |
| `python -m compileall -q scripts`, `git diff --check` | **PASS** |
| Live UART RX, loopback dan pin voltage | **NOT RUN** |

Tidak ada `serial.Serial.open()`, perubahan
`config.txt`, `pinctrl set`, perintah MCU,
atau gerakan aktuator dilakukan.
Pengujian benchmark/model lokal tetap tidak
menghasilkan artefak AI produksi.

**Tindak lanjut:** operator harus menyatakan
(1) memakai FT232 USB-to-TTL atau GPIO14/15,
(2) UART ATmega yang digunakan dan tegangan
logika/level shifter. Barulah SOP G0/G2
dan uji read-only dapat dilanjutkan
dengan port tepat tanpa menyentuh
firmware atau aktuator.

SOP khusus:
`docs/STAGE7_UART_ATMEGA_PI5_SOP.md`.
