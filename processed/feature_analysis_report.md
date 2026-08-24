# Feature Analysis Report -- E-NOSE Kopi

**Tanggal Analisis:** 2026-08-24 14:29:56

---

## 0. Ringkasan Dataset
| Keterangan | Nilai |
|---|---|
| Total RUN | 180 |
| Total Fitur Numerik | 120 |
| Sensor | 10 channel ADC |
| Statistik per sensor | 12 |
| Roast: Light | 70 RUN |
| Roast: Medium | 60 RUN |
| Roast: Dark | 50 RUN |
| Batch | B01, B02, B03, B04, B05 |

## 1. Boxplot Perbandingan Roast Level
Boxplot berikut menampilkan distribusi fitur statistik setiap sensor terhadap roast level (Light / Medium / Dark).
File disimpan di: `plots/features/boxplots/boxplot_<sensor>.png`
## 2. Distribusi Fitur per Roast Level (KDE)
Plot distribusi KDE menampilkan tumpang tindih antar roast level. Separasi yang baik mengindikasikan fitur berpotensi diskriminatif.
File disimpan di: `plots/features/distributions/dist_<sensor>.png`
## 3. Correlation Matrix
Heatmap korelasi Pearson antar fitur. Korelasi tinggi (>0.95) mengindikasikan fitur yang redundan.

### Pasangan Fitur dengan Korelasi Sangat Tinggi (r > 0.95)
Total: 307 pasangan
| Fitur A | Fitur B | r |
|---------|---------|---|
| TGS2611_auc | TGS2611_mean | 1.0000 |
| TGS2620_auc | TGS2620_mean | 1.0000 |
| TGS2611_median | TGS2611_mean | 1.0000 |
| TGS822_auc | TGS822_mean | 1.0000 |
| TGS813_auc | TGS813_mean | 1.0000 |
| TGS2611_auc | TGS2611_median | 1.0000 |
| TGS816_auc | TGS816_mean | 1.0000 |
| MQ8_auc | MQ8_mean | 0.9999 |
| TGS2602_auc | TGS2602_mean | 0.9999 |
| MQ9_median | MQ9_mean | 0.9999 |
| MQ135_median | MQ135_mean | 0.9999 |
| TGS2600_median | TGS2600_mean | 0.9998 |
| MQ8_initial | MQ8_min | 0.9996 |
| TGS2611_max | TGS2611_median | 0.9993 |
| TGS2611_auc | TGS2611_max | 0.9991 |
| TGS2611_max | TGS2611_mean | 0.9991 |
| TGS2611_initial | TGS2611_min | 0.9989 |
| TGS2611_final | TGS2611_max | 0.9988 |
| TGS816_initial | TGS816_min | 0.9988 |
| MQ9_initial | MQ9_max | 0.9988 |

File disimpan di: `plots/features/correlations/corr_<stat>.png`
## 4. Analisis Batch Effect
Analisis ini mendeteksi apakah terdapat perbedaan baseline atau drift antar batch pengambilan data.

### Ringkasan Perubahan Mean ADC Antar Batch
| Sensor | B01 | B02 | B03 | B04 | B05 | Trend |
|--------|-----|-----|-----|-----|-----|-------|
| TGS822 | 13554 | 14849 | 12348 | 14277 | 16005 | DRIFT +18.1% |
| MQ135 | 2820 | 2827 | 2846 | 2825 | 2868 | Stabil (+1.7%) |
| MQ9 | 2807 | 2812 | 2835 | 2810 | 2851 | Stabil (+1.6%) |
| TGS2611 | 8861 | 8606 | 8202 | 8521 | 10474 | DRIFT +18.2% |
| TGS2620 | 10360 | 11024 | 8346 | 10223 | 11362 | Stabil (+9.7%) |
| TGS2600 | 2799 | 2807 | 2824 | 2804 | 2844 | Stabil (+1.6%) |
| TGS2602 | 9510 | 10022 | 8921 | 9594 | 9921 | Stabil (+4.3%) |
| MQ8 | 15910 | 17491 | 14970 | 15889 | 16895 | Stabil (+6.2%) |
| TGS813 | 15718 | 16391 | 13089 | 15415 | 15997 | Stabil (+1.8%) |
| TGS816 | 14395 | 15763 | 12931 | 14898 | 14745 | Stabil (+2.4%) |

> **Perhatian:** Indikasi drift terdeteksi pada sensor: TGS822, TGS2611. Perlu dianalisis lebih lanjut apakah ini drift sensor atau perbedaan kondisi pengambilan sampel.

File disimpan di: `plots/features/batch_comparison/batch_<sensor>.png`
## 5. Uji Diskriminasi Fitur (Kruskal-Wallis)
Kruskal-Wallis H-test menguji apakah distribusi fitur berbeda secara signifikan antar roast level (p < 0.05 = signifikan).

**Total fitur diuji    :** 120
**Fitur signifikan (p<0.05):** 82
**Fitur tidak signifikan  :** 38

### Top 30 Fitur Paling Diskriminatif (p terkecil)
| Rank | Fitur | p-value (Kruskal) | CV |
|------|-------|-------------------|----|
| 1 | TGS2602_max | 6.8459e-12 | 0.067 |
| 2 | TGS2602_range | 9.9681e-10 | 0.667 |
| 3 | TGS822_max | 2.4777e-09 | 0.117 |
| 4 | TGS2620_max | 5.1039e-09 | 0.115 |
| 5 | TGS2602_auc | 3.2545e-08 | 0.058 |
| 6 | TGS2602_mean | 3.2651e-08 | 0.058 |
| 7 | TGS816_max | 4.3735e-08 | 0.082 |
| 8 | TGS2602_var | 2.2355e-07 | 1.672 |
| 9 | TGS2602_std | 2.2355e-07 | 0.662 |
| 10 | MQ8_max | 2.2520e-07 | 0.078 |
| 11 | TGS2602_median | 6.8385e-07 | 0.059 |
| 12 | MQ8_auc | 7.2689e-07 | 0.073 |
| 13 | MQ8_mean | 7.8878e-07 | 0.073 |
| 14 | TGS813_range | 7.9895e-07 | 0.618 |
| 15 | TGS816_auc | 1.0025e-06 | 0.079 |
| 16 | TGS816_mean | 1.0741e-06 | 0.079 |
| 17 | MQ8_median | 1.5220e-06 | 0.071 |
| 18 | TGS2620_range | 2.7972e-06 | 0.619 |
| 19 | MQ8_final | 3.0341e-06 | 0.069 |
| 20 | MQ135_slope | 3.8298e-06 | 2.163 |
| 21 | TGS2602_final | 4.2278e-06 | 0.058 |
| 22 | TGS822_mean | 4.8826e-06 | 0.112 |
| 23 | TGS822_auc | 5.0941e-06 | 0.112 |
| 24 | TGS813_max | 5.9867e-06 | 0.102 |
| 25 | TGS816_median | 6.7417e-06 | 0.078 |
| 26 | MQ8_initial | 1.3957e-05 | 0.092 |
| 27 | TGS816_range | 1.4035e-05 | 0.607 |
| 28 | MQ8_min | 1.8286e-05 | 0.092 |
| 29 | TGS2620_std | 3.0556e-05 | 0.671 |
| 30 | TGS2620_var | 3.0556e-05 | 1.536 |
## 6. Ringkasan Mean per Roast Level
Tabel ini menampilkan perbedaan rata-rata fitur `mean` per sensor antara roast level.

| Sensor | Fitur | Light Mean | Medium Mean | Dark Mean | Diff L-D |
|--------|-------|-----------|------------|---------|----------|
| TGS822 | mean | 13884.4 | 13399.0 | 14803.8 | -919.4 (6.6%) |
| TGS822 | delta | 3179.1 | 2830.9 | 2721.8 | +457.3 (14.4%) |
| TGS822 | slope | 3.1 | 5.8 | -0.6 | +3.7 (117.8%) |
| MQ135 | mean | 2827.8 | 2825.1 | 2838.2 | -10.4 (0.4%) |
| MQ135 | delta | 1.1 | 1.9 | -1.1 | +2.2 (200.5%) |
| MQ135 | slope | -0.0 | -0.0 | -0.0 | +0.0 (82.0%) |
| MQ9 | mean | 2814.2 | 2812.2 | 2823.0 | -8.8 (0.3%) |
| MQ9 | delta | -3.7 | -2.8 | -5.4 | +1.7 (46.0%) |
| MQ9 | slope | -0.0 | -0.0 | -0.0 | +0.0 (52.3%) |
| TGS2611 | mean | 8375.5 | 8856.2 | 8929.6 | -554.1 (6.6%) |
| TGS2611 | delta | -6.8 | 22.5 | 75.8 | -82.6 (1212.4%) |
| TGS2611 | slope | -0.1 | 0.1 | 0.3 | -0.4 (476.1%) |
| TGS2620 | mean | 9974.4 | 10006.4 | 10710.7 | -736.3 (7.4%) |
| TGS2620 | delta | 459.0 | 387.6 | 362.8 | +96.2 (21.0%) |
| TGS2620 | slope | -0.3 | 0.3 | -1.7 | +1.4 (396.5%) |
| TGS2600 | mean | 2807.9 | 2805.8 | 2814.1 | -6.2 (0.2%) |
| TGS2600 | delta | -3.2 | -3.2 | -4.8 | +1.6 (50.7%) |
| TGS2600 | slope | -0.0 | -0.0 | -0.0 | +0.0 (34.4%) |
| TGS2602 | mean | 9516.8 | 9400.7 | 9854.9 | -338.1 (3.6%) |
| TGS2602 | delta | 251.9 | 225.4 | 338.7 | -86.8 (34.4%) |
| TGS2602 | slope | -0.8 | -0.3 | -1.4 | +0.6 (74.4%) |
| MQ8 | mean | 16055.3 | 15733.1 | 16796.1 | -740.8 (4.6%) |
| MQ8 | delta | 1065.2 | 942.5 | 974.9 | +90.4 (8.5%) |
| MQ8 | slope | 1.7 | 2.7 | 0.1 | +1.6 (95.3%) |
| TGS813 | mean | 15111.2 | 15076.7 | 16051.0 | -939.7 (6.2%) |
| TGS813 | delta | 1021.1 | 856.1 | 918.8 | +102.3 (10.0%) |
| TGS813 | slope | 1.2 | 2.2 | -1.6 | +2.8 (234.1%) |
| TGS816 | mean | 14523.3 | 14250.9 | 15177.4 | -654.1 (4.5%) |
| TGS816 | delta | 704.3 | 638.7 | 672.3 | +32.0 (4.5%) |
| TGS816 | slope | 0.4 | 1.4 | -0.9 | +1.3 (331.1%) |

## 7. Ringkasan & Rekomendasi

### 7.1 Fitur Stabil (Low Variance)
Tidak ada fitur dengan variance sangat kecil.

### 7.2 Fitur dengan Variasi Tinggi (CV > 0.5)
Jumlah: 46
- `TGS822_var`
- `TGS822_delta`
- `TGS822_slope`
- `MQ135_std`
- `MQ135_var`
- `MQ135_delta`
- `MQ135_slope`
- `MQ9_std`
- `MQ9_var`
- `MQ9_delta`
- `MQ9_slope`
- `TGS2611_range`
- `TGS2611_std`
- `TGS2611_var`
- `TGS2611_delta`

### 7.3 Fitur yang Menunjukkan Indikasi Perbedaan Roast Level
*(p-value Kruskal-Wallis < 0.05)*

Total: **82** fitur signifikan

| Sensor | Fitur Signifikan |
|--------|------------------|
| TGS822 | mean, median, min, max, range, std, var, initial, final, slope, auc |
| MQ135 | range, std, var, slope |
| MQ9 | range, std, var, delta, slope |
| TGS2611 | max, range, std, var, final, delta, slope |
| TGS2620 | mean, median, min, max, range, std, var, initial, final, slope, auc |
| TGS2600 | delta |
| TGS2602 | mean, median, min, max, range, std, var, initial, final, delta, slope, auc |
| MQ8 | mean, median, min, max, range, std, var, initial, final, slope, auc |
| TGS813 | mean, median, max, range, std, var, final, slope, auc |
| TGS816 | mean, median, min, max, range, std, var, initial, final, slope, auc |

### 7.4 Fitur Sangat Berkorelasi (r > 0.95) - Kemungkinan Redundan
Total pasangan: 307
Beberapa fitur yang sangat berkorelasi dapat direduksi pada tahap preprocessing ML.

### 7.5 Perbedaan Antar Batch
**Indikasi drift terdeteksi** pada sensor: TGS822, TGS2611.
Kemungkinan penyebab: kondisi lingkungan berbeda antar hari pengambilan, atau sensor baseline bergeser. Disarankan untuk:
- Menganalisis lebih lanjut apakah drift terjadi sistematis atau acak.
- Mempertimbangkan normalisasi per batch pada tahap preprocessing ML.

### 7.6 Rekomendasi untuk Tahap Machine Learning

> **CATATAN:** Rekomendasi ini berdasarkan analisis statistik eksploratoris.
> Validasi akhir fitur harus dilakukan setelah training model.

**Kandidat Fitur Prioritas** (30 fitur dengan p-value terkecil):

1. `TGS2602_max` (p = 6.8459e-12)
2. `TGS2602_range` (p = 9.9681e-10)
3. `TGS822_max` (p = 2.4777e-09)
4. `TGS2620_max` (p = 5.1039e-09)
5. `TGS2602_auc` (p = 3.2545e-08)
6. `TGS2602_mean` (p = 3.2651e-08)
7. `TGS816_max` (p = 4.3735e-08)
8. `TGS2602_var` (p = 2.2355e-07)
9. `TGS2602_std` (p = 2.2355e-07)
10. `MQ8_max` (p = 2.2520e-07)
11. `TGS2602_median` (p = 6.8385e-07)
12. `MQ8_auc` (p = 7.2689e-07)
13. `MQ8_mean` (p = 7.8878e-07)
14. `TGS813_range` (p = 7.9895e-07)
15. `TGS816_auc` (p = 1.0025e-06)
16. `TGS816_mean` (p = 1.0741e-06)
17. `MQ8_median` (p = 1.5220e-06)
18. `TGS2620_range` (p = 2.7972e-06)
19. `MQ8_final` (p = 3.0341e-06)
20. `MQ135_slope` (p = 3.8298e-06)
21. `TGS2602_final` (p = 4.2278e-06)
22. `TGS822_mean` (p = 4.8826e-06)
23. `TGS822_auc` (p = 5.0941e-06)
24. `TGS813_max` (p = 5.9867e-06)
25. `TGS816_median` (p = 6.7417e-06)
26. `MQ8_initial` (p = 1.3957e-05)
27. `TGS816_range` (p = 1.4035e-05)
28. `MQ8_min` (p = 1.8286e-05)
29. `TGS2620_std` (p = 3.0556e-05)
30. `TGS2620_var` (p = 3.0556e-05)

**Fitur yang kemungkinan tidak informatif** (p > 0.05):
- `TGS2600_slope` -- indikasi tidak membedakan roast level
- `TGS813_initial` -- indikasi tidak membedakan roast level
- `MQ135_delta` -- indikasi tidak membedakan roast level
- `TGS813_min` -- indikasi tidak membedakan roast level
- `MQ135_max` -- indikasi tidak membedakan roast level
- `TGS2611_median` -- indikasi tidak membedakan roast level
- `MQ135_initial` -- indikasi tidak membedakan roast level
- `MQ135_mean` -- indikasi tidak membedakan roast level
- `MQ135_final` -- indikasi tidak membedakan roast level
- `MQ135_median` -- indikasi tidak membedakan roast level

---
*Laporan ini tidak mengandung output training machine learning.*
*RAW CSV data tidak diubah selama seluruh proses analisis.*
