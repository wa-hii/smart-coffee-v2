"""Stage 3: ekstraksi fitur kandidat MQ3, deterministik berbasis manifest SHA256.

Tidak melakukan fitting/training. Fitur identik untuk data file dan frame
sensor in-memory (calon Raspberry Pi); label hanya metadata luar fitur.
Jalankan: python scripts/stage3_feature_pipeline.py --output-dir data/processed/stage3_v3
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from extract_b32_features import extract_file, extract_sensor_features
from stage2_dataset_audit import COFFEE_BATCHES, read_exclusions

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "raw"
MANIFEST = ROOT / "data" / "analysis" / "stage2_v2" / "file_manifest.csv"
EXCLUSIONS = ROOT / "data" / "analysis" / "bench_only_exclusions.csv"
OUTPUT_FILES = (
    "candidate_features82.csv", "candidate_legacy62.csv",
    "feature_groups.json", "feature_quality.csv", "feature_rejections.csv",
    "snapshot.json", "summary.json",
)
SHA_PATTERN = re.compile(r"[a-f0-9]{64}")
STAGE3_VERSION = "stage3.feature.v1"


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def groups_for_features(columns: list[str]) -> dict[str, list[str]]:
    """Grup fitur ditentukan a priori, tanpa membaca label atau metrik model."""
    names = [sensor.removeprefix("adc_") for sensor in ADC_COLS]
    def names_for(suffix: str) -> list[str]:
        return [f"f_{sensor}_{suffix}" for sensor in names]

    rel_mean = names_for("relative_response_mean5")
    rel_std = names_for("relative_response_std5")
    collect_mean = names_for("collect_mean_mean5")
    dynamic30 = [
        key for name in names
        for key in (
            f"f_{name}_relative_response_mean5",
            f"f_{name}_collect_std_mean5",
            f"f_{name}_collect_slope_per_s_mean5",
        )
    ]
    env = ["f_temperature_mean", "f_humidity_mean"]
    full62 = [key for key in columns if not key.endswith(
        ("collect_mean_mean5", "collect_mean_std5")
    )]
    groups = {
        "response10": rel_mean,
        "response20": rel_mean + rel_std,
        "dynamic30": dynamic30,
        "dynamic32_environment": dynamic30 + env,
        "raw_collect10": collect_mean,
        "legacy62": full62,
        "expanded82": columns,
    }
    assert {name: len(items) for name, items in groups.items()} == {
        "response10": 10, "response20": 20, "dynamic30": 30,
        "dynamic32_environment": 32, "raw_collect10": 10,
        "legacy62": 62, "expanded82": 82,
    }
    for group, subset in groups.items():
        if len(set(subset)) != len(subset) or not set(subset).issubset(columns):
            raise AssertionError(f"Invalid group feature names: {group}")
    return groups


def manifest_candidates(
    manifest_file: Path, raw_dir: Path, exclusions_file: Path,
) -> tuple[pd.DataFrame, dict[str, str]]:
    manifest = pd.read_csv(manifest_file, dtype=str, keep_default_na=False)
    required = {
        "source_file", "source_sha256", "batch", "training_status",
        "validator_pass", "schema", "sample_id", "roast_level", "origin",
    }
    if not required.issubset(manifest.columns):
        raise ValueError("Stage2 manifest columns missing")
    if manifest["source_file"].duplicated().any():
        raise ValueError("Duplicate source_file in manifest")
    if manifest["source_sha256"].duplicated().any():
        raise ValueError("Duplicate source hash (same raw copied twice)")
    if not manifest["source_sha256"].map(
        lambda value: bool(SHA_PATTERN.fullmatch(value))
    ).all():
        raise ValueError("Invalid SHA256 manifest")

    exclusions = read_exclusions(exclusions_file)
    for name, expected in exclusions.items():
        match = manifest.loc[manifest["source_file"].eq(name)]
        if not match.empty and (
            match.iloc[0]["training_status"] != "excluded_bench_clean_air"
            or match.iloc[0]["source_sha256"] != expected
        ):
            raise ValueError(f"Bench provenance violation: {name}")
    clean_air_rows = manifest["sample_id"].str.upper().str.endswith("-CAW") | manifest["batch"].eq("B37")
    if not manifest.loc[clean_air_rows, "training_status"].eq(
        "excluded_bench_clean_air"
    ).all():
        raise ValueError("Clean-air CAW/B37 provenance violation in Stage2 manifest")
    if not set(manifest.loc[
        manifest["sample_id"].str.upper().str.endswith("-CAW"), "source_file"
    ]).issubset(exclusions):
        raise ValueError("CAW exclusion missing SHA256 entry")

    candidates = manifest.loc[manifest["training_status"].eq(
        "candidate_labels_unverified"
    )].copy().sort_values("source_file").reset_index(drop=True)
    if candidates.empty:
        raise ValueError("No candidate rows; fail closed")
    if not candidates["batch"].isin(COFFEE_BATCHES).all():
        raise ValueError("Non B32-B35 batch cannot be candidate")
    if not candidates["validator_pass"].str.lower().eq("true").all():
        raise ValueError("Input not validated")
    if not candidates["schema"].eq("MQ3_10ADC_5cycles").all():
        raise ValueError("Input schema changed / MQ9")
    if candidates["source_file"].isin(exclusions).any():
        raise ValueError("Bench file in candidate cohort")
    if not candidates["source_file"].map(
        lambda name: bool(re.fullmatch(
            r"[DML]-[A-Z0-9]+_B(?:32|33|34|35)(?:_[A-Za-z0-9_]+)?\.csv",
            name,
        ))
    ).all():
        raise ValueError("Unsafe/unknown filename in manifest")
    for record in candidates.itertuples(index=False):
        path = raw_dir / record.source_file
        if not path.is_file() or sha256(path) != record.source_sha256:
            raise ValueError(f"Missing/changed raw source: {record.source_file}")
    return candidates, exclusions


def extract_candidate(
    manifest: pd.DataFrame, raw_dir: Path
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    rows = []
    held = []
    for item in manifest.itertuples(index=False):
        file = raw_dir / item.source_file
        try:
            record = extract_file(file)
        except ValueError as error:
            held.append({
                "source_file": item.source_file,
                "source_sha256": item.source_sha256,
                "status": "HOLD_FOR_QA_NOT_FEATURE_READY",
                "reason": str(error),
            })
            continue
        for key, value in (
            ("source_sha256", item.source_sha256),
            ("sample_id", item.sample_id),
            ("roast_level", item.roast_level),
            ("origin", item.origin),
            ("batch_id", item.batch),
        ):
            if record[key] != value:
                raise ValueError(f"Manifest metadata disagreement: {file.name}:{key}")
        # Frame sensor tanpa target, identik dengan input sensor Raspberry Pi.
        from validate_acquisition import classify_rows
        frame = pd.read_csv(file)
        mask, _, _ = classify_rows(frame)
        try:
            full_features = extract_sensor_features(
                frame.loc[mask].copy(), include_collect_mean=True
            )
        except ValueError as error:
            held.append({
                "source_file": item.source_file,
                "source_sha256": item.source_sha256,
                "status": "HOLD_FOR_QA_NOT_FEATURE_READY",
                "reason": str(error),
            })
            continue
        for key, value in record.items():
            if key.startswith("f_") and not np.isclose(
                value, full_features[key], atol=1e-10, rtol=1e-12,
            ):
                raise AssertionError(f"Training/inference feature parity: {file.name}:{key}")
        # Metadata bukan masukan model. Label belum dikonfirmasi secara fisik.
        row = {
            "source_file": record["source_file"],
            "source_sha256": item.source_sha256,
            "batch_id": record["batch_id"],
            "sample_id": record["sample_id"],
            "roast_level": record["roast_level"],
            "origin": record["origin"],
            "training_status": "candidate_labels_unverified",
            "n_cycles": 5,
            **full_features,
        }
        rows.append(row)
    if not rows:
        raise ValueError("No QC-qualified feature rows; fail closed")
    full = pd.DataFrame(rows)
    feature_cols = [key for key in full if key.startswith("f_")]
    matrix = full[feature_cols].to_numpy(dtype=float)
    if len(feature_cols) != 82 or not np.isfinite(matrix).all():
        raise ValueError("Unexpected/nonfinite 82-feature matrix")
    # Legacy columns preserve the historical 62-feature contract exactly.
    legacy = full[[col for col in full if col not in
        [name for name in feature_cols if name.endswith(
            ("collect_mean_mean5", "collect_mean_std5")
        )]]].copy()
    assert len([name for name in legacy if name.startswith("f_")]) == 62
    return full, legacy, pd.DataFrame(held, columns=[
        "source_file", "source_sha256", "status", "reason"
    ])


def quality_diagnostics(features: pd.DataFrame) -> pd.DataFrame:
    """Unsupervised deskriptif untuk review, BUKAN pemilihan fitur global."""
    names = [name for name in features if name.startswith("f_")]
    matrix = features[names].to_numpy(dtype=float)
    quality = []
    for i, name in enumerate(names):
        values = matrix[:, i]
        std = float(np.std(values))
        quality.append({
            "feature": name,
            "finite_count": int(np.isfinite(values).sum()),
            "min": float(values.min()), "median": float(np.median(values)),
            "max": float(values.max()), "std_population": std,
            "iqr": float(np.percentile(values, 75) -
                         np.percentile(values, 25)),
            "near_constant_abs_1e-9": bool(std < 1e-9),
            "note": "DESCRIPTIVE_GLOBAL_ONLY_NOT_FEATURE_SELECTION",
        })
    return pd.DataFrame(quality)


def build_outputs(
    raw_dir: Path, manifest_file: Path, exclusions_file: Path,
) -> tuple[dict[str, object], dict[str, object]]:
    source, exclusions = manifest_candidates(manifest_file, raw_dir, exclusions_file)
    full, legacy, held = extract_candidate(source, raw_dir)
    columns = [key for key in full if key.startswith("f_")]
    groups = groups_for_features(columns)
    quality = quality_diagnostics(full)
    snapshot = {
        "version": STAGE3_VERSION,
        "input_manifest_sha256": sha256(manifest_file),
        "bench_exclusions_sha256": sha256(exclusions_file),
        "raw_files": [
            {"source_file": item.source_file, "source_sha256": item.source_sha256}
            for item in source.itertuples(index=False)
        ],
        "feature_rows_accepted": full["source_file"].tolist(),
        "feature_rows_held": held["source_file"].tolist(),
        "sensor_adc_order": ADC_COLS,
        "feature_order": columns,
        "unit_of_observation": "one five-cycle acquisition file",
        "labels_physical_specimens_verified": False,
        "status": "CANDIDATE_NOT_APPROVED_FOR_TRAINING_OR_DEPLOYMENT",
    }
    summary = {
        "version": STAGE3_VERSION, "candidate_rows": len(full),
        "manifest_candidate_rows": len(source),
        "held_for_feature_quality": len(held),
        "held_file_names": held["source_file"].tolist(),
        "feature_count_expanded": len(columns), "feature_count_legacy": 62,
        "feature_groups": {k: len(v) for k, v in groups.items()},
        "counts_by_batch": {
            key: int(value) for key, value in
            sorted(full["batch_id"].value_counts().items())
        },
        "label_distribution_unverified": {
            key: int(value) for key, value in
            sorted(full["roast_level"].value_counts().items())
        },
        "near_constant_global_feature_count": int(
            quality["near_constant_abs_1e-9"].sum()
        ),
        "input_raw_sha256_verified": True,
        "missing_or_nonfinite_features": 0,
        "bench_files_excluded": sorted(
            set(exclusions).intersection(
                pd.read_csv(manifest_file)["source_file"].astype(str)
            )
        ),
        "fit_on_all_data": False,
        "model_trained": False,
        "warning": "Group variants predefined; descriptive diagnostics never "
                   "used to select predictors on full dataset. Future scaling, "
                   "PCA, selection and tuning MUST fit within training folds. "
                   "Known labels/specimens remain unverified.",
    }
    outputs = dict(zip(OUTPUT_FILES, (
        full, legacy,
        {
            "status": "CANDIDATE_NOT_APPROVED_FOR_TRAINING_OR_DEPLOYMENT",
            "sensor_adc_order": ADC_COLS,
            "feature_order": columns,
            "groups": groups,
            "metadata_columns_not_features": [
                "source_file", "source_sha256", "batch_id", "sample_id",
                "roast_level", "origin", "training_status", "n_cycles",
            ],
            "formula": "per-cycle median(last 5 purging) baseline; "
                       "collect mean, std(ddof=1), linear slope vs MCU seconds; "
                       "mean/std(ddof=1) across 5 cycles; ambient mean",
        },
        quality, held, snapshot, summary,
    )))
    return outputs, summary


def write_outputs(output_dir: Path, outputs: dict[str, object],
                  raw_dir: Path, replace_derived: bool) -> None:
    dest = output_dir.resolve()
    raw = raw_dir.resolve()
    if dest == raw or raw in dest.parents:
        raise ValueError("Cannot write into raw")
    if dest.exists() and not replace_derived:
        raise FileExistsError("Output directory exists: use NEW version dir "
                              "or explicitly --replace-derived")
    if dest.exists() and any(p.name not in OUTPUT_FILES for p in dest.iterdir()):
        raise ValueError("Output contains unmanaged files; cannot replace")
    dest.mkdir(parents=True, exist_ok=True)
    for name in OUTPUT_FILES:
        target = dest / name
        value = outputs[name]
        if name.endswith(".json"):
            target.write_text(
                json.dumps(value, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        else:
            assert isinstance(value, pd.DataFrame)
            value.to_csv(target, index=False, float_format="%.15g")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=RAW)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    parser.add_argument("--exclusions", type=Path, default=EXCLUSIONS)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--replace-derived", action="store_true")
    args = parser.parse_args()
    outputs, summary = build_outputs(args.raw_dir, args.manifest, args.exclusions)
    write_outputs(args.output_dir, outputs, args.raw_dir, args.replace_derived)
    print("STAGE3_FEATURE_PIPELINE_PASS")
    print(json.dumps(summary, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
