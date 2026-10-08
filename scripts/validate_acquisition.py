"""Validate canonical E-NOSE raw acquisitions (B32 and newer).

Historical B33-B35 files can contain metadata-only PHASE_CHANGE rows created
by an older LCD autosave listener.  Those rows are recognized explicitly and
do not invalidate otherwise complete sensor data.  Partial sensor rows,
however, fail validation.
"""

from __future__ import annotations

import re
from pathlib import Path

import pandas as pd

from acquisition_schema import ADC_COLS, CSV_COLUMNS, VALID_PHASES


ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
EXPECTED_RUNS = [1, 2, 3, 4, 5]
ROAST_FROM_PREFIX = {"L": "light", "M": "medium", "D": "dark"}
BATCH_RE = re.compile(r"_B(\d+)(?:_|\.csv$)", re.IGNORECASE)


def classify_rows(df: pd.DataFrame) -> tuple[pd.Series, pd.Series, pd.Series]:
    """Return masks for complete sensor, metadata-only, and partial rows."""
    core_columns = ["timestamp", "sample_idx"] + ADC_COLS
    numeric = pd.DataFrame(
        {
            column: pd.to_numeric(df[column], errors="coerce")
            for column in core_columns
        },
        index=df.index,
    )
    sensor_rows = numeric.notna().all(axis=1)
    # An actual legacy PHASE_CHANGE CSV row has *empty* sensor fields.
    # Nonnumeric/corrupt text in those columns must not masquerade as an event.
    metadata_only = df[core_columns].isna().all(axis=1)
    partial_rows = ~(sensor_rows | metadata_only)
    return sensor_rows, metadata_only, partial_rows


def validate_file(path: Path) -> list[str]:
    errors: list[str] = []
    try:
        df = pd.read_csv(path)
    except Exception as exc:
        return [f"CSV tidak dapat dibaca: {exc}"]

    if list(df.columns) != CSV_COLUMNS:
        return [
            "header tidak sesuai canonical acquisition schema; "
            f"actual={list(df.columns)}"
        ]

    if df.empty:
        return ["CSV kosong"]

    sample_values = set(df["sample_id"].dropna().astype(str).str.strip())
    batch_values = set(df["batch_id"].dropna().astype(str).str.strip())
    roast_values = set(
        df["roast_level"].dropna().astype(str).str.strip().str.lower()
    )

    if len(sample_values) != 1:
        errors.append(f"sample_id tidak konsisten: {sorted(sample_values)}")
    if len(batch_values) != 1:
        errors.append(f"batch_id tidak konsisten: {sorted(batch_values)}")
    if len(roast_values) != 1:
        errors.append(f"roast_level tidak konsisten: {sorted(roast_values)}")

    sample_id = next(iter(sample_values), "")
    batch_id = next(iter(batch_values), "")
    roast_level = next(iter(roast_values), "")

    if sample_id and batch_id:
        expected_prefix = f"{sample_id}_{batch_id}"
        if not path.stem.startswith(expected_prefix):
            errors.append(
                f"nama file tidak cocok metadata: expected prefix "
                f"{expected_prefix!r}"
            )

    expected_roast = ROAST_FROM_PREFIX.get(sample_id[:1])
    if expected_roast and roast_level != expected_roast:
        errors.append(
            f"roast_level {roast_level!r} tidak cocok prefix "
            f"{sample_id[:1]!r}"
        )

    run_numeric = pd.to_numeric(df["run_id"], errors="coerce")
    run_values = sorted(run_numeric.dropna().astype(int).unique().tolist())
    if run_values != EXPECTED_RUNS:
        errors.append(f"run_id harus 1..5, actual={run_values}")

    phases = set(df["phase"].dropna().astype(str).str.strip().str.lower())
    unknown_phases = phases - VALID_PHASES
    if unknown_phases:
        errors.append(f"phase tidak dikenal: {sorted(unknown_phases)}")

    sensor_mask, metadata_mask, partial_mask = classify_rows(df)
    partial_count = int(partial_mask.sum())
    metadata_count = int(metadata_mask.sum())
    if partial_count:
        errors.append(
            f"terdapat {partial_count} row sensor parsial "
            "(sebagian field wajib kosong)"
        )
    if int(sensor_mask.sum()) == 0:
        errors.append("tidak ada row sensor lengkap")

    # Older LCD listener produced exactly one metadata event row per phase
    # transition: 9 for a five-run acquisition.  More than that is suspicious.
    if metadata_count > 9:
        errors.append(
            f"metadata-only rows terlalu banyak: {metadata_count} (maks 9)"
        )
    metadata = df.loc[metadata_mask]
    if not metadata.empty:
        required_meta = ["sample_id", "roast_level", "origin", "batch_id",
                         "run_id", "phase"]
        if metadata[required_meta].isna().any().any():
            errors.append("metadata-only row has missing event metadata")
        if metadata.duplicated(subset=["run_id", "phase"]).any():
            errors.append("duplicate historical phase-change metadata rows")

    sensor_df = df.loc[sensor_mask].copy()
    if not sensor_df.empty:
        duplicate_keys = ["run_id", "phase", "sample_idx"]
        duplicates = sensor_df.duplicated(subset=duplicate_keys, keep=False)
        if duplicates.any():
            errors.append(
                f"duplicate sensor index (run_id, phase, sample_idx): "
                f"{int(duplicates.sum())} rows"
            )

        for field in ("run_id", "sample_idx"):
            numeric = pd.to_numeric(sensor_df[field], errors="coerce")
            if (
                numeric.isna().any()
                or (numeric < 1).any()
                or (numeric % 1 != 0).any()
            ):
                errors.append(f"{field}: non-integer, missing, or nonpositive")

        for column in ADC_COLS:
            values = pd.to_numeric(sensor_df[column], errors="coerce")
            if ((values < 0) | (values > 32767) | (values % 1 != 0)).any():
                errors.append(
                    f"{column} bukan integer dalam rentang ADS1115 0..32767"
                )

        timestamps = pd.to_numeric(sensor_df["timestamp"], errors="coerce")
        if not (timestamps.diff().dropna() > 0).all():
            errors.append("timestamp sensor tidak strictly increasing")

        for column, lower, upper, label in (
            ("temperature", -40, 125, "temperature"),
            ("humidity", 0, 100, "humidity"),
        ):
            values = pd.to_numeric(sensor_df[column], errors="coerce")
            present = values.dropna()
            if not present.empty and (
                (present < lower) | (present > upper)
            ).any():
                errors.append(
                    f"{label} di luar rentang plausibel "
                    f"{lower}..{upper}"
                )

        sensor_run = pd.to_numeric(sensor_df["run_id"], errors="coerce")
        for run_id in EXPECTED_RUNS:
            run = sensor_df.loc[sensor_run == run_id]
            if run.empty:
                errors.append(f"run {run_id}: tidak ada sensor row")
                continue

            for phase in ("purging", "collecting"):
                count = int(
                    (
                        run["phase"].astype(str).str.lower().str.strip()
                        == phase
                    ).sum()
                )
                if phase == "purging" and not (23 <= count <= 27):
                    errors.append(
                        f"run {run_id}: purging sensor rows={count}, "
                        "expected sekitar 25"
                    )
                if phase == "collecting" and not (4 <= count <= 7):
                    errors.append(
                        f"run {run_id}: collecting sensor rows={count}, "
                        "expected sekitar 5"
                    )

    return errors


def file_summary(path: Path) -> dict[str, int]:
    df = pd.read_csv(path)
    sensor, metadata, partial = classify_rows(df)
    return {
        "rows": len(df),
        "sensor_rows": int(sensor.sum()),
        "metadata_rows": int(metadata.sum()),
        "partial_rows": int(partial.sum()),
    }


def batch_number(path: Path) -> int | None:
    match = BATCH_RE.search(path.name)
    return int(match.group(1)) if match else None


def main() -> int:
    files = [
        path
        for path in sorted(RAW_DIR.glob("*.csv"))
        if (batch_number(path) or 0) >= 32
    ]
    if not files:
        print(f"[FAIL] Tidak ada canonical B32+ CSV di {RAW_DIR}")
        return 1

    failures = 0
    print("=" * 78)
    print("VALIDASI RAW ACQUISITION B32+ - MQ3 / 5 RUN")
    print("=" * 78)
    for path in files:
        errors = validate_file(path)
        summary = file_summary(path)
        if errors:
            failures += 1
            print(f"[FAIL] {path.name}")
            for error in errors:
                print(f"       - {error}")
        else:
            print(
                f"[PASS] {path.name:<38} "
                f"sensor={summary['sensor_rows']:3d} "
                f"metadata={summary['metadata_rows']:2d} "
                f"partial={summary['partial_rows']:2d}"
            )

    print("-" * 78)
    print(f"Files checked : {len(files)}")
    print(f"PASS          : {len(files) - failures}")
    print(f"FAIL          : {failures}")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
