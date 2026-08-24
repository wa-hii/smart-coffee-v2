# ML Dataset Summary -- E-NOSE Kopi

**Tanggal:** 2026-08-24 14:39:38

---

## 1. Total Data

| Keterangan | Nilai |
|---|---|
| Total RUN (baris) | 180 |
| Jumlah Light | 70 (38.9%) |
| Jumlah Medium | 60 (33.3%) |
| Jumlah Dark | 50 (27.8%) |
| Jumlah Batch | 5 (B01, B02, B03, B04, B05) |
| Jumlah Sample ID | 9 |

## 2. Ringkasan Feature

| Keterangan | Jumlah |
|---|---|
| Feature awal | 120 |
| Feature RECOMMENDED (final) | 45 |
| Feature REDUNDANT (tidak masuk final) | 50 |
| Feature NOT_SIGNIFICANT (tidak masuk final) | 21 |
| Feature LOW_VARIANCE | 0 |

## 3. Feature yang Direkomendasikan (ml_dataset_final.csv)

| Sensor | Features | Jumlah |
|--------|----------|--------|
| TGS822 *(drift terdeteksi)* | max, mean, min, range, slope, std | 6 |
| MQ135 | slope, std | 2 |
| MQ9 | slope, std | 2 |
| TGS2611 *(drift terdeteksi)* | delta, max, range, slope, std | 5 |
| TGS2620 | max, mean, min, range, slope, std | 6 |
| TGS2600 | - | 0 |
| TGS2602 | delta, max, mean, min, range, slope, std | 7 |
| MQ8 | max, mean, min, range, slope, std | 6 |
| TGS813 | max, mean, range, slope, std | 5 |
| TGS816 | max, mean, min, range, slope, std | 6 |

## 4. Feature yang Tidak Direkomendasikan

### 4a. Redundan (r > 0.95 dengan fitur lain)

Fitur-fitur berikut sangat berkorelasi dengan fitur lain dan direduksi untuk menghindari multikolinearitas:

| Fitur yang Di-drop | Alasan | Fitur Representatif |
|---|---|---|
| `TGS822_auc` | r~1.0 dengan mean | `TGS822_mean` |
| `TGS822_final` | r~0.999 dengan mean/median | `TGS822_mean` |
| `TGS822_initial` | r~0.999 dengan min | `TGS822_min` |
| `TGS822_median` | r~1.0 dengan mean | `TGS822_mean` |
| `TGS822_var` | r=1.0 dengan std (var = std^2) | `TGS822_std` |
| `MQ135_auc` | r~1.0 dengan mean | `MQ135_mean` |
| `MQ135_final` | r~0.999 dengan mean/median | `MQ135_mean` |
| `MQ135_initial` | r~0.999 dengan min | `MQ135_min` |
| `MQ135_median` | r~1.0 dengan mean | `MQ135_mean` |
| `MQ135_var` | r=1.0 dengan std (var = std^2) | `MQ135_std` |
| `MQ9_auc` | r~1.0 dengan mean | `MQ9_mean` |
| `MQ9_final` | r~0.999 dengan mean/median | `MQ9_mean` |
| `MQ9_initial` | r~0.999 dengan min | `MQ9_min` |
| `MQ9_median` | r~1.0 dengan mean | `MQ9_mean` |
| `MQ9_var` | r=1.0 dengan std (var = std^2) | `MQ9_std` |
| `TGS2611_auc` | r~1.0 dengan mean | `TGS2611_mean` |
| `TGS2611_final` | r~0.999 dengan mean/median | `TGS2611_mean` |
| `TGS2611_initial` | r~0.999 dengan min | `TGS2611_min` |
| `TGS2611_median` | r~1.0 dengan mean | `TGS2611_mean` |
| `TGS2611_var` | r=1.0 dengan std (var = std^2) | `TGS2611_std` |
| `TGS2620_auc` | r~1.0 dengan mean | `TGS2620_mean` |
| `TGS2620_final` | r~0.999 dengan mean/median | `TGS2620_mean` |
| `TGS2620_initial` | r~0.999 dengan min | `TGS2620_min` |
| `TGS2620_median` | r~1.0 dengan mean | `TGS2620_mean` |
| `TGS2620_var` | r=1.0 dengan std (var = std^2) | `TGS2620_std` |
| `TGS2600_auc` | r~1.0 dengan mean | `TGS2600_mean` |
| `TGS2600_final` | r~0.999 dengan mean/median | `TGS2600_mean` |
| `TGS2600_initial` | r~0.999 dengan min | `TGS2600_min` |
| `TGS2600_median` | r~1.0 dengan mean | `TGS2600_mean` |
| `TGS2600_var` | r=1.0 dengan std (var = std^2) | `TGS2600_std` |
| `TGS2602_auc` | r~1.0 dengan mean | `TGS2602_mean` |
| `TGS2602_final` | r~0.999 dengan mean/median | `TGS2602_mean` |
| `TGS2602_initial` | r~0.999 dengan min | `TGS2602_min` |
| `TGS2602_median` | r~1.0 dengan mean | `TGS2602_mean` |
| `TGS2602_var` | r=1.0 dengan std (var = std^2) | `TGS2602_std` |
| `MQ8_auc` | r~1.0 dengan mean | `MQ8_mean` |
| `MQ8_final` | r~0.999 dengan mean/median | `MQ8_mean` |
| `MQ8_initial` | r~0.999 dengan min | `MQ8_min` |
| `MQ8_median` | r~1.0 dengan mean | `MQ8_mean` |
| `MQ8_var` | r=1.0 dengan std (var = std^2) | `MQ8_std` |
| `TGS813_auc` | r~1.0 dengan mean | `TGS813_mean` |
| `TGS813_final` | r~0.999 dengan mean/median | `TGS813_mean` |
| `TGS813_initial` | r~0.999 dengan min | `TGS813_min` |
| `TGS813_median` | r~1.0 dengan mean | `TGS813_mean` |
| `TGS813_var` | r=1.0 dengan std (var = std^2) | `TGS813_std` |
| `TGS816_auc` | r~1.0 dengan mean | `TGS816_mean` |
| `TGS816_final` | r~0.999 dengan mean/median | `TGS816_mean` |
| `TGS816_initial` | r~0.999 dengan min | `TGS816_min` |
| `TGS816_median` | r~1.0 dengan mean | `TGS816_mean` |
| `TGS816_var` | r=1.0 dengan std (var = std^2) | `TGS816_std` |

### 4b. Tidak Signifikan (p >= 0.05)

| Sensor | Features Tidak Signifikan |
|--------|---------------------------|
| TGS822 | delta |
| MQ135 | delta, max, mean, min |
| MQ9 | max, mean, min |
| TGS2611 | mean, min |
| TGS2620 | delta |
| TGS2600 | max, mean, min, range, slope, std |
| TGS2602 | Semua signifikan |
| MQ8 | delta |
| TGS813 | delta, min |
| TGS816 | delta |

## 5. Missing Value

**PASS** -- Tidak ditemukan missing value pada seluruh feature.


## 6. Outlier Report

**Metode:** Z-score per feature (threshold |z| > 3.5)

**Total run dengan outlier feature:** 23 / 180

> **Catatan:** Outlier TIDAK dihapus. Ditandai dengan kolom `is_outlier_run=True` pada dataset. Perlu dianalisis lebih lanjut sebelum memutuskan apakah run tersebut valid atau tidak.

| Sample | Batch | Run | Roast | n_outlier_feats | max_z | Outlier Features (5 teratas) |
|--------|-------|-----|-------|-----------------|-------|------------------------------|
| D-BAR | B05 | 1 | dark | 19 | 8.07 | `MQ135_range, MQ135_std, MQ135_var, MQ9_range, MQ9_std` |
| D-BAR | B05 | 2 | dark | 6 | 6.52 | `TGS2602_std, TGS2602_var, MQ8_var, TGS816_range, TGS816_std` |
| D-MAN | B01 | 1 | dark | 2 | 4.69 | `MQ8_range, MQ8_var` |
| D-MAN | B02 | 1 | dark | 18 | 12.35 | `MQ135_range, MQ135_std, MQ135_var, MQ135_delta, MQ135_slope` |
| D-MAN | B02 | 2 | dark | 4 | 4.28 | `TGS2620_var, TGS2602_std, TGS2602_var, TGS813_var` |
| D-MAN | B02 | 3 | dark | 2 | 4.48 | `TGS2620_var, TGS813_var` |
| D-MAN | B02 | 4 | dark | 1 | 4.05 | `TGS813_var` |
| D-MAN | B02 | 6 | dark | 1 | 3.56 | `TGS813_var` |
| D-RAT | B02 | 9 | dark | 2 | 3.88 | `TGS2602_min, TGS2602_initial` |
| D-RAT | B02 | 10 | dark | 6 | 3.94 | `TGS2602_mean, TGS2602_median, TGS2602_min, TGS2602_initial, TGS2602_final` |
| D-RAT | B04 | 1 | dark | 12 | 5.76 | `TGS822_var, TGS2620_range, TGS2620_var, TGS2600_range, TGS2600_std` |
| L-GAY | B03 | 1 | light | 28 | 5.05 | `MQ135_mean, MQ135_median, MQ135_min, MQ135_max, MQ135_final` |
| L-GAY | B03 | 2 | light | 5 | 5.39 | `TGS2600_range, TGS2600_std, TGS2600_var, TGS2600_delta, TGS2600_slope` |
| L-GAY | B03 | 3 | light | 1 | 3.54 | `MQ9_var` |
| L-GAY | B04 | 1 | light | 2 | 3.60 | `MQ8_range, MQ8_var` |
| L-MAN | B03 | 1 | light | 5 | 5.04 | `TGS2620_range, MQ8_range, TGS813_range, TGS813_delta, TGS816_range` |
| L-MAN | B03 | 2 | light | 1 | 4.24 | `TGS813_delta` |
| L-MAN | B04 | 1 | light | 2 | 4.35 | `MQ8_range, MQ8_delta` |
| L-MER | B01 | 2 | light | 2 | 3.66 | `TGS2600_std, TGS2600_var` |
| L-MER | B02 | 1 | light | 6 | 3.85 | `TGS2602_mean, TGS2602_median, TGS2602_min, TGS2602_initial, TGS2602_final` |

*...dan 3 run lainnya. Lihat `processed/outlier_report.csv`.*

## 7. Class Balance

| Roast Level | Jumlah | Persentase |
|-------------|--------|------------|
| light  | 70  | 38.9% |
| medium | 60 | 33.3% |
| dark   | 50   | 27.8% |

**Imbalance Ratio (max/min):** 1.40

> Distribusi kelas cukup seimbang.

## 8. Distribusi Batch per Roast Level

| Roast | B01 | B02 | B03 | B04 | B05 |
|-------|-----|-----|-----|-----|-----|
| light | 20 | 10 | 20 | 20 | - |
| medium | 20 | 10 | 10 | 20 | - |
| dark | 10 | 20 | - | 10 | 10 |

> **Catatan drift batch:** Sensor TGS822 dan TGS2611 menunjukkan indikasi perubahan baseline antar batch (>18%). Perlu dipertimbangkan normalisasi per batch atau penggunaan fitur relatif (delta, slope, range) yang lebih robust terhadap drift.

## 9. Pemeriksaan Data Leakage

| Kolom | Status | Keterangan |
|-------|--------|------------|
| `sample_id` | METADATA | Tidak masuk fitur input model |
| `origin` | METADATA | Tidak masuk fitur input model |
| `batch_id` | METADATA | Tidak masuk fitur input model |
| `run_id` | METADATA | Tidak masuk fitur input model |
| `roast_level` | TARGET | Hanya sebagai label |
| `timestamp` | TIDAK ADA | Tidak bocor ke feature dataset |
| `phase` | TIDAK ADA | Tidak bocor ke feature dataset |
| `sample_idx` | TIDAK ADA | Tidak bocor ke feature dataset |

> **PASS** -- Tidak terdeteksi data leakage. Seluruh fitur diekstrak dari fase `collecting` saja, tanpa informasi label bocor ke fitur.

> **Catatan tambahan:** Karena satu sample_id dapat muncul di lebih dari satu batch, gunakan **GroupKFold** dengan group=`sample_id` atau `batch_id` saat cross-validation untuk menghindari data leakage antar fold.

## 10. Rekomendasi Tahap Machine Learning

### 10.1 Input File
- Gunakan `ml_dataset_final.csv` untuk training model.
- `ml_dataset_full.csv` untuk eksperimen dan ablation study.

### 10.2 Feature Engineering (Opsional)
- Pertimbangkan normalisasi per batch untuk TGS822 dan TGS2611 (drift terdeteksi).
- Fitur `slope` dan `delta` relatif lebih robust terhadap drift baseline.

### 10.3 Cross-Validation
- Gunakan **Stratified K-Fold** (k=5 atau k=10) untuk menjaga proporsi kelas.
- Atau **GroupKFold** dengan group=`sample_id` agar data dari sample yang sama tidak tersebar di train dan test sekaligus.

### 10.4 Model
- **Random Forest** dengan `class_weight='balanced'` untuk mengatasi class imbalance.
- Evaluasi dengan: Accuracy, macro-F1, Confusion Matrix, per-class Precision/Recall.

### 10.5 Feature yang Perlu Diperhatikan
- **Paling diskriminatif:** TGS2602_max, TGS822_max, TGS2620_max, MQ8_mean, TGS816_mean
- **Kurang informatif:** MQ135 (sebagian besar fitur tidak signifikan), TGS2600 (hanya delta signifikan)
- **Perhatian drift:** TGS822, TGS2611 (pertimbangkan normalisasi)

---
*Laporan ini tidak mengandung hasil training machine learning.*
*Dataset siap digunakan untuk tahap training Random Forest.*
