# Re-audit independen P0 — Smart Coffee E-Nose v2 pasca-reboot Pi

**Tanggal:** 13 Oktober 2026, pemeriksaan 20:09–20:12 WIB.
**Workspace:** branch `wahyu`, HEAD awal `528cb9f` (sudah
memuat hasil reboot operator). **Lingkup:** Git, firmware source,
listener, checksum Pi, log kernel, tes offline. **Tidak membuka
serial, mengirim perintah MCU, mengubah catu, atau melakukan G3**.

## 1. Current state (bukti primer)

| Domain | Temuan dan status |
|---|---|
| Git | `wahyu` tracking `origin/wahyu` tanpa ahead/behind yang dilaporkan; `platformio.ini` COM5 masih modified, 3 CSV raw dan `results/stage4_lobo_v1/` untracked — dipertahankan |
| Boot Pi | `uptime -s`: `2026-10-13 19:49:19`; operator telah reboot Pi secara lokal |
| USB enumerasi | `lsusb -d 0403:6001`: FT232R Bus 003 Device 002; serial `A10KMM3S`; by-id → `/dev/ttyUSB0`; `ftdi_sio` aktif. Cek 20:09 dan 20:12 WIB konsisten |
| Host port/power | `fuser /dev/ttyUSB0` kosong saat preflight; serial-getty dan ModemManager inactive; `vcgencmd get_throttled=0x0`. Log kernel boot baru memuat attach 19:49:22, tidak memuat `USB disconnect` saat dicek |
| G2 historis | Baca FT232R read-only 12s menerima **4.313 byte, 33 baris**, 0 sensor aktif; PASS transport RX **terbatas** |
| G3 historis | Run02: **52.224 byte, 203 baris lengkap, 189 JSON valid tetapi bukan event/sensor yang dikenali**; `ACQ_START=0`, `ACQ_COMPLETE=0`, sensor tervalidasi=0, `NOT_STARTED`. Operator mengamati lima siklus Nextion lengkap. **INCONCLUSIVE** |
| Release AI | `model_promotion_allowed=false`, runtime AI TEST `N/A`; **NO-GO** |

Checksum `stage7_pi_adapter.py` pada Windows **sama dengan Pi**:
`5628304575b3d28d2234106b5f198e8670614b82301174206429df2b`.
File asli Pi `results/pi_stage7/custom_pcb_usb_g3_nextion_run02.json`
masih memiliki SHA256:
`9a6733326df5f941110433dc888bb25dede37a10ec8df7db6070ea461a6dec20`.
Tidak mengedit evidence asli.

## 2. Analisis akar masalah — fakta vs hipotesis

1. **FT232R disconnect 19:24:44 (fakta historis):** `ftdi_set_termios`
   gagal dan kernel mencatat `usb 3-1: USB disconnect` saat
   upaya `serial-readonly` 15s. `lsusb` lalu kehilangan FT232R.
   **Reboot operator terbukti memulihkan enumerasi** pukul 19:49:22.
   Kedua fakta tersebut tidak menetapkan penyebab awal. Kandidat
   yang belum dibedakan: kabel/konektor, jalur VBUS/GND, rail FT232R,
   reset/perilaku chip, host USB/hub/driver, atau interaksi DTR/open.
   `throttled=0x0` hanya bukti status daya Pi, bukan pengukuran PCB.
2. **G3 Run01 (fakta):** listener lama bisa menganggap fragmen
   `read_until()` timeout sebagai frame JSON; bug ini telah
   direproduksi lalu diperbaiki oleh `SerialLineFramer`.
3. **G3 Run02 (fakta):** sesudah patch, Pi menerima 189 JSON valid
   tetapi tidak mengenali event START/COMPLETE maupun sensor. Source
   `src/main.cpp` menerbitkan `ACQ_START`, `PHASE_CHANGE`, dan
   `ACQ_COMPLETE`, sementara `src/sensor.cpp::printJsonData()`
   memiliki `phase`, `cycle`, `sample_idx`, `timestamp`, sepuluh
   `adc_*`, temperatur dan kelembapan. **Kesamaan source dengan
   firmware yang benar-benar terpasang belum dibuktikan**.
   Hipotesis: protokol firmware terpasang berbeda, jenis JSON yang
   dibaca bukan stream sesi, atau mismatch lain. Tidak tersedia
   field names dari 189 JSON historis; jangan menyebutnya sampel.

## 3. QA/QC yang dijalankan saat audit ini

| Uji | Windows | Pi 5 |
|---|---|---|
| `test_stage7_bridge.py` | PASS | PASS |
| `test_stage7_pi_adapter.py` | PASS | PASS |
| `test_stage7_usb_readonly_probe.py` | PASS | PASS |
| `test_stage8_offline_e2e.py` | PASS | PASS |
| `test_stage7_pi_preflight.py` | PASS | NOT RUN |
| `pio run -e mega2560 -e nextion_test` | 2 build SUCCESS | NOT RUN |
| `verify_nextion_atmega_contract.py` | PASS (12 halaman, 23 event) | NOT RUN |
| `test_stage1_firmware_contract.py` | PASS | NOT RUN |
| `test_stage6_release_gate.py` | PASS | NOT RUN |
| `python -m compileall -q scripts` | PASS | NOT RUN |

Pemeriksa HMI mengeluarkan peringatan deprecation Pillow
`Image.getdata`, bukan kegagalan kontrak. Semua uji di atas
**offline**, bukan verifikasi firmware terpasang/arus listrik/aktuator.

## 4. Prioritas dan syarat transisi

- **P0 — PASS terbatas pada enumerasi:** pertahankan status
  perangkat dan pantau log pasif bila dibutuhkan. Jangan
  menganggap dua cek enumerasi sebagai uji stabilitas UART.
- **P1 — Butuh persetujuan baru:** setelah operator memastikan
  alat IDLE, kabel dan catu aman, serta berada di lokasi,
  lakukan paling banyak satu capture USB **read-only pendek**,
  dengan `other_json_key_signatures` tanpa raw nilai, nama
  evidence baru, dan kontrol risiko DTR/USB disconnect. Jika
  port kembali hilang, **stop** dan investigasi fisik.
- **P2 — Setelah diagnosis P1:** cocokkan key aktual dengan
  source/perangkat, perbaiki mismatch minimal bila terbukti,
  tes negatif/regresi offline; barulah satu G3 dengan izin
  khusus dan kriteria `COMPLETE_QA`, lima siklus, event lengkap,
  indeks/timestamp konsisten, jumlah sampel dan varians tercatat.
- **AI:** lanjutkan model hanya sesudah gate dataset/provenance,
  deteksi udara bersih/unknown, dan validasi prospektif; tetap `N/A`.

**Keputusan akhir:** **USB ENUMERATION RESTORED / PASS pasif**;
**USB serial-open stability NOT RUN pasca-reboot**;
**G3 INCONCLUSIVE**; **AI deployment NO-GO**.
