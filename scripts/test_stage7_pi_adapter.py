"""Stage7 Pi runner safety QA: no ports touched or models invoked."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from stage7_pi_adapter import (
    LIVE_OPT_IN, main, receive_lines, replay_real_csv, save_report,
    serial_readonly,
    validate_live_args,
)
from stage7_bridge import MAX_LINE_BYTES


def must_fail(callback, exception, fragment):
    try:
        callback()
    except exception as error:
        assert fragment in str(error), str(error)
    else:
        raise AssertionError(f"Missing expected failure: {fragment}")


def main_test():
    root = Path(__file__).resolve().parents[1]
    original = root / "data/raw/D-GAW_B33.csv"
    original_hash = original.read_bytes()
    replay = replay_real_csv(original)
    assert replay["hardware_serial_opened"] is False
    assert replay["bridge"]["quality"] == "COMPLETE_QA"
    assert replay["bridge"]["status"] == "N/A"
    assert replay["bridge"]["model_invoked"] is False
    assert replay["bridge"]["sensor_samples"] >= 140
    assert original.read_bytes() == original_hash

    must_fail(lambda: validate_live_args("/dev/ttyACM0", "", 115200),
              ValueError, "not_authorized")
    must_fail(lambda: validate_live_args("/dev/ttyS0", LIVE_OPT_IN, 115200),
              ValueError, "unsafe_serial_port")
    must_fail(lambda: validate_live_args("/dev/ttyACM0", LIVE_OPT_IN, 9600),
              ValueError, "requires_baud_115200")

    with TemporaryDirectory() as root_tmp:
        tmp = Path(root_tmp)
        dest = tmp / "result.json"
        assert main([
            "replay-csv", "--input", str(original), "--output", str(dest)
        ]) == 0
        result = json.loads(dest.read_text(encoding="utf-8"))
        assert result["model_promotion_allowed"] is False
        assert result["bridge"]["sent_to_atmega"] is False
        must_fail(lambda: save_report(dest, result),
                  FileExistsError, "already_exists")
        must_fail(lambda: save_report(original, result, input_path=original),
                  ValueError, "project_raw")

        # JSON lines are protocol fixtures only; not training data.
        start = json.dumps({
            "event": "ACQ_START", "mode": "ai_test", "cycle": 1,
            "phase": "purging", "cycles_total": 5, "purge_s": 25,
            "collect_s": 5,
        }).encode()
        bad = receive_lines([start, b'{"bad json"'])
        assert bad["final"]["status"] == "N/A"
        assert bad["final"]["quality"] == "FAIL_CLOSED"
        assert bad["terminal_event_count"] == 1
        assert bad["final"]["actuator_commands_sent"] == 0
        disconnect = receive_lines([start])
        assert disconnect["final"]["reason"] == "stream_eof_or_disconnect"
        assert receive_lines([])["final"]["quality"] == "NOT_STARTED"
        must_fail(lambda: receive_lines([], max_seconds=181),
                  ValueError, "max_duration")
        # Explicit check that even the serial CLI without opt-in never
        # reaches pyserial/open().
        must_fail(lambda: main([
            "serial-readonly", "--port", "/dev/ttyACM0",
            "--output", str(tmp / "serial.json"),
        ]), ValueError, "live_serial_not_authorized")
        must_fail(lambda: main([
            "serial-readonly", "--port", "/dev/ttyACM0",
            "--acknowledgment", LIVE_OPT_IN,
            "--output", str(dest),
        ]), FileExistsError, "output_already_exists")

        # Mock the *library* entirely: confirms read-only API contract
        # without opening a real tty or making a training-data fixture.
        observations = {}

        class StubPort:
            def __init__(self, **options):
                observations["config"] = options
                observations["opened"] = False
                self.port = None
                self.dtr = True
                self.rts = True
                self.frames = iter([start + b"\n", b"not json\n"])

            def open(self):
                observations["dtr_at_open"] = self.dtr
                observations["rts_at_open"] = self.rts
                observations["port_at_open"] = self.port
                observations["opened"] = True

            def read_until(self, expected, size):
                observations["read_bound"] = size
                return next(self.frames)

            def write(self, unused):
                raise AssertionError("USB bench read-only mode must never write")

            def close(self):
                observations["closed"] = True

        with patch.dict(sys.modules, {"serial": SimpleNamespace(Serial=StubPort)}):
            result = serial_readonly(
                "/dev/ttyACM0", LIVE_OPT_IN, 115200, 20
            )
        assert result["hardware_serial_opened"] is True  # simulated only
        assert result["final"]["quality"] == "FAIL_CLOSED"
        assert observations["opened"] and observations["closed"]
        assert observations["config"]["exclusive"] is True
        assert observations["dtr_at_open"] is False
        assert observations["rts_at_open"] is False
        assert observations["read_bound"] == MAX_LINE_BYTES + 1
    print("STAGE7_PI_ADAPTER_REGRESSION_PASS")


if __name__ == "__main__":
    main_test()
