"""Non-destructive, source-bound quality review of the frozen MQ3 cohort.

The quality result is a REVIEW queue, not a label rewrite, sample dropping
mechanism, independent-specimen certificate, or a new ML selection criterion.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from stage11_provenance_guard import ROOT, RAW, STAGE2, sha
from stage4_model_benchmark import INPUT, load_snapshot


def review() -> tuple[pd.DataFrame, dict]:
    historic = pd.read_csv(STAGE2, keep_default_na=False)
    features, _, _ = load_snapshot()
    dev = set(features["source_file"])
    if historic["source_file"].duplicated().any():
        raise ValueError("Duplicate canonical source filenames")
    if len(historic) != 89 or len(dev) != 83:
        raise ValueError("Frozen cohort differs; do not silently reselect")
    duplicate_cells = (
        historic.loc[historic["source_file"].isin(dev)]
        .groupby(["batch", "sample_id"])["source_file"].transform("size")
    )
    duplication_by_file = dict(zip(
        historic.loc[historic["source_file"].isin(dev), "source_file"],
        duplicate_cells.astype(int)
    ))
    records = []
    for record in historic.itertuples(index=False):
        path = RAW / record.source_file
        if not path.is_file() or sha(path) != record.source_sha256:
            raise ValueError("Frozen historical hash mismatch: " + record.source_file)
        is_coffee = record.source_file in dev
        flags: list[str] = []
        if int(record.validator_error_count):
            flags.append("CANONICAL_VALIDATOR_ERROR")
        if int(record.adc_missing_cells):
            flags.append("MISSING_SENSOR_ADC")
        if int(record.adc_saturation_cells):
            flags.append("SATURATED_SENSOR_ADC")
        if int(record.adc_zero_cells):
            flags.append("ZERO_SENSOR_ADC_REVIEW")
        if int(record.temperature_missing) or int(record.humidity_missing):
            flags.append("AMBIENT_MISSING")
        if float(record.timestamp_step_min_ms) < 900 or float(record.timestamp_step_max_ms) > 1100:
            flags.append("SAMPLE_CADENCE_JITTER_REVIEW")
        if is_coffee and duplication_by_file.get(record.source_file, 1) > 1:
            flags.append("SAME_UI_CODE_IN_SAME_BATCH_REPEAT_NOT_INDEPENDENT")
        if is_coffee and (not str(record.physical_specimen_id).strip()
                          or not str(record.operator_session_id).strip()):
            flags.append("PHYSICAL_SPECIMEN_OR_SESSION_UNVERIFIED")
        if is_coffee:
            flags.append("ORIGIN_AND_ROAST_LABELS_NOT_INDEPENDENTLY_VERIFIED")
        if not is_coffee:
            flags.append("KNOWN_AIR_NOT_COFFEE_TRAINING")
        records.append({
            "source_file": record.source_file,
            "source_sha256": record.source_sha256,
            "status": "DEV_ONLY_UNVERIFIED" if is_coffee else "EXCLUDED_CLEAN_AIR",
            "source_validator_pass": str(record.validator_pass).lower() == "true",
            "source_validator_errors": int(record.validator_error_count),
            "duplicate_ui_code_in_batch_count": duplication_by_file.get(record.source_file, 0),
            "adc_zero_cells": int(record.adc_zero_cells),
            "adc_saturation_cells": int(record.adc_saturation_cells),
            "adc_missing_cells": int(record.adc_missing_cells),
            "temperature_missing": int(record.temperature_missing),
            "humidity_missing": int(record.humidity_missing),
            "flags": "|".join(flags),
            "flags_n": len(flags),
            "blind_test_eligible": False,
            "automatic_sample_exclusion": False,
        })
    output = pd.DataFrame(records)
    if set(output.loc[output["status"] == "DEV_ONLY_UNVERIFIED", "source_file"]) != dev:
        raise ValueError("Source/Stage3 cross-check failed")
    count_flags = output["flags"].str.split("|").explode().value_counts().sort_index()
    summary = {
        "status": "SOURCE_QUALITY_REVIEW_ONLY_NO_RELABEL_NO_DROPPING",
        "stage2_manifest_sha256": sha(STAGE2),
        "stage3_features_sha256": sha(INPUT / "candidate_features82.csv"),
        "frozen_files_verified_by_sha256": len(output),
        "coffee_dev_only": int(output["status"].eq("DEV_ONLY_UNVERIFIED").sum()),
        "air_excluded": int(output["status"].eq("EXCLUDED_CLEAN_AIR").sum()),
        "files_with_any_review_flag": int(output["flags_n"].gt(0).sum()),
        "flags_file_counts": count_flags.to_dict(),
        "automatic_exclusions": 0,
        "labels_edited": False,
        "raw_files_edited": False,
        "verified_independent_specimen_ids": 0,
        "new_sealed_blind_test_files": 0,
        "model_promotion_allowed": False,
        "caveat": "Cadence 900-1100 ms, zero/saturation and repeated UI codes are pre-review diagnostics, not validated outlier rejection rules; all historical labels remain unverified.",
    }
    return output, summary


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--output-dir", required=True, type=Path)
    args = p.parse_args()
    dst = args.output_dir.resolve()
    raw = RAW.resolve()
    if dst.exists() or dst == raw or raw in dst.parents:
        raise ValueError("Use a new derived directory outside raw")
    flagged, summary = review()
    dst.mkdir(parents=True)
    flagged.to_csv(dst / "quality_review_flags.csv", index=False)
    (dst / "quality_review_summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print("STAGE11_FROZEN_SOURCE_QUALITY_REVIEW_PASS")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
