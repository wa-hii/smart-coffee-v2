"""Offline Stage11: immutable historical evidence and prospective split gate.

This module NEVER edits raw, opens serial, invents specimen identities,
trains models, or certifies a final blind test before real new data exist.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from uuid import UUID
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from stage2_dataset_audit import read_exclusions
from stage4_model_benchmark import ROOT, INPUT, load_snapshot
from validate_acquisition import validate_file

RAW = ROOT / "data/raw"
STAGE2 = ROOT / "data/analysis/stage2_v2/file_manifest.csv"
EXCLUSIONS = ROOT / "data/analysis/bench_only_exclusions.csv"
MIN_PROSPECTIVE_UTC = datetime(2026, 10, 15, tzinfo=timezone.utc)

# This is the private custodian registry. Holdout class labels MUST remain empty
# in this shared version. A separately secured custodian label vault supplies
# blind labels only after prediction/model freeze.
FIELDS = (
    "blind_id", "source_file", "source_sha256", "split",
    "physical_specimen_id", "coffee_lot_id", "roast_batch_id",
    "operator_session_id", "collection_date_utc", "operator_id",
    "firmware_build_id", "recording_condition", "roast_verified",
    "origin_verified", "roast_evidence_id", "origin_evidence_id",
    "independent_reviewer", "quality_review_id",
)
SPLITS = {"development", "calibration", "blind_final"}
CONDITIONS = {"coffee", "clean_air", "other_voc", "unknown_coffee"}
ROASTS = {"light", "medium", "dark"}
FILE_SHA = re.compile(r"^[a-f0-9]{64}$")
ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]{3,127}$")


def opaque_blind_id(value: str) -> bool:
    """Require canonical UUIDv4: no sample code, class or origin in the ID."""
    try:
        token = UUID(value)
    except (ValueError, AttributeError, TypeError):
        return False
    return token.version == 4 and str(token) == value


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _assert_safe_output(dest: Path) -> None:
    raw = RAW.resolve()
    actual = dest.resolve()
    if actual == raw or raw in actual.parents:
        raise ValueError("Forbidden: cannot write derived outputs under data/raw")
    if actual.exists():
        raise FileExistsError("Refusing to overwrite prior audit output")


def historical_inventory(output_dir: Path) -> dict:
    _assert_safe_output(output_dir)
    frozen = pd.read_csv(STAGE2, keep_default_na=False)
    if frozen["source_file"].duplicated().any():
        raise ValueError("Duplicate historical filenames")
    old = load_snapshot()[0]
    known = set(old["source_file"])
    excluded = read_exclusions(EXCLUSIONS)
    records = []
    for row in frozen.itertuples(index=False):
        path = RAW / row.source_file
        if not path.is_file() or sha(path) != row.source_sha256:
            raise ValueError(f"Historic source missing or SHA changed: {row.source_file}")
        issues = validate_file(path)
        if row.source_file in excluded and excluded[row.source_file] != row.source_sha256:
            raise ValueError(f"Excluded file SHA mismatch: {row.source_file}")
        if row.source_file in known and issues:
            raise ValueError(f"Frozen development file failed validation: {row.source_file}")
        status = ("DEV_ONLY_LABELS_UNVERIFIED" if row.source_file in known
                  else "EXCLUDED_CLEAN_AIR" if row.source_file in excluded
                  else "HOLD_FOR_REVIEW")
        records.append({
            "source_file": row.source_file,
            "source_sha256": row.source_sha256,
            "historic_batch": row.batch,
            "recorded_sample_code_not_specimen": row.sample_id,
            "recorded_roast_unverified": row.roast_level,
            "recorded_origin_unverified": row.origin,
            "canonical_qa_errors": len(issues),
            "adc_zero_cells": int(row.adc_zero_cells),
            "adc_saturation_cells": int(row.adc_saturation_cells),
            "adc_missing_cells": int(row.adc_missing_cells),
            "temperature_missing": int(row.temperature_missing),
            "humidity_missing": int(row.humidity_missing),
            "physical_specimen_id": "",
            "coffee_lot_id": "",
            "operator_session_id": "",
            "independent_origin_evidence": "",
            "independent_roast_evidence": "",
            "eligibility": status,
            "blind_final_eligible": False,
        })
    inventory = pd.DataFrame(records)
    if set(inventory.loc[inventory["eligibility"].eq("DEV_ONLY_LABELS_UNVERIFIED"),
                     "source_file"]) != known:
        raise ValueError("Historical dev cohort changed")
    if not set(excluded).issubset(set(inventory["source_file"])):
        raise ValueError("Excluded historical set changed")

    # A newly arrived, unregistered file must not silently enter the frozen
    # cohort. Do not read content or infer roast from these unknown filenames.
    visible_unknown = sorted(p.name for p in RAW.glob("*.csv")
                             if p.name not in set(inventory["source_file"]))
    summary = {
        "status": "HISTORICAL_DEVELOPMENT_ONLY_NOT_INDEPENDENT_BLIND",
        "frozen_stage2_manifest_sha256": sha(STAGE2),
        "frozen_stage3_features_sha256": sha(INPUT / "candidate_features82.csv"),
        "frozen_exclusions_sha256": sha(EXCLUSIONS),
        "frozen_file_count": len(inventory),
        "historical_dev_only": int(inventory["eligibility"].eq("DEV_ONLY_LABELS_UNVERIFIED").sum()),
        "historical_excluded_clean_air": int(inventory["eligibility"].eq("EXCLUDED_CLEAN_AIR").sum()),
        "historic_hold_for_review": int(inventory["eligibility"].eq("HOLD_FOR_REVIEW").sum()),
        "visible_files_outside_frozen_inventory": visible_unknown,
        "prospective_test_acquisitions": 0,
        "independent_specimen_count_verified": 0,
        "historical_blind_test_eligible": False,
        "model_promotion_allowed": False,
        "raw_files_edited": False,
    }
    output_dir.mkdir(parents=True)
    inventory.to_csv(output_dir / "historical_provenance.csv", index=False)
    pd.DataFrame(columns=FIELDS).to_csv(output_dir / "prospective_registry_TEMPLATE.csv", index=False)
    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def validate_registry(frame: pd.DataFrame, *, raw_dir: Path = RAW,
                      historical: Path = STAGE2,
                      require_all_splits: bool = True) -> dict:
    """Checks identity, actual raw hashes and genuine provenance constraints.

    This validates declared IDs/evidence references. It cannot independently
    prove the human-held physical specimen certificates are authentic.
    """
    if set(frame.columns) != set(FIELDS):
        raise ValueError("Prospective registry schema missing or changed")
    if frame.empty:
        raise ValueError("NO_PROSPECTIVE_ACQUISITIONS: empty registry")
    frame = frame.loc[:, FIELDS].fillna("").astype(str)
    prior = pd.read_csv(historical, keep_default_na=False)
    prior_hashes = set(prior["source_sha256"])
    prior_files = set(prior["source_file"])
    if not frame["split"].isin(SPLITS).all():
        raise ValueError("Unknown split; must be development/calibration/blind_final")
    if require_all_splits and set(frame["split"]) != SPLITS:
        raise ValueError("INDEPENDENT_SPLIT_NOT_READY: all three splits required")
    for key in ("blind_id", "source_file", "source_sha256"):
        if frame[key].duplicated().any():
            raise ValueError(f"Duplicate {key} in prospective registry")
    if any(not opaque_blind_id(i) for i in frame["blind_id"]):
        raise ValueError("Opaque random UUIDv4 blind_id required")
    if frame["source_sha256"].map(lambda x: not FILE_SHA.fullmatch(x)).any():
        raise ValueError("Invalid SHA256 format")
    if frame["source_sha256"].isin(prior_hashes).any() or frame["source_file"].isin(prior_files).any():
        raise ValueError("HISTORICAL_LEAKAGE: reused B32-B35/B37 source")

    # One coffee lot, roast batch, physical specimen, session, AND day is
    # restricted to a single role; intentional conservative temporal holdout.
    for col in ("physical_specimen_id", "coffee_lot_id", "roast_batch_id",
                "operator_session_id"):
        if frame[col].eq("").any() or not frame[col].map(lambda x: bool(ID.fullmatch(x))).all():
            raise ValueError(f"Unverified/missing identity field: {col}")
        overlap = frame.groupby(col)["split"].nunique()
        if (overlap > 1).any():
            raise ValueError(f"SPLIT_LEAKAGE: same {col} in different partitions")
    dates = []
    for value in frame["collection_date_utc"]:
        try:
            instant = datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError as exc:
            raise ValueError("Missing/invalid collection_date_utc") from exc
        if instant.tzinfo is None or instant.astimezone(timezone.utc) < MIN_PROSPECTIVE_UTC:
            raise ValueError("NOT_PROSPECTIVE: collection must be after frozen dev data")
        dates.append(instant.astimezone(timezone.utc).date().isoformat())
    temp = frame.assign(collection_day_utc=dates)
    if (temp.groupby("collection_day_utc")["split"].nunique() > 1).any():
        raise ValueError("SPLIT_LEAKAGE: acquisition day reused across partitions")

    for key in ("operator_id", "firmware_build_id", "roast_evidence_id",
                "origin_evidence_id", "independent_reviewer", "quality_review_id"):
        if not frame[key].map(lambda x: bool(ID.fullmatch(x))).all():
            raise ValueError(f"Missing independent provenance evidence: {key}")
    if not frame["firmware_build_id"].eq("g3-rc2-20261014").all():
        raise ValueError("Unapproved firmware for prospective acquisition protocol")
    if (frame["operator_id"] == frame["independent_reviewer"]).any():
        raise ValueError("Reviewer must be independent of acquisition operator")
    if not frame["recording_condition"].isin(CONDITIONS).all():
        raise ValueError("Recording condition unknown")
    if frame.loc[frame["split"].eq("blind_final"),
                 ["roast_verified", "origin_verified"]].ne("").any().any():
        raise ValueError("BLIND_LABEL_LEAKAGE: final labels must be held in separate vault")
    coffee_labeled = frame["recording_condition"].eq("coffee") & frame["split"].ne("blind_final")
    if not frame.loc[coffee_labeled, "roast_verified"].isin(ROASTS).all():
        raise ValueError("Missing validated training/calibration roast")
    if frame.loc[coffee_labeled, "origin_verified"].eq("").any():
        raise ValueError("Missing validated training/calibration origin")
    if frame.loc[~coffee_labeled, ["roast_verified", "origin_verified"]].ne("").any().any():
        raise ValueError("Non-coffee or blind observation must not get a forced coffee label")

    for rec in frame.itertuples(index=False):
        path = raw_dir / rec.source_file
        if not rec.source_file.endswith(".csv") or Path(rec.source_file).name != rec.source_file:
            raise ValueError("Unsafe source filename")
        if not path.is_file() or sha(path) != rec.source_sha256:
            raise ValueError(f"Missing/tampered prospective source: {rec.blind_id}")
        issues = validate_file(path)
        if issues:
            raise ValueError(f"Physical sensor acquisition invalid: {rec.blind_id}: {issues[0]}")
    return {
        "status": "PROSPECTIVE_REGISTRY_STRUCTURAL_GATE_PASS_NOT_BLIND_EVALUATED",
        "rows": len(frame),
        "counts_by_split": frame["split"].value_counts().to_dict(),
        "distinct_specimens": int(frame["physical_specimen_id"].nunique()),
        "distinct_lots": int(frame["coffee_lot_id"].nunique()),
        "distinct_sessions": int(frame["operator_session_id"].nunique()),
        "distinct_collection_days": len(set(dates)),
        "physical_provenance_certificates_independently_inspected": False,
        "blind_prediction_scoring_performed": False,
        "model_promotion_allowed": False,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_subparsers(dest="command", required=True)
    inv = mode.add_parser("inventory")
    inv.add_argument("--output-dir", type=Path, required=True)
    check = mode.add_parser("check-prospective")
    check.add_argument("--registry", type=Path, required=True)
    check.add_argument("--raw-dir", type=Path, default=RAW)
    args = p.parse_args()
    if args.command == "inventory":
        result = historical_inventory(args.output_dir)
        print("STAGE11_HISTORICAL_PROVENANCE_AUDIT_PASS")
    else:
        result = validate_registry(pd.read_csv(args.registry, keep_default_na=False),
                                   raw_dir=args.raw_dir)
        print("STAGE11_PROSPECTIVE_SPLIT_STRUCTURAL_GATE_PASS")
    print(json.dumps(result, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
