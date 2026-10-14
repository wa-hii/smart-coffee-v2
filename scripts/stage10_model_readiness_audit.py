"""Independent evidence audit for model promotion on MQ3 Smart Coffee data.

NO model export, firmware/Nextion access, port open, or G3 trigger.
Frozen Stage3/Stage5 are treated as candidate evidence, NOT ground truth.
All findings are exploratory; physical specimen/label verification is missing.

Example:
 python scripts/stage10_model_readiness_audit.py --output-dir results/stage10_readiness_20261014
"""
from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from math import sqrt
from pathlib import Path
import re

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score

from stage4_model_benchmark import (
    BATCHES, INPUT, LABELS, ROOT, load_snapshot, model_definitions, sha256,
)
from stage5_validation import BASELINE

STAGE5 = ROOT / "results/stage5_validation_v1"
STAGE4 = ROOT / "results/stage4_lobo_v2"
STAGE2 = ROOT / "data/analysis/stage2_v2"
EXCLUSIONS = ROOT / "data/analysis/bench_only_exclusions.csv"
OUTPUT_FILES = (
    "summary.json", "roast_confidence_diagnostics.csv",
    "origin_coverage.csv", "group_holdout_sensitivity.csv",
)


def wilson_lower(success: int, total: int, z: float = 1.959963984540054) -> float | None:
    if not total:
        return None
    p = success / total
    zz = z * z
    return float((p + zz / (2 * total) - z * sqrt(
        p * (1 - p) / total + zz / (4 * total * total)
    )) / (1 + zz / total))


def check_oof(frame: pd.DataFrame, heldout: pd.DataFrame) -> None:
    required = {"model", "group", "source_file", "source_sha256", "held_out_batch",
                "predicted_roast", "true_roast_ui_unverified",
                "confidence_uncalibrated", *(f"prob_{x}" for x in LABELS)}
    if not required.issubset(heldout.columns) or len(heldout) != len(frame) * len(BASELINE):
        raise ValueError("Stage5 OOF missing columns or records")
    if heldout.duplicated(["model", "source_file"]).any():
        raise ValueError("OOF repeated file in model")
    candidates = frame.set_index("source_file")
    expected = set(frame["source_file"])
    for model, group in BASELINE:
        fold = heldout.loc[(heldout["model"] == model) & (heldout["group"] == group)]
        if set(fold["source_file"]) != expected or len(fold) != len(expected):
            raise ValueError("OOF missing/foreign files")
        meta = candidates.loc[fold["source_file"]]
        for column, base in (("source_sha256", "source_sha256"),
                             ("held_out_batch", "batch_id"),
                             ("true_roast_ui_unverified", "roast_level")):
            if not np.array_equal(fold[column].to_numpy(str), meta[base].to_numpy(str)):
                raise ValueError(f"OOF metadata mismatch: {column}")
        if fold.apply(lambda row: row["held_out_batch"] in str(
                row["train_batches"]).split("|"), axis=1).any():
            raise ValueError("Train/test batch leakage")
        prob = fold[[f"prob_{c}" for c in LABELS]].to_numpy(dtype=float)
        if not np.isfinite(prob).all() or (prob < 0).any() or (prob > 1).any():
            raise ValueError("Invalid OOF probabilities")
        if not np.allclose(prob.sum(axis=1), 1.0, atol=1e-6):
            raise ValueError("OOF probabilities do not sum to one")
        if not np.array_equal(np.array(LABELS)[prob.argmax(axis=1)],
                              fold["predicted_roast"].to_numpy(str)):
            raise ValueError("OOF prediction/probability conflict")
        if not np.allclose(prob.max(axis=1),
                           fold["confidence_uncalibrated"].to_numpy(float),
                           atol=1e-6):
            raise ValueError("OOF max confidence mismatch")
    if set(heldout["model"]) != {m for m, _ in BASELINE}:
        raise ValueError("Unexpected model included in Stage5")


def confidence_metrics(heldout: pd.DataFrame) -> tuple[list[dict], dict]:
    rows: list[dict] = []
    summary = {}
    for model, group in BASELINE:
        data = heldout.loc[heldout["model"] == model]
        good = data["predicted_roast"] == data["true_roast_ui_unverified"]
        confidence = data["confidence_uncalibrated"].to_numpy(float)
        acc = float(good.mean())
        macro = float(f1_score(data["true_roast_ui_unverified"],
                               data["predicted_roast"], labels=list(LABELS),
                               average="macro", zero_division=0))
        # Exploratory maximum-probability ECE, NOT a calibration certificate.
        ece = 0.0
        for lo, hi in zip(np.linspace(0, 1, 11)[:-1], np.linspace(0, 1, 11)[1:]):
            mask = (confidence >= lo) & (confidence < hi if hi < 1 else confidence <= hi)
            if mask.any():
                ece += float(mask.mean() * abs(confidence[mask].mean() - good.to_numpy()[mask].mean()))
        for threshold in (0.0, 0.6, 0.8, 0.9):
            accepted = confidence >= threshold
            total = int(accepted.sum())
            correct = int(good.to_numpy()[accepted].sum())
            rows.append({
                "model": model, "features_group": group,
                "threshold_descriptive_not_calibrated": threshold,
                "accepted_n": total, "correct_n": correct,
                "wrong_n": total - correct, "coverage": total / len(data),
                "accuracy_conditional_unverified": correct / total if total else None,
                "wilson95_lower_descriptive": wilson_lower(correct, total),
            })
        summary[model] = {
            "feature_group": group, "n_files": len(data),
            "correct": int(good.sum()), "wrong": int((~good).sum()),
            "accuracy_unverified_labels": acc, "pooled_macro_f1_unverified": macro,
            "max_confidence_ece_diagnostic_only": ece,
            "mean_max_confidence": float(confidence.mean()),
        }
    return rows, summary


def sensitivity(frame: pd.DataFrame, groups: dict) -> list[dict]:
    """Counterfactual evaluation only, not unbiased final holdout.

    Disjoint acquisition files are always held out together by a
    sample code or origin. Their physical independence remains unknown.
    """
    out = []
    models = model_definitions()
    candidates = (("random_forest", "expanded82"),
                  ("lda_shrinkage", "response10"),
                  ("dummy_prior", "response10"))
    targets = (("roast_level", "sample_id", "leave_sample_code_out"),
               ("roast_level", "origin", "leave_origin_out"),
               ("origin", "batch_id", "origin_leave_batch_out"))
    for target, group_column, experiment in targets:
        y = frame[target].to_numpy(str)
        grouping = frame[group_column].to_numpy(str)
        unique = sorted(set(grouping))
        for model_name, feature_group in candidates:
            if target == "origin" and feature_group != "expanded82" and model_name != "dummy_prior":
                continue
            if target == "origin" and model_name == "dummy_prior" and feature_group != "response10":
                continue
            X = frame[groups[feature_group]].to_numpy(float)
            predicted = np.full(len(y), "", dtype=object)
            folds_no_target_class = 0
            for hold in unique:
                is_test = grouping == hold
                is_train = ~is_test
                if np.any(is_train & is_test) or not np.all(is_train | is_test):
                    raise ValueError("Group-leakage in sensitivity split")
                missing = set(y[is_test]) - set(y[is_train])
                if missing:
                    folds_no_target_class += 1
                est = clone(models[model_name])
                est.fit(X[is_train], y[is_train])
                predicted[is_test] = est.predict(X[is_test])
            if any(not value for value in predicted):
                raise ValueError("Sensitivity test predictions incomplete")
            classes = sorted(set(y))
            out.append({
                "experiment": experiment, "model": model_name,
                "feature_group": feature_group,
                "label_classes": len(classes), "heldout_groups": len(unique),
                "test_files": len(y), "correct": int(np.sum(predicted == y)),
                "accuracy": float(accuracy_score(y, predicted)),
                "balanced_accuracy": float(balanced_accuracy_score(y, predicted)),
                "macro_f1": float(f1_score(y, predicted, labels=classes,
                                          average="macro", zero_division=0)),
                "folds_with_unseen_target_class": folds_no_target_class,
                "interpretation": "SENSITIVITY_ONLY_NO_INDEPENDENT_SPECIMEN",
            })
    return out


def audit_runtime_feature_parity(groups: dict) -> dict:
    """Read source only; never compile, flash, train or load .joblib.

    Hard-coded legacy inference feature formula is not identical to the
    source feature pipeline. Parity must be established before promotion.
    """
    sensor = (ROOT / "src/sensor.h").read_text(encoding="utf-8")
    inference = (ROOT / "src/inference.cpp").read_text(encoding="utf-8")
    flags = (ROOT / "src/inference.h").read_text(encoding="utf-8")
    legacy = json.loads((ROOT / "models/feature_list.json").read_text(encoding="utf-8"))
    n_match = re.search(r"^#define NUM_SENSORS\s+(\d+)", sensor, flags=re.MULTILINE)
    if n_match is None:
        raise ValueError("Sensor channel count cannot be verified")
    n_sensors = int(n_match.group(1))
    if not (n_sensors == 10 and
            'float features[NUM_SENSORS * 2];' in inference and
            '#define USE_ON_DEVICE_INFERENCE 0' in flags):
        raise ValueError("Unknown or enabled on-device inference contract")
    if len(groups.get("expanded82", [])) != 82:
        raise ValueError("Frozen current feature contract mismatch")
    return {
        "rc2_ondevice_inference_default_enabled": False,
        "rc2_legacy_ondevice_sensor_channels": n_sensors,
        "rc2_legacy_inference_features_mean_plus_max": 2 * n_sensors,
        "candidate_stage3_feature_count": len(groups["expanded82"]),
        "training_runtime_feature_parity_verified": False,
        "legacy_model_feature_list_count": len(legacy),
        "legacy_feature_list_contains_MQ9_not_in_rc2_10_adc": any(
            "MQ9" in name.upper() for name in legacy
        ),
        "origin_model_in_rc2_runtime": False,
        "roast_probability_in_rc2_runtime": False,
        "warning": "Existing legacy artifacts and firmware feature functions are not the same pipeline; no .joblib is loaded or deployed",
    }


def generate() -> tuple[dict, dict[str, pd.DataFrame]]:
    frame, groups, snapshot = load_snapshot()
    heldout = pd.read_csv(STAGE5 / "heldout_probabilities.csv")
    check_oof(frame, heldout)
    assert len(frame) == 83 and set(frame["batch_id"]) == set(BATCHES)
    assert not frame["source_file"].duplicated().any()
    origin = frame.groupby("origin", sort=True).agg(
        files=("source_file", "size"), sample_codes=("sample_id", "nunique"),
        batches=("batch_id", "nunique"),
        roast_classes=("roast_level", "nunique"),
    ).reset_index()
    for cls in LABELS:
        origin[f"n_{cls}"] = origin["origin"].map(
            frame[frame["roast_level"] == cls].groupby("origin").size()
        ).fillna(0).astype(int)
    conf_rows, candidate = confidence_metrics(heldout)
    air = pd.read_csv(STAGE5 / "clean_air_surrogate.csv")
    if len(air) != 10 or set(air["model"]) != {m for m, _ in BASELINE}:
        raise ValueError("Stage5 air surrogate set differs")
    clean_air = {}
    for model, group in BASELINE:
        records = air.loc[air["model"] == model]
        if len(records) != 5 or records["source_file"].duplicated().any():
            raise ValueError("Clean air per-model provenance mismatch")
        clean_air[model] = {
            "strict_valid_known_air_files": len(records),
            "closed_set_forced_as_coffee": len(records),
            "predicted_as_light": int((records["predicted_coffee_roast_if_no_rejection"] == "light").sum()),
            "max_confidence_min": float(records["confidence_uncalibrated"].min()),
            "max_confidence_max": float(records["confidence_uncalibrated"].max()),
            "abstained_using_exploratory_0_6": int(records["would_abstain_t06"].astype(str).str.lower().eq("true").sum()),
        }
    groups_out = sensitivity(frame, groups)
    s5summary = json.loads((STAGE5 / "summary.json").read_text(encoding="utf-8"))
    if s5summary.get("models_promoted") != 0 or s5summary.get("confidence_calibrated") is not False:
        raise ValueError("Stage5 is not a safe baseline")
    results = {
        "status": "NO_GO_NOT_READY_FOR_DEVICE",
        "model_promotion_allowed": False, "device_inference": "N/A",
        "scope": "OFFLINE_ONLY_NO_FIRMWARE_NO_SERIAL_NO_G3",
        "source": {
            "stage3_snapshot_sha256": sha256(INPUT / "snapshot.json"),
            "stage3_features_sha256": sha256(INPUT / "candidate_features82.csv"),
            "stage5_oof_sha256": sha256(STAGE5 / "heldout_probabilities.csv"),
            "stage5_summary_sha256": sha256(STAGE5 / "summary.json"),
            "stage2_manifest_sha256": sha256(STAGE2 / "file_manifest.csv"),
            "exclusion_manifest_sha256": sha256(EXCLUSIONS),
        },
        "files_per_acquisition": 1, "correlated_cycles_per_acquisition": 5,
        "roast_candidate_acquisitions": len(frame),
        "roast_counts_unverified": frame["roast_level"].value_counts().sort_index().to_dict(),
        "physical_specimen_ids_verified": False,
        "origin_labels_independently_verified": False,
        "roast_labels_independently_verified": False,
        "specimen_independent_prospective_test": False,
        "unique_roast_origin_sample_codes": int(frame["sample_id"].nunique()),
        "unique_origin_metadata_labels": len(origin),
        "origins_in_only_one_roast_class": int(origin["roast_classes"].eq(1).sum()),
        "origins_with_fewer_than_5_acquisitions": int(origin["files"].lt(5).sum()),
        "origins_missing_one_or_more_batches": int(origin["batches"].lt(4).sum()),
        "candidate_roast_metrics": candidate,
        "known_clean_air_closed_set_probe": clean_air,
        "confidence_calibrated": False,
        "unknown_coffee_or_other_voc_tested": False,
        "origin_classifier_approved": False,
        "source_model_files_production_approved": False,
        "runtime_feature_parity": audit_runtime_feature_parity(groups),
        "sensitivity_experiments": "Descriptive only; same known files, no sealed prospective dataset",
        "critical_blockers": [
            "Specimen identity/collection session/date/lot missing; independent labels unverified",
            "Roast accuracy and F1 below proposed target; no unbiased final holdout",
            "Known clean air can be confidently forced into light roast without a real unknown gate",
            "Probability estimates not calibrated; confidence thresholds not validated",
            "Origin coverage sparse/unbalanced; origin labels are operator CSV metadata only",
            "Device parity and model runtime path not tested; must keep AI N/A",
            "Legacy on-device mean+max 20-feature input differs from 82-feature Stage3 candidates; saved legacy feature list still contains MQ9",
        ],
    }
    return results, {
        "roast_confidence_diagnostics.csv": pd.DataFrame(conf_rows),
        "origin_coverage.csv": origin,
        "group_holdout_sensitivity.csv": pd.DataFrame(groups_out),
    }


def save(output_dir: Path, summary: dict, frames: dict[str, pd.DataFrame]) -> None:
    path = output_dir.resolve()
    raw = (ROOT / "data/raw").resolve()
    if path == raw or raw in path.parents:
        raise ValueError("Cannot write model audit to raw folder")
    if path.exists():
        raise FileExistsError("Never overwrite earlier independent audit")
    path.mkdir(parents=True)
    (path / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )
    for name, frame in frames.items():
        frame.to_csv(path / name, index=False, float_format="%.10g")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", required=True, type=Path)
    args = parser.parse_args()
    summary, frames = generate()
    save(args.output_dir, summary, frames)
    print("STAGE10_MODEL_READINESS_AUDIT_PASS")
    print(json.dumps({
        "status": summary["status"],
        "roast_candidate_acquisitions": summary["roast_candidate_acquisitions"],
        "origin_metadata_labels": summary["unique_origin_metadata_labels"],
        "roast_metrics": summary["candidate_roast_metrics"],
        "clean_air": summary["known_clean_air_closed_set_probe"],
        "group_sensitivity": frames["group_holdout_sensitivity.csv"].to_dict("records"),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
