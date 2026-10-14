# Pra-onsite — penyelesaian enam P0, audit regresi, dan pembekuan software

**Tanggal:** 14 Oktober 2026 (WIB). **Scope:** software Windows, firmware
source/build offline, parser dan Pi 5 offline. Perangkat menyala tetapi
tidak ada operator onsite; tidak ada port serial dibuka, flashing,
kalibrasi, kontrol valve/pompa, atau upload Nextion.

## Hasil keenam P0

1. **Gap sampel CSV:** `validate_acquisition.py` mewajibkan urutan
   `sample_idx=1..N` untuk setiap (siklus, fase), bukan hanya count.
   Uji hapus indeks 3 ditolak, bukan PASS palsu.
2. **Urutan siklus/fase:** validator menuntut tepat urutan
   1 purging/collecting → … → 5 purging/collecting, bukan
   sekadar keberadaan tiap kelompok. Uji memindahkan fase
   dengan timestamp tetap meningkat ditolak.
3. **Sesi Windows LCD tidak boleh tercampur:**
   `lcd_acquisition_service.py` mengarsipkan sesi labeled yang
   belum selesai sebelum START lain, termasuk `ai_test`, dan
   memblokir start dengan durasi/phase tidak sesuai.
   Verifikasi total `ACQ_COMPLETE` terhadap row count sebelum
   publish final. Sensor rusak/timeout menyebabkan karantina.
4. **Framing antar-host:** `serial_wire.py` adalah satu sumber
   framing line berbatas 4096 byte dan JSON decode ketat,
   digunakan Pi adapter, autosave LCD, dan collector manual.
   Timeout tidak memotong frame; boot banner diabaikan;
   malformed/oversized frame dikarantina bila sesi aktif.
5. **Collector manual:** `3_collect_data.py` sekarang memerlukan
   `--arm-hardware` sebelum membuka port / `#start;`; setelah
   start ditransmisikan, upaya STOP dilakukan bila sesi gagal,
   termasuk ketika event ACK hilang. CSV final hanya dapat
   dipublikasikan jika ACQ_COMPLETE dan validator penuh PASS;
   otherwise hasil di `data/raw/incomplete/` dengan UUID,
   tidak overwrite. Pengujian disarmed PASS tanpa serial open.
6. **Identitas firmware:** `src/main.cpp` akan mengirim startup
   `FW_HELLO protocol=legacy-json.v1, build_id=p0-freeze-20261014`.
   Pi adapter mencatat `MATCHED`, `INCOMPATIBLE`, `NOT_OBSERVED`
   dengan fixed contract, tanpa menyimpan build id asing.
   **Kode boot baru belum di-flash; versi binary MCU masih
   belum terbukti cocok.** Itu gate onsite yang tidak dapat
   ditutup melalui audit software.

## Pengecualian historis secara eksplisit

89 CSV B32+ diperiksa. 88 lolos validator baru;
`L-CAW_B34.csv` (SHA256 dipin pada manifest) adalah
**KNOWN_INVALID_EXCLUDED**: indeks 8 purging siklus 1
hilang, dan file itu sudah dikecualikan dari cohort kopi
sebagai udara bersih. File asli tidak diubah dan tidak
boleh dipromosikan sebagai data valid. 0 kegagalan
dataset tak terduga. `stage5_validation` kini mengizinkan
alasan penolakan muncul lebih awal dari validator baru;
tidak ada pelonggaran QA untuk data baru.

## Audit regresi independen terhadap perubahan

Tes adversarial terpisah `test_preonsite_p0_freeze.py`
membangun fixture dari nol pada direktori sementara dan
memastikan: gap dan urutan fase ditolak, pergantian mode
menutup sesi tanpa label leakage, START timing salah
ditolak, malformed/oversized/timeout UART ditangani,
FW_HELLO kompatibilitas menolak build asing, dan collector
manual tanpa `--arm-hardware` berhenti sebelum I/O.

Regresi proyek yang dieksekusi di Windows:

- `test_acquisition_suite.py` — PASS dengan 88 VALID,
  1 KNOWN_INVALID_EXCLUDED dan 0 unanticipated failure.
- `test_stage0_contract.py` sampai `test_stage9_passive_readiness.py`
  yang relevan, termasuk Stage2/3/4/5/6/7/8 — PASS.
- `test_preonsite_p0_freeze.py` — PASS.
- `pio run -e mega2560 -e nextion_test` — dua build SUCCESS.
- Nextion source/HMI verifier — 12 pages / 23 events PASS.
- `python -m compileall -q scripts` dan `git diff --check` — PASS.

Pi, pada repo `/home/enose-v3/smart-coffee-stage7`:
`serial_wire.py` dan `stage7_pi_adapter.py` disalin
tanpa membuka tty; `test_stage7_pi_adapter.py`,
`test_stage7_bridge.py`, `test_stage8_transport_integration.py`,
`test_stage8_offline_e2e.py` PASS. Pi tetap
mendeteksi FT232R `0403:6001 A10KMM3S`, `/dev/ttyUSB0`,
`throttled=0x0`. Ini **bukan** test physical acquisition.

## Release candidate / software freeze

**Git tag setelah commit:** `pre-onsite-software-2026-10-14-rc1`.
Manifest file: `docs/releases/2026-10-14_pre-onsite-rc1.json`.
Manifest menyimpan SHA256 file kritis dan firmware `.hex`
hasil build Windows. `.hex` berada di build lokal yang
diabaikan Git; source di Git tag adalah acuan rebuild.
Commit/tag menentukan snapshot; binary MCU belum diprogram.

Tidak mencampur perubahan user `platformio.ini` (COM5),
CSV untracked, atau eksperimen `stage4_lobo_v1`.

## Hal yang masih menghalangi go-live hardware

- Periksa G0 kelistrikan USB-VBUS/backfeed dan wiring PCB,
  serta kecocokan firmware yang **benar-benar** di-flash.
- Saat onsite, gunakan prosedur backup/pemulihan dan
  supervision untuk satu G3 lima siklus dengan evidence baru.
- Jangan menganggap identitas udev USB atau complete offline
  QA sebagai bukti timing, kualitas sensor, keamanan pompa/
  valve, atau hasil di Nextion fisik.
- Model AI tetap **NO_GO**, semua AI TEST `N/A`.

**Definisi pembekuan:** source/testing snapshot dibekukan
untuk pemeriksaan bench berikutnya. Jika ada perubahan kode
setelah tag, buat RC baru dan ulangi seluruh regresi.
