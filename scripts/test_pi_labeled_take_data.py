#!/usr/bin/env python3
"""Offline QA for Pi Take Data CSV + AI coexistence; no USB used."""
from __future__ import annotations

from contextlib import redirect_stdout
import csv
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from pi_labeled_take_data import (
    LabeledDataError, LabeledTakeRecorder, validate_labeled_start,
)
from rf500_pi_persistent_listener import PersistentHandler
from test_rf30_pi_result_bridge import frames


def labeled_fixture(sample_id="D-TOR", batch_id="B70"):
    source = frames()
    start = json.loads(source[1])
    start.pop("ai_session_token", None)
    start.update({
        "mode": "labeled_data",
        "sample_id": sample_id,
        "roast_level": {"L": "light", "M": "medium", "D": "dark"}[sample_id[0]],
        "origin_code": sample_id[2:],
        "batch_id": batch_id,
        "filename": f"{sample_id}_{batch_id}.csv",
        "total_samples_expected": 900,
    })
    serial = [(json.dumps(start) + "\n").encode()]
    for raw in source[2:]:
        obj = json.loads(raw)
        if obj.get("event") == "AI_AWAITING_RESULT":
            break
        if "adc_tgs822" in obj:
            obj["temperature_c"] = 33.72
            obj["humidity_rh"] = 48.42
        serial.append((json.dumps(obj) + "\n").encode())
    assert sum("adc_tgs822" in json.loads(s) for s in serial) == 900
    return serial


def test_full_recording_and_no_overwrite():
    with TemporaryDirectory() as tmp:
        target = Path(tmp) / "data" / "raw"
        seen = []
        listener = PersistentHandler(
            predictor=lambda _: seen.append("SHOULD_NOT_INFER"),
            archive_dir=Path(tmp) / "recordings",
            take_data_dir=target)
        stream = labeled_fixture("L-TOR", "B01")
        with redirect_stdout(StringIO()):
            for _ in range(2):
                status = None
                for raw in stream:
                    cmd, status = listener.receive(raw)
                    assert cmd is None
                assert status["status"] == "LABELED_CSV_SAVED_900_VALID"
                assert listener.labeled.active is False
        csv_files = sorted(target.glob("*.csv"))
        assert len(csv_files) == 2 and len(set(p.name for p in csv_files)) == 2
        assert csv_files[0].name == "L-TOR_B01.csv"
        assert len(list(target.glob("*.csv.json"))) == 2
        for path in csv_files:
            with path.open(newline="", encoding="utf8") as f:
                rows = list(csv.DictReader(f))
            assert len(rows) == 900
            assert rows[0]["sample_id"] == "L-TOR"
            assert rows[0]["origin"] == "TOR"
            assert rows[0]["roast_level"] == "light"
            assert rows[0]["run_id"] == "1"
            assert rows[0]["phase"] == "purging"
            assert rows[0]["sample_idx"] == "1"
            assert rows[-1]["run_id"] == "30"
            assert rows[-1]["phase"] == "collecting"
            assert rows[-1]["sample_idx"] == "5"
            assert rows[0]["adc_tgs822"] not in ("", None)
            assert rows[0]["temperature"] not in ("", None)
            meta = json.loads((target / (path.name + ".json")).read_text())
            assert meta["status"] == "COMPLETE_30_CYCLES_900_SAMPLES"
            assert meta["rows"] == 900
        assert not list((target / ".incoming").glob("*"))
        assert not seen
        print("TAKE_DATA_TWO_CONSECUTIVE_CSV_900_NO_OVERWRITE_PASS")


def test_invalid_capture_fails_closed():
    with TemporaryDirectory() as tmp:
        target = Path(tmp) / "raw"
        listener = PersistentHandler(
            predictor=lambda _: (_ for _ in ()).throw(
                AssertionError("labeled_inference_not_allowed")),
            archive_dir=Path(tmp) / "ai",
            take_data_dir=target)
        stream = labeled_fixture("D-TOR", "B70")
        with redirect_stdout(StringIO()):
            for raw in stream[:-2]:
                cmd, status = listener.receive(raw)
                assert cmd is None
            # Exactly one missing sensor frame -> incomplete on completion
            _, status = listener.receive(stream[-1])
        assert status["status"] == "LABELED_INCOMPLETE_QUARANTINED"
        assert not list(target.glob("*.csv"))
        incomplete = list((target / "incomplete").glob("*_INCOMPLETE.csv"))
        assert len(incomplete) == 1
        with incomplete[0].open(newline="", encoding="utf8") as f:
            assert len(list(csv.DictReader(f))) == 899
        # Malformed/contradictory header is rejected BEFORE a file is opened.
        invalid = json.loads(stream[0])
        invalid["roast_level"] = "light"
        try:
            validate_labeled_start(invalid)
        except LabeledDataError:
            pass
        else:
            raise AssertionError("contradictory_roast_label_was_accepted")
        # A 30-second stalled acquisition can't silently become complete.
        listener.receive(stream[0])
        assert listener.labeled.active
        timeout = listener.labeled.check_timeout(
            listener.labeled.last_activity + 13)
        assert timeout["status"] == "LABELED_INCOMPLETE_QUARANTINED"
        assert not listener.labeled.active
        print("TAKE_DATA_INCOMPLETE_ABORT_AND_TIMEOUT_QUARANTINE_PASS")


def test_crash_recovery_and_ai_test_isolated():
    with TemporaryDirectory() as tmp:
        root = Path(tmp) / "raw"
        recorder = LabeledTakeRecorder(root)
        stream = labeled_fixture("M-TOR", "B99")
        recorder.start(json.loads(stream[0]))
        for raw in stream[1:8]:
            recorder.receive(raw)
        recorder._close()  # emulate unexpected process loss; keep .partial
        recovered = LabeledTakeRecorder(root).recover_stale_partials()
        assert recovered == 1
        assert not list((root / ".incoming").glob("*.partial.csv"))
        assert len(list((root / "incomplete").glob("*BOOT_RECOVERED.csv"))) == 1
        called = []
        handler = PersistentHandler(
            predictor=lambda _: (called.append(True) or {"roast_predicted": "dark"}),
            archive_dir=Path(tmp) / "ai_recordings",
            take_data_dir=root)
        with redirect_stdout(StringIO()):
            for raw in frames():
                command, status = handler.receive(raw)
        assert called == [True]
        assert command == b"#rf30:B1F503A9:dark;"
        assert not list(root.glob("*.csv"))
        assert handler.labeled.active is False
        print("TAKE_DATA_STALE_PARTIAL_RECOVERY_AND_AI_RF500_UNCHANGED_PASS")


if __name__ == "__main__":
    test_full_recording_and_no_overwrite()
    test_invalid_capture_fails_closed()
    test_crash_recovery_and_ai_test_isolated()
