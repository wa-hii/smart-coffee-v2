# Final (Tuned) Random Forest Results

**Tanggal:** 2026-08-24 15:10:12

## Data
| Keterangan | Nilai |
|---|---|
| Train batches | B01, B02, B04 |
| Test batches  | B03, B05 |
| Train samples | 140 |
| Test samples  | 40 |

## Performa Model
| Metrik | Nilai |
|--------|-------|
| Train Accuracy     | 99.29% |
| Test Accuracy      | 55.00% |
| Test Precision (macro) | 70.61% |
| Test Recall (macro)    | 53.33% |
| Test F1 (macro)        | 52.83% |
| CV F1 (5-fold, mean)   | 77.86% +/- 7.70% |

> **Perhatian:** Gap Train-Test = 44.3% -- indikasi overfitting.

## Classification Report

```
              precision    recall  f1-score   support

       light       1.00      0.30      0.46        10
      medium       0.80      0.60      0.69        20
        dark       0.32      0.70      0.44        10

    accuracy                           0.55        40
   macro avg       0.71      0.53      0.53        40
weighted avg       0.73      0.55      0.57        40
```

## Analisis Kesalahan Klasifikasi

| Actual | Diprediksi | Count |
|--------|-----------|-------|
| light | medium | 8 |
| light | dark | 0 |
| medium | light | 3 |
| medium | dark | 0 |
| dark | light | 0 |
| dark | medium | 7 |

## Top 15 Feature Paling Penting

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

## Parameter Model

```json
{
  "bootstrap": "True",
  "ccp_alpha": "0.0",
  "class_weight": "balanced",
  "criterion": "gini",
  "max_depth": "None",
  "max_features": "sqrt",
  "max_leaf_nodes": "None",
  "max_samples": "None",
  "min_impurity_decrease": "0.0",
  "min_samples_leaf": "1",
  "min_samples_split": "5",
  "min_weight_fraction_leaf": "0.0",
  "monotonic_cst": "None",
  "n_estimators": "100",
  "n_jobs": "-1",
  "oob_score": "False",
  "random_state": "42",
  "verbose": "0",
  "warm_start": "False"
}
```
