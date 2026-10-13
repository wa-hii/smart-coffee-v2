"""Stage7 Pi runner safety QA: no ports touched or models invoked."""

from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from stage7_pi_adapter import (
    LIVE_OPT_IN, SerialLineFramer, json_key_signature, main, receive_lines,
    receive_serial_chunks, replay_real_csv, save_report,
    sensor_like_rejection_code, sensor_like_phase_category,
    nextion_event_category,
    serial_readonly,
    validate_live_args,
)
from stage7_bridge import MAX_LINE_BYTES
from acquisition_schema import ADC_COLS
from stage8_offline_e2e import _firmware_samples, read_real_csv


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

    # Reproduce G3 failure class: serial read() may cut JSON anywhere,
    # including inside ACQ_START, without an LF terminator.
    sample_start = json.dumps({
        "event": "ACQ_START", "mode": "ai_test",
        "cycle": 1, "phase": "purging", "cycles_total": 5,
        "purge_s": 25, "collect_s": 5,
    }).encode() + b"\n"
    assert receive_lines([
        sample_start[:17], sample_start[17:],
    ])["final"]["quality"] == "NOT_STARTED"
    parsed = receive_serial_chunks([
        sample_start[:17], b"", sample_start[17:],
    ], monotonic=lambda: 1)
    assert parsed["final"]["quality"] == "FAIL_CLOSED"
    assert parsed["final"]["reason"] == "stream_eof_or_disconnect"
    assert parsed["diagnostics"]["wire_events_seen"] == {"ACQ_START": 1}

    # Full mock serial stream reconstructed from ORIGINAL 151-sample
    # physical CSV; fragmented at varying boundaries and with timeouts.
    rows, source_hash = read_real_csv(original)
    assert len([x for x in rows if x["sample_idx"]]) == 151
    messages = [b"boot plain text\n", sample_start]
    messages.extend(
        raw.encode() + b"\n"
        for _, _, raw in _firmware_samples(rows)
    )
    messages.append(json.dumps({
        "event": "ACQ_COMPLETE", "cycles": 5,
        "total_samples": 151,
    }).encode() + b"\n")
    wire = b"".join(messages)
    fragmented = []
    offset = 0
    while offset < len(wire):
        take = [1, 3, 11, 7, 29][offset % 5]
        fragmented.append(wire[offset:offset + take])
        fragmented.append(b"")  # timeout is not end-of-line
        offset += take
    recovery = receive_serial_chunks(
        fragmented, monotonic=lambda: 1
    )
    assert recovery["final"]["quality"] == "COMPLETE_QA"
    assert recovery["final"]["sensor_samples"] == 151
    assert recovery["final"]["status"] == "N/A"
    assert recovery["diagnostics"]["valid_sensor_frames_seen"] == 151
    assert recovery["diagnostics"]["wire_events_seen"]["ACQ_START"] == 1
    assert recovery["diagnostics"]["wire_events_seen"]["ACQ_COMPLETE"] == 1
    assert recovery["diagnostics"]["malformed_json_lines"] == 1  # boot
    assert recovery["diagnostics"]["listener_transmitted_bytes"] == 0
    assert recovery["diagnostics"]["raw_sensor_values_persisted"] is False
    assert original.read_bytes() == original_hash

    # JSON shape metadata for a later authorized capture:
    # Only field names appear in reports, not private/sample values.
    mystery = {
        "telemetry": {"channel_a": 932, "private_name": "NEVER_RECORD_ME"},
        "state": "NEVER_RECORD_ME",
    }
    signature = json_key_signature(mystery)
    assert signature == (
        "state", "telemetry", "telemetry.channel_a",
        "telemetry.private_name",
    )
    diagnostic = receive_serial_chunks(
        [json.dumps(mystery).encode() + b"\n"] * 3,
        monotonic=lambda: 1,
    )["diagnostics"]
    assert diagnostic["other_json_lines"] == 3
    assert diagnostic["other_json_key_signatures"] == [
        {"keys": list(signature), "lines": 3}
    ]
    assert "NEVER_RECORD_ME" not in json.dumps(diagnostic)
    assert diagnostic["json_signature_contents"] == "field_names_only_no_values"
    assert len(json_key_signature({f"field{i}": i for i in range(100)})) <= 32

    # Reproduce 15-second USB diagnosis: full ADC key shape can be present
    # even though IDLE / index zero makes it an INVALID session sample.
    idle_frame = {key: 17123 for key in ADC_COLS}
    idle_frame.update({"phase": "idle", "cycle": 0,
                       "sample_idx": 0, "timestamp": 10123})
    assert sensor_like_rejection_code(idle_frame) == "invalid_phase"
    invalid_adc = {**idle_frame, "phase": "purging", "cycle": 1,
                   "sample_idx": 1, ADC_COLS[0]: "SECRET_ADC_VALUE"}
    assert sensor_like_rejection_code(invalid_adc) == f"invalid_{ADC_COLS[0]}"
    invalid_diag = receive_serial_chunks([
        json.dumps(idle_frame).encode() + b"\n",
        json.dumps(invalid_adc).encode() + b"\n",
    ], monotonic=lambda: 1)["diagnostics"]
    assert invalid_diag["other_json_lines"] == 2
    assert invalid_diag["valid_sensor_frames_seen"] == 0
    assert invalid_diag["sensor_like_invalid_frames_by_reason"] == {
        f"invalid_{ADC_COLS[0]}": 1, "invalid_phase": 1,
    }
    assert "SECRET_ADC_VALUE" not in json.dumps(invalid_diag)

    # Legacy firmware before commit 75cb38a emitted idle sensor-shaped
    # JSON 1Hz. Keep it rejected as a sample; show a bounded phase enum.
    assert sensor_like_phase_category(idle_frame) == "idle"
    assert sensor_like_phase_category({**idle_frame, "phase": "DO_NOT_LEAK"}) == (
        "unknown_or_noncanonical"
    )
    assert sensor_like_phase_category({"phase": "idle"}) is None
    assert nextion_event_category({"nextion_event": "EVT:AI_START"}) == (
        "EVT:AI_START"
    )
    assert nextion_event_category({"nextion_event": "SENSITIVE_UNKNOWN"}) == (
        "OTHER_NEXTION_EVENT"
    )
    categories = receive_serial_chunks([
        json.dumps(idle_frame).encode() + b"\n",
        json.dumps({**idle_frame, "phase": "DO_NOT_LEAK"}).encode() + b"\n",
        b'{"nextion_event":"EVT:AI_START"}\n',
        b'{"nextion_event":"SENSITIVE_UNKNOWN"}\n',
    ], monotonic=lambda: 1)["diagnostics"]
    assert categories["sensor_like_phase_categories"] == {
        "idle": 1, "unknown_or_noncanonical": 1,
    }
    assert categories["nextion_event_categories"] == {
        "EVT:AI_START": 1, "OTHER_NEXTION_EVENT": 1,
    }
    assert "DO_NOT_LEAK" not in json.dumps(categories)
    assert "SENSITIVE_UNKNOWN" not in json.dumps(categories)
    valid_active = {**idle_frame, "phase": "purging", "cycle": 1,
                    "sample_idx": 1}
    valid_diag = receive_serial_chunks([
        json.dumps(valid_active).encode() + b"\n",
    ], monotonic=lambda: 1)["diagnostics"]
    assert valid_diag["valid_sensor_frames_seen"] == 1
    assert valid_diag["sensor_like_phase_categories"] == {"purging": 1}
    assert valid_diag["sensor_like_invalid_frames_by_reason"] == {}

    # Firmware prior to 75cb38a includes sample_id/roast_label even in
    # AI_TEST ACQ_START. Reject label leakage, but expose its safe reason
    # (not the values), to avoid mistakenly treating G3 as no event.
    clean_start = {
        "event": "ACQ_START", "mode": "ai_test", "cycle": 1,
        "phase": "purging", "cycles_total": 5, "purge_s": 25,
        "collect_s": 5,
    }
    legacy_start = {**clean_start, "sample_id": "PRIVATE_LABEL"}
    leaked = receive_serial_chunks([
        json.dumps(legacy_start).encode() + b"\n",
    ], monotonic=lambda: 1)
    assert leaked["diagnostics"]["wire_events_seen"] == {"ACQ_START": 1}
    assert leaked["diagnostics"]["acq_start_contract_outcomes"] == {
        "ai_test_label_leakage": 1,
    }
    assert leaked["final"]["quality"] == "NOT_STARTED"
    assert "PRIVATE_LABEL" not in json.dumps(leaked)
    compliant = receive_serial_chunks([
        json.dumps(clean_start).encode() + b"\n",
    ], monotonic=lambda: 1)
    assert compliant["diagnostics"]["acq_start_contract_outcomes"] == {
        "accepted": 1,
    }
    assert compliant["final"]["quality"] == "FAIL_CLOSED"
    bad_start = receive_serial_chunks([
        json.dumps({**clean_start, "purge_s": 999}).encode() + b"\n",
    ], monotonic=lambda: 1)
    assert bad_start["diagnostics"]["acq_start_contract_outcomes"] == {
        "bad_start_contract": 1,
    }

    framer = SerialLineFramer()
    assert framer.feed(b"x" * (MAX_LINE_BYTES + 50) + b"\n") == []
    assert framer.oversized_lines == 1
    assert framer.feed(b'{"warn":"recover"}\r\n') == [
        b'{"warn":"recover"}\r\n'
    ]

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
                # Emulate a physical 1 Hz acquisition frame fragmented by
                # a 1-second timeout; serial calls must NOT be parsed as
                # individual JSON messages until LF arrives.
                self.frames = iter([
                    start[:14], b"", start[14:] + b"\n",
                    b"not json\n",
                ])

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
        assert result["final"]["reason"] == "invalid_json_or_encoding"
        assert result["diagnostics"]["wire_events_seen"]["ACQ_START"] == 1
        assert result["diagnostics"]["complete_newline_frames"] == 2
        assert result["diagnostics"]["malformed_json_lines"] == 1
        assert observations["opened"] and observations["closed"]
        assert observations["config"]["exclusive"] is True
        assert observations["dtr_at_open"] is False
        assert observations["rts_at_open"] is False
        assert observations["read_bound"] == MAX_LINE_BYTES + 1
    print("STAGE7_PI_ADAPTER_REGRESSION_PASS")


if __name__ == "__main__":
    main_test()
