"""Uji split batch, leakage guards, reproducibility metrik dan snapshot Stage 4."""

from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler

from stage4_model_benchmark import (
    BATCHES, INPUT, LABELS, EXCLUSIONS, S2_MANIFEST,
    benchmark, load_snapshot, save, sha256,
)


def must_fail(action, message: str) -> None:
    try:
        action()
    except (ValueError, FileExistsError) as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError(f"Expected failure: {message}")


def main() -> int:
    frame, groups, frozen = load_snapshot()
    assert len(frame) == 83
    assert not frame["sample_id"].str.endswith("-CAW").any()
    assert not frame["batch_id"].eq("B37").any()
    assert all(k.startswith("f_") for group in groups.values() for k in group)
    assert set(frozen["feature_rows_accepted"]) == set(frame["source_file"])

    prototypes = {
        "dummy_prior": DummyClassifier(strategy="prior"),
        "logistic_l2": make_pipeline(
            StandardScaler(),
            LogisticRegression(C=1.0, max_iter=2500, random_state=20261009),
        ),
    }
    short_groups = {"response10": groups["response10"]}
    folds, preds, ranking = benchmark(frame, short_groups, prototypes)
    second, pred2, rank2 = benchmark(frame, short_groups, prototypes)
    assert len(folds) == 8 and len(preds) == 83 * 2
    assert set(folds["held_out_batch"]) == set(BATCHES)
    assert set(ranking["model"]) == set(prototypes)
    assert np.allclose(folds["macro_f1"], second["macro_f1"])
    assert np.allclose(folds["balanced_accuracy"], second["balanced_accuracy"])
    assert preds.equals(pred2)
    for fold in folds.itertuples():
        assert fold.held_out_batch not in fold.train_batches
        assert fold.test_files + fold.train_files == len(frame)
        assert json.loads(fold.confusion_matrix_D_L_M)
        assert 0 <= fold.macro_f1 <= 1
    assert all(preds["held_out_batch"].eq(
        preds["source_file"].map(
            frame.set_index("source_file")["batch_id"]
        )
    ))

    must_fail(lambda: benchmark(
        frame, {"invalid": ["roast_level"]}, prototypes
    ), "Invalid/label-leaking")
    wrong_classes = frame.loc[frame["roast_level"] != "light"]
    must_fail(lambda: benchmark(
        wrong_classes, short_groups, prototypes
    ), "Missing roast class")

    with TemporaryDirectory() as tmp:
        directory = Path(tmp)
        source = directory / "input"
        source.mkdir()
        for name in ("candidate_features82.csv", "feature_groups.json",
                     "snapshot.json"):
            (source / name).write_bytes((INPUT / name).read_bytes())

        bad_data = frame.copy()
        bad_data.loc[0, "batch_id"] = "B37"
        bad_data.to_csv(source / "candidate_features82.csv", index=False)
        must_fail(lambda: load_snapshot(source), "Stage3/Stage2 metadata mismatch")

        bad_data = frame.copy()
        bad_data.loc[0, "sample_id"] = "L-CAW"
        bad_data.to_csv(source / "candidate_features82.csv", index=False)
        must_fail(lambda: load_snapshot(source), "Stage3/Stage2 metadata mismatch")

        # Protect frozen Stage2/exclusion hashes; no stale CAW labels allowed.
        manifest = directory / "stage2_manifest.csv"
        manifest.write_bytes(S2_MANIFEST.read_bytes())
        manifest.write_text(manifest.read_text() + "\n", encoding="utf-8")
        must_fail(lambda: load_snapshot(INPUT, manifest, EXCLUSIONS),
                  "Frozen snapshot SHA256 changed")

        config = {"test": True}
        summary = {"status": "TEST_ONLY"}
        out = directory / "results"
        save(out, folds, preds, ranking, config, summary)
        assert len(list(out.glob("*"))) == 6
        must_fail(lambda: save(
            out, folds, preds, ranking, config, summary
        ), "Output directory already exists")

    print("STAGE4_MODEL_BENCHMARK_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
