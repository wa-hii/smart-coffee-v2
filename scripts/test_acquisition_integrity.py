"""Offline regression of full-run CSV validation and filename collision rules.

Creates only temporary synthetic CSVs; never opens a serial port or edits raw.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import Mock
from unittest.mock import patch

import pandas as pd

from acquisition_schema import ADC_COLS, CSV_COLUMNS
from lcd_acquisition_service import AcquisitionService, AcquisitionSession, unique_final_path
from test_acquisition_payload import make_sensor_payload
from validate_acquisition import file_summary, validate_file


def make_complete_run() -> pd.DataFrame:
    rows = []
    timestamp = 1_000_000
    for run_id in range(1, 6):
        for phase, n in (("purging", 25), ("collecting", 5)):
            for idx in range(1, n + 1):
                row = {
                    "timestamp": timestamp,
                    "sample_id": "D-GAW",
                    "roast_level": "dark",
                    "origin": "Arabika Gayo Wine",
                    "batch_id": "B99",
                    "run_id": run_id,
                    "phase": phase,
                    "sample_idx": idx,
                    "temperature": 28.1,
                    "humidity": 60.5,
                }
                row.update({col: 1000 + k for k, col in enumerate(ADC_COLS)})
                rows.append(row)
                timestamp += 1000
    return pd.DataFrame(rows, columns=CSV_COLUMNS)


def main() -> int:
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        csv_file = root / "D-GAW_B99.csv"

        def check(df: pd.DataFrame, expected_problem: str | None = None):
            df.to_csv(csv_file, index=False)
            errors = validate_file(csv_file)
            if expected_problem is None:
                assert not errors, errors
            else:
                assert any(expected_problem in e for e in errors), errors

        valid = make_complete_run()
        check(valid)

        duplicate = valid.copy()
        duplicate.loc[10, "sample_idx"] = duplicate.loc[9, "sample_idx"]
        check(duplicate, "duplicate sensor index")

        bad_adc = valid.copy()
        bad_adc.loc[2, "adc_mq3"] = 32768
        check(bad_adc, "adc_mq3")

        partial = valid.copy()
        partial.loc[2, "adc_mq3"] = None
        check(partial, "row sensor parsial")

        corrupt = valid.copy()
        for col in ["timestamp", "sample_idx"] + ADC_COLS:
            corrupt[col] = corrupt[col].astype(object)
            corrupt.loc[2, col] = "BAD_PACKET"
        check(corrupt, "row sensor parsial")

        old_event = {col: None for col in CSV_COLUMNS}
        old_event.update(sample_id="D-GAW", roast_level="dark",
                         origin="Arabika Gayo Wine", batch_id="B99",
                         run_id=3, phase="collecting")
        historical = pd.concat([valid, pd.DataFrame([old_event])],
                               ignore_index=True)
        check(historical)
        summary = file_summary(csv_file)
        assert summary["metadata_rows"] == 1
        assert summary["sensor_rows"] == 150

        with patch("lcd_acquisition_service.RAW_DIR", root):
            reserved = root / "D-GAW_B99.csv"
            assert reserved.exists()
            with patch("lcd_acquisition_service.time.strftime",
                       return_value="20261008_173700"):
                candidate = unique_final_path(reserved.name)
                candidate.touch()
                next_candidate = unique_final_path(reserved.name)
                assert candidate != next_candidate
                assert next_candidate.name.endswith("_2.csv")

        # Simulate a second file materializing after session start. The first
        # file must remain byte-identical; completed data gets a new name.
        with patch("lcd_acquisition_service.RAW_DIR", root), \
             patch("lcd_acquisition_service.INCOMING_DIR", root / ".incoming"), \
             patch("lcd_acquisition_service.INCOMPLETE_DIR", root / "incomplete"):
            existing = root / "L-GAW_B98.csv"
            event = {"sample_id": "L-GAW", "roast_level": "light",
                     "origin_code": "GAW", "batch_id": "B98",
                     "filename": existing.name}
            session = AcquisitionSession(event, Mock())
            existing.write_bytes(b"DO_NOT_OVERWRITE")
            session.write_sensor(make_sensor_payload())
            completed = session.complete()
            assert completed != existing and completed.exists()
            assert existing.read_bytes() == b"DO_NOT_OVERWRITE"
            assert not session.partial_path.exists()

        with patch("lcd_acquisition_service.RAW_DIR", root), \
             patch("lcd_acquisition_service.INCOMING_DIR", root / ".incoming"), \
             patch("lcd_acquisition_service.INCOMPLETE_DIR", root / "incomplete"):
            logger = Mock()
            service = AcquisitionService("TEST", 115200, 0.1, logger)
            event = {"sample_id": "D-GAW", "roast_level": "dark",
                     "origin_code": "GAW", "batch_id": "B97",
                     "filename": "D-GAW_B97.csv"}
            service.session = AcquisitionSession(event, logger)
            service.session.write_sensor(make_sensor_payload())
            service.handle_event({"event": "ACQ_COMPLETE"})
            assert service.session is None
            assert not (root / "D-GAW_B97.csv").exists()
            assert list((root / "incomplete").glob("D-GAW_B97*_INCOMPLETE.csv"))

            # Valid staged data is promoted to final path only after QA.
            service.session = AcquisitionSession(event, logger)
            service.session.file.close()
            make_complete_run().assign(batch_id="B97").to_csv(
                service.session.partial_path, index=False
            )
            service.handle_event({"event": "ACQ_COMPLETE"})
            assert service.session is None
            assert (root / "D-GAW_B97.csv").exists()

    print("ACQUISITION_INTEGRITY_REGRESSION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
