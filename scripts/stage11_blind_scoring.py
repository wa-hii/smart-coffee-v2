"""Custodian-only, one-time blind score AFTER prospective predictions are frozen.

Never fit/tune a model here. Never use this on pre-examined historical CSVs.
Real blindness requires human-controlled access separation: project raw CSV
filenames/metadata themselves can disclose roast and origin! This script
checks hashes/protocol invariants but CANNOT attest human separation.
"""
from __future__ import annotations

import argparse
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score, precision_recall_fscore_support

from stage11_provenance_guard import FILE_SHA, ROOT, sha, validate_registry

PRED_COLUMNS = ("blind_id", "model_id", "predicted_roast", "abstained",
                "prob_dark", "prob_light", "prob_medium")
VAULT_COLUMNS = ("blind_id", "condition", "true_roast", "origin_verified",
                 "label_evidence_id", "independent_reviewer")
CLASSES = ("dark", "light", "medium")


def evaluate(registry_path: Path, raw_dir: Path, predictions_path: Path,
             labels_path: Path, freeze_path: Path) -> dict:
    # Label vault/attestation cannot be stored with publicly visible project
    # source files; the independent custodian must retain them externally.
    checkout = ROOT.resolve()
    for protected in (labels_path, freeze_path):
        location = protected.resolve()
        if location == checkout or checkout in location.parents:
            raise ValueError("Private blind labels/freeze must remain outside checkout")
    frozen = json.loads(freeze_path.read_text(encoding="utf-8"))
    for key, file in (("registry_sha256", registry_path),
                      ("predictions_sha256", predictions_path),
                      ("custodian_labels_sha256", labels_path)):
        if sha(file) != frozen.get(key):
            raise ValueError("BLIND_FREEZE_HASH_MISMATCH: " + key)
    if not (frozen.get("independent_custodian_id") and
            frozen.get("analyst_id") and
            frozen["independent_custodian_id"] != frozen["analyst_id"] and
            all(isinstance(frozen.get(key), str) and
                bool(FILE_SHA.fullmatch(frozen[key]))
                for key in ("model_artifact_sha256", "feature_schema_sha256",
                            "predeclared_acceptance_rules_sha256"))):
        raise ValueError("Freeze lacks model/protocol/custodian attestation")
    model_ids = frozen.get("predeclared_model_ids")
    if (not isinstance(model_ids, list) or not model_ids or
            len(set(model_ids)) != len(model_ids) or
            any(not isinstance(name, str) or not name.strip() for name in model_ids)):
        raise ValueError("Predeclared unique model roster required")
    try:
        lock = datetime.fromisoformat(frozen["prediction_freeze_utc"].replace("Z", "+00:00"))
        release = datetime.fromisoformat(frozen["label_release_utc"].replace("Z", "+00:00"))
    except (ValueError, KeyError) as exc:
        raise ValueError("Invalid independent freeze/release timestamps") from exc
    if (lock.tzinfo is None or release.tzinfo is None or
            release.astimezone(timezone.utc) <= lock.astimezone(timezone.utc)):
        raise ValueError("BLINDNESS_INVALID: labels cannot precede prediction freeze")

    registry = pd.read_csv(registry_path, keep_default_na=False, dtype=str)
    check = validate_registry(registry, raw_dir=raw_dir)
    final = registry.loc[registry["split"] == "blind_final"].copy()
    if len(final) < 1:
        raise ValueError("Prospective final holdout absent")
    predictions = pd.read_csv(predictions_path, keep_default_na=False, dtype=str)
    vault = pd.read_csv(labels_path, keep_default_na=False, dtype=str)
    if list(predictions.columns) != list(PRED_COLUMNS) or list(vault.columns) != list(VAULT_COLUMNS):
        raise ValueError("Predictions/independent label-vault schema mismatch")
    if vault["blind_id"].duplicated().any() or set(vault["blind_id"]) != set(final["blind_id"]):
        raise ValueError("Blind label vault must cover final blind IDs exactly once")
    if predictions.duplicated(["model_id", "blind_id"]).any():
        raise ValueError("Repeated model predictions")
    if not set(predictions["blind_id"]) == set(final["blind_id"]):
        raise ValueError("Prediction set does not match locked final registry")
    if not predictions["model_id"].map(lambda x: bool(x.strip())).all():
        raise ValueError("Blank model ID")
    if set(predictions["model_id"]) != set(model_ids):
        raise ValueError("Blind predictions model roster differs from predeclared freeze")
    if (predictions.groupby("model_id")["blind_id"].nunique() != len(final)).any():
        raise ValueError("Each frozen model must predict every final blind ID")
    if not predictions["abstained"].isin(["true", "false"]).all():
        raise ValueError("Invalid abstention")
    probabilities = predictions[["prob_dark", "prob_light", "prob_medium"]].astype(float).to_numpy()
    if not np.isfinite(probabilities).all() or ((probabilities < 0) | (probabilities > 1)).any():
        raise ValueError("Invalid numeric probability")
    if not np.allclose(probabilities.sum(axis=1), 1, atol=1e-6):
        raise ValueError("Probabilities do not sum to one")
    if not predictions["predicted_roast"].isin(CLASSES).all():
        raise ValueError("Unrecognized predicted roast class")
    if not np.array_equal(np.array(CLASSES)[probabilities.argmax(axis=1)],
                          predictions["predicted_roast"].to_numpy()):
        raise ValueError("Predicted class differs from highest probability")
    if not (vault["label_evidence_id"].str.len() >= 4).all() or not (
            vault["independent_reviewer"].str.len() >= 4).all():
        raise ValueError("Blind label records lack external evidence/reviewer")
    actual = vault.merge(final[["blind_id", "recording_condition", "operator_id"]],
                         on="blind_id", validate="one_to_one")
    if (actual["condition"] != actual["recording_condition"]).any():
        raise ValueError("Vault condition differs from predeclared final registry")
    if (actual["independent_reviewer"] == actual["operator_id"]).any():
        raise ValueError("Custodian/reviewer not independent")
    coffee = actual["condition"].eq("coffee")
    if (not actual.loc[coffee, "true_roast"].isin(CLASSES).all() or
            actual.loc[coffee, "origin_verified"].eq("").any() or
            actual.loc[~coffee, ["true_roast", "origin_verified"]].ne("").any().any()):
        raise ValueError("Missing or leaked independent blind coffee labels")
    merged = predictions.merge(actual[["blind_id", "condition", "true_roast"]],
                               on="blind_id", validate="many_to_one")
    rows = []
    for model, part in merged.groupby("model_id", sort=True):
        is_coffee = part["condition"].eq("coffee")
        known = part.loc[is_coffee]
        unseen = part.loc[~is_coffee]
        accepted = known.loc[known["abstained"].eq("false")]
        correct_all = ((known["abstained"] == "false") &
                       (known["predicted_roast"] == known["true_roast"]))
        # Abstention is a miss for known coffee and is not silently removed
        # from recall. Conditional accepted-only scores are reported separately.
        as_displayed = known["predicted_roast"].where(
            known["abstained"].eq("false"), other="N/A")
        if len(known):
            _, per_recall, _, support = precision_recall_fscore_support(
                known["true_roast"], as_displayed, labels=CLASSES,
                zero_division=0,
            )
            vectors = known[["prob_dark", "prob_light", "prob_medium"]].astype(float).to_numpy()
            correct_vectors = (known["true_roast"].to_numpy()[:, None]
                               == np.array(CLASSES)[None, :]).astype(float)
            brier_multiclass = float(((vectors - correct_vectors)**2).sum(axis=1).mean())
        else:
            per_recall, support, brier_multiclass = [], [], None
        rows.append({
            "model_id": model,
            "final_total": len(part), "known_coffee": len(known),
            "noncoffee_or_unknown": len(unseen),
            "known_coffee_accepted": len(accepted),
            "correct_known_coffee": int(correct_all.sum()),
            "known_coffee_total_accuracy_with_abstention_wrong": (
                float(correct_all.mean()) if len(known) else None),
            "known_coffee_coverage": len(accepted) / len(known) if len(known) else None,
            "accepted_coffee_macro_f1": float(f1_score(
                accepted["true_roast"], accepted["predicted_roast"],
                labels=CLASSES, average="macro", zero_division=0,
            )) if len(accepted) else None,
            "all_coffee_macro_f1_with_abstentions_counted_as_miss": (
                float(f1_score(known["true_roast"], as_displayed,
                               labels=CLASSES, average="macro", zero_division=0))
                if len(known) else None),
            "per_class_recall_with_abstentions_counted_as_miss": {
                label: float(recall) for label, recall in zip(CLASSES, per_recall)
            },
            "per_class_support": {
                label: int(count) for label, count in zip(CLASSES, support)
            },
            "multiclass_brier_diagnostic_not_calibration_certificate": brier_multiclass,
            "noncoffee_or_unknown_false_accept_n": int((unseen["abstained"] == "false").sum()),
            "noncoffee_or_unknown_rejection_n": int((unseen["abstained"] == "true").sum()),
            "unbiased_label_score_conditional_on_custodian_process": True,
        })
    return {
        "status": "ONE_TIME_FINAL_BLIND_SCORED_NOT_DEVICE_APPROVAL",
        "custodian_split_gate": check,
        "blindness_requires_independent_human_attestation": True,
        "model_promotion_allowed": False,
        "results": rows,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    for arg in ("registry", "raw-dir", "predictions", "labels", "freeze", "output"):
        p.add_argument("--" + arg, required=True, type=Path)
    args = p.parse_args()
    if args.output.exists():
        raise FileExistsError("Blind final score is one-time; refuse overwrite")
    result = evaluate(args.registry, args.raw_dir, args.predictions, args.labels,
                      args.freeze)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2, allow_nan=False) + "\n",
                           encoding="utf-8")
    print("STAGE11_CUSTODIAN_BLIND_SCORING_COMPLETE_NOT_APPROVED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
