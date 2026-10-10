"""Regression on actual published Zenodo bytes, never on generated dummy data."""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from evaluate_external_coffee_enose import (
    DATASETS, EXTERNAL, FILES, algorithms, evaluate_one,
    evaluation_targets, load_data, run, save, split_indices, verify_overlap,
)
from research_external_coffee_datasets import verify_bytes


def expected_exception(action, msg: str) -> None:
    try:
        action()
    except (ValueError, FileExistsError) as exc:
        assert msg in str(exc), str(exc)
    else:
        raise AssertionError("Expected failure: " + msg)


def main() -> int:
    coffee, coffee_y, coffee_stat = load_data(EXTERNAL, "CoffeePow-4")
    aroma, aroma_y, aroma_stat = load_data(EXTERNAL, "Aroma-7")
    assert coffee.shape == (3583, 10)
    assert aroma.shape == (4750, 10)
    assert coffee_stat["discarded_from_analysis_incomplete_tail_rows"] == 0
    assert aroma_stat["discarded_from_analysis_incomplete_tail_rows"] == 4
    assert verify_overlap(coffee, coffee_y, aroma, aroma_y)
    assert {int(k): v for k, v in coffee_stat["class_counts"].items()} == {
        0: 880, 1: 1010, 2: 974, 3: 719
    }
    assert set(aroma_y) == set(range(7))
    assert not np.isnan(coffee).any() and (coffee > 0).all()

    for dataset, y in (("CoffeePow-4", coffee_y), ("Aroma-7", aroma_y)):
        target = evaluation_targets(dataset, y)
        assert len(target) == 2
        for label in target.values():
            for name in ("stratified_random", "within_class_tail"):
                tr, te = split_indices(label, name)
                assert len(tr) + len(te) == len(label)
                assert not np.intersect1d(tr, te).size
                assert set(label[tr]) == set(label[te])
            expected_exception(lambda: split_indices(label, "leaky_shuffle"),
                               "Unknown split strategy")
    # Directly check actual real-signal evaluation with no dummy observations.
    target = evaluation_targets("CoffeePow-4", coffee_y)[
        "air0_vs_coffee123_assumed_author_order"
    ]
    subset = {"dummy_prior": algorithms()["dummy_prior"],
              "logistic": algorithms()["logistic"]}
    m1, c1, s1 = evaluate_one(
        coffee, target, "CoffeePow-4", "air_assumed", "within_class_tail",
        subset,
    )
    m2, c2, s2 = evaluate_one(
        coffee, target, "CoffeePow-4", "air_assumed", "within_class_tail",
        subset,
    )
    assert pd.DataFrame(m1).equals(pd.DataFrame(m2))
    assert pd.DataFrame(c1).equals(pd.DataFrame(c2))
    assert s1.equals(s2)
    assert all(0 <= row["macro_f1"] <= 1 for row in m1)

    outputs, summary = run(EXTERNAL)
    assert set(outputs) == set(FILES)
    assert summary["evaluation_rows"] == 40
    assert summary["coffee_pow4_included_identically_in_aroma7"]
    assert summary["external_data_added_to_local_roast_training"] is False
    assert summary["local_model_approval"] == "NO_GO"
    with TemporaryDirectory() as td:
        out = Path(td) / "results"
        save(out, outputs)
        assert set(p.name for p in out.iterdir()) == set(FILES)
        expected_exception(lambda: save(out, outputs), "Use new result directory")
        tampered_dir = Path(td) / "tampered"
        tampered_dir.mkdir()
        for ds in DATASETS.values():
            (tampered_dir / ds["filename"]).write_bytes(
                (EXTERNAL / ds["filename"]).read_bytes()
            )
        tampered_file = tampered_dir / "CoffeePow-4.csv"
        orig = tampered_file.read_bytes()
        tampered_file.write_bytes(orig + b"\n0,0")
        expected_exception(lambda: load_data(
            tampered_dir, "CoffeePow-4"
        ), "checksum mismatch")
        expected_exception(lambda: verify_bytes(
            b"not a real dataset", DATASETS["CoffeePow-4"]["md5"]
        ), "checksum mismatch")
        assert (EXTERNAL / "CoffeePow-4.csv").read_bytes() == orig
    print("REAL_EXTERNAL_DATA_EVALUATION_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
