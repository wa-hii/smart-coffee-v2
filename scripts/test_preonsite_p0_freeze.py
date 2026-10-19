"""Independent-style P0 adversarial regression; all I/O is temporary/offline.

Do not use any connected serial device, live MCU, GPIO, or real source writes.
Tests intentionally corrupt synthetic copies to challenge canonical guards.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

from acquisition_schema import ADC_COLS
from lcd_acquisition_service import AcquisitionService, AcquisitionSession
from serial_wire import MAX_LINE_BYTES, SerialLineFramer, serial_json_frames
from stage7_pi_adapter import EXPECTED_FW_HELLO, receive_serial_chunks
from test_acquisition_integrity import make_complete_run
from validate_acquisition import validate_file

ROOT = Path(__file__).resolve().parents[1]


class MockPort:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def read(self, size):
        return next(self.chunks)


def corrupt_csv_contract(directory: Path) -> None:
    path = directory / "D-GAW_B99.csv"
    baseline = make_complete_run()

    def check(df, error):
        df.to_csv(path, index=False)
        problems = validate_file(path)
        if error is None:
            assert not problems, problems
        else:
            assert any(error in item for item in problems), problems

    check(baseline, None)
    # Gap while count remains within tolerance 23–27.
    missing = baseline.loc[~((baseline["run_id"] == 1) &
                             (baseline["phase"] == "purging") &
                             (baseline["sample_idx"] == 3))]
    check(missing, "sample_idx tidak kontigu")
    # Out-of-order phases while timestamps still monotonically increase.
    reordered = baseline.copy()
    cols = ["run_id", "phase", "sample_idx"]
    reordered.loc[[0, 50], cols] = reordered.loc[[50, 0], cols].to_numpy()
    check(reordered, "urutan fase/siklus")
    # Index 1 must exist; duplicates without gaps are also forbidden.
    shifted = baseline.copy()
    shifted.loc[0, "sample_idx"] = 42
    check(shifted, "sample_idx tidak kontigu")


def fragmented_frames() -> None:
    sample = {"event": "ACQ_START", "mode": "ai_test"}
    raw = (json.dumps(sample) + "\n").encode()
    frames = serial_json_frames(MockPort([
        b"Boot line\r\n", raw[:6], b"", raw[6:], b"{bad\n",
        b"x" * 5000 + b"\n", b"",
    ]))
    assert next(frames) is None  # read() timeout, not message terminator
    assert next(frames) == sample
    malformed = next(frames)
    assert malformed["event"] == "TRANSPORT_ERROR"
    assert malformed["reason"] == "malformed_json"
    assert malformed["detail"] == "invalid_json_or_encoding"
    assert malformed["frame_bytes"] == len(b"{bad\n")
    oversized = next(frames)
    assert oversized["event"] == "TRANSPORT_ERROR"
    assert oversized["reason"] == "oversized_line"
    assert oversized["limit_bytes"] == MAX_LINE_BYTES
    assert next(frames) is None
    framing = SerialLineFramer()
    assert not framing.feed(raw[:4])
    assert framing.feed(raw[4:]) == [raw]


def cross_mode_quarantine(directory: Path) -> None:
    with patch("lcd_acquisition_service.RAW_DIR", directory), \
            patch("lcd_acquisition_service.INCOMING_DIR", directory / ".incoming"), \
            patch("lcd_acquisition_service.INCOMPLETE_DIR", directory / "incomplete"):
        listener = AcquisitionService("MOCK_ONLY", 115200, 0.1, Mock())
        labeled = {"event": "ACQ_START", "mode": "labeled_data",
                   "sample_id": "D-GAW", "roast_level": "dark",
                   "origin_code": "GAW", "batch_id": "B99",
                   "cycle": 1, "phase": "purging", "cycles_total": 5,
                   "purge_s": 25, "collect_s": 5}
        listener.handle_event(labeled)
        assert listener.session is not None
        listener.handle_event({"event": "ACQ_START", "mode": "ai_test"})
        assert listener.session is None
        assert list((directory / "incomplete").glob("*_INCOMPLETE.csv"))
        listener.handle_event({"event": "ACQ_START", **{
            **labeled, "purge_s": 24}})
        assert listener.session is None
        listener.handle_event(labeled)
        assert listener.session is not None
        listener.handle_event({"event": "TRANSPORT_ERROR"})
        assert listener.session is None
        assert len(list((directory / "incomplete").glob("*_INCOMPLETE.csv"))) == 2


def firmware_contract() -> None:
    valid = (json.dumps(EXPECTED_FW_HELLO) + "\n").encode()
    good = receive_serial_chunks([valid], monotonic=lambda: 1)
    assert good["diagnostics"]["firmware_hello_status"] == "MATCHED"
    wrong = {**EXPECTED_FW_HELLO, "build_id": "OLD_FIRMWARE_DO_NOT_LEAK"}
    bad = receive_serial_chunks([(json.dumps(wrong) + "\n").encode()],
                                monotonic=lambda: 1)
    assert bad["diagnostics"]["firmware_hello_status"] == "INCOMPATIBLE"
    assert bad["diagnostics"]["physical_g3_compatibility_verified"] is False
    assert "OLD_FIRMWARE_DO_NOT_LEAK" not in json.dumps(bad)
    absent = receive_serial_chunks([b'{}\n'], monotonic=lambda: 1)
    assert absent["diagnostics"]["firmware_hello_status"] == "NOT_OBSERVED"


def manual_collector_disarmed() -> None:
    command = [sys.executable, str(ROOT / "scripts/3_collect_data.py"),
               "--sample", "D-GAW", "--batch", "B99", "--no-plot"]
    run = subprocess.run(command, cwd=ROOT, capture_output=True,
                         text=True, check=False, timeout=20)
    assert run.returncode == 2, run.stdout + run.stderr
    assert "DISARMED" in run.stdout


def main():
    with TemporaryDirectory() as temp:
        location = Path(temp)
        corrupt_csv_contract(location)
        cross_mode_quarantine(location / "quarantine")
    fragmented_frames()
    firmware_contract()
    manual_collector_disarmed()
    print("PRE_ONSITE_P0_ADVERSARIAL_INDEPENDENT_STYLE_QA_PASS")


if __name__ == "__main__":
    main()
