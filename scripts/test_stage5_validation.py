"""Regresi Tahap 5: split, prediksi OOF, threshold, negative controls, fail closed."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from stage4_model_benchmark import INPUT, load_snapshot
from stage5_validation import (
    BATCHES, BASELINE, THRESHOLDS, OUTFILES, ROOT,
    check_inputs, clean_air_features, cluster_bootstrap, coverage_tables,
    generate, perturbed_feature_matrix, save_output,
)


def fails(action, reason: str) -> None:
    try:
        action()
    except (ValueError, FileExistsError) as err:
        assert reason in str(err), str(err)
    else:
        raise AssertionError("Should reject: " + reason)


def main() -> int:
    artifacts, summary = generate()
    assert set(artifacts) == set(OUTFILES)
    assert summary["coffee_candidate_files"] == 83
    assert summary["oof_predictions"] == 166
    assert summary["clean_air_known_files"] == 6
    assert summary["clean_air_strict_valid"] == 5
    assert summary["clean_air_feature_hold"] == ["L-CAW_B34.csv"]
    assert summary["models_promoted"] == 0
    assert not summary["unknown_coffee_tested"]

    oof = artifacts["heldout_probabilities.csv"]
    previous = pd.read_csv(ROOT / "results/stage4_lobo_v2/predictions.csv")
    assert not oof["source_file"].str.contains("CAW|B37").any()
    assert len(oof) == 2 * 83
    for model, group in BASELINE:
        selected = oof.loc[oof["model"].eq(model)].copy()
        earlier = previous.loc[
            previous["model"].eq(model) & previous["group"].eq(group)
        ]
        comparison = selected.merge(
            earlier, on=["model", "group", "held_out_batch",
                         "source_file", "source_sha256"],
            suffixes=("_new", "_stage4"), validate="one_to_one",
        )
        assert len(comparison) == 83
        assert (comparison["predicted_roast_new"] ==
                comparison["predicted_roast_stage4"]).all()
        assert (comparison["true_roast_ui_unverified_new"] ==
                comparison["true_roast_ui_unverified_stage4"]).all()
        assert selected.groupby("held_out_batch").size().to_dict() == {
            "B32": 19, "B33": 19, "B34": 21, "B35": 24,
        }
        assert all(~selected.apply(
            lambda row: row.held_out_batch in row.train_batches.split("|"),
            axis=1,
        ))
        probabilities = selected[[f"prob_{name}" for name in (
            "dark", "light", "medium"
        )]].to_numpy(float)
        assert np.allclose(probabilities.sum(axis=1), 1.0, atol=1e-6)
        assert int(selected["correct"].sum()) == 45

    risk = artifacts["risk_coverage.csv"]
    for (model, scope), sub in risk.groupby(["model", "scope"]):
        arranged = sub.sort_values("threshold_prespecified")
        assert np.all(np.diff(arranged["accepted_files"]) <= 0)
        first = arranged.iloc[0]
        assert first["threshold_prespecified"] == 0
        assert first["accepted_files"] == first["all_files"]
        assert np.array_equal(arranged["threshold_prespecified"].to_numpy(),
                              np.array(THRESHOLDS))
    boot = artifacts["batch_bootstrap.csv"]
    assert len(boot) == 2 and (boot["batch_resamples"] == 256).all()
    assert boot["batch_bootstrap_macro_f1_p025"].le(
        boot["batch_bootstrap_macro_f1_p975"]
    ).all()
    classes = artifacts["class_metrics.csv"]
    assert len(classes) == 2 * 4 * 3
    assert set(classes["class"]) == {"dark", "light", "medium"}
    assert (classes.groupby(["model", "batch"])["support"].sum().to_numpy()
            == np.array([19, 19, 21, 24] * 2)).all()

    surrogate = artifacts["clean_air_surrogate.csv"]
    assert len(surrogate) == 10
    assert surrogate["true_medium"].eq("clean_air").all()
    assert surrogate["predicted_coffee_roast_if_no_rejection"].eq("light").all()
    assert not surrogate["would_abstain_t06"].any()
    assert not surrogate["source_file"].str.contains("L-CAW_B34").any()
    held = artifacts["clean_air_held.csv"]
    assert len(held) == 1 and "non-contiguous" in held.iloc[0]["reason"]

    frame, groups, _ = load_snapshot()
    fake = frame.copy()
    fake.loc[0, "sample_id"] = "L-CAW"
    fails(lambda: check_inputs(
        fake, groups, ROOT / "data/analysis/stage2_v2/file_manifest.csv",
        ROOT / "data/analysis/bench_only_exclusions.csv",
        ROOT / "data/raw",
    ), "Clean air in coffee predictors")
    vectors = frame[groups["expanded82"]].to_numpy(float)[:3]
    same = perturbed_feature_matrix(vectors, groups["expanded82"], 1.0)
    assert np.array_equal(same, vectors)
    shifted = perturbed_feature_matrix(vectors, groups["expanded82"], 1.1)
    for i, name in enumerate(groups["expanded82"]):
        if "relative_response_" in name or name.startswith(
            ("f_temperature_", "f_humidity_")
        ):
            assert np.array_equal(vectors[:, i], shifted[:, i])
        else:
            assert np.allclose(shifted[:, i], vectors[:, i] * 1.1)
    fails(lambda: perturbed_feature_matrix(
        vectors, groups["expanded82"], 10.0
    ), "Gain outside")

    exclusions_file = ROOT / "data/analysis/bench_only_exclusions.csv"
    from stage2_dataset_audit import read_exclusions
    exclusions = read_exclusions(exclusions_file)
    bad = dict(exclusions)
    bad["L-CAW_B33.csv"] = "0" * 64
    source = pd.read_csv(ROOT / "data/analysis/stage2_v2/file_manifest.csv")
    excluded = source.loc[source["training_status"].eq(
        "excluded_bench_clean_air"
    )]
    fails(lambda: clean_air_features(
        excluded, bad, ROOT / "data/raw"
    ), "Clean air SHA256 changed")

    with TemporaryDirectory() as tmp:
        folder = Path(tmp) / "audit_results"
        save_output(folder, artifacts)
        assert {p.name for p in folder.iterdir()} == set(OUTFILES)
        fails(lambda: save_output(folder, artifacts), "Output already exists")
        fails(lambda: save_output(ROOT / "data/raw", artifacts),
              "Cannot write results to raw data")
    print("STAGE5_VALIDATION_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
