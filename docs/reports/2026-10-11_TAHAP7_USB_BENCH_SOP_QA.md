# Tahap 7 — Audit SOP bench USB ATmega → Raspberry Pi 5

**Tanggal:** 11 Oktober 2026
**Status:** SOP teknis **SIAP REVIEW**, regresi offline dapat dieksekusi,
hardware **BELUM DIUJI**.

## 1. Basis bukti dan kebutuhan keselamatan

Hasil pekerjaan sebelumnya:

- SSH Tailscale `enose-v3@enose-pi5` sudah berhasil;
  Pi 5 Rev 1.1/Debian 13/Python 3.13.5 terkonfirmasi.
- Lingkungan `~/smart-coffee-stage7/.venv` berisi
  `pyserial==3.5`. Replay CSV historis **151
  frame COMPLETE_QA**, tanpa membuka serial,
  tanpa mengirim perintah MCU, hasil `N/A`.
- Firmware ATmega menerbitkan JSON-per-line
  di `Serial` **115200 8N1** dan mengirimkan
  frame selama akuisisi lima siklus:
  `25 s purging + 5 s collecting`.
  Nextion terpisah lewat `Serial2` 9600.
- Model Tahap 6 tetap **NO-GO**; serial
  read-only bukan izin mengaktifkan inferensi.

## 2. Temuan risiko utama

1. **USB VBUS/backfeed:** skematik
   daya ATmega custom, sensor/heater,
   pompa/valve dan USB bridge **belum
   diperiksa bersama operator**. Sambungan
   USB bisa membawa 5 V. **G0 harus
   diperiksa secara fisik sebelum kabel
   dipasang; jika tidak diketahui, STOP.**
2. **Reset pada DTR:** dokumentasi
   resmi Arduino Mega mengonfirmasi
   reset melalui DTR pada desain standar;
   PySerial juga memperingatkan transient
   DTR/RTS di saat `open()`. Karena
   rangkaian custom belum diperiksa,
   `dtr=False` tidak menjamin reset-free.
3. **Pemilik port:** dua program pada
   `ttyACM/ttyUSB` dapat berebut akses.
   Periksa `/dev/serial/by-id`,
   VID/PID, `readlink`, `fuser`,
   dan `ModemManager` **sebelum
   G2**, jangan mematikan layanan otomatis.
4. **Bahaya aktuator:** uji G3
   melalui Nextion dapat menjalankan
   pompa/valve. Sesi tersebut **wajib
   izin terpisah dan operator fisik**,
   tidak terotorisasi oleh G2.

SOP berisi checklist/kriteria lulus,
perintah dan mekanisme rollback:
`docs/STAGE7_USB_ATMEGA_PI_BENCH_SOP.md`.

## 3. Persiapan software yang dilakukan

- `scripts/stage7_pi_adapter.py`:
  menggunakan `exclusive=True` advisory lock
  POSIX pada Linux dan `read_until`
  dengan batas `MAX_LINE_BYTES + 1`.
  DTR/RTS disetel False **sebelum**
  pemanggilan `open()`. Program
  tidak memiliki operasi `write()`
  dalam jalur receive-only. Tidak
  mengubah state MCU atau aktuator.
- `scripts/test_stage7_pi_adapter.py`:
  menambahkan *stub serial* yang
  menegaskan `exclusive=True`,
  DTR/RTS False, batas baca frame,
  penutupan port, no-write, dan
  fail-closed pada JSON rusak.
  Mock **tidak memakai port fisik**.
- SOP terkait, roadmap, current state,
  QA notes dan changelog diperbarui
  sesuai batas hardware.

## 4. Preflight Raspberry Pi terkini (read-only)

Pemeriksaan baru melalui SSH pada 11 Oktober:

| Komponen | Hasil aktual |
|---|---|
| Device | Raspberry Pi 5 Model B Rev 1.1 |
| Kernel | `6.18.50+rpt-rpi-2712` |
| Python | 3.13.5, `aarch64` |
| `vcgencmd get_throttled` | `0x0` pada saat preflight |
| Kandidat `ttyACM/ttyUSB/by-id` | **0** (ATmega belum disambungkan) |
| User Linux | `enose-v3` dalam grup `dialout` |
| `ModemManager` | inactive saat pemeriksaan |
| Serial port opened | **Tidak** |

**Catatan:** preflight ini hanya menunjukkan keadaan
Pi; tidak mengesahkan rangkaian daya, kabel USB,
reset, jalur serial atau alur lima siklus.

## 5. Keputusan dan batas QA

| Tahap | Status |
|---|---|
| G0 verifikasi catu daya/skema USB | **NOT RUN / memerlukan operator** |
| G1 izin memasang USB data | **NOT RUN / memerlukan persetujuan** |
| G2 izin membuka port 115200 read-only | **NOT RUN / memerlukan persetujuan** |
| G3 izin satu sesi Nextion dengan aktuator | **NOT RUN / terpisah dari G2** |
| Adapter no-write / bounded read / eksklusivitas | **PASS offline mock** |
| SSH dan kondisi Pi read-only | **PASS** |
| Komunikasi fisik ATmega–Pi | **NOT TESTED** |
| AI inference / Pi→Nextion / E2E penuh | **NO-GO / NOT TESTED** |

**Kesimpulan:** dokumen SOP dan pembatasan
software siap untuk review/operator. Jangan
menandai Tahap 7 hardware sebagai PASS
hingga G0–G3 dijalankan sesuai izin,
pengamatan fisik dan bukti nyata
disimpan tanpa mengubah data mentah.

Referensi teknis:
- https://store.arduino.cc/products/arduino-mega-2560-rev3
- https://pyserial.readthedocs.io/en/latest/pyserial_api.html

## 6. Rekap regresi offline setelah penyusunan

| Pemeriksaan aktual | Hasil |
|---|---|
| `python scripts/test_stage7_pi_adapter.py` pada Windows dan Pi | **PASS**, termasuk stub PySerial tanpa port nyata |
| `python scripts/test_stage7_bridge.py` dan `test_stage7_pi_preflight.py` | **PASS** |
| `test_stage6_release_gate.py` dan regresi Tahap 0–5 | **PASS** |
| `test_acquisition_suite.py` | **89/89 PASS**, validitas struktur CSV |
| Kontrak Nextion | **PASS**, 12 halaman/23 event |
| `pio run -e mega2560 -e nextion_test` | **2/2 SUCCESS**, build saja, tidak upload |
| `python -m compileall -q scripts` dan `git diff --check` | **PASS**; peringatan LF/CRLF informasional |
| SHA256 adapter/test host dengan Raspberry Pi | **Cocok** setelah sinkronisasi |
| Pembukaan port tty/USB | **NOT RUN** |

Pada Pi sebelum pemasangan kabel:
`serial_device_candidates_not_opened=[]`,
`ModemManager=inactive`, `throttled=0x0`,
user `enose-v3` berada pada grup `dialout`.
Ini hanya preflight read-only; **bukan
bukti komunikasi serial**. Proses mock dalam
unit test tidak mengakses aktuator atau USB
dan tidak menghasilkan data latih/dummy.
