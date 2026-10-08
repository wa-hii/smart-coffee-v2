# Repository Structure

Dokumen ini menjelaskan batas tanggung jawab setiap folder agar source,
dataset, hasil eksperimen, dan file lama tidak bercampur lagi.

## Canonical source

- `src/` — firmware ATmega2560 yang dibuild oleh PlatformIO.
- `include/` — header proyek dan model hasil export untuk firmware.
- `lib/` — library embedded lokal.
- `test/` — test khusus firmware/transport.
- `platformio.ini` — konfigurasi build/upload.

## Nextion

`nextion/NX4827T043_011/` adalah sumber tunggal untuk UI Nextion:

- `project/*.HMI` — source project Nextion Editor.
- `build/*.tft` — hasil compile untuk panel.
- `nextion_events/` — event Touch Release.
- asset BMP/PNG dan font.
- dokumentasi komunikasi/wiring.

Komunikasi produksi menggunakan USART2 (`Serial2`) 9600 baud:
ATmega2560 PH0/RXD2 physical pin 8 dan PH1/TXD2 physical pin 9.

## Data

- `data/raw/` — data mentah hasil akuisisi. Jangan dimodifikasi oleh pipeline
  preprocessing.
- `data/raw/*_B32.csv` — baseline akuisisi aktif: MQ3, 5 run, 25 s purging,
  5 s collecting, temperature + humidity.
- `data/raw/legacy_mq9/` — raw data historis yang header-nya masih memakai
  adc_mq9. Data dipertahankan apa adanya dan tidak ikut QA B32.
- `data/processed/` — feature dataset dan dataset siap training.
- `data/analysis/` — report/log validasi dataset.

QA akuisisi aktif:

    python scripts/validate_b32_acquisition.py
    python scripts/test_acquisition_suite.py
    python scripts/audit_b32_dataset.py

Validator pertama hanya memeriksa B32, dua perintah berikutnya mencakup B32+
dan inventory B32–B35. Candidate extractor MQ3 adalah
`scripts/extract_b32_features.py` (output terpisah di `data/processed/`).
`scripts/8_extract_features.py` adalah legacy MQ9 dan sengaja menolak
pencampuran dengan B32+; `models/random_forest_*.joblib` juga masih historis.

Roadmap dan audit canonical: `docs/00_CURRENT_STATE.md`,
`docs/01_MASTER_E2E_ROADMAP.md`, `docs/03_AI_MODEL_RESEARCH_AND_EVALUATION.md`,
`docs/04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md`,
`docs/06_INDEPENDENT_AUDIT_QA_QC.md`. Training dan deployment Pi belum DONE.

### Host autosave acquisition

- scripts/lcd_acquisition_service.py — passive listener COM5 untuk START dari Nextion.
- scripts/install_lcd_autosave.ps1 — pasang listener ke Windows Startup dan jalankan hidden menggunakan pythonw.exe.
- scripts/status_lcd_autosave.ps1 — cek process/status/log listener.
- scripts/uninstall_lcd_autosave.ps1 — hentikan listener dan hapus autostart.

COM5 hanya boleh dimiliki satu process pada satu waktu. Stop listener sebelum
firmware upload, Serial Monitor, atau manual collector.

## AI dan hasil

- `models/` — model terlatih serta metadata fitur.
- `results/` — laporan evaluasi.
- `results/plots/` — visualisasi analisis/model.
- `results/sensor-plots/` — visualisasi per sampel/sensor.

## Archive

- `archive/legacy/` — source/arsip lama yang tidak lagi canonical.
- `archive/experiments/` — notebook atau eksperimen eksploratif.

File di `archive/` tidak boleh digunakan oleh build produksi.

## Aturan penambahan file

1. Firmware baru masuk ke `src/`, bukan root.
2. CSV hasil alat masuk ke `data/raw/`.
3. Dataset hasil transformasi masuk ke `data/processed/`.
4. Plot dan laporan hasil eksperimen masuk ke `results/`.
5. File sementara, cache, dan output build tidak di-commit.
6. Eksperimen yang sudah tidak aktif dipindahkan ke `archive/`.
