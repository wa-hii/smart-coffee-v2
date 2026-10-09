"""Regresi determinisme, parity, provenance dan kegagalan aman Tahap 3."""

from __future__ import annotations

import hashlib
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from extract_b32_features import extract_file, extract_sensor_features
from stage3_feature_pipeline import (
    OUTPUT_FILES, build_outputs, groups_for_features, manifest_candidates,
    sha256, write_outputs,
)
from test_acquisition_integrity import make_complete_run


def must_fail(fn, text: str) -> None:
    try:
        fn()
    except (ValueError, FileExistsError) as exc:
        assert text in str(exc), f"unexpected error: {exc}"
    else:
        raise AssertionError(f"Must fail: {text}")


def main() -> int:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        raw = root / "raw"
        raw.mkdir()
        base = make_complete_run()
        manifest_rows = []
        for name, sample, roast, origin, batch in [
            ("D-GAW_B32.csv", "D-GAW", "dark", "Arabika Gayo Wine", "B32"),
            ("L-MING_B33.csv", "L-MING", "light", "Arabika Sumatra Utara", "B33"),
            ("D-GAW_B34.csv", "D-GAW", "dark", "Arabika Gayo Wine", "B34"),
            ("M-GAW_B35.csv", "M-GAW", "medium", "Arabika Gayo Wine", "B35"),
            ("L-MING_B37.csv", "L-MING", "light", "Arabika Sumatra Utara", "B37"),
        ]:
            path = raw / name
            data = base.assign(
                sample_id=sample, roast_level=roast, origin=origin,
                batch_id=batch
            )
            if name == "M-GAW_B35.csv":
                # Deliberate gap at purge index 8; canonical validator is lenient
                # but Stage 3 strict features must HOLD it.
                data = data.loc[~(
                    (data["run_id"] == 1) &
                    (data["phase"] == "purging") &
                    (data["sample_idx"] == 8)
                )]
            data.to_csv(path, index=False)
            manifest_rows.append({
                "source_file": name, "source_sha256": sha256(path),
                "sample_id": sample, "roast_level": roast, "origin": origin,
                "batch": batch, "schema": "MQ3_10ADC_5cycles",
                "validator_pass": "True",
                "training_status": (
                    "excluded_bench_clean_air" if batch == "B37"
                    else "candidate_labels_unverified"
                ),
            })
        manifest_file = root / "file_manifest.csv"
        pd.DataFrame(manifest_rows).to_csv(manifest_file, index=False)
        exclusions_file = root / "exclusions.csv"
        pd.DataFrame([{
            "source_file": "L-MING_B37.csv",
            "source_sha256": sha256(raw / "L-MING_B37.csv"),
            "training_eligible": "false",
        }]).to_csv(exclusions_file, index=False)
        raw_hashes = {path.name: sha256(path) for path in raw.glob("*.csv")}

        source, _ = manifest_candidates(manifest_file, raw, exclusions_file)
        assert len(source) == 4
        outputs, summary = build_outputs(raw, manifest_file, exclusions_file)
        assert summary["manifest_candidate_rows"] == 4
        assert summary["candidate_rows"] == 3
        assert summary["held_file_names"] == ["M-GAW_B35.csv"]
        assert len(outputs["candidate_features82.csv"]) == 3
        assert len(outputs["candidate_legacy62.csv"]) == 3
        assert len(outputs["feature_quality.csv"]) == 82
        assert len(outputs["feature_rejections.csv"]) == 1
        cols = [key for key in outputs["candidate_features82.csv"]
                if key.startswith("f_")]
        assert groups_for_features(cols) == outputs["feature_groups.json"]["groups"]
        assert not any("B37" in name for name in
                       outputs["candidate_features82.csv"]["source_file"])
        assert not np.isnan(
            outputs["candidate_features82.csv"][cols].to_numpy(float)
        ).any()

        raw_file = raw / "D-GAW_B32.csv"
        sensor = pd.read_csv(raw_file).drop(columns=[
            "sample_id", "origin", "roast_level", "batch_id"
        ])
        in_memory = extract_sensor_features(sensor, include_collect_mean=True)
        from_csv = outputs["candidate_features82.csv"].loc[
            outputs["candidate_features82.csv"]["source_file"].eq(raw_file.name)
        ].iloc[0]
        for key, value in in_memory.items():
            assert np.isclose(from_csv[key], value, rtol=1e-12, atol=1e-10)
        legacy = extract_file(raw_file)
        for key, value in legacy.items():
            if key.startswith("f_"):
                assert np.isclose(from_csv[key], value, rtol=1e-12, atol=1e-10)

        output_dir = root / "stage3"
        write_outputs(output_dir, outputs, raw, replace_derived=False)
        assert set(p.name for p in output_dir.iterdir()) == set(OUTPUT_FILES)
        first_hashes = {p.name: sha256(p) for p in output_dir.iterdir()}
        must_fail(lambda: write_outputs(
            output_dir, outputs, raw, replace_derived=False
        ), "Output directory exists")
        write_outputs(output_dir, outputs, raw, replace_derived=True)
        assert {p.name: sha256(p) for p in output_dir.iterdir()} == first_hashes
        must_fail(lambda: write_outputs(
            raw, outputs, raw, replace_derived=True
        ), "Cannot write into raw")
        assert {p.name: sha256(p) for p in raw.glob("*.csv")} == raw_hashes

        # Invalidate the frozen snapshot by changing an otherwise valid CSV.
        raw_file.write_text("changed", encoding="utf-8")
        must_fail(lambda: manifest_candidates(
            manifest_file, raw, exclusions_file
        ), "Missing/changed raw source")
        raw_file.unlink()
        # Bench with fake candidate label must fail even if its hash matches.
        modified = pd.read_csv(manifest_file, dtype=str)
        modified.loc[
            modified["source_file"].eq("L-MING_B37.csv"), "training_status"
        ] = "candidate_labels_unverified"
        modified.to_csv(manifest_file, index=False)
        must_fail(lambda: manifest_candidates(
            manifest_file, raw, exclusions_file
        ), "Bench provenance violation")

        # Inference path rejects invalid ADC and missing all ambient readings.
        broken = sensor.copy()
        broken.loc[0, ADC_COLS[0]] = np.nan
        must_fail(lambda: extract_sensor_features(
            broken, include_collect_mean=True
        ), "nonfinite sensor column")
        no_env = sensor.assign(temperature=np.nan)
        must_fail(lambda: extract_sensor_features(no_env), "missing/nonfinite temperature")
        partial_env = sensor.copy()
        partial_env.loc[0, "humidity"] = np.nan
        must_fail(lambda: extract_sensor_features(partial_env), "missing/nonfinite humidity")
        bad_adc = sensor.copy()
        bad_adc.loc[0, ADC_COLS[0]] = 40000
        must_fail(lambda: extract_sensor_features(bad_adc), "ADC outside")
        wrong_phase = sensor.copy()
        wrong_phase.loc[wrong_phase.index[1], "phase"] = "collecting"
        must_fail(lambda: extract_sensor_features(wrong_phase),
                  "non-contiguous sample_idx")

    print("STAGE3_FEATURE_PIPELINE_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
