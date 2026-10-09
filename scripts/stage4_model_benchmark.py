"""Benchmark klasifikasi roast MQ3 secara eksploratori, Leave-One-Batch-Out.

Sumber wajib Stage3 v2 dan manifest SHA256. Hanya tujuh grup fitur a priori,
fit scaler/model di training fold. Tidak memilih/mengirim model produksi.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import platform
from pathlib import Path
from time import perf_counter

import numpy as np
import pandas as pd
import sklearn
from sklearn.discriminant_analysis import LinearDiscriminantAnalysis
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import ExtraTreesClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    balanced_accuracy_score, confusion_matrix, f1_score,
    precision_recall_fscore_support,
)
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT = Path(__file__).resolve().parents[1]
INPUT = ROOT / "data" / "processed" / "stage3_v2"
EXCLUSIONS = ROOT / "data" / "analysis" / "bench_only_exclusions.csv"
S2_MANIFEST = ROOT / "data" / "analysis" / "stage2_v2" / "file_manifest.csv"
BATCHES = ("B32", "B33", "B34", "B35")
LABELS = ("dark", "light", "medium")
SEED = 20261009
OUTPUT_FILES = ("fold_metrics.csv", "predictions.csv", "model_ranking.csv",
                "class_metrics.csv", "config.json", "summary.json")


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_snapshot(input_dir: Path = INPUT, stage2: Path = S2_MANIFEST,
                  exclusions: Path = EXCLUSIONS) -> tuple[pd.DataFrame, dict, dict]:
    frame_file = input_dir / "candidate_features82.csv"
    groups_file = input_dir / "feature_groups.json"
    freeze_file = input_dir / "snapshot.json"
    group_info = json.loads(groups_file.read_text(encoding="utf-8"))
    frozen = json.loads(freeze_file.read_text(encoding="utf-8"))
    frame = pd.read_csv(frame_file)
    stage2_frame = pd.read_csv(stage2)
    exclusion = pd.read_csv(exclusions, dtype=str)
    if frozen["input_manifest_sha256"] != sha256(stage2) or (
        frozen["bench_exclusions_sha256"] != sha256(exclusions)
    ):
        raise ValueError("Frozen snapshot SHA256 changed")
    expected = {item["source_file"]: item["source_sha256"]
                for item in frozen["raw_files"]}
    if len(frame) != len(expected) or len(set(frame["source_file"])) != len(frame):
        raise ValueError("Row count/filename differs from frozen snapshot")
    actual = dict(zip(frame["source_file"], frame["source_sha256"]))
    if actual != expected:
        raise ValueError("Candidate features do not match frozen filenames/hashes")
    stage2_by_file = stage2_frame.set_index("source_file")
    for row in frame.itertuples(index=False):
        if row.source_file not in stage2_by_file.index or (
            stage2_by_file.loc[row.source_file, "training_status"] !=
            "candidate_labels_unverified"
        ):
            raise ValueError("Candidate row not approved by Stage2 provenance")
        for key_stage3, key_stage2 in (
            ("source_sha256", "source_sha256"),
            ("sample_id", "sample_id"),
            ("roast_level", "roast_level"),
            ("origin", "origin"),
            ("batch_id", "batch"),
        ):
            if str(getattr(row, key_stage3)) != str(
                stage2_by_file.loc[row.source_file, key_stage2]
            ):
                raise ValueError(
                    f"Stage3/Stage2 metadata mismatch: {row.source_file}/{key_stage3}"
                )
    excluded = set(exclusion["source_file"].astype(str))
    if set(frame["source_file"]) & excluded:
        raise ValueError("Clean-air manifest included in features")
    if frame["sample_id"].str.upper().str.endswith("-CAW").any() or (
        frame["batch_id"].eq("B37").any()
    ):
        raise ValueError("CAW/B37 clean air leaked into coffee cohort")
    if not frame["batch_id"].isin(BATCHES).all():
        raise ValueError("Unknown batch in cohort")
    if not frame["roast_level"].isin(LABELS).all():
        raise ValueError("Unexpected roast labels")
    actual_features = [name for name in frame if name.startswith("f_")]
    if group_info["feature_order"] != frozen["feature_order"] or (
        actual_features != frozen["feature_order"]
    ):
        raise ValueError("Feature order changed")
    if not all(name.startswith("f_") for group in group_info["groups"].values()
               for name in group):
        raise ValueError("Non-feature metadata/label in predictor group")
    for group in group_info["groups"].values():
        if not group or not set(group).issubset(actual_features):
            raise ValueError("Feature group includes unapproved fields")
    if not np.isfinite(frame[actual_features].to_numpy(dtype=float)).all():
        raise ValueError("Nonfinite predictors")
    return frame, group_info["groups"], frozen


def model_definitions() -> dict[str, object]:
    """Single fixed hyperparameter per model, no grid search / test tuning."""
    return {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "logistic_l2": make_pipeline(
            StandardScaler(), LogisticRegression(
                C=1.0, max_iter=2500, random_state=SEED,
            )
        ),
        "lda_shrinkage": make_pipeline(
            StandardScaler(),
            LinearDiscriminantAnalysis(solver="lsqr", shrinkage="auto"),
        ),
        "linear_svm": make_pipeline(
            StandardScaler(), SVC(kernel="linear", C=1.0)
        ),
        "rbf_svm": make_pipeline(
            StandardScaler(), SVC(kernel="rbf", C=1.0, gamma="scale")
        ),
        "knn5": make_pipeline(
            StandardScaler(), KNeighborsClassifier(n_neighbors=5)
        ),
        "random_forest": RandomForestClassifier(
            n_estimators=80, max_features="sqrt", min_samples_leaf=2,
            random_state=SEED, n_jobs=1,
        ),
        "extra_trees": ExtraTreesClassifier(
            n_estimators=80, max_features="sqrt", min_samples_leaf=2,
            random_state=SEED, n_jobs=1,
        ),
    }


def benchmark(frame: pd.DataFrame, groups: dict[str, list[str]],
              models: dict[str, object] | None = None
              ) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if models is None:
        models = model_definitions()
    if not set(LABELS).issubset(frame["roast_level"]):
        raise ValueError("Missing roast class across cohort")
    fold_rows = []
    pred_rows = []
    batches = frame["batch_id"].astype(str).to_numpy()
    y = frame["roast_level"].astype(str).to_numpy()
    if set(batches) != set(BATCHES):
        raise ValueError("LOBO requires B32 through B35")
    for group_name, columns in groups.items():
        if not columns or not set(columns).issubset(frame.columns) or any(
            not name.startswith("f_") for name in columns
        ):
            raise ValueError(f"Invalid/label-leaking feature group {group_name}")
        X = frame[columns].to_numpy(dtype=float)
        for holdout in BATCHES:
            train = batches != holdout
            test = batches == holdout
            if not train.any() or not test.any() or np.any(train & test):
                raise ValueError("Invalid group split")
            if not set(LABELS).issubset(set(y[train])) or not set(LABELS).issubset(
                set(y[test])
            ):
                raise ValueError(f"Fold missing class: {holdout}")
            for model_name, prototype in models.items():
                from sklearn.base import clone
                model = clone(prototype)
                t0 = perf_counter()
                model.fit(X[train], y[train])
                fit_ms = (perf_counter() - t0) * 1000
                t1 = perf_counter()
                prediction = model.predict(X[test])
                inference_ms = (perf_counter() - t1) * 1000
                macro = f1_score(y[test], prediction, labels=list(LABELS),
                                 average="macro", zero_division=0)
                bal = balanced_accuracy_score(y[test], prediction)
                matrix = confusion_matrix(y[test], prediction, labels=LABELS)
                fold_rows.append({
                    "group": group_name, "feature_count": len(columns),
                    "model": model_name, "held_out_batch": holdout,
                    "train_files": int(train.sum()), "test_files": int(test.sum()),
                    "train_batches": "|".join(
                        batch for batch in BATCHES if batch != holdout
                    ),
                    "macro_f1": float(macro),
                    "balanced_accuracy": float(bal),
                    "fit_ms": float(fit_ms),
                    "predict_ms": float(inference_ms),
                    "confusion_matrix_D_L_M": json.dumps(matrix.tolist()),
                    "labels_order": "|".join(LABELS),
                })
                for idx, pred in zip(np.flatnonzero(test), prediction):
                    pred_rows.append({
                        "group": group_name, "model": model_name,
                        "held_out_batch": holdout,
                        "source_file": frame.iloc[idx]["source_file"],
                        "source_sha256": frame.iloc[idx]["source_sha256"],
                        "true_roast_ui_unverified": y[idx],
                        "predicted_roast": str(pred),
                    })
    folds = pd.DataFrame(fold_rows)
    predictions = pd.DataFrame(pred_rows)
    ranking = folds.groupby(["group", "model", "feature_count"], as_index=False).agg(
        macro_f1_mean=("macro_f1", "mean"),
        macro_f1_std_folds=("macro_f1", "std"),
        balanced_accuracy_mean=("balanced_accuracy", "mean"),
        balanced_accuracy_std_folds=("balanced_accuracy", "std"),
        median_fit_ms=("fit_ms", "median"),
        median_predict_ms=("predict_ms", "median"),
        folds=("held_out_batch", "nunique"),
    ).sort_values(
        ["macro_f1_mean", "balanced_accuracy_mean", "group", "model"],
        ascending=[False, False, True, True],
    ).reset_index(drop=True)
    return folds, predictions, ranking


def per_class_report(predictions: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for (group, model, batch), data in predictions.groupby(
        ["group", "model", "held_out_batch"], sort=True,
    ):
        precision, recall, f1, support = precision_recall_fscore_support(
            data["true_roast_ui_unverified"],
            data["predicted_roast"],
            labels=list(LABELS),
            zero_division=0,
        )
        for i, label in enumerate(LABELS):
            rows.append({
                "group": group, "model": model,
                "held_out_batch": batch, "class": label,
                "precision": float(precision[i]),
                "recall": float(recall[i]),
                "f1": float(f1[i]),
                "support": int(support[i]),
            })
    return pd.DataFrame(rows)


def save(output_dir: Path, folds: pd.DataFrame, predictions: pd.DataFrame,
         ranking: pd.DataFrame, config: dict, summary: dict) -> None:
    if output_dir.exists() and any(
        item.name != "README.md" for item in output_dir.iterdir()
    ):
        raise FileExistsError("Output directory already exists; use a NEW run id")
    if output_dir.resolve() == ROOT / "data" / "raw" or (
        ROOT / "data" / "raw" in output_dir.resolve().parents
    ):
        raise ValueError("Cannot write benchmark into raw")
    output_dir.mkdir(parents=True, exist_ok=True)
    for name, data in (
        ("fold_metrics.csv", folds), ("predictions.csv", predictions),
        ("model_ranking.csv", ranking),
        ("class_metrics.csv", per_class_report(predictions)),
    ):
        data.to_csv(output_dir / name, index=False, float_format="%.12g")
    for name, data in (("config.json", config), ("summary.json", summary)):
        (output_dir / name).write_text(
            json.dumps(data, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input-dir", type=Path, default=INPUT)
    parser.add_argument("--manifest", type=Path, default=S2_MANIFEST)
    parser.add_argument("--exclusions", type=Path, default=EXCLUSIONS)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    frame, groups, snapshot = load_snapshot(
        args.input_dir, args.manifest, args.exclusions
    )
    folds, predictions, ranking = benchmark(frame, groups)
    config = {
        "experiment": "stage4.LOBO.roast.exploratory.v1",
        "seed": SEED,
        "input_features_sha256": sha256(args.input_dir / "candidate_features82.csv"),
        "feature_group_sha256": sha256(args.input_dir / "feature_groups.json"),
        "stage3_snapshot_sha256": sha256(args.input_dir / "snapshot.json"),
        "stage2_manifest_sha256": sha256(args.manifest),
        "clean_air_exclusion_sha256": sha256(args.exclusions),
        "python": platform.python_version(), "sklearn": sklearn.__version__,
        "grouping": "leave-one-batch-out",
        "feature_groups": {k: len(v) for k, v in groups.items()},
        "model_definitions": {
            "dummy_prior": "prior",
            "logistic_l2": "StandardScaler + LogisticRegression C=1",
            "lda_shrinkage": "StandardScaler + LDA lsqr shrinkage=auto",
            "linear_svm": "StandardScaler + SVC linear C=1",
            "rbf_svm": "StandardScaler + SVC rbf C=1 gamma=scale",
            "knn5": "StandardScaler + KNN k=5",
            "random_forest": "RF n=80 min_leaf=2 seed fixed",
            "extra_trees": "ExtraTrees n=80 min_leaf=2 seed fixed",
        },
        "selection": "none; ranking is descriptive only, no untouched final holdout",
        "labels": list(LABELS),
        "physical_specimen_independence_verified": False,
    }
    summary = {
        "status": "EXPLORATORY_ONLY_NOT_VALIDATED_NO_MODEL_PROMOTION",
        "observations": len(frame),
        "held_out_batches": list(BATCHES),
        "groups_tested": len(groups), "models_tested": len(model_definitions()),
        "fold_fits": len(folds), "predictions": len(predictions),
        "clean_air_CAW_B37_excluded": True,
        "best_descriptive_row": ranking.iloc[0][[
            "group", "model", "feature_count", "macro_f1_mean",
            "balanced_accuracy_mean"
        ]].to_dict(),
        "warning": "All folds were inspected in this same experiment; "
                   "the highest-ranked configuration is NOT unbiased "
                   "final performance. No physical specimen IDs, prospective "
                   "test, confidence calibration or unknown rejection.",
    }
    save(args.output_dir, folds, predictions, ranking, config, summary)
    print("STAGE4_EXPLORATORY_LOBO_PASS")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
