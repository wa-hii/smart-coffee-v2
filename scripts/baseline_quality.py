"""Read-only baseline B0 diagnostics; a clean-air claim needs operator evidence."""
from __future__ import annotations

import csv
import hashlib
import json
import math
from pathlib import Path
from statistics import median

from baseline_recording import BASELINE_COLS, BASELINE_SAMPLES
from acquisition_schema import ADC_COLS


def inspect_baseline(path: Path) -> dict:
    with path.open(newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        if reader.fieldnames != BASELINE_COLS:
            raise ValueError("Unexpected baseline schema")
        rows = list(reader)
    if len(rows) != BASELINE_SAMPLES:
        raise ValueError("Baseline CSV must have exactly 60 samples")
    idx = [int(r["sample_idx"]) for r in rows]
    timestamps = [int(r["timestamp"]) for r in rows]
    if idx != list(range(1, BASELINE_SAMPLES+1)):
        raise ValueError("Baseline index is not contiguous")
    if any(not 900 <= b-a <= 1100 for a,b in zip(timestamps,timestamps[1:])):
        raise ValueError("Baseline timestamp gap is not 1 Hz")
    channels = []
    for name in ADC_COLS:
        values = [int(row[name]) for row in rows]
        if any(not 1 <= x <= 32766 for x in values):
            raise ValueError(f"Out-of-range baseline ADC {name}")
        first, last = median(values[:10]), median(values[-10:])
        drift_pct = 100 * (last-first) / first
        channels.append({
            "sensor": name,
            "b0_last10_median_adc": last,
            "first10_median_adc": first,
            "first_to_last_drift_pct": round(drift_pct, 4),
            "last10_min": min(values[-10:]),
            "last10_max": max(values[-10:]),
            "stable_within_1pct_by_window_medians": abs(drift_pct) <= 1.0,
        })
    temp=[float(row["temperature"]) for row in rows]
    humidity=[float(row["humidity"]) for row in rows]
    if any(not (math.isfinite(x) and -40 <= x <= 125) for x in temp) or any(not (math.isfinite(x) and 0 <= x <= 100) for x in humidity):
        raise ValueError("Environment plausibility")
    return {
        "source": path.name,
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "sample_count": len(rows),
        "duration_first_to_last_ms": timestamps[-1]-timestamps[0],
        "temperature_range_c": [min(temp),max(temp)],
        "humidity_range_rh": [min(humidity),max(humidity)],
        "sensor_b0": channels,
        "drift_review_recommended": any(not x["stable_within_1pct_by_window_medians"] for x in channels),
        "status": "CAPTURE_COMPLETE_AIR_QUALITY_UNVERIFIED",
        "interpretation": "B0 uses median of final 10 samples. Stability is an exploratory 1% threshold, not sensor-specific acceptance evidence.",
        "r0_eeprom_modified": False,
    }


def publish_quality(path: Path, build_id: str = "UNKNOWN") -> Path:
    report = inspect_baseline(path)
    report["fw_build_id_from_start_event"] = build_id
    target=path.with_suffix(".baseline_qc.json")
    with target.open("x",encoding="utf-8") as f:
        json.dump(report,f,ensure_ascii=False,indent=2)
        f.write("\n")
    return target
