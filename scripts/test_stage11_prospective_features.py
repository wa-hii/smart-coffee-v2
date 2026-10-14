"""Synthetic positive & negative blinded feature export; temp fixtures only."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from stage11_provenance_guard import FIELDS, RAW, sha
from stage11_prospective_features import export_features


def main() -> int:
    with TemporaryDirectory() as td:
        tmp = Path(td)
        raw = tmp / "fixture_raw"
        raw.mkdir()
        old = pd.read_csv(RAW / "D-CAT_B32.csv")
        registry = []
        for idx in range(9):
            roast = ("dark", "light", "medium")[idx % 3]
            prefix = {"dark": "D", "light": "L", "medium": "M"}[roast]
            batch = f"B{38 + idx}"
            name = f"{prefix}-CAT_{batch}.csv"
            df = old.copy()
            df["sample_id"] = f"{prefix}-CAT"
            df["roast_level"] = roast
            df["batch_id"] = batch
            df.to_csv(raw / name, index=False)
            split = ("development", "calibration", "blind_final")[idx // 3]
            registry.append({
                "blind_id": f"00000000-0000-4000-8000-{idx+1:012d}", "source_file": name,
                "source_sha256": sha(raw / name), "split": split,
                "physical_specimen_id": f"unit-specimen-{idx}",
                "coffee_lot_id": f"unit-lot-{idx}",
                "roast_batch_id": f"unit-roastbatch-{idx}",
                "operator_session_id": f"unit-session-{idx}",
                "collection_date_utc": f"2026-11-{idx+1:02d}T08:00:00Z",
                "operator_id": "operator-test", "firmware_build_id": "g3-rc2-20261014",
                "recording_condition": "coffee",
                "roast_verified": roast if split != "blind_final" else "",
                "origin_verified": "Arabika Catuji Mekarwangi" if split != "blind_final" else "",
                "roast_evidence_id": f"roast-cert-{idx}",
                "origin_evidence_id": f"origin-cert-{idx}",
                "independent_reviewer": "reviewer-test",
                "quality_review_id": f"quality-log-{idx}",
            })
        index_file = tmp / "registry.csv"
        pd.DataFrame(registry, columns=FIELDS).to_csv(index_file, index=False)
        out = tmp / "views"
        result = export_features(index_file, raw, out)
        assert result["status"] == "PROSPECTIVE_FEATURE_VIEWS_GENERATED_NOT_MODEL_APPROVAL"
        assert result["model_promotion_allowed"] is False
        for name in ("development", "calibration", "blind_final"):
            features = pd.read_csv(out / f"{name}_features.csv")
            assert len(features) == 3
            assert len([col for col in features if col.startswith("f_")]) == 82
            assert not any(token in features.columns for token in (
                "source_file", "source_sha256", "sample_id", "batch_id",
                "roast_level", "origin", "coffee_lot_id", "operator_session_id"
            ))
            if name == "blind_final":
                assert "verified_roast" not in features.columns
                assert "verified_origin" not in features.columns
            else:
                assert set(features["verified_roast"]) == {"dark", "light", "medium"}

        try:
            export_features(index_file, raw, out)
        except ValueError as exc:
            assert "fresh derived output" in str(exc)
        else:
            raise AssertionError("Export must refuse overwrite")

    print("STAGE11_PROSPECTIVE_FEATURE_BLIND_EXPORT_FIXTURE_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
