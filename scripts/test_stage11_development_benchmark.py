"""Regression for Stage11 retrospective grouped comparison; no file writes."""
from __future__ import annotations

import pandas as pd

from stage11_development_benchmark import ROSTER, compare
from stage4_model_benchmark import load_snapshot


def main() -> int:
    folds, predictions, summary = compare()
    frame, _, _ = load_snapshot()
    assert summary["status"] == "DEVELOPMENT_COMPARISON_ONLY_NOT_BLIND"
    assert summary["model_promotion_allowed"] is False
    assert summary["sealed_final_holdout_available"] is False
    assert len(folds) == 4 * len(ROSTER)
    assert len(predictions) == len(frame) * len(ROSTER)
    assert set(folds["held_out_batch"]) == {"B32", "B33", "B34", "B35"}
    for name, group in ROSTER:
        one = predictions.loc[predictions["model"].eq(name)]
        assert len(one) == len(frame)
        assert not one["source_file"].duplicated().any()
        assert set(one["source_sha256"]) == set(frame["source_sha256"])
        pairs = one.merge(frame[["source_file", "batch_id", "roast_level"]],
                          on="source_file", validate="one_to_one")
        assert (pairs["held_out_batch"] == pairs["batch_id"]).all()
        assert (pairs["roast_from_ui_unverified"] == pairs["roast_level"]).all()
        report = next(x for x in summary["comparison"] if x["model"] == name)
        assert report["total_files"] == 83
        assert 0 <= report["mean_fold_macro_f1"] <= 1
        assert 0 <= report["pooled_macro_f1"] <= 1
        assert report["correct_files"] == int(
            (one["roast_from_ui_unverified"] == one["predicted_roast"]).sum()
        )
    assert next(x for x in summary["comparison"] if x["model"] == "lda_shrinkage")["correct_files"] == 45
    assert next(x for x in summary["comparison"] if x["model"] == "random_forest")["correct_files"] == 45
    print("STAGE11_DEVELOPMENT_BENCHMARK_GROUPED_REGRESSION_PASS_NOT_BLIND")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
