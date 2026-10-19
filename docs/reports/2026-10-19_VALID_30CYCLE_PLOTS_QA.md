# Plot 30 siklus — valid audited files, 19 Oktober 2026

## Data scope

- Folder: `data/raw/data 30 siklus/HASIL_AUDIT_30_SIKLUS_20261019/01_VALID_30_SIKLUS/`.
- `audit_manifest.json` mengklasifikasi 38 valid dari 69 file CSV input.
- Script memverifikasi SHA256 semua file input valid terhadap manifest sebelum plotting.
- 31 file kategori incomplete, duplikat, metadata salah, baseline, dan anomali fase/durasi TIDAK dipakai.

## Hasil plot

Hasil utama lokal: `results/plots_30_siklus_valid_audit_20261019/`.

| Family | Directory | PNG | Group definition |
|---|---|---:|---|
| 01 | `01_sensor_per_batch` | 380 | 38 recordings × 10 ADC sensors |
| 02 | `02_roast_same_origin_same_batch` | 60 | 6 shared origin+batch with 2–3 roast levels × 10 sensors |
| 03 | `03_same_origin_roast_cross_batch` | 110 | 11 origin+roast groupings with >=2 different batches × 10 sensors |
| 04 | `04_roast_same_origin_batch_t0` | 60 | the same 6 cross-roast groups, each 10 sensors with ADC(t)−ADC(t0) |
| **Total** | | **610** | |

- t0 = **purging siklus pertama, sample_idx 25**, yakni pembacaan purging terakhir tepat sebelum sampel collecting pertama (t26). Setiap kurva memiliki anchor miliknya sendiri.
- Time axis menggunakan timestamp asli yang direlatifkan terhadap awal rekaman atau t0; 30 cycles retained, no smoothing or interpolation.
- Warna roasting berbeda: Light biru, Medium oranye, Dark merah.
- `M-TEM_B62.csv` dan `M-TEM_B62_20261019_175906.csv` adalah dua rekaman valid berbeda tetapi batch metadata sama; keduanya ditandai dengan nama file penuh dalam grafik cross-batch. Jangan anggap kedua file sebagai batch independen hanya karena nama file berbeda.
- Semua grafik per sensor memakai 10 kolom ADC; suhu dan kelembapan tidak diplot pada paket ini.

## File navigasi dan audit

- `GALERI_GRAFIK.html`: filter jenis grafik, grup, sensor, kata kunci; membuka PNG dari disk tanpa koneksi internet.
- `README.md`: metodologi dan daftar grup.
- `summary.json`: total grafik dan definisi sumbu/normalisasi.
- `plot_index.csv`: referensi 610 PNG terhadap CSV input.
- `input_provenance.csv`: referensi 38 CSV dan SHA256 yang cocok.
- `series_index.csv`: statistik ADC dan baseline t0 setiap kurva.
- `comparison_groups.csv`: anggota masing-masing perbandingan.

## QA hasil

- Output 610 file PNG, 610 entri di `plot_index.csv`, semua path unik, tidak ada yang hilang atau berukuran <10 KB.
- SHA256 38 input pada `input_provenance.csv` diverifikasi sama dengan file CSV yang digunakan.
- Smoke test dua level roast `L-GAW_B60` vs `M-GAW_B60` sukses menghasilkan 40 PNG dalam folder temporary.
- Unit test `test_plot_valid_30_siklus_audit.py`: memastikan 38 input, 6 roast groups, 11 cross-batch groups, anchor purging ke-25 dan posisi collecting setelahnya.
- 69 CSV sumber dan 69 copy klasifikasi tidak diubah. Seluruh visualisasi berada di folder baru `results/`.

## Limitasi ilmiah

Chart overlay antar-rekaman adalah analisis eksploratif. Provenance instrumen fisik dan kesamaan spesimen antar alat belum terbukti. Belum ada normalisasi antar-alat, inferensi model, atau uji signifikansi. `t0` bukan baseline kalibrasi clean-air eksternal; ia adalah nilai ADC purging akhir siklus pertama pada file yang sama.
