# AI model research and evaluation decision — 2026-10-08

**Status: research and evaluation plan; no new model trained or approved.**

## Current evidence and formulation

- B32–B35: 86 acquisition CSVs, 23 observed roast-origin combinations,
  4 batches; only ~5 collecting points/cycle. Five cycles in one CSV are
  repeated measurements, not independent labeled specimens.
- Historic RF B01–B05, legacy MQ9, 45 selected features: test accuracy 57.50%
  baseline, 55.00% tuned. Do not report these scores as current performance.
- Candidate `scripts/extract_b32_features.py` exports 1 row per CSV and
  a versioned feature schema. It uses per-cycle last-5 purging baseline,
  collecting relative response/SD/slope, then mean and SD over 5 cycles;
  temperature/humidity means. **62 numerical features are provisional**.
- Primary target to evaluate: roast-only (light/medium/dark). Second task:
  known-origin-only, conditioned on adequate independent physical specimens.
  Joint classification and hierarchical inference are research candidates,
  not default conclusions. Unknown origin must be an explicit state.

## Model-selection matrix (hypotheses, not measured performance)

| Candidate | Strength | Main risk | Decision |
|---|---|---|---|
| L2 multinomial Logistic Regression / shrinkage LDA | Low variance, explainable, good small-data sanity check | Linear separability | **Primary baseline pair** |
| StandardScaler + RBF SVM | Nonlinear small-data challenger | Needs tuning/calibration | **Primary challenger** |
| Regularized Random Forest / ExtraTrees | Nonlinear, feature attribution | Overfitting with 86 grouped observations | **Secondary challenger** |
| PLS-DA | Projection suited to collinear e-nose features | Component count tuning inside CV | Research comparator |
| Linear SVM, QDA, kNN | Simple comparators | QDA covariance unstable; kNN scaling/batch drift | Limited benchmark |
| Gradient boosting / XGBoost / LightGBM / CatBoost | Captures nonlinear interactions | Higher tuning/data need | Optional if repeated folds justify |
| ROCKET/MiniROCKET, 1D CNN, CNN-LSTM, LSTM/GRU | Raw sequence temporal patterns | ~5 collecting points and 86 acquisition units inadequate | **Deferred pending new data** |

No model may be declared 'best' before group-aware cross-batch scores and
prospective held-out data demonstrate superiority. Simpler alternatives are
preferred if performance is statistically indistinguishable.

## Mandatory evaluation protocol

1. Build a frozen data manifest: `source_sha256`, acquisition file, sample
   code, roast, origin taxonomy, batch, instrument/firmware version, date,
   **physical specimen ID and session ID** (new data). Count genuine independent
   samples; with present metadata, batch is only an imperfect proxy.
2. Gate failed CSVs prior to extraction. Keep metadata out of `X`: never
   include sample_id, roast_level, origin, batch_id, filename, source hash,
   sample_idx or elapsed uptime as classifier inputs.
3. Split by `batch_id` with LeaveOneGroupOut on B32–B35 as an initial
   stress test; report four separate fold metrics and **class coverage**.
   Do not interpret it as a final prospective test because development already
   inspected these batches and their labels/classes vary.
4. Refit StandardScaler, imputer, feature selection, PCA/PLS, calibration and
   model using **training fold only**, encapsulated in sklearn Pipeline.
   Tune C, gamma, trees, dimension and abstention thresholds inside an inner
   grouped CV **only when enough groups exist**. If not, predefine small
   hyperparameter grids and report uncertainty honestly.
5. Score at **file/specimen level**, not by pooling all correlated cycles as
   independent samples. For roast-only: accuracy, balanced accuracy,
   macro-F1, per-class recall/F1, confusion matrix; also calibration error,
   Brier/log loss if calibrated, abstention coverage/risk, inference latency,
   model bytes, reproducibility.
6. Run ablation: (a) collecting mean only, (b) baseline-relative response,
   (c) slope/SD, (d) include/exclude temperature/humidity, (e) combine cycles,
   (f) early-cycle decision with strict no look-ahead. Quantify sensor drift,
   repeated-file effects and batch shift.
7. Freeze test policy before training. Collect new prospective batch(es) and
   known physical specimen/session IDs; never use the final holdout to select
   features, thresholds or hyperparameters.
8. For known-origin, report performance only across origins with adequate
   training/holdout representation. Origin held out entirely cannot be scored
   as a correct known-origin multiclass prediction. Use an explicit unknown
   detection/rejection test separately.

## Model artifact and promotion contract

The deployable artifact must package: model + fitted preprocessing pipeline,
`feature_schema_version`, **ordered feature names**, ADC order, missing-value
policy, class label mapping, sensor/firmware compatibility, threshold config,
source dataset hashes, training revision, Python/library versions and tests.

Go/no-go: no data leakage, reproducible extraction, batch-level evaluation
reported, no unsupported origin classes, calibrated abstain/failure path,
interpreter matches training within tolerance, memory/latency benchmark on
actual Raspberry Pi 5, and a fresh prospective test meeting a **pre-agreed**
quality target. Numerical acceptance targets must be agreed against the
business error cost and collected baseline; do not fabricate performance.

## Relevant external literature and official references

- 2023 coffee E-nose study: PLSR, LDA and ANN were explored; its outcomes
  do not transfer to our sensor arrangement or batches.
  https://doi.org/10.1016/j.snb.2023.134229
- 2024 roast-profile e-nose study with TGS sensors and ANN; its high published
  cross-validation scores are **not** independent evidence for RoastSense.
  https://doi.org/10.1016/j.sbsr.2024.100632
- 2025 food E-nose review: drift, standardization and field reliability remain
  challenges despite high performance in some controlled studies.
  https://pmc.ncbi.nlm.nih.gov/articles/PMC12301011/
- Official scikit-learn GroupKFold/LeaveOneGroupOut:
  https://scikit-learn.org/stable/modules/cross_validation.html
- Official scikit-learn leakage avoidance and Pipeline:
  https://scikit-learn.org/stable/common_pitfalls.html
