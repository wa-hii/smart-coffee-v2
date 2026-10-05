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
- `data/processed/` — feature dataset dan dataset siap training.
- `data/analysis/` — report/log validasi dataset.

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
