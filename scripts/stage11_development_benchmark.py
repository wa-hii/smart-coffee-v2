"""Fixed-roster retrospective development-only benchmark.

This is NOT a blind test. All B32–B35 measurements have been seen during
Stages 4–10. All transformations (scaling) are fitted inside each fold.
No .joblib export or hardware interaction.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
    precision_recall_fscore_support,
)

from stage4_model_benchmark import (
    BATCHES, LABELS, INPUT, ROOT, load_snapshot, model_definitions, sha256,
)

# Frozen for this experiment before the new run; algorithms appeared in earlier
# benchmarks, therefore comparison is not retrospectively unbiased.
ROSTER = (
    ("dummy_prior", "response10"),
    ("logistic_l2", "response10"),
    ("lda_shrinkage", "response10"),
    ("random_forest", "expanded82"),
)


def compare() -> tuple[pd.DataFrame, pd.DataFrame, dict]:
    frame, groups, _ = load_snapshot()
    targets = frame["roast_level"].to_numpy(str)
    batch = frame["batch_id"].to_numpy(str)
    if len(frame) != 83 or set(batch) != set(BATCHES):
        raise ValueError("Frozen development cohort changed")
    if frame["source_file"].duplicated().any() or frame["source_sha256"].duplicated().any():
        raise ValueError("Duplicate independent acquisition IDs or bytes")
    model_defs = model_definitions()
    folds = []
    predictions = []
    for name, group in ROSTER:
        feats = groups[group]
        if any(not feat.startswith("f_") for feat in feats):
            raise ValueError("Label leakage in feature group")
        X = frame[feats].to_numpy(float)
        if not np.isfinite(X).all():
            raise ValueError("Nonfinite predictors")
        for held in BATCHES:
            tr = batch != held
            te = batch == held
            if not set(LABELS).issubset(targets[tr]) or not set(LABELS).issubset(targets[te]):
                raise ValueError("All roast classes required in all folds")
            model = clone(model_defs[name])
            model.fit(X[tr], targets[tr])
            pred = model.predict(X[te])
            matrix = confusion_matrix(targets[te], pred, labels=LABELS)
            folds.append({
                "model": name, "feature_group": group,
                "held_out_batch": held, "train_files": int(tr.sum()),
                "test_files": int(te.sum()),
                "accuracy_unverified": float(accuracy_score(targets[te], pred)),
                "macro_f1_unverified": float(f1_score(targets[te], pred,
                    labels=LABELS, average="macro", zero_division=0)),
                "balanced_accuracy_unverified": float(balanced_accuracy_score(targets[te], pred)),
                "confusion_D_L_M": json.dumps(matrix.tolist()),
            })
            indices = np.flatnonzero(te)
            predictions.extend({
                "model": name, "feature_group": group,
                "held_out_batch": held,
                "source_file": frame.iloc[idx]["source_file"],
                "source_sha256": frame.iloc[idx]["source_sha256"],
                "roast_from_ui_unverified": targets[idx],
                "predicted_roast": str(got),
            } for idx, got in zip(indices, pred))
    df = pd.DataFrame(folds)
    pred = pd.DataFrame(predictions)
    summary = {
        "status": "DEVELOPMENT_COMPARISON_ONLY_NOT_BLIND",
        "model_promotion_allowed": False,
        "tested_prior_historical_data": True,
        "independent_specimen_ids_available": False,
        "fold_group": "UI_batch_id_NOT_VERIFIED_PHYSICAL_SESSION",
        "unit_of_observation": "one five-cycle acquisition CSV",
        "dev_files": len(frame), "folds_per_model": 4,
        "roster_fixed_for_stage11": [list(pair) for pair in ROSTER],
        "origin_model_not_approved": True,
        "sealed_final_holdout_available": False,
        "source_feature_snapshot_sha256": sha256(INPUT / "candidate_features82.csv"),
        "comparison": [],
    }
    for name, group in ROSTER:
        subset = pred.loc[pred["model"].eq(name)]
        one = df.loc[df["model"].eq(name)]
        if len(subset) != len(frame) or subset["source_file"].duplicated().any():
            raise ValueError("Missing or repeated OOF predictions")
        y = subset["roast_from_ui_unverified"].to_numpy(str)
        p = subset["predicted_roast"].to_numpy(str)
        precision, recall, f1, support = precision_recall_fscore_support(
            y, p, labels=LABELS, zero_division=0)
        summary["comparison"].append({
            "model": name, "features": group,
            "mean_fold_macro_f1": float(one["macro_f1_unverified"].mean()),
            "pooled_macro_f1": float(f1_score(y, p, labels=LABELS, average="macro", zero_division=0)),
            "pooled_balanced_accuracy": float(balanced_accuracy_score(y, p)),
            "correct_files": int((y == p).sum()),
            "total_files": len(frame),
            "per_class_recall": {label: float(v) for label, v in zip(LABELS, recall)},
            "per_class_support": {label: int(v) for label, v in zip(LABELS, support)},
        })
    return df, pred, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    dst = args.output_dir.resolve()
    raw = (ROOT / "data/raw").resolve()
    if dst == raw or raw in dst.parents or dst.exists():
        raise ValueError("Output must be fresh derived directory outside data/raw")
    metrics, preds, summary = compare()
    dst.mkdir(parents=True)
    metrics.to_csv(dst / "development_fold_metrics.csv", index=False, float_format="%.12g")
    preds.to_csv(dst / "development_oof_predictions.csv", index=False)
    (dst / "summary.json").write_text(
        json.dumps(summary, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    print("STAGE11_DEVELOPMENT_COMPARISON_PASS_NOT_BLIND")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
