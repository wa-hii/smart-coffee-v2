"""Adversarial Stage11 split-provenance tests (synthetic data in temp only)."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from stage11_provenance_guard import (
    RAW, FIELDS, historical_inventory, sha, validate_registry,
)


def fails(action, message: str) -> None:
    try:
        action()
    except (ValueError, FileExistsError) as exc:
        assert message in str(exc), str(exc)
    else:
        raise AssertionError(f"Expected rejection: {message}")


def main() -> int:
    with TemporaryDirectory() as folder:
        tmp = Path(folder)
        inventory = historical_inventory(tmp / "historic")
        assert inventory["historical_dev_only"] == 83
        assert inventory["historical_excluded_clean_air"] == 6
        assert not inventory["historical_blind_test_eligible"]
        fails(lambda: historical_inventory(tmp / "historic"), "Refusing to overwrite")
        fields = pd.read_csv(tmp / "historic/prospective_registry_TEMPLATE.csv")
        assert list(fields.columns) == list(FIELDS)
        fails(lambda: validate_registry(fields), "NO_PROSPECTIVE_ACQUISITIONS")

        raw_dir = tmp / "synthetic_future_raw"
        raw_dir.mkdir()
        source = pd.read_csv(RAW / "D-CAT_B32.csv")
        rows = []
        for index, role in enumerate(("development", "development", "calibration",
                                      "calibration", "blind_final", "blind_final")):
            batch = f"B{38 + index}"
            frame = source.copy()
            frame["batch_id"] = batch
            name = f"D-CAT_{batch}.csv"
            destination = raw_dir / name
            frame.to_csv(destination, index=False)
            rows.append({
                "blind_id": f"00000000-0000-4000-8000-{index+1:012d}",
                "source_file": name, "source_sha256": sha(destination),
                "split": role,
                "physical_specimen_id": f"test-specimen-{index}",
                "coffee_lot_id": f"test-lot-{index}",
                "roast_batch_id": f"test-roastbatch-{index}",
                "operator_session_id": f"test-session-{index}",
                "collection_date_utc": f"2026-11-{index+1:02d}T08:00:00+00:00",
                "operator_id": "test-operator",
                "firmware_build_id": "g3-rc2-20261014",
                "recording_condition": "coffee",
                "roast_verified": "dark" if role != "blind_final" else "",
                "origin_verified": "Arabika Catuji Mekarwangi" if role != "blind_final" else "",
                "roast_evidence_id": f"fixture-roast-cert-{index}",
                "origin_evidence_id": f"fixture-origin-cert-{index}",
                "independent_reviewer": "test-independent-reviewer",
                "quality_review_id": f"fixture-quality-review-{index}",
            })
        base = pd.DataFrame(rows, columns=FIELDS)
        outcome = validate_registry(base, raw_dir=raw_dir)
        assert outcome["rows"] == 6
        assert outcome["physical_provenance_certificates_independently_inspected"] is False
        assert outcome["model_promotion_allowed"] is False

        broken = base.copy()
        broken.loc[4, "coffee_lot_id"] = broken.loc[0, "coffee_lot_id"]
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "SPLIT_LEAKAGE")
        broken = base.copy()
        broken.loc[4, "operator_session_id"] = broken.loc[0, "operator_session_id"]
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "SPLIT_LEAKAGE")
        broken = base.copy()
        broken.loc[4, "collection_date_utc"] = broken.loc[0, "collection_date_utc"]
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "SPLIT_LEAKAGE")
        broken = base.copy()
        broken.loc[4, "roast_verified"] = "dark"
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "BLIND_LABEL_LEAKAGE")
        broken = base.copy()
        broken.loc[0, "roast_verified"] = ""
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "validated training")
        broken = base.copy()
        broken.loc[0, "independent_reviewer"] = broken.loc[0, "operator_id"]
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "Reviewer must be independent")
        broken = base.copy()
        broken.loc[0, "collection_date_utc"] = "2026-10-01T08:00:00Z"
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "NOT_PROSPECTIVE")
        broken = base.copy()
        broken.loc[0, "source_sha256"] = "a"*64
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "Missing/tampered prospective source")
        broken = base.copy()
        broken.loc[4, "blind_id"] = broken.loc[0, "blind_id"]
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "Duplicate blind_id")
        broken = base.loc[base["split"] != "calibration"].copy()
        fails(lambda: validate_registry(broken, raw_dir=raw_dir), "INDEPENDENT_SPLIT_NOT_READY")

    print("STAGE11_PROVENANCE_HISTORICAL_AND_SPLIT_NEGATIVE_TESTS_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
