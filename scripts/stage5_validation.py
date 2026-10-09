"""Tahap 5: QA LOBO, risk–coverage, clean-air surrogate, stress sintetik.

Eksperimen offline dan eksploratori. Tidak melatih artefak final, tidak
mengkalibrasi threshold dari test folds, dan tidak menyentuh COM5/raw.
Gunakan folder hasil BARU untuk setiap rerun.
"""

from __future__ import annotations

import argparse
from itertools import product
import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (
    accuracy_score, balanced_accuracy_score, confusion_matrix, f1_score,
    precision_recall_fscore_support,
)

from acquisition_schema import ADC_COLS
from extract_b32_features import extract_sensor_features
from stage2_dataset_audit import read_exclusions
from stage4_model_benchmark import (
    BATCHES, EXCLUSIONS, INPUT, LABELS, ROOT, S2_MANIFEST, SEED, load_snapshot,
    model_definitions, sha256,
)
from validate_acquisition import classify_rows, validate_file

BASELINE = (
    ("random_forest", "expanded82"),
    ("lda_shrinkage", "response10"),
)
# Predefined diagnostics only, never retrospectively selected as deployment threshold.
THRESHOLDS = (0.0, 0.5, 0.6, 0.7, 0.8, 0.9)
GAINS = (0.90, 0.95, 1.05, 1.10)
OUTFILES = (
    "heldout_probabilities.csv", "risk_coverage.csv", "class_metrics.csv",
    "calibration_diagnostic.csv", "batch_bootstrap.csv",
    "clean_air_surrogate.csv", "clean_air_held.csv", "gain_stress.csv",
    "input_audit.csv", "config.json", "summary.json",
)


def check_inputs(frame: pd.DataFrame, groups: dict, stage2: Path,
                 exclusions: Path, raw: Path) -> tuple[pd.DataFrame, dict]:
    source = pd.read_csv(stage2)
    excluded = read_exclusions(exclusions)
    subset = source.loc[source["training_status"].eq(
        "excluded_bench_clean_air"
    )].copy()
    if set(subset["source_file"]) != set(excluded):
        raise ValueError("Stage2 clean-air inventory differs from exclusion manifest")
    if not (subset["sample_id"].str.endswith("-CAW") |
            subset["batch"].eq("B37")).all():
        raise ValueError("Non-CAW/non-B37 in clean-air manifest requires review")
    if frame["sample_id"].str.endswith("-CAW").any() or frame["batch_id"].eq(
        "B37"
    ).any():
        raise ValueError("Clean air in coffee predictors")
    if set(frame["batch_id"]) != set(BATCHES):
        raise ValueError("Missing batch in LOBO input")
    for batch in BATCHES:
        sample = frame.loc[frame["batch_id"].eq(batch)]
        if set(sample["roast_level"]) != set(LABELS):
            raise ValueError(f"Class missing in batch {batch}")
    for model_name, group_name in BASELINE:
        if model_name not in model_definitions() or group_name not in groups:
            raise ValueError("Comparator changed")
    if not raw.is_dir():
        raise ValueError("Raw path not available for independent clean-air audit")
    if not all((raw / name).is_file() for name in excluded):
        raise ValueError("Clean-air files unavailable; cannot silently omit")
    return subset, excluded


def fit_coffee_model(model_name: str, X: np.ndarray, y: np.ndarray):
    estimator = clone(model_definitions()[model_name])
    estimator.fit(X, y)
    if not hasattr(estimator, "predict_proba"):
        raise ValueError("Comparator needs predict_proba")
    return estimator


def predict_probabilities(estimator, X: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    probs = estimator.predict_proba(X)
    if list(estimator.classes_) != list(LABELS) or (
        probs.shape[1] != len(LABELS)
    ):
        raise ValueError("Unexpected label order in predict_proba")
    if not np.isfinite(probs).all() or (
        (probs < 0).any() or (probs > 1).any()
    ) or not np.allclose(probs.sum(axis=1), 1, atol=1e-6):
        raise ValueError("Non-probabilistic predictions")
    labels = np.array(LABELS)[probs.argmax(axis=1)]
    return labels, probs


def perturbed_feature_matrix(X: np.ndarray, features: list[str],
                             gain: float) -> np.ndarray:
    """Synthetic common-mode ADC gain *approximation* on extracted features.

    No physical gas/valve response simulated. Relative responses are kept
    invariant under positive gain when absolute baseline > 1. Mean/SD/slope
    features from ADC count scale with the ADC gain. Ambient unchanged.
    """
    if not 0.5 <= gain <= 1.5:
        raise ValueError("Gain outside bounded stress test")
    modified = X.copy()
    for i, name in enumerate(features):
        if name.startswith(("f_temperature_", "f_humidity_")) or (
            "_relative_response_" in name
        ):
            continue
        if not name.startswith("f_"):
            raise ValueError("Metadata in model input")
        modified[:, i] *= gain
    return modified


def lo_bo_diagnostics(frame: pd.DataFrame, groups: dict) -> tuple[pd.DataFrame, pd.DataFrame]:
    out = []
    stress = []
    y = frame["roast_level"].to_numpy(dtype=str)
    batches = frame["batch_id"].to_numpy(dtype=str)
    for model_name, group_name in BASELINE:
        features = groups[group_name]
        X = frame[features].to_numpy(dtype=float)
        for batch in BATCHES:
            train = batches != batch
            test = batches == batch
            if not set(LABELS).issubset(y[train]) or not set(LABELS).issubset(y[test]):
                raise ValueError("Missing class within fold")
            estimator = fit_coffee_model(model_name, X[train], y[train])
            predict, probs = predict_probabilities(estimator, X[test])
            held = frame.loc[test]
            for idx, (_, rec) in enumerate(held.iterrows()):
                out.append({
                    "model": model_name, "group": group_name, "held_out_batch": batch,
                    "train_batches": "|".join(b for b in BATCHES if b != batch),
                    "source_file": rec["source_file"],
                    "source_sha256": rec["source_sha256"],
                    "sample_id": rec["sample_id"],
                    "true_roast_ui_unverified": y[test][idx],
                    "predicted_roast": str(predict[idx]),
                    "correct": bool(predict[idx] == y[test][idx]),
                    "confidence_uncalibrated": float(probs[idx].max()),
                    **{f"prob_{label}": float(probs[idx, j])
                       for j, label in enumerate(LABELS)},
                })
            for gain in GAINS:
                perturbed = perturbed_feature_matrix(X[test], features, gain)
                changed, changed_probs = predict_probabilities(estimator, perturbed)
                stress.append({
                    "model": model_name, "group": group_name,
                    "held_out_batch": batch, "gain": gain,
                    "test_files": int(test.sum()),
                    "changed_predictions": int((changed != predict).sum()),
                    "changed_fraction": float(np.mean(changed != predict)),
                    "mean_abs_delta_max_confidence": float(
                        np.mean(np.abs(changed_probs.max(axis=1) -
                                       probs.max(axis=1)))
                    ),
                    "note": "SYNTHETIC_FEATURE_GAIN_NOT_PHYSICAL_SENSOR_DRIFT",
                })
    oof = pd.DataFrame(out)
    if oof.groupby(["model", "source_file"]).size().ne(1).any():
        raise ValueError("One held-out prediction per model/file required")
    if set(oof["held_out_batch"]) != set(BATCHES):
        raise ValueError("Missing LOBO fold")
    return oof, pd.DataFrame(stress)


def coverage_tables(oof: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    risk_rows = []
    class_rows = []
    cal_rows = []
    for (model, group), data in oof.groupby(["model", "group"], sort=True):
        scopes = [("ALL_LOBO", data)] + [
            (batch, data.loc[data["held_out_batch"].eq(batch)])
            for batch in BATCHES
        ]
        for scope, piece in scopes:
            confidence = piece["confidence_uncalibrated"].to_numpy(dtype=float)
            for threshold in THRESHOLDS:
                accepted = piece.loc[confidence >= threshold]
                if len(accepted):
                    accuracy = accuracy_score(
                        accepted["true_roast_ui_unverified"],
                        accepted["predicted_roast"],
                    )
                    macro = f1_score(
                        accepted["true_roast_ui_unverified"],
                        accepted["predicted_roast"],
                        labels=LABELS, average="macro", zero_division=0,
                    )
                    wrong = int((~accepted["correct"]).sum())
                else:
                    accuracy = macro = float("nan")
                    wrong = 0
                risk_rows.append({
                    "model": model, "group": group, "scope": scope,
                    "threshold_prespecified": threshold,
                    "all_files": len(piece), "accepted_files": len(accepted),
                    "coverage": len(accepted) / len(piece),
                    "accepted_correct": len(accepted) - wrong,
                    "accepted_wrong": wrong,
                    "accepted_accuracy": accuracy,
                    "accepted_error_risk": (
                        1 - accuracy if len(accepted) else float("nan")
                    ),
                    "accepted_macro_f1": macro,
                    "warning": "test-fold descriptive, NOT calibrated threshold",
                })
        for batch, piece in data.groupby("held_out_batch", sort=True):
            precision, recall, f1, support = precision_recall_fscore_support(
                piece["true_roast_ui_unverified"], piece["predicted_roast"],
                labels=list(LABELS), zero_division=0,
            )
            for i, cls in enumerate(LABELS):
                class_rows.append({
                    "model": model, "group": group, "batch": batch, "class": cls,
                    "precision": float(precision[i]),
                    "recall": float(recall[i]), "f1": float(f1[i]),
                    "support": int(support[i]),
                })
        for lo, hi in ((0.0, 0.5), (0.5, 0.6), (0.6, 0.7),
                       (0.7, 0.8), (0.8, 0.9), (0.9, 1.00001)):
            bin_data = data.loc[
                (data["confidence_uncalibrated"] >= lo) &
                (data["confidence_uncalibrated"] < hi)
            ]
            if len(bin_data):
                cal_rows.append({
                    "model": model, "group": group, "conf_bin_low": lo,
                    "conf_bin_high": min(hi, 1.0),
                    "files": len(bin_data),
                    "mean_uncalibrated_confidence": float(
                        bin_data["confidence_uncalibrated"].mean()
                    ),
                    "observed_accuracy_unverified_label": float(
                        bin_data["correct"].mean()
                    ),
                })
    return pd.DataFrame(risk_rows), pd.DataFrame(class_rows), pd.DataFrame(cal_rows)


def cluster_bootstrap(oof: pd.DataFrame) -> pd.DataFrame:
    """All 4^4 batch resamples, exhaustive cluster bootstrap descriptive CI.

    Only four distinct clusters; bounds are NOT strong inferential guarantees.
    """
    rows = []
    repeats = list(product(BATCHES, repeat=len(BATCHES)))
    for (model, group), data in oof.groupby(["model", "group"], sort=True):
        per_batch = {b: data.loc[data["held_out_batch"].eq(b)] for b in BATCHES}
        macro, balanced = [], []
        for selection in repeats:
            repeated = pd.concat([per_batch[b] for b in selection], ignore_index=True)
            yt = repeated["true_roast_ui_unverified"]
            yp = repeated["predicted_roast"]
            macro.append(float(f1_score(
                yt, yp, labels=LABELS, average="macro", zero_division=0,
            )))
            balanced.append(float(balanced_accuracy_score(yt, yp)))
        observed = f1_score(
            data["true_roast_ui_unverified"], data["predicted_roast"],
            labels=LABELS, average="macro", zero_division=0,
        )
        rows.append({
            "model": model, "group": group,
            "pooled_oof_macro_f1": float(observed),
            "batch_bootstrap_macro_f1_p025": float(np.percentile(macro, 2.5)),
            "batch_bootstrap_macro_f1_p975": float(np.percentile(macro, 97.5)),
            "batch_bootstrap_balanced_p025": float(np.percentile(balanced, 2.5)),
            "batch_bootstrap_balanced_p975": float(np.percentile(balanced, 97.5)),
            "unique_batches": 4, "batch_resamples": len(repeats),
            "interpretation": "DESCRIPTIVE_ONLY_4_CLUSTERS_LABELS_UNVERIFIED",
        })
    return pd.DataFrame(rows)


def clean_air_features(subset: pd.DataFrame, exclusions: dict,
                       raw_dir: Path) -> tuple[pd.DataFrame, pd.DataFrame]:
    valid, held = [], []
    for record in subset.itertuples(index=False):
        file = raw_dir / record.source_file
        if sha256(file) != exclusions[record.source_file]:
            raise ValueError(f"Clean air SHA256 changed: {record.source_file}")
        issues = validate_file(file)
        if issues:
            held.append({
                "source_file": record.source_file,
                "source_sha256": record.source_sha256,
                "reason": "Canonical validator: " + " | ".join(issues),
            })
            continue
        frame = pd.read_csv(file)
        mask, _, _ = classify_rows(frame)
        try:
            features = extract_sensor_features(
                frame.loc[mask].copy(), include_collect_mean=True
            )
        except ValueError as error:
            held.append({
                "source_file": record.source_file,
                "source_sha256": record.source_sha256,
                "reason": str(error),
            })
            continue
        valid.append({
            "source_file": record.source_file, "source_sha256": record.source_sha256,
            "batch": record.batch,
            "true_medium_operator": "clean_air",
            **features,
        })
    return pd.DataFrame(valid), pd.DataFrame(held, columns=[
        "source_file", "source_sha256", "reason",
    ])


def clean_air_surrogate(frame: pd.DataFrame, groups: dict,
                        clean_air: pd.DataFrame) -> pd.DataFrame:
    """Separate smoke test. Train on all coffee; NEVER use clean air to tune."""
    if clean_air.empty:
        raise ValueError("No clean-air samples meet strict feature contract")
    rows = []
    for model_name, group_name in BASELINE:
        features = groups[group_name]
        est = fit_coffee_model(
            model_name, frame[features].to_numpy(dtype=float),
            frame["roast_level"].to_numpy(dtype=str),
        )
        labels, probs = predict_probabilities(
            est, clean_air[features].to_numpy(dtype=float)
        )
        for index, record in enumerate(clean_air.itertuples(index=False)):
            rows.append({
                "model": model_name, "group": group_name,
                "source_file": record.source_file,
                "source_sha256": record.source_sha256,
                "batch": record.batch,
                "true_medium": "clean_air",
                "predicted_coffee_roast_if_no_rejection": str(labels[index]),
                "confidence_uncalibrated": float(probs[index].max()),
                "would_abstain_t06": bool(probs[index].max() < 0.6),
                "would_abstain_t08": bool(probs[index].max() < 0.8),
                "warning": "NOT_A_UNKNOWN_COFFEE_VALIDATION",
            })
    return pd.DataFrame(rows)


def save_output(directory: Path, artifacts: dict) -> None:
    dest = directory.resolve()
    raw = (ROOT / "data" / "raw").resolve()
    if raw == dest or raw in dest.parents:
        raise ValueError("Cannot write results to raw data")
    if dest.exists() and any(dest.iterdir()):
        raise FileExistsError("Output already exists; create a new version")
    dest.mkdir(parents=True, exist_ok=True)
    for name in OUTFILES:
        value = artifacts[name]
        if name.endswith(".json"):
            (dest / name).write_text(
                json.dumps(value, ensure_ascii=False, indent=2,
                           allow_nan=False) + "\n", encoding="utf-8",
            )
        else:
            value.to_csv(dest / name, index=False, float_format="%.12g")


def generate(input_dir: Path = INPUT, manifest: Path = S2_MANIFEST,
             exclusions: Path = EXCLUSIONS,
             raw_dir: Path = ROOT / "data" / "raw") -> tuple[dict, dict]:
    frame, groups, frozen = load_snapshot(input_dir, manifest, exclusions)
    subset, excluded = check_inputs(frame, groups, manifest, exclusions, raw_dir)
    oof, stress = lo_bo_diagnostics(frame, groups)
    risk, classes, calibration = coverage_tables(oof)
    bootstrap = cluster_bootstrap(oof)
    clean_valid, clean_held = clean_air_features(subset, excluded, raw_dir)
    clean_results = clean_air_surrogate(frame, groups, clean_valid)
    # Audit real cohort's physical independence: sample code is not specimen ID.
    count_per_batch = frame.groupby(["sample_id", "batch_id"]).size()
    repeated_ids = frame.groupby("sample_id")["batch_id"].nunique()
    audit = pd.DataFrame([{
        "batch": b, "total_files": int(frame["batch_id"].eq(b).sum()),
        **{label + "_files": int(
            ((frame["batch_id"] == b) & (frame["roast_level"] == label)).sum()
        ) for label in LABELS},
    } for b in BATCHES])
    config = {
        "id": "stage5.validation.exploratory.v1",
        "seed": SEED, "comparators_posthoc_from_stage4": list(BASELINE),
        "confidence_thresholds_prespecified": list(THRESHOLDS),
        "feature_gain_perturbations": list(GAINS),
        "snapshot_sha256": sha256(input_dir / "snapshot.json"),
        "candidate_features_sha256": sha256(input_dir / "candidate_features82.csv"),
        "stage2_manifest_sha256": sha256(manifest),
        "clean_air_exclusions_sha256": sha256(exclusions),
        "labels_order": list(LABELS),
        "no_threshold_optimization": True,
        "calibration_fitted": False,
        "final_model_fitted_or_saved": False,
    }
    summary = {
        "status": "EXPLORATORY_STAGE5_NO_GO_PROSPECTIVE_UNAVAILABLE",
        "coffee_candidate_files": len(frame),
        "oof_predictions": len(oof),
        "clean_air_known_files": len(subset),
        "clean_air_strict_valid": len(clean_valid),
        "clean_air_feature_hold": clean_held["source_file"].tolist(),
        "sample_codes": int(frame["sample_id"].nunique()),
        "codes_in_multiple_batches": int((repeated_ids > 1).sum()),
        "repeated_code_batch_cells": int((count_per_batch > 1).sum()),
        "physical_specimen_ids_verified": False,
        "roast_labels_verified": False,
        "confidence_calibrated": False,
        "unknown_coffee_tested": False,
        "prospective_external_batch_tested": False,
        "models_promoted": 0,
        "warning": "Risk/coverage uses held-out folds but prespecified thresholds "
                   "were not calibrated. Comparators chosen after inspecting "
                   "Stage4 LOBO; no unbiased final estimate. Clean air is NOT "
                   "an unknown coffee class; only four batch clusters.",
    }
    artifacts = dict(zip(OUTFILES, (
        oof, risk, classes, calibration, bootstrap,
        clean_results, clean_held, stress, audit, config, summary,
    )))
    return artifacts, summary


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    artifacts, summary = generate()
    save_output(args.output_dir, artifacts)
    print("STAGE5_EXPLORATORY_VALIDATION_PASS")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
