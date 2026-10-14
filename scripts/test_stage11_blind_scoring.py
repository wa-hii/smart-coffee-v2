"""Synthetic custodian-only blind score tests; never touches hardware/raw.

The independent provenance guard has separate real CSV fixture tests. Here
we mock ONLY that gate to test freeze/score checks in isolation.
"""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pandas as pd

from stage11_blind_scoring import evaluate, PRED_COLUMNS, VAULT_COLUMNS
from stage11_provenance_guard import FIELDS, sha


def fail(func, expected: str) -> None:
    try:
        func()
    except ValueError as err:
        assert expected in str(err), str(err)
    else:
        raise AssertionError("Expected fail-closed " + expected)


def main() -> int:
    with TemporaryDirectory() as folder:
        tmp = Path(folder)
        registry = pd.DataFrame([
            {**dict.fromkeys(FIELDS, ""), "blind_id": bid,
             "split": "blind_final", "recording_condition": condition,
             "operator_id": "operator-X"}
            for bid, condition in (("BID001", "coffee"),
                                   ("BID002", "coffee"),
                                   ("BID003", "clean_air"))
        ], columns=FIELDS)
        regpath = tmp / "registry.csv"
        registry.to_csv(regpath, index=False)
        predictions = pd.DataFrame([
            ("BID001", "frozen_model_one", "dark", "false", "0.8", "0.1", "0.1"),
            ("BID002", "frozen_model_one", "light", "false", "0.1", "0.7", "0.2"),
            ("BID003", "frozen_model_one", "light", "true", "0.1", "0.7", "0.2"),
        ], columns=PRED_COLUMNS)
        predpath = tmp / "predictions.csv"
        predictions.to_csv(predpath, index=False)
        labels = pd.DataFrame([
            ("BID001", "coffee", "dark", "Arabika Test", "certificate-1", "reviewer-1"),
            ("BID002", "coffee", "medium", "Arabika Test", "certificate-2", "reviewer-1"),
            ("BID003", "clean_air", "", "", "certificate-3", "reviewer-1"),
        ], columns=VAULT_COLUMNS)
        vaultpath = tmp / "external_vault.csv"
        labels.to_csv(vaultpath, index=False)

        freeze = {
            "registry_sha256": sha(regpath),
            "predictions_sha256": sha(predpath),
            "custodian_labels_sha256": sha(vaultpath),
            "independent_custodian_id": "custodian-1",
            "analyst_id": "researcher-1",
            "model_artifact_sha256": "f"*64,
            "feature_schema_sha256": "f"*64,
            "predeclared_acceptance_rules_sha256": "f"*64,
            "predeclared_model_ids": ["frozen_model_one"],
            "prediction_freeze_utc": "2026-12-01T00:00:00Z",
            "label_release_utc": "2026-12-02T00:00:00Z",
        }
        freeze_path = tmp / "freeze.json"
        def write_freeze():
            freeze_path.write_text(json.dumps(freeze), encoding="utf-8")
        def run():
            return evaluate(regpath, tmp, predpath, vaultpath, freeze_path)
        write_freeze()
        with patch("stage11_blind_scoring.validate_registry",
                   return_value={"status": "MOCKED_ONLY_IN_SCORER_TEST"}):
            score = run()
            assert score["status"] == "ONE_TIME_FINAL_BLIND_SCORED_NOT_DEVICE_APPROVAL"
            assert score["model_promotion_allowed"] is False
            assert score["results"][0]["correct_known_coffee"] == 1
            assert score["results"][0]["noncoffee_or_unknown_rejection_n"] == 1
            assert score["results"][0]["per_class_support"] == {
                "dark": 1, "light": 0, "medium": 1,
            }
            assert 0 <= score["results"][0]["multiclass_brier_diagnostic_not_calibration_certificate"] <= 2

            freeze["label_release_utc"] = "2026-11-30T00:00:00Z"
            write_freeze()
            fail(run, "BLINDNESS_INVALID")
            freeze["label_release_utc"] = "2026-12-02T00:00:00Z"

            freeze["predeclared_model_ids"] = ["different_model"]
            write_freeze()
            fail(run, "model roster differs")
            freeze["predeclared_model_ids"] = ["frozen_model_one"]

            freeze["predictions_sha256"] = "1"*64
            write_freeze()
            fail(run, "BLIND_FREEZE_HASH_MISMATCH")
            freeze["predictions_sha256"] = sha(predpath)

            corrupt = labels.copy()
            corrupt.loc[0, "true_roast"] = ""
            corrupt.to_csv(vaultpath, index=False)
            freeze["custodian_labels_sha256"] = sha(vaultpath)
            write_freeze()
            fail(run, "Missing or leaked independent blind coffee labels")

    print("STAGE11_BLIND_SCORE_CUSTODIAN_NEGATIVE_FIXTURES_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
