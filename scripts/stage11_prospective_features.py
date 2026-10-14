"""Custodian-run feature export for verified prospective splits, label-safe.

No historical samples are accepted, no raw edits. Public blind features must
be distributed WITHOUT the raw files or registry that reveal roast/origin.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

from extract_b32_features import extract_sensor_features
from stage4_model_benchmark import INPUT, ROOT, sha256
from stage11_provenance_guard import validate_registry
from validate_acquisition import classify_rows


def export_features(registry_path: Path, raw_dir: Path, output: Path) -> dict:
    raw = raw_dir.resolve()
    dst = output.resolve()
    if dst.exists() or dst == raw or raw in dst.parents:
        raise ValueError("Use fresh derived output; never overwrite raw")
    registry = pd.read_csv(registry_path, keep_default_na=False, dtype=str)
    summary = validate_registry(registry, raw_dir=raw_dir)
    frozen_columns = json.loads((INPUT / "feature_groups.json").read_text(
        encoding="utf-8"))["feature_order"]
    if len(frozen_columns) != 82:
        raise ValueError("82 feature order changed")
    outputs = {"development": [], "calibration": [], "blind_final": []}
    for rec in registry.itertuples(index=False):
        frame = pd.read_csv(raw_dir / rec.source_file)
        sensors, _, partial = classify_rows(frame)
        if partial.any():
            raise ValueError("Partial sensor rows in prospective data")
        vectors = extract_sensor_features(
            frame.loc[sensors].copy(), include_collect_mean=True,
        )
        if list(vectors) != frozen_columns:
            raise ValueError("Training/host feature contract changed")
        # No source filename, sample code, raw hash, lot, batch, session,
        # UI roast or origin is exported to the ML analyst.
        feature_row = {"blind_id": rec.blind_id,
                       **{name: vectors[name] for name in frozen_columns}}
        if rec.split != "blind_final":
            feature_row["recording_condition"] = rec.recording_condition
            feature_row["verified_roast"] = rec.roast_verified
            feature_row["verified_origin"] = rec.origin_verified
            # For coffee the operator UI must not disagree with independent
            # human-verified labels without a documented adjudication.
            if rec.recording_condition == "coffee" and (
                rec.roast_verified != str(frame["roast_level"].dropna().iloc[0]).lower()
                or rec.origin_verified != str(frame["origin"].dropna().iloc[0])
            ):
                raise ValueError("LABEL_DISAGREEMENT: requires independent adjudication")
        outputs[rec.split].append(feature_row)
    for scope in ("development", "calibration"):
        coffee = [row for row in outputs[scope] if row["recording_condition"] == "coffee"]
        if set(row["verified_roast"] for row in coffee) != {"dark", "light", "medium"}:
            raise ValueError(f"Insufficient roast class coverage in {scope}")
    if not outputs["blind_final"]:
        raise ValueError("No unseen final features available")
    dst.mkdir(parents=True)
    files = {}
    for scope, rows in outputs.items():
        dest = dst / f"{scope}_features.csv"
        # UUIDv4-based ordering avoids leaking the acquisition order/roast
        # run grouping to the ML analyst through CSV row order.
        pd.DataFrame(rows).sort_values("blind_id").to_csv(
            dest, index=False, float_format="%.15g")
        files[scope] = {"n": len(rows), "sha256": sha256(dest)}
    info = {
        "status": "PROSPECTIVE_FEATURE_VIEWS_GENERATED_NOT_MODEL_APPROVAL",
        "registry_validation": summary,
        "frozen_feature_schema_sha256": sha256(INPUT / "feature_groups.json"),
        "blind_final_view_contains_label_or_source_filename": False,
        "raw_csv_label_metadata_requires_external_access_control": True,
        "counts_and_hashes": files,
        "model_promotion_allowed": False,
    }
    (dst / "summary.json").write_text(json.dumps(
        info, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return info


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--registry", type=Path, required=True)
    p.add_argument("--raw-dir", type=Path, required=True)
    p.add_argument("--output-dir", type=Path, required=True)
    a = p.parse_args()
    print(json.dumps(export_features(a.registry, a.raw_dir, a.output_dir),
                     ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
