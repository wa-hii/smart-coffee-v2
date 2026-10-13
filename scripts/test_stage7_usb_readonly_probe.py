"""Prove the USB probe is gated and frames survive arbitrary chunking."""
from __future__ import annotations

import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

from stage7_usb_readonly_probe import (
    ACK, BoundedLines, ClassifiedFrames, EXPECTED_BY_ID,
    MAX_LINE, capture, validate_gate,
)


def must_fail(fn, exc, expected):
    try:
        fn()
    except exc as e:
        assert expected in str(e), str(e)
    else:
        raise AssertionError("expected failure: " + expected)


def main():
    from acquisition_schema import ADC_COLS
    msg = json.dumps({
        "phase": "purging", "cycle": 1, "sample_idx": 1,
        "timestamp": 1000,
        **{k: 100 for k in ADC_COLS},
    }).encode() + b"\r\n"
    framer = BoundedLines()
    assert framer.feed(b"startup_partial" + b"\n") == []
    assert framer.feed(msg[:6]) == []
    assert framer.feed(b"") == []
    assert framer.feed(msg[6:23]) == []
    assert framer.feed(msg[23:]) == [msg]
    assert framer.feed(b"x" * (MAX_LINE + 4) + b"\n") == []
    assert framer.discarded_long == 1
    assert framer.feed(b"{\"warn\":\"ok\"}\n") == [b"{\"warn\":\"ok\"}\n"]
    classes = ClassifiedFrames()
    for line in (
        msg,
        b'{"event":"ACQ_START"}\n',
        b'{"warn":"ok"}\n',
        b'{"a":1,"a":2}\n',
        b'{"x":NaN}\n',
    ):
        classes.feed(line)
    d = classes.result(duration=10, bytes_read=500, overflow=1, opened=False)
    assert d["line_classes"]["valid_sensor_sample"] == 1
    assert d["line_classes"]["event_ACQ_START"] == 1
    assert d["line_classes"]["warning"] == 1
    assert d["line_classes"]["invalid_json"] == 2
    assert d["user_commands_sent"] == 0
    with TemporaryDirectory() as t:
        path = Path(t) / "serial.json"
        for ack, idle, supervision, port, dur, fragment in (
            ("", "I_CONFIRM_IDLE", "I_AM_ONSITE", EXPECTED_BY_ID, 12,
             "explicit_G2"),
            (ACK, "", "I_AM_ONSITE", EXPECTED_BY_ID, 12,
             "idle_state"),
            (ACK, "I_CONFIRM_IDLE", "", EXPECTED_BY_ID, 12,
             "onsite_supervision"),
            (ACK, "I_CONFIRM_IDLE", "I_AM_ONSITE", "/dev/ttyUSB0", 12,
             "only_known_FT232R"),
            (ACK, "I_CONFIRM_IDLE", "I_AM_ONSITE", EXPECTED_BY_ID, 31,
             "duration_outside"),
        ):
            must_fail(
                lambda ack=ack,idle=idle,supervision=supervision,port=port,dur=dur:
                    validate_gate(ack, idle, supervision, dur, port, path),
                ValueError, fragment,
            )
        validate_gate(ACK, "I_CONFIRM_IDLE", "I_AM_ONSITE",
                      12, EXPECTED_BY_ID, path)
        path.write_text("exists", encoding="utf8")
        must_fail(
            lambda: validate_gate(
                ACK, "I_CONFIRM_IDLE", "I_AM_ONSITE",
                12, EXPECTED_BY_ID, path,
            ), FileExistsError, "overwrite",
        )

    # A complete fake serial library catches any accidental WRITE,
    # verifies false DTR/RTS BEFORE open, exclusive access, bounded reads
    # and closure. No actual USB device is touched by this QA.
    seen = {}
    example = msg
    class StubSerial:
        def __init__(self, **kwargs):
            seen["config"] = kwargs
            self.dtr = True
            self.rts = True
            self.port = None
            self.parts = iter([b"partial\n", example[:10],
                               example[10:50], example[50:]])
        def open(self):
            seen["opened_port"] = self.port
            seen["dtr"] = self.dtr
            seen["rts"] = self.rts
        def read(self, size):
            assert size == 128
            return next(self.parts, b"")
        def write(self, anything):
            raise AssertionError("USB passive G2 attempted a WRITE")
        def close(self):
            seen["closed"] = True

    ticks = iter([0, 0, 0.1, 0.2, 0.3, 10.1])
    with patch.dict(sys.modules, {"serial": SimpleNamespace(
        Serial=StubSerial,
        EIGHTBITS=8, PARITY_NONE="N", STOPBITS_ONE=1,
    )}):
        with patch("stage7_usb_readonly_probe.time.monotonic",
                   side_effect=lambda: next(ticks, 10.2)):
            probe = capture(EXPECTED_BY_ID, 10)
    assert probe["status"] == "VALID_SENSOR_DATA_SEEN"
    assert probe["line_classes"]["valid_sensor_sample"] == 1
    assert seen["config"]["exclusive"] is True
    assert seen["opened_port"] == EXPECTED_BY_ID
    assert seen["dtr"] is False and seen["rts"] is False
    assert seen["closed"] is True
    assert probe["user_commands_sent"] == 0
    print("STAGE7_USB_CUSTOM_PCB_GUARDED_PROBE_TEST_PASS")


if __name__ == "__main__":
    main()
