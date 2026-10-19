# Plot 30 siklus — hanya dataset VALID hasil audit

Input: `D:\ENOSE\smart-coffee-v2-hardware\smart-coffee-v2-hardware\data\raw\data 30 siklus\HASIL_AUDIT_30_SIKLUS_20261019` (salinan 01_VALID_30_SIKLUS, SHA256 diperiksa)
Dataset: **38** / 69 diaudit; grafik: **610**.

## Empat jenis grafik

- `01_sensor_per_batch/`: **380** PNG (10 ADC per grup)
- `02_roast_same_origin_same_batch/`: **60** PNG (10 ADC per grup)
- `03_same_origin_roast_cross_batch/`: **110** PNG (10 ADC per grup)
- `04_roast_same_origin_batch_t0/`: **60** PNG (10 ADC per grup)

## Metode dan interpretasi
- Setiap dataset valid: 900 baris, 30 siklus, 25 purging dan 5 collecting per siklus, diperiksa melalui laporan audit dan SHA256.
- Sumbu X: detik dihitung dari `timestamp` firmware masing-masing CSV, **bukan tanggal absolut**.
- Area jingga samar: interval collecting nominal 5 detik tiap 30 detik. Tanpa smoothing/interpolasi/resampling.
- Warna Light=biru, Medium=oranye, Dark=merah pada grafik perbandingan roasting.
- Normalisasi: nilai sensor dikurangi ADC di akhir purging siklus pertama (indeks sampel 25). Sampel collecting pertama adalah **t26** setelah 25 detik purging. Titik acuan ditandai t0=0.
- Semua 900 sampel dipertahankan dalam grafik normalisasi; 24 sampel purging awal tampak pada waktu negatif.
- Jika dua roast tidak tersedia dalam origin dan batch sama, **tidak dibuat grafik roast kosong** dan tidak dipaksakan mencampur batch.
- Jika satu roast pada satu origin hanya memiliki satu batch, tidak dipaksakan membuat cross-batch.
- Rekaman ulang `M-TEM_B62.csv` dan `M-TEM_B62_20261019_175906.csv` adalah dua CSV berbeda dan keduanya dilabel jelas pada cross-batch; belum terbukti spesimen/alat sama.
- Hasil adalah grafik eksploratif. Identitas alat fisik / kesetaraan spesimen belum diverifikasi lintas CSV.

## Indeks dan provenance

- `plot_index.csv`: semua plot dan input CSV masing-masing.
- `input_provenance.csv`: SHA256, metadata, waktu t0 dari 38 file.
- `series_index.csv`: ringkasan ADC dan titik t0 per kurva.
- `comparison_groups.csv`: grup perbandingan yang benar-benar tersedia.

## Grup roast dalam origin dan batch sama

- CAT B62: L-CAT_B62.csv, M-CAT_B62.csv
- CAT B63: L-CAT_B63.csv, M-CAT_B63.csv
- GAW B60: L-GAW_B60.csv, M-GAW_B60.csv
- GAW B61: L-GAW_B61.csv, M-GAW_B61.csv
- TOR B63: L-TOR_B63.csv, M-TOR_B63.csv, D-TOR_B63.csv
- TOR B65: L-TOR_B65.csv, M-TOR_B65.csv

## Grup cross-batch dengan origin dan roast sama

- CAT Light: L-CAT_B60.csv, L-CAT_B62.csv, L-CAT_B63.csv
- CAT Medium: M-CAT_B62.csv, M-CAT_B63.csv, M-CAT_B64.csv
- GAW Light: L-GAW_B60.csv, L-GAW_B61.csv
- GAW Medium: M-GAW_B60.csv, M-GAW_B61.csv
- GAY Light: L-GAY_B62.csv, L-GAY_B63.csv, L-GAY_B65.csv
- GRB Light: L-GRB_B62.csv, L-GRB_B63.csv, L-GRB_B64.csv, L-GRB_B65.csv, L-GRB_B66.csv
- GRB Medium: M-GRB_B60.csv, M-GRB_B61.csv
- TEM Medium: M-TEM_B60.csv, M-TEM_B61.csv, M-TEM_B62.csv, M-TEM_B62_20261019_175906.csv, M-TEM_B63.csv, M-TEM_B64.csv
- TOR Dark: D-TOR_B60.csv, D-TOR_B61.csv, D-TOR_B63.csv
- TOR Light: L-TOR_B62.csv, L-TOR_B63.csv, L-TOR_B65.csv
- TOR Medium: M-TOR_B63.csv, M-TOR_B64.csv, M-TOR_B65.csv, M-TOR_B66.csv, M-TOR_B67.csv
