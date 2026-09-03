# Baseline Random Forest Results

**Tanggal:** 2026-08-24 15:09:54

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
| Train Accuracy     | 100.00% |
| Test Accuracy      | 57.50% |
| Test Precision (macro) | 69.44% |
| Test Recall (macro)    | 51.67% |
| Test F1 (macro)        | 50.40% |
| CV F1 (5-fold, mean)   | 75.61% +/- 6.28% |

> **Perhatian:** Gap Train-Test = 42.5% -- indikasi overfitting.

## Classification Report

```
              precision    recall  f1-score   support

       light       1.00      0.20      0.33        10
      medium       0.75      0.75      0.75        20
        dark       0.33      0.60      0.43        10

    accuracy                           0.57        40
   macro avg       0.69      0.52      0.50        40
weighted avg       0.71      0.57      0.57        40
```

## Analisis Kesalahan Klasifikasi

| Actual | Diprediksi | Count |
|--------|-----------|-------|
| light | medium | 5 |
| light | dark | 0 |
| medium | light | 4 |
| medium | dark | 0 |
| dark | light | 1 |
| dark | medium | 7 |

## Top 15 Feature Paling Penting

| Rank | Feature | Importance |
|------|---------|------------|
| 1 | `TGS2602_range` | 0.0512 |
| 2 | `TGS2611_max` | 0.0498 |
| 3 | `TGS2602_max` | 0.0474 |
| 4 | `TGS813_range` | 0.0469 |
| 5 | `TGS816_mean` | 0.0417 |
| 6 | `TGS816_max` | 0.0326 |
| 7 | `TGS822_min` | 0.0297 |
| 8 | `TGS822_std` | 0.0294 |
| 9 | `TGS2620_range` | 0.0294 |
| 10 | `TGS2602_mean` | 0.0256 |
| 11 | `MQ135_slope` | 0.0249 |
| 12 | `TGS2620_std` | 0.0236 |
| 13 | `MQ9_slope` | 0.0230 |
| 14 | `TGS816_range` | 0.0226 |
| 15 | `TGS2620_min` | 0.0222 |

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
  "min_samples_split": "2",
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
