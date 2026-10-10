# Tahap 7 — Venv Python dan adapter serial Pi 5 via Tailscale SSH

**Tanggal:** 11 Oktober 2026
**Target terverifikasi:** `enose-v3@enose-pi5`, Tailscale
`100.103.211.125`, Raspberry Pi 5 Model B Rev 1.1.

## Ruang lingkup, SOP dan kondisi perangkat

User mengizinkan pemasangan Python virtual environment di
Raspberry Pi melalui SSH dan pengujian offline dengan replay
CSV data asli. **ATmega2560 belum dihubungkan** ke PC maupun
Pi. Tidak boleh membuka COM5/ttyACM/ttyUSB, mengontrol GPIO,
mem-flash firmware, menyentuh Nextion, mengubah layanan
OS, atau menjalankan inferensi yang belum disetujui.

**SSH aktual PASS**, `StrictHostKeyChecking=yes` dan
`BatchMode=yes`. Pemeriksaan non-invasif sebelumnya:
Debian GNU/Linux 13 (trixie), Python 3.13.5 aarch64,
RAM tersedia ~7,4 GiB, storage tersedia ~18 GiB,
`vcgencmd get_throttled = 0x0`, CPU ~48,3°C.
Itu snapshot waktu pemeriksaan, bukan pengukuran
berkelanjutan. SSH dan Tailscale service active.
`/dev/ttyACM*` dan `/dev/ttyUSB*` tidak ditemukan.

## Implementasi pada Pi

Seluruh penulisan dilakukan **di direktori baru milik
user non-root**:

```text
/home/enose-v3/smart-coffee-stage7/
  .venv/                                   # Python 3.13, pyserial 3.5
  scripts/
    acquisition_schema.py
    stage6_release_gate.py
    stage7_bridge.py
    stage7_pi_adapter.py
    stage7_pi_preflight.py
    test_stage7_bridge.py
    test_stage7_pi_adapter.py
    test_stage7_pi_preflight.py
    requirements-stage7-pi.txt
  data/raw/
    D-GAW_B33.csv                          # salinan asli untuk replay
  results/
    stage5_validation_v1/summary.json
    external_coffee_enose_v1/summary.json
    pi_stage7/replay_d_gaw_b33_v1.json
```

Venv dibuat dengan `python3 -m venv` dan
`pyserial==3.5` dipasang **hanya ke venv**
(`pip freeze` menunjukkan satu paket). Tidak ada
instalasi global, tidak ada service systemd baru,
tidak ada paket model/pandas/sklearn yang diperlukan.
File source Python, ringkasan Stage 5/eksternal,
dan satu CSV asli dikirim via SCP melalui SSH.
Gate Stage 6 diverifikasi di Pi pada setiap run
(`NO_GO_PENDING_LOCAL_VALIDATION`).

## QA dan bukti hasil pada Pi nyata

| QA | Hasil |
|---|---|
| SSH login pengguna `enose-v3` | PASS |
| Model Pi 5, arsitektur, kernel, OS, Python | PASS |
| Venv dibuat dan `pyserial==3.5` terpasang | PASS |
| `test_stage7_bridge.py` dijalankan di Pi | PASS |
| `test_stage7_pi_adapter.py` dijalankan di Pi | PASS |
| `test_stage7_pi_preflight.py` dijalankan di Pi | PASS |
| Replay `D-GAW_B33.csv` di Pi | `COMPLETE_QA`, 151 sampel, hasil `N/A` |
| Hash SHA256 CSV pada host vs Pi | Cocok persis |
| Hash SHA256 adapter host vs Pi saat deployment awal | Cocok persis |
| Port serial fisik | **NOT RUN**, tidak ada ttyACM/ttyUSB |
| Running service/background process permanen | **Tidak ada** |
| Model AI, perintah aktuator, balasan ke MCU | **Tidak digunakan** |

**SHA256 file CSV asli** (host dan Pi sama):
`d5e690f538a3967e2d07ded64903d284a348c1988bcc331a380dd50b0a8be819`.

**SHA256 adapter versi final host dan Pi:**
`2bd51621dcdaef4717f70abae48fe9ece63140b3c1d6c58a8b99cc7e4a38cb6b`.
Runner versi final menolak penimpaan output dan
penulisan ke raw **sebelum** kemungkinan port serial
dibuka. Perbaikan kalimat audit replay sudah
disinkronkan ke Pi dan replay dijalankan ulang.

Replay membentuk frame bertipe firmware dari baris
CSV sebenarnya, dengan fase, indeks dan timestamp
MCU tanpa memakai label roast/origin sebagai input AI.
Hasil v1: `sensor_samples=151`, `nominal_150_samples=false`,
`quality=COMPLETE_QA`, `status=N/A`,
`reason=five_cycles_checked_no_approved_model`,
`hardware_serial_opened=false`, `sent_to_atmega=false`,
`actuator_commands_sent=0`. Ini lulus **toleransi
protokol replay**, **bukan** verifikasi timing fisik
150 sampel tepat ataupun serial port asli.

Artefak ringkas tersalin ke
`results/stage7_pi_remote_v1/replay_d_gaw_b33.json`
di repo, tanpa menduplikasi CSV mentah pengguna.

## Cara menjalankan dan menghentikan

Pada komputer Windows:

```powershell
ssh enose-v3@enose-pi5
```

Di Raspberry Pi:

```bash
cd ~/smart-coffee-stage7
.venv/bin/python scripts/test_stage7_bridge.py
.venv/bin/python scripts/test_stage7_pi_adapter.py
.venv/bin/python scripts/test_stage7_pi_preflight.py

# Replay satu kali; gunakan nama keluaran baru, tidak menimpa hasil sebelumnya
.venv/bin/python scripts/stage7_pi_adapter.py replay-csv \
  --input data/raw/D-GAW_B33.csv \
  --output results/pi_stage7/replay_d_gaw_b33_v2.json
```

Berhenti: proses **otomatis selesai** sesudah satu
replay. Bila dijalankan manual dan perlu dihentikan,
tekan `Ctrl+C`; tidak ada service untuk dimatikan.
Jangan memberi flag `serial-readonly` saat ATmega
belum disambungkan/diizinkan: sekalipun hanya membaca,
membuka port USB dapat me-reset MCU melalui DTR.
Jangan mengirim perintah ke aktuator.

## Keputusan dan blocker

**Tahap 7 remote + isolated Python environment + offline
real CSV replay: PASS.** Tahap 7 end-to-end hardware
masih **NOT TESTED**. Kebutuhan selanjutnya:

### QA regresi lintas repo setelah deploy

| Pengujian tambahan di Windows/DevSpace | Hasil |
|---|---|
| `test_stage7_pi_adapter.py`, `test_stage7_bridge.py`, `test_stage7_pi_preflight.py` | **PASS** |
| `test_stage6_release_gate.py`, `test_stage5_validation.py`, `test_stage4_model_benchmark.py` | **PASS** |
| `test_stage3_feature_pipeline.py`, `test_stage2_dataset_audit.py`, `test_stage2_plot_provenance.py` | **PASS** |
| `test_bench_stage1_passive_qa.py`, `test_stage0_contract.py`, `test_stage1_firmware_contract.py` | **PASS** |
| `test_acquisition_suite.py` | **89/89 CSV valid secara struktur** |
| Verifier Nextion | **12 halaman/23 event PASS** |
| `pio run -e mega2560 -e nextion_test` | **2/2 SUCCESS, tidak di-upload** |
| `python -m compileall -q scripts`, `git diff --check` | **PASS** (peringatan LF/CRLF informasional) |

1. Tentukan SOP waktu menyambungkan USB ATmega→Pi,
   pastikan satu pemilik port dan antisipasi auto-reset.
2. Periksa firmware menghasilkan JSON real-time dan
   nilai baud 115200 di Pi (serial read-only dengan
   persetujuan bench spesifik).
3. Sepakati protokol sesi/ACK/NACK dua arah dan
   handler hasil Pi→Nextion; kode v1 saat ini baru mock.
4. Model roast dan unknown tetap **NO-GO** sampai
   validasi prospektif/coffee presence berhasil.
