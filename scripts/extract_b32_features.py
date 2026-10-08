"""Candidate leakage-safe feature extraction for MQ3/5-cycle acquisitions.

Each accepted CSV file produces *one* experimental observation. Five cycles
are aggregated within that observation, not represented as independent data.
No model fitting or training is performed. Raw CSVs are never altered.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from validate_acquisition import classify_rows, validate_file

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
FEATURE_NAMES = ("relative_response", "collect_std", "collect_slope_per_s")


def extract_file(path: Path) -> dict:
    errors = validate_file(path)
    if errors:
        raise ValueError(f"{path.name}: " + "; ".join(errors))
    df = pd.read_csv(path)
    sensor_mask, _, _ = classify_rows(df)
    df = df.loc[sensor_mask].copy()
    row = {
        "source_file": path.name,
        "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sample_id": str(df["sample_id"].iloc[0]),
        "roast_level": str(df["roast_level"].iloc[0]),
        "origin": str(df["origin"].iloc[0]),
        "batch_id": str(df["batch_id"].iloc[0]),
        "n_cycles": 5,
    }
    metrics: dict[str, list[float]] = {
        f"f_{sensor.removeprefix('adc_')}_{name}": []
        for sensor in ADC_COLS for name in FEATURE_NAMES
    }
    for cycle in range(1, 6):
        section = df.loc[df["run_id"] == cycle]
        purge = section.loc[section["phase"] == "purging"]
        collect = section.loc[section["phase"] == "collecting"]
        if len(purge) < 5 or len(collect) < 4:
            raise ValueError(f"{path.name}: incomplete cycle {cycle}")
        ts = pd.to_numeric(collect["timestamp"]).to_numpy(dtype=float) / 1000.0
        elapsed = ts - ts[0]
        if not np.all(np.diff(elapsed) > 0):
            raise ValueError(f"{path.name}: non-monotonic collecting timestamp")
        for sensor in ADC_COLS:
            baseline = pd.to_numeric(purge[sensor].tail(5)).to_numpy(dtype=float)
            response = pd.to_numeric(collect[sensor]).to_numpy(dtype=float)
            reference = float(np.median(baseline))
            prefix = f"f_{sensor.removeprefix('adc_')}"
            metrics[f"{prefix}_relative_response"].append(
                float((response.mean() - reference) / max(abs(reference), 1.0))
            )
            metrics[f"{prefix}_collect_std"].append(
                float(response.std(ddof=1))
            )
            metrics[f"{prefix}_collect_slope_per_s"].append(
                float(np.polyfit(elapsed, response, 1)[0])
            )
    # Mean and standard deviation summarize repeatability without splitting
    # correlated cycles between train and validation.
    for key, values in metrics.items():
        row[key + "_mean5"] = float(np.mean(values))
        row[key + "_std5"] = float(np.std(values, ddof=1))
    for sensor in ("temperature", "humidity"):
        row[f"f_{sensor}_mean"] = float(pd.to_numeric(df[sensor]).mean())
    return row


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True,
                        help="Explicit candidate feature CSV path (never raw input)")
    args = parser.parse_args()
    output = (ROOT / args.output).resolve()
    if output.parent == RAW_DIR.resolve() or RAW_DIR.resolve() in output.parents:
        parser.error("Refusing to write into raw data directory")
    if output.exists():
        parser.error("Output already exists; preserve earlier experiment artifact")
    paths = sorted(p for p in RAW_DIR.glob("*.csv")
                   if p.stem.split("_B")[-1].split("_")[0]
                   in {"32", "33", "34", "35"})
    if not paths:
        parser.error("No B32–B35 files found")
    rows = [extract_file(path) for path in paths]
    table = pd.DataFrame(rows)
    features = [col for col in table.columns if col.startswith("f_")]
    if not np.isfinite(table[features].to_numpy(dtype=float)).all():
        parser.error("Non-finite feature detected; output withheld")
    output.parent.mkdir(parents=True, exist_ok=True)
    table.to_csv(output, index=False)
    contract = {
        "status": "CANDIDATE_NOT_APPROVED_FOR_TRAINING_OR_DEPLOYMENT",
        "unit_of_observation": "one acquisition CSV, five cycles aggregated",
        "input_adc_order": ADC_COLS,
        "features": features,
        "feature_count": len(features),
        "rows": len(table),
        "preprocessing_fit": "none (per-cycle baseline uses only same acquisition)",
        "grouping_for_evaluation": "batch_id minimum; future physical specimen/session IDs required",
    }
    output.with_suffix(".schema.json").write_text(
        json.dumps(contract, indent=2), encoding="utf-8"
    )
    print(f"FEATURE_CANDIDATE_PASS rows={len(table)} cols={len(features)}")
    print(output)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
