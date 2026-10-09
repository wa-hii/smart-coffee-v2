"""QA pasif terhadap CSV akuisisi bench yang SUDAH SELESAI.

Tidak mengakses COM/USB, tidak mengirim perintah MCU, tidak mengubah CSV
atau EEPROM. Timestamp yang diperiksa adalah uptime ATmega, bukan pengukuran
aktuator menggunakan alat ukur eksternal.

Contoh:
    python scripts/bench_stage1_passive_qa.py --file data/raw/CONTOH_B99.csv
"""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

import pandas as pd

from acquisition_schema import ADC_COLS, CSV_COLUMNS
from validate_acquisition import file_summary, validate_file


EXPECTED_CYCLES = 5
PHASE_COUNTS = {"purging": 25, "collecting": 5}
MIN_SAMPLE_STEP_MS = 900
MAX_SAMPLE_STEP_MS = 1100


def inspect_completed_csv(path: Path) -> dict:
    """Baca file final saja. Semua pemeriksaan bersifat non-destruktif."""
    path = path.resolve()
    if not path.is_file() or path.suffix.lower() != ".csv":
        raise ValueError("File CSV final tidak ditemukan")
    if (any(part.lower() in {".incoming", "incomplete"} for part in path.parts)
            or "partial" in path.name.lower()):
        raise ValueError("Menolak berkas parsial/incomplete yang mungkin masih ditulis")

    errors = list(validate_file(path))
    df = pd.read_csv(path)
    if list(df.columns) != CSV_COLUMNS:
        raise ValueError("Skema CSV tidak sesuai kontrak, tidak diproses lebih lanjut")
    summary = file_summary(path)
    if summary["metadata_rows"] != 0 or summary["partial_rows"] != 0:
        errors.append("Run bench baru tidak boleh menyimpan baris event/parsial")
    if summary["sensor_rows"] != EXPECTED_CYCLES * sum(PHASE_COUNTS.values()):
        errors.append("Jumlah sampel bench 1 Hz harus 150 untuk run tanpa pause")

    phase_counts = {}
    for cycle in range(1, EXPECTED_CYCLES + 1):
        for phase, expected in PHASE_COUNTS.items():
            group = df.loc[
                (df["run_id"] == cycle) & (df["phase"] == phase)
            ]
            phase_counts[f"{cycle}:{phase}"] = len(group)
            if len(group) != expected:
                errors.append(
                    f"Siklus {cycle} {phase}: {len(group)} sampel, harapan {expected}"
                )
            if len(group) and group["sample_idx"].tolist() != list(
                range(1, expected + 1)
            ):
                errors.append(f"sample_idx tidak kontigu: {cycle}:{phase}")

    steps = pd.to_numeric(df["timestamp"]).diff().dropna()
    step_min = float(steps.min()) if not steps.empty else None
    step_max = float(steps.max()) if not steps.empty else None
    if (steps.empty or
            (steps < MIN_SAMPLE_STEP_MS).any() or
            (steps > MAX_SAMPLE_STEP_MS).any()):
        errors.append("Interval timestamp MCU keluar dari toleransi 900–1100 ms")

    warnings = []
    if df[ADC_COLS].isna().any().any():
        errors.append("ADC hilang")
    if (df[ADC_COLS] == 0).any().any():
        warnings.append("Ada ADC bernilai 0; tinjau validitas dan wiring")
    if (df[ADC_COLS] == 32767).any().any():
        warnings.append("Ada ADC jenuh 32767; tinjau gain dan tegangan")
    for key in ("temperature", "humidity"):
        if df[key].isna().any():
            warnings.append(f"Ada nilai {key} kosong; periksa SHT30")

    return {
        "file": str(path),
        "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "rows": summary["rows"],
        "cycles": phase_counts,
        "timestamp_step_ms_min": step_min,
        "timestamp_step_ms_max": step_max,
        "temp_range_c": (
            float(df["temperature"].min()), float(df["temperature"].max())
        ),
        "humidity_range_pct": (
            float(df["humidity"].min()), float(df["humidity"].max())
        ),
        "errors": errors,
        "warnings": warnings,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, required=True)
    args = parser.parse_args()
    try:
        info = inspect_completed_csv(args.file)
    except (ValueError, OSError) as error:
        print(f"BLOCKED/FAIL: {error}")
        return 1

    print("BENCH_STAGE1_PASSIVE_QA")
    for key in (
        "file", "sha256", "rows", "cycles",
        "timestamp_step_ms_min", "timestamp_step_ms_max",
        "temp_range_c", "humidity_range_pct",
    ):
        print(f"{key}: {info[key]}")
    for warning in info["warnings"]:
        print("WARNING:", warning)
    for error in info["errors"]:
        print("FAIL:", error)
    print("CSV_INTEGRITY:", "PASS" if not info["errors"] else "FAIL")
    print("HARDWARE_ACTUATOR_TIMING: NOT_VERIFIED_BY_CSV")
    print("FIRMWARE_VERSION_ON_BOARD: NOT_VERIFIED_BY_CSV")
    return 0 if not info["errors"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
