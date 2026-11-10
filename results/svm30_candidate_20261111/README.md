# Reproducible 30-cycle SVM candidate (11 Nov 2026)

This folder stores **metadata**, never the serialized SVM model or raw CSV.

- `source_manifest.json`: exact SHA256 of the local staging training
  and holdout feature tables; the source data are private/untracked.
- `svm30_9feat_metadata.json`: full feature contract, library versions,
  balanced accuracy / per-class metrics and model SHA256.
- `train_a_b_133.csv`, `holdout_c_66.csv`,
  `holdout_predictions.csv`: **local private working outputs**, not
  intended for publication to GitHub without research-data review.

The real `svm30_9feat_candidate.joblib` was trained on Raspberry Pi 5
under `~/smart-coffee-stage7/svm30_staging/svm30_model/` with
scikit-learn 1.7.2. It is **not** a released/production model.

Generate from verified original CSVs available in the local workspace:

```bash
python scripts/export_svm30_candidate_features.py \
  --output-dir ./prepared_features
```

For a clean new output directory and on the dedicated Pi venv:

```bash
python scripts/fit_svm30_candidate.py \
  --features-dir ./prepared_features \
  --output-dir ./svm30_model
```

Use exact feature order and the training-fitted StandardScaler from
the pipeline; do not refit at inference. Live USB and firmware are
separate SOP-gated milestones. See report
`docs/reports/2026-11-11_SVM30_PI_TRAINING_AND_NEXTION_CANDIDATE.md`.
