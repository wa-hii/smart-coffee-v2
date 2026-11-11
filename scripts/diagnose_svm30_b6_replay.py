#!/usr/bin/env python3
"""Read-only diagnosis of SVM30 offline replay after a physical L->D incident.

This script NEVER opens COM, loads an untrusted joblib, triggers Nextion,
stores fresh ADC, modifies model weights, or attempts MCU flashing.
It reports replay classification errors and feature z-scores from the
existing private golden comparison; these are NOT fresh MCU readings.
"""
from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime, timezone
import json
from pathlib import Path

from svm30_embedded_features import FEATURE_ORDER

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_GOLDEN = ROOT / "private/svm30_golden_scores_full199.json"
DEFAULT_OUT = ROOT / "private/svm30_b6_light_dark_replay_diagnosis.json"
CLASSES = ("dark", "light", "medium")


def assess(golden: dict) -> dict:
    rows = golden.get("cases", [])
    if not rows or golden.get("prediction_mismatches") != 0:
        raise ValueError("golden_corpus_missing_or_native_parity_mismatch")
    counts = Counter((row["source_roast_label_not_used_as_input"],
                      row["python_model_prediction"]) for row in rows)
    for true, pred in counts:
        if true not in CLASSES or pred not in CLASSES:
            raise ValueError("unexpected_class")
    per_class = {}
    for actual in CLASSES:
        total = sum(counts[(actual, p)] for p in CLASSES)
        correct = counts[(actual, actual)]
        per_class[actual] = {
            "count": total,
            "match_count": correct,
            "match_fraction": round(correct / total, 6) if total else None,
            "predicted_as": {p: counts[(actual, p)] for p in CLASSES},
        }
    light_to_dark = []
    by_origin: dict[str, Counter] = defaultdict(Counter)
    for row in rows:
        original = row["source_roast_label_not_used_as_input"]
        predicted = row["python_model_prediction"]
        origin = row["filename"].split("_")[0].split("-")[-1]
        by_origin[origin][(original, predicted)] += 1
        if original == "light" and predicted == "dark":
            scaled = row["features_scaled_python"]
            if len(scaled) != len(FEATURE_ORDER):
                raise ValueError("feature_vector_wrong_size")
            largest = sorted(range(len(scaled)),
                             key=lambda i: abs(scaled[i]), reverse=True)[:6]
            light_to_dark.append({
                "filename": row["filename"],
                "cohort": row["cohort"],
                "origin": origin,
                "vote_margin": row["native_vote_margin"],
                "pair_scores_dark_light_dark_medium_light_medium":
                    row["libsvm_pair_scores_python"],
                "largest_absolute_scaled_features": [
                    {"feature": FEATURE_ORDER[i],
                     "training_scaled_value": round(scaled[i], 4)}
                    for i in largest
                ],
            })
    label_agreements = sum(counts[(x, x)] for x in CLASSES)
    return {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "OFFLINE_REPLAY_ANALYSIS_NOT_LIVE_SENSOR_DIAGNOSIS",
        "reported_field_actual": "light",
        "reported_field_predicted": "dark",
        "live_sensor_adc_available": False,
        "live_feature_vector_available": False,
        "live_svm_scores_available": False,
        "field_model_root_cause_verified": False,
        "replay_count": len(rows),
        "replay_label_match_count": label_agreements,
        "replay_label_match_fraction": round(label_agreements/len(rows), 6),
        "replay_is_not_independent_prospective_accuracy": True,
        "native_python_prediction_equivalence": golden["prediction_mismatches"] == 0,
        "per_true_class": per_class,
        "light_predicted_as_dark_cases": light_to_dark,
        "light_predicted_as_dark_by_origin": {
            origin: count[("light", "dark")]
            for origin, count in sorted(by_origin.items())
        },
        "notes": [
            "A physical LIGHT->DARK result is a documented misclassification; device functional prediction works.",
            "Original model uses raw absolute ADC, vulnerable to session/device/environmental distribution shift.",
            "The standalone mode does not store raw ADC or feature/decision score telemetry; cannot reconstruct physical sample.",
            "Replay error cases are examples of model behavior, not proof that these specific features occurred in the field.",
            "Do not change class mapping or retrain from one observation.",
        ],
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--golden", type=Path, default=DEFAULT_GOLDEN)
    p.add_argument("--output", type=Path, default=DEFAULT_OUT)
    args = p.parse_args()
    if args.output.resolve().parent != (ROOT/"private").resolve():
        raise ValueError("DIAGNOSTIC_OUTPUT_MUST_BE_PRIVATE")
    if args.output.exists():
        raise FileExistsError("DO_NOT_OVERWRITE_PRIOR_DIAGNOSIS")
    result = assess(json.loads(args.golden.read_text(encoding="utf8")))
    args.output.write_text(json.dumps(result, indent=2)+"\n",encoding="utf8")
    print("SVM30_B6_REPLAY_DIAGNOSIS", json.dumps({
        "replay_count": result["replay_count"],
        "replay_label_matches": result["replay_label_match_count"],
        "per_true_class": result["per_true_class"],
        "light_predicted_dark_examples": [
            {"filename": x["filename"], "origin": x["origin"]}
            for x in result["light_predicted_as_dark_cases"]
        ],
        "physical_root_cause_confirmed": False,
        "device_accessed": False,
    }), flush=True)


if __name__ == "__main__":
    main()
