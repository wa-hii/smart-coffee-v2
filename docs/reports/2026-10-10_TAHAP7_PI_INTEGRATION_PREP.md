# Tahap 7 — Persiapan Pi 5 ↔ ATmega2560 (non-invasif)

**Tanggal dokumentasi:** 10 Oktober 2026.

**Konfirmasi operator:** ATmega **tidak terhubung ke COM5**.
Raspberry Pi 5 dinyalakan untuk siap akses remote.
Tidak ada identitas SSH (alamat/user/fingerprint) atau bukti
komunikasi USB/UART Pi–ATmega yang dapat diverifikasi.

## Temuan audit dan desain

1. Perangkat aktif lama: ATmega `Serial` USB **115200 baud**
   mengirim JSON per baris; Nextion `Serial2` **9600 baud**.
   Data dikirim dari MCU (read-only bridge belum membalas).
2. `Serial1` ATmega belum diaktifkan untuk Pi; pin TX D18/RX D19
   memerlukan pemeriksaan skematik custom PCB dan penerjemah
   level tegangan UART TTL **5→3,3 V**. Pi 5 UART utama default
   pada debug header dedicated, sehingga asumsi GPIO14/15
   langsung aktif bisa salah.
3. Source firmware `INFERENCE` default `N/A` dan Nextion
   `pResult` masih diperbarui oleh ATmega lokal. Model
   tahap 6 tidak lulus; **tidak ada server inference siap produksi**.
4. Risiko kompatibilitas: payload serial produksi
   **belum membawa session_id / message_seq**, belum mendukung
   ACK/NACK atau handler hasil dari Pi. Dokumentasi usulan
   v1 tidak sama dengan kode produksi sekarang.
   Teks Nextion seperti `LOCAL`/`LOCAL READY` berasal
   dari konstanta firmware, **bukan indikator Raspberry Pi
   tersambung**.

## Implementasi Tahap 7 (offline)

- `scripts/stage7_bridge.py` — adapter stateful baca-saja
  untuk *firmware-shaped* JSON legacy, session ID host, satu
  hasil terminal/sesi, validasi 5 siklus, mode AI_TEST
  tanpa label, output AI N/A, fail-closed apabila terputus.
  Tidak membuka serial fisik atau menggunakan model.
- `V1SequenceGuard` — kontrak envelope v1, deteksi
  replay/duplicate/out-of-order, ACK/NACK **mock** dan
  penolakan model/result `light/medium/dark` yang
  tidak disetujui. **Firmware belum memakai v1.**
- `scripts/stage7_pi_preflight.py` — cek host/read-only
  untuk dijalankan lewat SSH pada Pi setelah user memberikan
  hostname/alamat dan akun, tanpa serial/GPIO writes.
- `scripts/test_stage7_bridge.py` dan
  `scripts/test_stage7_pi_preflight.py` — pengujian
  positif/negatif, replay satu CSV asli tanpa perubahan
  raw, ketidakcocokan label, abort, duplicate,
  invalid JSON dan stale session.
- Output `results/stage7_offline_v1/replay_d_gaw_b33.json`
  dibuat dari file **nyata** `D-GAW_B33.csv`, hasilnya
  `quality=COMPLETE_QA` tetapi `status=N/A`,
  `sent_to_atmega=false`. Ini **simulasi protokol**
  bukan bukti Pi terhubung.

## Status gerbang

| Cakupan | Status |
|---|---|
| Audit protokol dan arsitektur | **PASS (source + dokumentasi)** |
| Adapter legacy parser/state machine | **PASS offline**, setelah regresi akhir |
| Envelope v1, ACK/NACK | **PASS mock only** |
| Pi OS + identitas Pi 5 via SSH | **NOT TESTED — SSH target tidak tersedia** |
| USB/Serial1 koneksi Pi ke ATmega | **NOT TESTED — ATmega belum tersambung** |
| Firmware v1 dan Pi→Nextion handler | **NOT IMPLEMENTED** |
| Aktuator, UART GPIO voltage, kalibrasi | **NO ACTION** |
| AI model dan unknown untuk deployment | **NO-GO Tahap 6** |

Rujukan SOP yang siap dipakai operator:
`docs/STAGE7_PI_REMOTE_AND_SERIAL_SOP.md`.
QA build dan regresi lengkap dicatat setelah pelaksanaan.

**Keputusan:** Tahap 7 software/mock dapat dituntaskan;
**verifikasi remote Pi, transport nyata dan komunikasi dua
arah tetap tertunda**. Lanjut Tahap 8 offline mock setelah
gerbang desain sesuai, bukan langsung Tahap 9.

## QA akhir yang benar-benar dijalankan

| Pemeriksaan | Hasil |
|---|---|
| `python scripts/test_stage7_bridge.py` | **PASS**, parser malformed/duplicate/NaN, V1 ACK/NACK mock, phase/order/sequence, timeout/abort, AI_TEST N/A, replay data asli |
| `python scripts/test_stage7_pi_preflight.py` | **PASS pada PC** (uji sifat read-only; **bukan** pemeriksaan Pi nyata) |
| `python scripts/stage7_bridge.py --replay-csv data/raw/D-GAW_B33.csv --output results/stage7_offline_v1/replay_d_gaw_b33.json` | **PASS**, `quality=COMPLETE_QA`, `status=N/A`, `sent_to_atmega=false` |
| Tahap 6, 5, 4, 3, 2 serta regresi bench Tahap 1 / kontrak Tahap 0 | **PASS** |
| Validator `test_acquisition_suite.py` | **89/89 PASS** skema umum |
| Nextion HMI contract | **PASS**, 12 halaman, 23 event, Serial2 9600 |
| PlatformIO `mega2560` + `nextion_test` | **2/2 SUCCESS**, **tanpa upload** |
| `compileall -q scripts` / `git diff --check` | **PASS** |
| Ketersediaan klien SSH Windows (`where.exe ssh`) | **PASS**: OpenSSH tersedia di host, **bukan** bukti Pi dapat diakses |

**NOT RUN:** SSH live Pi (target tidak tersedia),
port serial fisik Pi–ATmega, UART voltage/baud, kamera/Nextion
sebagai tampilan hasil Pi, pengujian aktuator.
Perubahan lokal `platformio.ini` dan seluruh CSV raw pengguna
dipertahankan.
