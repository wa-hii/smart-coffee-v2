"""Audit reproducible provenance dan kualitas MQ3 B32+ tanpa mengubah raw.

Menghasilkan manifest SHA256, skor kualitas eksploratori per fase, matriks
kelengkapan batch, proxy recovery dan drift. B37 udara bersih secara eksplisit
tidak boleh digunakan untuk ML kopi. Tidak ada fitting atau training model.

Contoh (output khusus, aman tanpa overwrite):
    python scripts/stage2_dataset_audit.py --output-dir data/analysis/stage2
    python scripts/stage2_dataset_audit.py --output-dir data/analysis/stage2 --replace-derived
"""

from __future__ import annotations

import argparse
from collections import Counter
from io import BytesIO
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS, CSV_COLUMNS
from validate_acquisition import classify_rows, validate_file

ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = ROOT / "data" / "raw"
EXCLUSIONS = ROOT / "data" / "analysis" / "bench_only_exclusions.csv"
FILE_RE = re.compile(
    r"^(?P<sample>[DML]-[A-Z0-9]+)_B(?P<batch>\d{2})(?:_[^.]+)?\.csv$"
)
COFFEE_BATCHES = ("B32", "B33", "B34", "B35")
OUTPUT_FILES = (
    "file_manifest.csv", "phase_metrics.csv", "sample_batch_coverage.csv",
    "paired_baseline_drift.csv", "outlier_review.csv", "summary.json",
)


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def read_exclusions(path: Path) -> dict[str, str]:
    if not path.is_file():
        raise ValueError(f"Daftar pengecualian wajib tidak ditemukan: {path}")
    frame = pd.read_csv(path, dtype=str).fillna("")
    required = {"source_file", "source_sha256", "training_eligible"}
    if not required.issubset(frame.columns):
        raise ValueError("Header pengecualian tidak lengkap")
    if frame["source_file"].duplicated().any():
        raise ValueError("Nama file ganda pada manifest pengecualian")
    if (frame["training_eligible"].str.lower() != "false").any():
        raise ValueError("Daftar pengecualian tidak boleh mengizinkan training")
    return dict(zip(frame["source_file"], frame["source_sha256"]))


def scan_paths(raw_dir: Path) -> list[Path]:
    # Hanya CSV final di root: jangan membaca staging, incomplete atau legacy MQ9.
    result = []
    for path in sorted(raw_dir.glob("*.csv")):
        match = FILE_RE.fullmatch(path.name)
        if match and int(match["batch"]) >= 32:
            result.append(path)
    return result


def _finite_median(values: pd.Series) -> float:
    numbers = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    valid = numbers[np.isfinite(numbers)]
    return float(np.median(valid)) if len(valid) else float("nan")


def audit_files(raw_dir: Path, exclusions: dict[str, str]) -> tuple[pd.DataFrame, pd.DataFrame]:
    records: list[dict] = []
    cycles: list[dict] = []
    for path in scan_paths(raw_dir):
        match = FILE_RE.fullmatch(path.name)
        assert match is not None
        raw = path.read_bytes()
        checksum = sha256(raw)
        if path.name in exclusions and checksum != exclusions[path.name]:
            raise ValueError(f"P0: file bench berubah, hash tidak cocok: {path.name}")
        # Validator membaca file. Pastikan akuisisi baru tidak mengubahnya diam-diam.
        errors = validate_file(path)
        if sha256(path.read_bytes()) != checksum:
            raise ValueError(f"P0: berkas berubah selama audit: {path.name}")
        try:
            frame = pd.read_csv(BytesIO(raw))
        except (ValueError, pd.errors.ParserError) as exc:
            raise ValueError(f"CSV tidak dapat diparse: {path.name}") from exc
        if list(frame.columns) != CSV_COLUMNS:
            raise ValueError(f"Skema tidak cocok: {path.name}")
        sensor_mask, event_mask, partial_mask = classify_rows(frame)
        sensor = frame.loc[sensor_mask].copy()
        meta = sensor.iloc[0] if len(sensor) else None
        batch = f"B{int(match['batch']):02d}"
        if path.name in exclusions:
            status = "excluded_bench_clean_air"
        elif meta is not None and str(meta["sample_id"]).upper().endswith("-CAW"):
            raise ValueError(f"P0: CAW clean air missing exclusion hash: {path.name}")
        elif batch == "B37":
            status = "excluded_bench_clean_air"
        elif errors:
            status = "rejected_invalid"
        elif batch in COFFEE_BATCHES:
            status = "candidate_labels_unverified"
        else:
            status = "hold_new_batch_for_review"
        timestamps = pd.to_numeric(sensor["timestamp"], errors="coerce")
        steps = timestamps.diff().dropna()
        record = {
            "source_file": path.name, "source_sha256": checksum,
            "batch": batch, "sample_id": str(meta["sample_id"]) if meta is not None else "",
            "roast_level": str(meta["roast_level"]) if meta is not None else "",
            "origin": str(meta["origin"]) if meta is not None else "",
            "label_source": "recorded_csv_metadata_not_specimen_verified",
            "physical_specimen_id": "", "collection_date_utc": "",
            "operator_session_id": "", "firmware_hash": "",
            "raw_bytes": len(raw), "raw_rows": len(frame), "sensor_rows": int(sensor_mask.sum()),
            "metadata_rows": int(event_mask.sum()), "partial_rows": int(partial_mask.sum()),
            "unique_cycles": int(sensor["run_id"].nunique()) if len(sensor) else 0,
            "adc_missing_cells": int(sensor[ADC_COLS].isna().sum().sum()),
            "adc_zero_cells": int(sensor[ADC_COLS].eq(0).sum().sum()),
            "adc_saturation_cells": int(sensor[ADC_COLS].eq(32767).sum().sum()),
            "temperature_missing": int(sensor["temperature"].isna().sum()),
            "humidity_missing": int(sensor["humidity"].isna().sum()),
            "timestamp_step_min_ms": float(steps.min()) if len(steps) else float("nan"),
            "timestamp_step_max_ms": float(steps.max()) if len(steps) else float("nan"),
            "temperature_mean_c": float(sensor["temperature"].mean()) if len(sensor) else float("nan"),
            "humidity_mean_pct": float(sensor["humidity"].mean()) if len(sensor) else float("nan"),
            "schema": "MQ3_10ADC_5cycles",
            "validator_pass": not bool(errors),
            "validator_error_count": len(errors),
            "validator_errors": " | ".join(errors),
            "training_status": status,
        }
        records.append(record)
        if errors or sensor.empty:
            continue
        for cycle in range(1, 6):
            subset = sensor.loc[sensor["run_id"] == cycle]
            purge = subset.loc[subset["phase"] == "purging"]
            collect = subset.loc[subset["phase"] == "collecting"]
            if len(purge) < 5 or len(collect) < 4:
                continue
            for channel in ADC_COLS:
                pfirst = _finite_median(purge[channel].head(5))
                plast = _finite_median(purge[channel].tail(5))
                response = float(pd.to_numeric(collect[channel]).mean())
                cycles.append({
                    "source_file": path.name,
                    "batch": batch,
                    "sample_id": record["sample_id"],
                    "training_status": status,
                    "cycle": cycle, "channel": channel,
                    "purging_n": len(purge), "collecting_n": len(collect),
                    "purge_first5_median": pfirst, "purge_last5_median": plast,
                    "collecting_mean": response,
                    # Indikator respons relatif; bukan kalibrasi ppm atau validasi gas.
                    "relative_response": (response - plast) / max(abs(plast), 1.0),
                    "recovery_proxy_abs_fraction": abs(pfirst - plast) /
                        max(abs(plast), 1.0),
                })

    # Daftar pengecualian hidup di Git, file mentah boleh hanya tersimpan di
    # komputer pengukuran. Tidak ditemukannya file berarti tidak ikut audit,
    # BUKAN izin otomatis terhadap file dengan nama sama namun hash berbeda.
    return pd.DataFrame(records), pd.DataFrame(cycles)


def coverage_table(manifest: pd.DataFrame) -> pd.DataFrame:
    cohort = manifest.loc[
        manifest["batch"].isin(COFFEE_BATCHES) &
        manifest["validator_pass"].astype(bool) &
        manifest["training_status"].eq("candidate_labels_unverified")
    ]
    keys = sorted(cohort["sample_id"].unique())
    records = []
    for sample in keys:
        group = cohort.loc[cohort["sample_id"] == sample]
        row = {
            "sample_id": sample,
            "roast_level": group["roast_level"].iloc[0],
            "origin": group["origin"].iloc[0],
        }
        for batch in COFFEE_BATCHES:
            row[batch + "_file_count"] = int(group["batch"].eq(batch).sum())
        row["total_files"] = len(group)
        row["batch_coverage"] = int(group["batch"].nunique())
        row["multiple_files_in_one_batch"] = bool(
            any(row[batch + "_file_count"] > 1 for batch in COFFEE_BATCHES)
        )
        records.append(row)
    return pd.DataFrame(records)


def paired_drift(phase: pd.DataFrame) -> pd.DataFrame:
    """Median baseline purge per file, per channel; pasangan sample_id per batch.

    Ukuran eksploratori; perbedaan hari, spesimen, firmware dan urutan pengukuran
    tidak diketahui, sehingga TIDAK dapat diatribusikan sebagai sensor drift.
    """
    if phase.empty:
        return pd.DataFrame()
    cohort = phase.loc[phase["training_status"].eq("candidate_labels_unverified")]
    per_file = cohort.groupby(
        ["source_file", "sample_id", "batch", "channel"], as_index=False
    )["purge_last5_median"].median()
    by_batch = per_file.groupby(
        ["sample_id", "batch", "channel"], as_index=False
    )["purge_last5_median"].median()
    first = by_batch.loc[by_batch["batch"] == "B32"]
    last = by_batch.loc[by_batch["batch"] == "B35"]
    joined = first.merge(last, on=["sample_id", "channel"],
                         suffixes=("_B32", "_B35"))
    if joined.empty:
        return pd.DataFrame()
    joined["relative_shift_B35_vs_B32"] = (
        (joined["purge_last5_median_B35"] - joined["purge_last5_median_B32"]) /
        joined["purge_last5_median_B32"].abs().clip(lower=1.0)
    )
    return joined[[
        "sample_id", "channel", "purge_last5_median_B32",
        "purge_last5_median_B35", "relative_shift_B35_vs_B32"
    ]].sort_values(["channel", "sample_id"])


def outlier_table(phase: pd.DataFrame) -> pd.DataFrame:
    """Flag eksploratori berdasarkan relatif respons file terhadap same sample_id.

    Tidak menghapus sampel. Karena N kecil dan banyak respons mendekati nol,
    hasil hanyalah antrian review, bukan ground truth outlier.
    """
    if phase.empty:
        return pd.DataFrame()
    cohort = phase.loc[phase["training_status"].eq("candidate_labels_unverified")]
    per_file = cohort.groupby(
        ["source_file", "sample_id", "batch", "channel"], as_index=False
    )["relative_response"].median()
    records = []
    for (sample, channel), group in per_file.groupby(["sample_id", "channel"]):
        values = group["relative_response"].to_numpy(dtype=float)
        if len(values) < 4:
            continue
        median = float(np.median(values))
        mad = float(np.median(np.abs(values - median)))
        # Epsilon floor: sangat kecil ≠ outlier ilmiah pasti.
        scale = max(1.4826 * mad, 1e-4)
        for rec, value in zip(group.to_dict("records"), values):
            score = abs(float(value) - median) / scale
            if score > 3.5:
                records.append({
                    "source_file": rec["source_file"], "batch": rec["batch"],
                    "sample_id": sample, "channel": channel,
                    "relative_response": float(value),
                    "group_median": median, "robust_score": score,
                    "review_only": True,
                })
    return pd.DataFrame(records, columns=[
        "source_file", "batch", "sample_id", "channel",
        "relative_response", "group_median", "robust_score", "review_only"
    ])


def generate_summary(manifest: pd.DataFrame, phase: pd.DataFrame,
                     coverage: pd.DataFrame, drift: pd.DataFrame,
                     outliers: pd.DataFrame,
                     exclusion_names: set[str] | None = None) -> dict:
    cohort = manifest.loc[manifest["batch"].isin(COFFEE_BATCHES)]
    candidates = cohort.loc[cohort["training_status"].eq("candidate_labels_unverified")]
    hash_duplicates = manifest.loc[
        manifest.duplicated("source_sha256", keep=False), "source_file"
    ].tolist()
    metadata_variants = candidates.groupby("sample_id")["origin"].nunique()
    return {
        "status": "AUDIT_ONLY_NOT_ML_APPROVAL",
        "unit_of_observation": "one CSV acquisition (5 correlated cycles)",
        "physical_specimen_identity_verified": False,
        "calendar_session_identity_verified": False,
        "files_all_B32plus": len(manifest),
        "files_B32_B35": len(cohort),
        "B32_B35_canonical_valid": int(cohort["validator_pass"].sum()),
        "B32_B35_training_candidates_not_approved": len(candidates),
        "bench_excluded": manifest.loc[
            manifest["training_status"].eq("excluded_bench_clean_air"),
            "source_file"
        ].tolist(),
        "bench_exclusions_not_present_in_checkout": sorted(
            (exclusion_names or set()) - set(manifest["source_file"])
        ),
        "files_by_batch": {k: int(v) for k, v in
                           sorted(manifest["batch"].value_counts().items())},
        "coffee_roast_counts": {k: int(v) for k, v in
                                sorted(candidates["roast_level"].value_counts().items())},
        "coffee_sample_combinations": len(coverage),
        "coffee_missing_sample_batch_cells": int(
            sum((coverage[batch + "_file_count"] == 0).sum()
                for batch in COFFEE_BATCHES)
        ) if len(coverage) else 0,
        "coffee_repeated_sample_batch_cells": int(
            sum((coverage[batch + "_file_count"] > 1).sum()
                for batch in COFFEE_BATCHES)
        ) if len(coverage) else 0,
        "same_sample_multiple_origin_strings": [
            key for key, value in metadata_variants.items() if value > 1
        ],
        "identical_csv_hash_duplicates": hash_duplicates,
        "phase_rows_exploratory": len(phase),
        "median_recovery_proxy_by_channel": {
            name: float(value) for name, value in
            phase.loc[phase["training_status"].eq("candidate_labels_unverified")]
            .groupby("channel")["recovery_proxy_abs_fraction"].median().items()
        },
        "paired_B32_B35_comparisons": len(drift),
        "median_abs_baseline_shift_B35_vs_B32_by_channel": {
            name: float(value) for name, value in
            drift.assign(abs_shift=drift["relative_shift_B35_vs_B32"].abs())
            .groupby("channel")["abs_shift"].median().items()
        } if len(drift) else {},
        "review_only_outlier_flags": len(outliers),
        "warning": (
            "Drift/recovery/carryover proxies explorative, confounded by "
            "unknown physical specimen/day/order and sensor conditioning; "
            "no causality claim and no automatic exclusion."
        ),
    }


def write_outputs(output_dir: Path, outputs: dict[str, object],
                  replace_derived: bool, raw_dir: Path = RAW_DIR) -> None:
    raw = raw_dir.resolve()
    destination = output_dir.resolve()
    if destination == raw or raw in destination.parents:
        raise ValueError("Tidak boleh menulis output ke data/raw")
    if any((destination / name).exists() for name in OUTPUT_FILES) and not replace_derived:
        raise FileExistsError("Hasil audit sudah ada; gunakan --replace-derived "
                              "hanya untuk file turunan di output-dir sendiri")
    destination.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILES:
        content = outputs[name]
        target = destination / name
        if name.endswith(".json"):
            target.write_text(
                json.dumps(content, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8"
            )
        else:
            assert isinstance(content, pd.DataFrame)
            content.to_csv(target, index=False, float_format="%.8g")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW_DIR)
    parser.add_argument("--exclusions", type=Path, default=EXCLUSIONS)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replace-derived", action="store_true")
    args = parser.parse_args()
    exclusions = read_exclusions(args.exclusions)
    manifest, phase = audit_files(args.raw_dir, exclusions)
    if manifest.empty:
        raise ValueError("Tidak ada file final MQ3 B32+")
    coverage = coverage_table(manifest)
    drift = paired_drift(phase)
    outliers = outlier_table(phase)
    summary = generate_summary(
        manifest, phase, coverage, drift, outliers, set(exclusions)
    )
    write_outputs(args.output_dir, dict(zip(OUTPUT_FILES, (
        manifest, phase, coverage, drift, outliers, summary
    ))), args.replace_derived, args.raw_dir)
    print("STAGE2_DATASET_AUDIT_PASS")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
