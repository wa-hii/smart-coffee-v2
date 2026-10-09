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


def extract_sensor_features(
    sensor_df: pd.DataFrame, *, include_collect_mean: bool = False
) -> dict[str, float]:
    """Pure MCU-frame -> fitur; sama untuk training, offline, dan calon host Pi.

    Input harus berisi hanya baris SENSOR, lima siklus serta fase terpisah.
    Tidak membutuhkan sample_id/roast/origin/batch. Tidak melakukan scaling,
    imputasi global, fitting atau pembagian train/test.

    include_collect_mean=False mempertahankan kontrak legacy 62 fitur.
    True menambahkan 20 fitur collecting_mean (82 keseluruhan).
    """
    df = sensor_df.copy()
    required = {"timestamp", "run_id", "phase", "sample_idx", *ADC_COLS,
                "temperature", "humidity"}
    if not required.issubset(df.columns):
        raise ValueError(f"missing sensor fields: {sorted(required - set(df.columns))}")
    if df.empty:
        raise ValueError("empty sensor frame")
    if not np.array_equal(
        np.sort(pd.to_numeric(df["run_id"], errors="raise").unique()),
        np.arange(1, 6),
    ):
        raise ValueError("sensor frames must contain exactly cycles 1..5")
    for column in ("timestamp", "run_id", "sample_idx", *ADC_COLS):
        vals = pd.to_numeric(df[column], errors="raise").to_numpy(dtype=float)
        if not np.isfinite(vals).all():
            raise ValueError(f"nonfinite sensor column: {column}")
        if column.startswith("adc_") and (
            (vals < 0).any() or (vals > 32767).any() or
            (vals % 1 != 0).any()
        ):
            raise ValueError(f"ADC outside 0..32767/integer: {column}")
    t_all = pd.to_numeric(df["timestamp"]).to_numpy(dtype=float)
    if not np.all(np.diff(t_all) > 0):
        raise ValueError("non-monotonic timestamp")
    if not set(df["phase"].astype(str).unique()).issubset({"purging", "collecting"}):
        raise ValueError("unknown sensor phase")

    metrics: dict[str, list[float]] = {
        f"f_{sensor.removeprefix('adc_')}_{name}": []
        for sensor in ADC_COLS for name in FEATURE_NAMES
    }
    extra_metrics: dict[str, list[float]] = {
        f"f_{sensor.removeprefix('adc_')}_collect_mean": []
        for sensor in ADC_COLS
    } if include_collect_mean else {}
    for cycle in range(1, 6):
        section = df.loc[df["run_id"] == cycle]
        purge = section.loc[section["phase"] == "purging"]
        collect = section.loc[section["phase"] == "collecting"]
        if len(purge) < 5 or len(collect) < 4:
            raise ValueError(f"incomplete cycle {cycle}")
        for phase_name, phase in (("purging", purge), ("collecting", collect)):
            indices = pd.to_numeric(phase["sample_idx"]).to_numpy(dtype=float)
            if not np.array_equal(indices, np.arange(1, len(phase) + 1)):
                raise ValueError(f"non-contiguous sample_idx cycle={cycle} {phase_name}")
        if section["phase"].tolist() != (
            ["purging"] * len(purge) + ["collecting"] * len(collect)
        ):
            raise ValueError(f"phase order invalid cycle={cycle}")
        ts = pd.to_numeric(collect["timestamp"]).to_numpy(dtype=float) / 1000.0
        elapsed = ts - ts[0]
        if not np.all(np.diff(elapsed) > 0):
            raise ValueError(f"non-monotonic collecting timestamp cycle={cycle}")
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
            if include_collect_mean:
                extra_metrics[f"{prefix}_collect_mean"].append(float(response.mean()))
    # Mean and standard deviation summarize repeatability without splitting
    # correlated cycles between train and validation.
    features: dict[str, float] = {}
    for key, values in metrics.items():
        features[key + "_mean5"] = float(np.mean(values))
        features[key + "_std5"] = float(np.std(values, ddof=1))
    for sensor in ("temperature", "humidity"):
        raw = pd.to_numeric(df[sensor], errors="coerce")
        if raw.isna().any() or not np.isfinite(raw.to_numpy(dtype=float)).all():
            raise ValueError(f"missing/nonfinite {sensor}; no silent imputation")
        features[f"f_{sensor}_mean"] = float(raw.mean())
    for key, values in extra_metrics.items():
        features[key + "_mean5"] = float(np.mean(values))
        features[key + "_std5"] = float(np.std(values, ddof=1))
    if len(features) != (82 if include_collect_mean else 62):
        raise AssertionError("feature contract count changed")
    if not np.isfinite(np.fromiter(features.values(), dtype=float)).all():
        raise ValueError("nonfinite feature; fail closed")
    return features


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
    row.update(extract_sensor_features(df))
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
