# Struktur Repositori Smart Coffee E-Nose v2

Dokumen ini menjelaskan batas tanggung jawab setiap folder agar kode sumber,
dataset, hasil eksperimen, dan file lama tidak bercampur lagi.

## Kode sumber utama

- `src/` — firmware ATmega2560 yang dikompilasi melalui PlatformIO.
- `include/` — berkas header proyek dan model hasil ekspor untuk firmware.
- `lib/` — pustaka embedded lokal.
- `test/` — pengujian firmware dan komunikasi.
- `platformio.ini` — konfigurasi kompilasi dan pengunggahan firmware.

## Antarmuka Nextion

`nextion/NX4827T043_011/` adalah sumber utama untuk antarmuka Nextion:

- `project/*.HMI` — sumber proyek yang dapat disunting di Nextion Editor.
- `build/*.tft` — hasil kompilasi untuk layar.
- `nextion_events/` — event sentuhan yang dilepas (Touch Release).
- aset gambar BMP/PNG dan huruf.
- dokumentasi komunikasi dan pengkabelan.

Komunikasi produksi menggunakan USART2 (`Serial2`) 9600 baud:
ATmega2560 PH0/RXD2 pada pin fisik IC 8 dan PH1/TXD2 pada pin fisik IC 9.

## Dataset dan hasil pemrosesan

- `data/raw/` — data mentah hasil akuisisi. Jangan dimodifikasi oleh alur
  prapemrosesan.
- `data/raw/*_B32.csv` — acuan akuisisi aktif: MQ3, 5 siklus, 25 detik purging,
  5 detik collecting, suhu dan kelembapan.
- `data/raw/legacy_mq9/` — data mentah historis yang nama kolomnya masih memakai
  adc_mq9. Data dipertahankan apa adanya dan tidak ikut QA B32.
- `data/processed/` — dataset fitur dan dataset siap pelatihan.
- `data/analysis/` — laporan serta catatan validasi dataset.

Perintah pemeriksaan kualitas akuisisi:

    python scripts/validate_b32_acquisition.py
    python scripts/test_acquisition_suite.py
    python scripts/audit_b32_dataset.py

Validator pertama hanya memeriksa B32, sedangkan dua perintah berikutnya mencakup B32+
serta inventaris B32–B35. Ekstraktor kandidat MQ3 adalah
`scripts/extract_b32_features.py` (hasil terpisah di `data/processed/`).
`scripts/8_extract_features.py` merupakan skrip historis MQ9 dan sengaja menolak
pencampuran dengan B32+; `models/random_forest_*.joblib` juga masih historis.

Peta jalan dan audit utama: `docs/00_CURRENT_STATE.md`,
`docs/01_MASTER_E2E_ROADMAP.md`, `docs/03_AI_MODEL_RESEARCH_AND_EVALUATION.md`,
`docs/04_NEXTION_ATMEGA_RASPI_ARCHITECTURE.md`,
`docs/06_INDEPENDENT_AUDIT_QA_QC.md`. Pelatihan model dan pemasangan sistem inferensi pada Raspberry Pi belum selesai.

### Layanan penyimpanan akuisisi otomatis pada komputer

- scripts/lcd_acquisition_service.py — penerima data COM5 pasif untuk proses yang dimulai melalui Nextion.
- scripts/install_lcd_autosave.ps1 — pasang penerima data agar berjalan otomatis saat Windows dinyalakan, tanpa menampilkan jendela.
- scripts/status_lcd_autosave.ps1 — periksa proses, status, dan catatan layanan akuisisi.
- scripts/uninstall_lcd_autosave.ps1 — hentikan layanan penerima dan nonaktifkan proses otomatis saat Windows dinyalakan.

COM5 hanya boleh dimiliki satu proses pada satu waktu. Hentikan layanan
penerima sebelum mengunggah firmware, membuka Serial Monitor, atau menjalankan
pengumpul data manual.

## Model AI dan hasil eksperimen

- `models/` — model terlatih serta metadata fitur.
- `results/` — laporan evaluasi.
- `results/plots/` — visualisasi analisis/model.
- `results/sensor-plots/` — visualisasi per sampel/sensor.

## Arsip

- `archive/legacy/` — kode sumber atau arsip lama yang tidak lagi menjadi acuan utama.
- `archive/experiments/` — buku catatan komputasi atau eksperimen eksploratif.

File dalam `archive/` tidak boleh digunakan pada kompilasi firmware produksi tanpa pemeriksaan.

## Aturan penambahan file

1. Firmware baru masuk ke `src/`, bukan direktori utama.
2. CSV hasil alat masuk ke `data/raw/`.
3. Dataset hasil transformasi masuk ke `data/processed/`.
4. Grafik dan laporan hasil eksperimen masuk ke `results/`.
5. File sementara, cache, dan hasil kompilasi tidak dimasukkan ke commit.
6. Eksperimen yang sudah tidak aktif dipindahkan ke `archive/`.
