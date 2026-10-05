"""
Validasi canonical raw acquisition B32.

Scope sengaja dibatasi ke file top-level data/raw/*_B32.csv.
Tidak membaca data legacy MQ9 dan tidak menjalankan preprocessing/training AI.

Kontrak aktif mulai B32:
  - 5 run
  - purging 25 s
  - collecting 5 s
  - sensor gas: 10 kanal dengan MQ3 (bukan MQ9)
  - temperature + humidity wajib tersimpan
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
BATCH_ID = "B32"

ADC_COLS = [
    "adc_tgs822",
    "adc_mq135",
    "adc_mq3",
    "adc_tgs2611",
    "adc_tgs2620",
    "adc_tgs2600",
    "adc_tgs2602",
    "adc_mq8",
    "adc_tgs813",
    "adc_tgs816",
]

EXPECTED_COLUMNS = [
    "timestamp",
    "sample_id",
    "roast_level",
    "origin",
    "batch_id",
    "run_id",
    "phase",
    "sample_idx",
] + ADC_COLS + ["temperature", "humidity"]

EXPECTED_RUNS = [1, 2, 3, 4, 5]
VALID_PHASES = {"purging", "collecting"}
ROAST_FROM_PREFIX = {"L": "light", "M": "medium", "D": "dark"}


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return [f"CSV tidak dapat dibaca: {exc}"]

    if list(df.columns) != EXPECTED_COLUMNS:
        errors.append(
            "header tidak sesuai kontrak B32; "
            f"actual={list(df.columns)}"
        )
        return errors

    if "adc_mq9" in df.columns:
        errors.append("masih mengandung adc_mq9")

    if df.empty:
        errors.append("CSV kosong")
        return errors

    expected_sample = path.stem.rsplit("_B32", 1)[0]
    sample_values = set(df["sample_id"].dropna().astype(str))
    if sample_values != {expected_sample}:
        errors.append(
            f"sample_id tidak cocok nama file: {sorted(sample_values)} "
            f"!= {expected_sample}"
        )

    batch_values = set(df["batch_id"].dropna().astype(str))
    if batch_values != {BATCH_ID}:
        errors.append(f"batch_id bukan B32: {sorted(batch_values)}")

    prefix = expected_sample[:1]
    expected_roast = ROAST_FROM_PREFIX.get(prefix)
    roast_values = set(df["roast_level"].dropna().astype(str).str.lower())
    if expected_roast and roast_values != {expected_roast}:
        errors.append(
            f"roast_level tidak cocok prefix {prefix}: {sorted(roast_values)}"
        )

    run_values = sorted(
        pd.to_numeric(df["run_id"], errors="coerce")
        .dropna()
        .astype(int)
        .unique()
    )
    if run_values != EXPECTED_RUNS:
        errors.append(f"run_id harus 1..5, actual={run_values}")

    phases = set(df["phase"].dropna().astype(str))
    if not phases <= VALID_PHASES:
        errors.append(f"phase tidak dikenal: {sorted(phases - VALID_PHASES)}")

    numeric_cols = (
        ["timestamp", "sample_idx"]
        + ADC_COLS
        + ["temperature", "humidity"]
    )
    for col in numeric_cols:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if numeric.isna().any():
            errors.append(
                f"{col} memiliki {int(numeric.isna().sum())} "
                "nilai kosong/non-numerik"
            )

    for col in ADC_COLS:
        numeric = pd.to_numeric(df[col], errors="coerce")
        if ((numeric < 0) | (numeric > 32767)).any():
            errors.append(
                f"{col} memiliki nilai di luar rentang ADS1115 0..32767"
            )

    temp = pd.to_numeric(df["temperature"], errors="coerce")
    hum = pd.to_numeric(df["humidity"], errors="coerce")
    if ((temp < -40) | (temp > 125)).any():
        errors.append("temperature di luar rentang plausibel -40..125 C")
    if ((hum < 0) | (hum > 100)).any():
        errors.append("humidity di luar rentang 0..100 %RH")

    timestamps = pd.to_numeric(df["timestamp"], errors="coerce")
    if timestamps.notna().all() and not (timestamps.diff().dropna() > 0).all():
        errors.append("timestamp tidak strictly increasing")

    numeric_run = pd.to_numeric(df["run_id"], errors="coerce")
    for run_id in EXPECTED_RUNS:
        run = df[numeric_run == run_id]
        if run.empty:
            continue

        for phase in ("purging", "collecting"):
            part = run[run["phase"] == phase]
            if part.empty:
                errors.append(f"run {run_id}: phase {phase} tidak ada")
                continue

            count = len(part)
            if phase == "purging" and not (24 <= count <= 26):
                errors.append(
                    f"run {run_id}: purging rows={count}, expected sekitar 25"
                )
            if phase == "collecting" and not (5 <= count <= 6):
                errors.append(
                    f"run {run_id}: collecting rows={count}, expected 5..6"
                )

            idx = pd.to_numeric(part["sample_idx"], errors="coerce")
            if idx.notna().all():
                actual = idx.astype(int).tolist()
                expected = list(range(1, len(part) + 1))
                if actual != expected:
                    errors.append(
                        f"run {run_id} {phase}: "
                        "sample_idx tidak kontigu dari 1"
                    )

    return errors


def main() -> int:
    files = sorted(RAW_DIR.glob("*_B32.csv"))
    if not files:
        print(f"[FAIL] Tidak ada file *_B32.csv di {RAW_DIR}")
        return 1

    failures = 0
    print("=" * 78)
    print("VALIDASI RAW ACQUISITION B32 — MQ3 / 5 RUN / SHT30")
    print("=" * 78)

    for path in files:
        errors = validate_file(path)
        if errors:
            failures += 1
            print(f"[FAIL] {path.name}")
            for error in errors:
                print(f"       - {error}")
        else:
            df = pd.read_csv(path)
            purge_n = int((df["phase"] == "purging").sum())
            collect_n = int((df["phase"] == "collecting").sum())
            print(
                f"[PASS] {path.name:<18} rows={len(df):3d} "
                f"purge={purge_n:3d} collect={collect_n:2d} "
                "temp/hum=complete"
            )

    print("-" * 78)
    print(f"Files checked : {len(files)}")
    print(f"PASS          : {len(files) - failures}")
    print(f"FAIL          : {failures}")
    print("Scope         : B32 only; legacy MQ9 intentionally excluded")

    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
