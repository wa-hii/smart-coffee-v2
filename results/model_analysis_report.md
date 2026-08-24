# Model Analysis Report -- E-NOSE Kopi Roast Classification

**Tanggal:** 2026-08-24 15:10:12

---

## 1. Dataset yang Digunakan

- File: `processed/ml_dataset_final.csv`
- Total RUN: **180**
- Feature input: **45** fitur numerik
- Target: `roast_level` (Light / Medium / Dark)

## 2. Train/Test Split

| Set | Batch | Jumlah | Light | Medium | Dark |
|-----|-------|--------|-------|--------|------|
| Train | B01, B02, B04 | 140 | 50 | 50 | 40 |
| Test  | B03, B05  | 40  | 20 | 10 | 10 |

**Metode:** Batch-based split (bukan random split).

**Alasan:**
- Mencegah data leakage antar batch (run dari batch sama tidak tersebar di train & test).
- Mensimulasikan generalisasi ke batch baru (realistic deployment scenario).
- B03+B05 dipilih sebagai test karena merupakan batch yang lebih sedikit dan
  keduanya saling melengkapi kelas yang tidak ada (B03 tidak ada dark, B05 hanya dark).

## 3. Keterbatasan Dataset

- **Class imbalance ringan:** Light(70) > Medium(60) > Dark(50). Diatasi dengan `class_weight='balanced'`.
- **Batch coverage tidak simetris:** Tidak semua kelas hadir di semua batch.
- **Jumlah data test kecil:** Hanya 40 sampel, evaluasi mungkin belum stabil.
- **Sample ID terbatas:** 9 sample ID unik; generalisasi ke sample baru belum teruji.
- **Drift sensor:** TGS822 dan TGS2611 menunjukkan indikasi drift antar batch (>18%).

## 4. Parameter Baseline

```json
{
  "n_estimators": "100",
  "max_depth": "None",
  "min_samples_split": "2",
  "min_samples_leaf": "1",
  "max_features": "sqrt",
  "class_weight": "balanced",
  "random_state": "42",
  "n_jobs": "-1"
}
```

## 5. Parameter Final (Setelah Tuning)

```json
{
  "max_depth": "None",
  "max_features": "sqrt",
  "min_samples_leaf": "1",
  "min_samples_split": "5",
  "n_estimators": "100",
  "class_weight": "balanced",
  "random_state": "42",
  "n_jobs": "-1"
}
```

## 6. Hasil Performa

| Metrik | Baseline | Final (Tuned) |
|--------|----------|---------------|
| Train Accuracy  | 100.00% | 99.29% |
| Test Accuracy   | 57.50% | 55.00% |
| Precision (macro)| 69.44% | 70.61% |
| Recall (macro)  | 51.67% | 53.33% |
| F1 (macro)      | 50.40% | 52.83% |
| CV F1 (5-fold)  | 75.61% +/-6.28% | 77.86% +/-7.70% |

## 7. Analisis Overfitting

| Model | Train Acc | Test Acc | Gap | Status |
|-------|-----------|----------|-----|--------|
| Baseline | 100.0% | 57.5% | 42.5% | OVERFITTING |
| Final    | 99.3% | 55.0% | 44.3% | OVERFITTING |

## 8. Confusion Matrix -- Final Model

```
              light  medium  dark
actual light       12       8     0
actual medium       3       7     0
actual dark         0       7     3
```

## 9. Analisis Kesalahan Klasifikasi

| Actual | Diprediksi | Jumlah |
|--------|-----------|--------|
| light | medium | 8 |
| medium | light | 3 |
| dark | medium | 7 |

**Detail run yang salah diklasifikasi:**

| Sample | Batch | Run | Actual | Predicted |
|--------|-------|-----|--------|----------|
| D-BAR | B05 | 3 | dark | medium |
| D-BAR | B05 | 4 | dark | medium |
| D-BAR | B05 | 5 | dark | medium |
| D-BAR | B05 | 6 | dark | medium |
| D-BAR | B05 | 8 | dark | medium |
| D-BAR | B05 | 9 | dark | medium |
| D-BAR | B05 | 10 | dark | medium |
| L-GAY | B03 | 3 | light | medium |
| L-GAY | B03 | 4 | light | medium |
| L-GAY | B03 | 8 | light | medium |
| L-MAN | B03 | 3 | light | medium |
| L-MAN | B03 | 4 | light | medium |
| L-MAN | B03 | 6 | light | medium |
| L-MAN | B03 | 7 | light | medium |
| L-MAN | B03 | 10 | light | medium |
| M-TIM | B03 | 1 | medium | light |
| M-TIM | B03 | 2 | medium | light |
| M-TIM | B03 | 4 | medium | light |

## 10. Feature Paling Penting

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | `TGS2602_range` | 0.0551 |
| 2 | `TGS2611_max` | 0.0507 |
| 3 | `TGS813_range` | 0.0492 |
| 4 | `TGS2602_max` | 0.0482 |
| 5 | `TGS816_mean` | 0.0420 |
| 6 | `TGS822_std` | 0.0350 |
| 7 | `TGS816_max` | 0.0331 |
| 8 | `TGS822_min` | 0.0311 |
| 9 | `TGS2620_range` | 0.0302 |
| 10 | `TGS2620_min` | 0.0299 |
| 11 | `TGS2602_mean` | 0.0266 |
| 12 | `MQ135_slope` | 0.0265 |
| 13 | `TGS2620_std` | 0.0243 |
| 14 | `MQ8_range` | 0.0231 |
| 15 | `TGS822_range` | 0.0227 |

**Analisis:**
- Feature terpenting: `TGS2602_range`, `TGS2611_max`, `TGS813_range`, `TGS2602_max`, `TGS816_mean`
- Konsisten dengan analisis Kruskal-Wallis sebelumnya di mana TGS2602, TGS822, TGS2620, MQ8, TGS816 memiliki p-value terkecil.
- Sensor MQ135 dan TGS2600 kemungkinan kurang informatif, sesuai ekspektasi dari analisis sebelumnya.

## 11. Rekomendasi Perbaikan

1. **Tambah data:** Lebih banyak RUN per sample akan meningkatkan stabilitas model.
2. **Normalisasi per batch:** Untuk mengatasi drift TGS822 dan TGS2611.
3. **Tambah sample D-GAY dan L-RAT:** Sample ID yang tidak ada di dataset saat ini.
4. **Test pada batch baru:** Lakukan pengambilan data batch baru dan evaluasi generalisasi.
5. **Feature engineering:** Pertimbangkan fitur normalisasi seperti Z-score per run atau normalisasi terhadap baseline purging.

---
*Model siap dievaluasi. Belum dilakukan deployment ke Raspberry Pi.*
