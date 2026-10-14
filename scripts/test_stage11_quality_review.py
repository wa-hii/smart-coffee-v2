"""Stage11 source quality regression; no raw writes or feature fitting."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from stage11_quality_review import review


def main() -> int:
    flagged, summary = review()
    assert len(flagged) == 89
    assert summary["frozen_files_verified_by_sha256"] == 89
    assert summary["coffee_dev_only"] == 83
    assert summary["air_excluded"] == 6
    assert summary["automatic_exclusions"] == 0
    assert summary["new_sealed_blind_test_files"] == 0
    assert summary["labels_edited"] is False
    assert summary["model_promotion_allowed"] is False
    assert not flagged["blind_test_eligible"].any()
    assert not flagged["automatic_sample_exclusion"].any()
    assert flagged["source_file"].nunique() == len(flagged)
    assert flagged["source_sha256"].nunique() == len(flagged)
    assert not flagged["flags"].eq("").any()
    assert summary["flags_file_counts"]["ORIGIN_AND_ROAST_LABELS_NOT_INDEPENDENTLY_VERIFIED"] == 83
    assert summary["flags_file_counts"]["KNOWN_AIR_NOT_COFFEE_TRAINING"] == 6
    print("STAGE11_SOURCE_QUALITY_REVIEW_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
