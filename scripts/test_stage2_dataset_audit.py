"""QA Tahap 2, fixture sintetis, tidak menulis data/raw maupun COM5."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pandas as pd

from stage2_dataset_audit import (
    audit_files, coverage_table, generate_summary, outlier_table,
    paired_drift, read_exclusions, write_outputs, OUTPUT_FILES,
)
from test_acquisition_integrity import make_complete_run


def file_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main() -> int:
    with TemporaryDirectory() as directory:
        root = Path(directory)
        raw = root / "raw"
        raw.mkdir()
        valid = make_complete_run()
        b32 = raw / "D-GAW_B32.csv"
        valid.assign(batch_id="B32").to_csv(b32, index=False)
        original = file_hash(b32)
        b35 = raw / "D-GAW_B35.csv"
        valid.assign(batch_id="B35").to_csv(b35, index=False)

        bench = raw / "L-MING_B37.csv"
        clean_air = valid.assign(
            sample_id="L-MING", roast_level="light",
            origin="Arabika Sumatra Utara", batch_id="B37"
        )
        clean_air.to_csv(bench, index=False)
        bench_hash = file_hash(bench)
        exclusion_file = root / "bench_exclusions.csv"
        pd.DataFrame([{
            "source_file": bench.name,
            "source_sha256": bench_hash,
            "training_eligible": "false",
        }]).to_csv(exclusion_file, index=False)
        exclusions = read_exclusions(exclusion_file)
        manifest, phase = audit_files(raw, exclusions)
        assert len(manifest) == 3
        assert set(manifest["training_status"]) == {
            "candidate_labels_unverified", "excluded_bench_clean_air"
        }
        assert len(phase) == 3 * 5 * 10
        assert all(manifest["validator_pass"])
        coverage = coverage_table(manifest)
        assert len(coverage) == 1
        assert coverage["batch_coverage"].iloc[0] == 2
        drift = paired_drift(phase)
        assert len(drift) == 10
        flags = outlier_table(phase)
        assert flags.empty
        summary = generate_summary(
            manifest, phase, coverage, drift, flags, set(exclusions)
        )
        assert summary["files_B32_B35"] == 2
        assert summary["bench_excluded"] == ["L-MING_B37.csv"]
        assert not summary["physical_specimen_identity_verified"]
        assert summary["coffee_missing_sample_batch_cells"] == 2

        out = root / "derived"
        outputs = dict(zip(OUTPUT_FILES, (
            manifest, phase, coverage, drift, flags, summary
        )))
        write_outputs(out, outputs, replace_derived=False, raw_dir=raw)
        assert set(p.name for p in out.iterdir()) == set(OUTPUT_FILES)
        assert json.loads((out / "summary.json").read_text())["files_all_B32plus"] == 3
        assert file_hash(b32) == original
        derived_before = {p.name: file_hash(p) for p in out.iterdir()}
        write_outputs(out, outputs, replace_derived=True, raw_dir=raw)
        assert {p.name: file_hash(p) for p in out.iterdir()} == derived_before
        try:
            write_outputs(out, outputs, replace_derived=False, raw_dir=raw)
        except FileExistsError:
            pass
        else:
            raise AssertionError("File output turunan tidak boleh tertimpa")
        try:
            write_outputs(raw, outputs, replace_derived=True, raw_dir=raw)
        except ValueError:
            pass
        else:
            raise AssertionError("Tidak boleh menulis ke raw")

        # Hash tidak cocok: file bench dengan nama sama tidak boleh dipakai.
        bench.write_text("TAMPERED", encoding="utf-8")
        try:
            audit_files(raw, exclusions)
        except ValueError as exc:
            assert "hash tidak cocok" in str(exc)
        else:
            raise AssertionError("Bench hash mismatch must fail closed")
        bench.unlink()
        manifest_missing, phase_missing = audit_files(raw, exclusions)
        missing_summary = generate_summary(
            manifest_missing, phase_missing,
            coverage_table(manifest_missing), paired_drift(phase_missing),
            outlier_table(phase_missing), set(exclusions)
        )
        assert missing_summary["bench_exclusions_not_present_in_checkout"] == [
            "L-MING_B37.csv"
        ]

        # Tidak boleh menganggap legacy MQ9 sebagai data canonical MQ3.
        mq9 = valid.assign(batch_id="B34").rename(
            columns={"adc_mq3": "adc_mq9"}
        )
        mq9.to_csv(raw / "M-GAW_B34.csv", index=False)
        try:
            audit_files(raw, exclusions)
        except ValueError as exc:
            assert "Skema" in str(exc)
        else:
            raise AssertionError("MQ9 schema should fail closed")

    print("STAGE2_DATASET_AUDIT_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
