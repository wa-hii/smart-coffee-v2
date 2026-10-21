# Grafik sensor 30 siklus — gabungan 112 CSV valid

Sumber: `D:\ENOSE\smart-coffee-v2-hardware\smart-coffee-v2-hardware\data\raw\data 30 siklus\HASIL_AUDIT_30_SIKLUS_20261019\HASIL_GABUNGAN_20261021\01_VALID_GABUNGAN`; seluruh CSV diperiksa ulang sebelum plotting.
Input: **112** rekaman valid dan **2160** PNG.

## Lima skema

- `01_sensor_per_batch`: 1120 grafik PNG · 01 · Sensor setiap rekaman / batch
- `02_roast_same_origin_batch`: 310 grafik PNG · 02 · Roast berbeda, origin + batch sama
- `03_same_origin_roast_cross_batch`: 210 grafik PNG · 03 · Origin + roast sama, lintas batch
- `04_roast_same_origin_batch_t0`: 310 grafik PNG · 04 · Roast berbeda, origin + batch sama, ΔADC t0
- `05_same_origin_roast_cross_batch_t0_norm`: 210 grafik PNG · 05 · Origin + roast sama, lintas batch, ΔADC t0

## Normalisasi t0

- t0 diambil dari pembacaan terakhir purging siklus pertama `sample_idx=25`, sebelum collecting pertama `t26`.
- ΔADC(t) = ADC(t) − ADC(t0), untuk **setiap** rekaman secara terpisah.
- Sumbu waktu berdasarkan timestamp asli, relatif ke awal rekaman atau t0; data purging awal tetap tampil pada waktu negatif.
- No smoothing, interpolasi, resampling, atau pemalsuan titik hilang.
- Area jingga samar menunjukkan rentang collecting nominal 5 detik, bukan hasil pengukuran aktuator terpisah.
- Warna roasting: Light biru, Medium oranye, Dark merah; lintas batch memakai warna berbeda untuk setiap berkas.
- File dengan batch sama tetapi pengambilan berbeda tetap diberi label **filename lengkap** sehingga tidak dianggap salinan identik.
- Kelompok tanpa perbandingan sah (misalnya hanya satu roast untuk origin+batch) tidak dipaksakan.
- Normalisasi t0 tidak sama dengan baseline udara bersih dari file kalibrasi eksternal.

## Navigasi dan audit

- `GALERI_5_SKEMA.html`: filter skema, grup, sensor, pencarian, klik PNG untuk resolusi penuh.
- `plot_index.csv`: semua grafik dan sumber tiap grafik.
- `input_provenance.csv`: SHA256 dan metadata dari seluruh CSV valid.
- `comparison_groups.csv`: keanggotaan grup roast dan cross-batch.
- `summary.json`: jumlah grafik dan metode.

## Batas interpretasi

Perbandingan lintas batch/alat adalah eksploratif; tidak membuktikan independensi spesimen, kesetaraan alat atau signifikansi. Semua ADC berasal dari CSV yang lolos audit 30 siklus.

## Kelompok roast dalam origin+batch sama

- CAT B60: L-CAT_B60.csv, D-CAT_B60.csv
- CAT B62: L-CAT_B62.csv, M-CAT_B62.csv, D-CAT_B62.csv
- CAT B63: L-CAT_B63.csv, M-CAT_B63.csv, D-CAT_B63.csv
- CAT B64: M-CAT_B64.csv, D-CAT_B64.csv
- CAT B66: L-CAT_B66.csv, M-CAT_B66.csv
- CAT B67: L-CAT_B67.csv, M-CAT_B67.csv
- GAW B60: L-GAW_B60.csv, M-GAW_B60.csv, D-GAW_B60.csv
- GAW B61: L-GAW_B61.csv, M-GAW_B61.csv, D-GAW_B61.csv
- GAW B66: L-GAW_B66.csv, M-GAW_B66.csv, D-GAW_B66.csv
- GAW B67: L-GAW_B67.csv, M-GAW_B67.csv
- GAW B68: L-GAW_B68.csv, M-GAW_B68.csv
- GRB B60: M-GRB_B60.csv, M-GRB_B60__NEW_9645c0fc1e.csv, D-GRB_B60.csv
- GRB B61: M-GRB_B61.csv, D-GRB_B61.csv
- GRB B62: L-GRB_B62.csv, D-GRB_B62.csv
- GRB B63: L-GRB_B63.csv, D-GRB_B63.csv
- GRB B64: L-GRB_B64.csv, D-GRB_B64.csv
- GRB B66: L-GRB_B66.csv, M-GRB_B66.csv
- MING B60: L-MING_B60.csv, D-MING_B60.csv
- MING B61: M-MING_B61.csv, D-MING_B61.csv
- MING B62: M-MING_B62.csv, D-MING_B62.csv
- MING B63: M-MING_B63.csv, D-MING_B63.csv
- MING B64: M-MING_B64.csv, D-MING_B64.csv
- TEM B60: L-TEM_B60.csv, M-TEM_B60.csv, D-TEM_B60.csv
- TEM B61: L-TEM_B61.csv, M-TEM_B61.csv, D-TEM_B61.csv
- TEM B62: L-TEM_B62.csv, M-TEM_B62.csv, M-TEM_B62_20261019_175906.csv, D-TEM_B62.csv
- TEM B63: L-TEM_B63.csv, M-TEM_B63.csv, D-TEM_B63.csv
- TEM B64: L-TEM_B64.csv, M-TEM_B64.csv, D-TEM_B64.csv
- TOR B63: L-TOR_B63.csv, M-TOR_B63.csv, D-TOR_B63.csv
- TOR B65: L-TOR_B65.csv, M-TOR_B65.csv
- TOR B66: L-TOR_B66.csv, M-TOR_B66.csv, D-TOR_B66.csv
- TOR B67: L-TOR_B67.csv, M-TOR_B67.csv, D-TOR_B67.csv

## Kelompok origin+roast sama lintas batch

- CAT Dark: D-CAT_B60.csv, D-CAT_B61.csv, D-CAT_B62.csv, D-CAT_B63.csv, D-CAT_B64.csv, D-CAT_B65.csv
- CAT Light: L-CAT_B60.csv, L-CAT_B62.csv, L-CAT_B63.csv, L-CAT_B66.csv, L-CAT_B67.csv
- CAT Medium: M-CAT_B62.csv, M-CAT_B63.csv, M-CAT_B64.csv, M-CAT_B66.csv, M-CAT_B67.csv
- GAW Dark: D-GAW_B60.csv, D-GAW_B61.csv, D-GAW_B62.csv, D-GAW_B63.csv, D-GAW_B64.csv, D-GAW_B65.csv, D-GAW_B66.csv
- GAW Light: L-GAW_B60.csv, L-GAW_B61.csv, L-GAW_B66.csv, L-GAW_B67.csv, L-GAW_B68.csv
- GAW Medium: M-GAW_B60.csv, M-GAW_B61.csv, M-GAW_B66.csv, M-GAW_B67.csv, M-GAW_B68.csv
- GAY Light: L-GAY_B62.csv, L-GAY_B63.csv, L-GAY_B65.csv, L-GAY_B66.csv, L-GAY_B67.csv
- GRB Dark: D-GRB_B60.csv, D-GRB_B61.csv, D-GRB_B62.csv, D-GRB_B63.csv, D-GRB_B64.csv
- GRB Light: L-GRB_B62.csv, L-GRB_B63.csv, L-GRB_B64.csv, L-GRB_B65.csv, L-GRB_B66.csv
- GRB Medium: M-GRB_B60.csv, M-GRB_B60__NEW_9645c0fc1e.csv, M-GRB_B61.csv, M-GRB_B66.csv, M-GRB_B67.csv, M-GRB_B68.csv
- MING Dark: D-MING_B60.csv, D-MING_B61.csv, D-MING_B62.csv, D-MING_B63.csv, D-MING_B64.csv
- MING Light: L-MING_B60.csv, L-MING_B66.csv, L-MING_B67.csv, L-MING_B68.csv, L-MING_B69.csv
- MING Medium: M-MING_B61.csv, M-MING_B62.csv, M-MING_B63.csv, M-MING_B64.csv, M-MING_B65.csv
- MUK Medium: M-MUK_B60.csv, M-MUK_B61.csv, M-MUK_B62.csv, M-MUK_B63.csv, M-MUK_B64.csv, M-MUK_B65.csv
- RAT Dark: D-RAT_B61.csv, D-RAT_B62.csv, D-RAT_B63.csv, D-RAT_B64.csv, D-RAT_B65.csv, D-RAT_B66.csv
- TEM Dark: D-TEM_B60.csv, D-TEM_B61.csv, D-TEM_B62.csv, D-TEM_B63.csv, D-TEM_B64.csv
- TEM Light: L-TEM_B60.csv, L-TEM_B61.csv, L-TEM_B62.csv, L-TEM_B63.csv, L-TEM_B64.csv
- TEM Medium: M-TEM_B60.csv, M-TEM_B61.csv, M-TEM_B62.csv, M-TEM_B62_20261019_175906.csv, M-TEM_B63.csv, M-TEM_B64.csv
- TOR Dark: D-TOR_B60.csv, D-TOR_B61.csv, D-TOR_B63.csv, D-TOR_B66.csv, D-TOR_B67.csv
- TOR Light: L-TOR_B62.csv, L-TOR_B63.csv, L-TOR_B65.csv, L-TOR_B66.csv, L-TOR_B67.csv
- TOR Medium: M-TOR_B63.csv, M-TOR_B64.csv, M-TOR_B65.csv, M-TOR_B66.csv, M-TOR_B67.csv
