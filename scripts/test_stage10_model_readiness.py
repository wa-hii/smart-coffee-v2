"""Fail-closed QA for Stage10; all tests offline on frozen derived data."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from stage4_model_benchmark import load_snapshot
from stage10_model_readiness_audit import (
    STAGE5, check_oof, generate, save, wilson_lower,
)


def must_fail(action, cause: str) -> None:
    try:
        action()
    except (ValueError, FileExistsError) as error:
        assert cause in str(error), str(error)
    else:
        raise AssertionError(f"Expected fail-closed: {cause}")


def main() -> int:
    frame, groups, frozen = load_snapshot()
    oof = pd.read_csv(STAGE5 / "heldout_probabilities.csv")
    check_oof(frame, oof)

    shifted = oof.copy()
    shifted.loc[0, "held_out_batch"] = "B37"
    must_fail(lambda: check_oof(frame, shifted), "OOF metadata mismatch")

    tampered = oof.copy()
    tampered.loc[0, "prob_light"] = -1
    must_fail(lambda: check_oof(frame, tampered), "Invalid OOF probabilities")

    mismatch = oof.copy()
    mismatch.loc[0, "source_sha256"] = "0" * 64
    must_fail(lambda: check_oof(frame, mismatch), "OOF metadata mismatch")

    duplicate = oof.copy()
    duplicate.loc[1, "source_file"] = duplicate.loc[0, "source_file"]
    must_fail(lambda: check_oof(frame, duplicate), "OOF repeated file")

    invalid = oof.copy()
    invalid.loc[0, "predicted_roast"] = "unapproved_predicted_label"
    must_fail(lambda: check_oof(frame, invalid), "OOF prediction/probability conflict")

    assert wilson_lower(0, 0) is None
    assert 0 < wilson_lower(6, 9) < 6/9

    summary, frames = generate()
    assert summary["status"] == "NO_GO_NOT_READY_FOR_DEVICE"
    assert summary["model_promotion_allowed"] is False
    assert summary["roast_candidate_acquisitions"] == 83
    assert summary["unique_origin_metadata_labels"] == 9
    assert summary["confidence_calibrated"] is False
    assert summary["origin_classifier_approved"] is False
    assert summary["specimen_independent_prospective_test"] is False
    runtime = summary["runtime_feature_parity"]
    assert runtime["rc2_legacy_inference_features_mean_plus_max"] == 20
    assert runtime["candidate_stage3_feature_count"] == 82
    assert runtime["legacy_feature_list_contains_MQ9_not_in_rc2_10_adc"] is True
    assert runtime["training_runtime_feature_parity_verified"] is False
    assert runtime["rc2_ondevice_inference_default_enabled"] is False
    assert frames["group_holdout_sensitivity.csv"].shape[0] == 8
    for candidate in ("random_forest", "lda_shrinkage"):
        metrics = summary["candidate_roast_metrics"][candidate]
        assert (metrics["correct"], metrics["wrong"]) == (45, 38)
        assert summary["known_clean_air_closed_set_probe"][candidate][
            "predicted_as_light"] == 5

    # Freeze: reports may only be created in a fresh derived directory.
    with TemporaryDirectory() as root_tmp:
        directory = Path(root_tmp) / "derived"
        save(directory, summary, frames)
        restored = json.loads((directory / "summary.json").read_text())
        assert restored["status"] == "NO_GO_NOT_READY_FOR_DEVICE"
        must_fail(lambda: save(directory, summary, frames),
                  "Never overwrite earlier independent audit")
        raw = Path(__file__).resolve().parents[1] / "data/raw"
        must_fail(lambda: save(raw, summary, frames),
                  "Cannot write model audit to raw folder")

    print("STAGE10_MODEL_READINESS_FAIL_CLOSED_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
