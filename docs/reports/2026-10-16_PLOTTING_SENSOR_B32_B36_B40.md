# Plot sensor batch B32–B36 dan B40

## Ringkasan

Plotting dilakukan **read-only** dengan `scripts/plot_batch_32_36_40.py`, menggunakan 10 kanal: TGS822, MQ135, MQ3, TGS2611, TGS2620, TGS2600, TGS2602, MQ8, TGS813, dan TGS816. Data kopi diambil dari `data/raw` (B32–B36) dan `data/raw/irfan_baseline_B36_B40/` (B40, 40 siklus). Hanya CSV dengan run dan indeks sampel sensor lengkap yang diikutkan; baris penanda pergantian fase dengan **seluruh** ADC kosong dikeluarkan dari plot tanpa mengubah CSV. Baris sensor yang sebagian hilang tidak diinterpolasi.

**Total 750 PNG**, meliputi:

| Folder output | Grafik | Penjelasan |
|---|---:|---|
| `01_sensor_per_batch` | 60 | Sepuluh kanal per batch, masing-masing memuat semua rekaman kopi lengkap |
| `02_roast_same_origin_batch` | 300 | Dark/medium/light di origin+batch yang sama bila minimal dua tersedia |
| `03_same_origin_roast_cross_batch` | 210 | Roast+origin sama, bandingkan antarbatch jika minimal dua tersedia |
| `04_roast_same_origin_baseline_t0` | 180 | Perbandingan roast dalam batch yang sama, dengan titik `t0` dari kontrol batch tersebut |

**100 CSV kopi valid untuk plotting.** Hasil dan metadata ada di `results/plots_batch_32_36_40_verified_20261016/plot_index.csv`, `skipped.csv`, `summary.json`. Rentang sumbu X adalah **indeks sampel berurutan, bukan detik absolut**. Sumbu Y adalah ADC mentah. Pada kelompok 04, nilai pada `t0` (x=0) memakai **median seluruh titik collecting** dari data kontrol batch yang ditentukan, diikuti sinyal kopi mentah pada x=1 dan seterusnya. Penyambungan `t0` dan kopi adalah referensi visual, bukan pengukuran kontinu secara fisik atau pengganti koreksi kalibrasi.

## Pemilihan baseline

Baseline sesuai instruksi: `L-CAW_B33.csv`, `L-CAW_B34.csv`, `L-CAW_B35.csv`, `L-CAW_B36.csv`; dan `BASELINE_B40.csv` untuk B40. Kontrol B33, B35, B36, dan B40 **lolos** filter plotting. `L-CAW_B34.csv` **dilewati** karena indeks sampel tidak kontigu, tercatat `baseline_missing_or_noncontiguous_samples`. Tidak ada baseline yang diminta untuk B32, sehingga **tanpa grafik t0 B32**. Tidak ada fallback diam-diam ke baseline lain atau penggunaan baseline B36 untuk B32.

## Interpretasi dan kehati-hatian

1. Kurva dari 40 siklus B40 **tidak dipotong menjadi lima**. Sumbu x adalah ordinal akuisisi sehingga plot B40 berbeda panjang dari B32–B36.
2. Nilai mentah ADC dari sesi berbeda dapat memuat drift, carryover, perubahan kondisi lingkungan serta perbedaan lot kopi; grafik tidak membuktikan efek roasting.
3. Perbandingan yang tidak memuat semua tiga level tetap dibuat ketika ada minimal dua level; legenda menunjukkan rekaman yang benar-benar tersedia.
4. Seluruh PNG hanya visualisasi, **bukan blind test atau hasil akurasi model**. Raw/firmware/Nextion tidak diubah.

## Penggunaan

Buka `results/plots_batch_32_36_40_verified_20261016/plot_index.csv` untuk menemukan path tiap grafik berdasarkan group/batch/origin/roast/sensor. Jalankan ulang **hanya dengan output folder baru**, karena skrip menolak overwrite hasil sebelumnya.
