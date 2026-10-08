"""Read-only inventory for B32-B35 MQ3 acquisition CSVs.

Run: python scripts/audit_b32_dataset.py
No raw, model, or processed dataset is modified.
"""

from collections import Counter, defaultdict
from pathlib import Path

import pandas as pd

from acquisition_schema import ADC_COLS
from validate_acquisition import classify_rows, validate_file

RAW_DIR = Path(__file__).resolve().parents[1] / "data" / "raw"


def main() -> int:
    paths = sorted(p for p in RAW_DIR.glob("*.csv")
                   if p.stem.split("_B")[-1].split("_")[0] in
                   {"32", "33", "34", "35"})
    summary = Counter()
    by_batch = Counter()
    by_roast = Counter()
    by_sample = Counter()
    origin_by_sample = defaultdict(set)
    failures = {}
    for path in paths:
        df = pd.read_csv(path)
        good, event, partial = classify_rows(df)
        sensor = df.loc[good]
        sample = str(sensor["sample_id"].iloc[0]) if len(sensor) else "?"
        batch = str(sensor["batch_id"].iloc[0]) if len(sensor) else "?"
        roast = str(sensor["roast_level"].iloc[0]) if len(sensor) else "?"
        by_batch[batch] += 1
        by_roast[roast] += 1
        by_sample[sample] += 1
        if len(sensor):
            origin_by_sample[sample].update(sensor["origin"].dropna().astype(str).unique())
        summary["files"] += 1
        summary["rows"] += len(df)
        summary["sensor"] += int(good.sum())
        summary["events"] += int(event.sum())
        summary["partial"] += int(partial.sum())
        summary["purging"] += int(sensor["phase"].eq("purging").sum())
        summary["collecting"] += int(sensor["phase"].eq("collecting").sum())
        summary["temperature_missing"] += int(sensor["temperature"].isna().sum())
        summary["humidity_missing"] += int(sensor["humidity"].isna().sum())
        for col in ADC_COLS:
            adc = pd.to_numeric(sensor[col], errors="coerce")
            summary["adc_zero"] += int(adc.eq(0).sum())
            summary["adc_saturated"] += int(adc.ge(32767).sum())
        issues = validate_file(path)
        if issues:
            failures[path.name] = issues

    print("B32-B35 data quality inventory (CSV validity only)")
    for key in sorted(summary):
        print(f"{key}: {summary[key]}")
    print("batch_files:", dict(sorted(by_batch.items())))
    print("roast_files:", dict(sorted(by_roast.items())))
    print("sample_files:", dict(sorted(by_sample.items())))
    print("sample_origin_mismatches:",
          {key: sorted(val) for key, val in origin_by_sample.items() if len(val) > 1})
    print("validator_pass:", len(paths) - len(failures), "/", len(paths))
    for name, issues in failures.items():
        print("FAIL", name, issues)
    print("NOTE: files and 5-cycle runs are not guaranteed independent coffee specimens")
    print("NOTE: millis timestamps are MCU uptime, not calendar acquisition timestamps")
    return 1 if not paths or failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
