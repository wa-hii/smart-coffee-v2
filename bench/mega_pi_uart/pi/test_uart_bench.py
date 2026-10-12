"""Offline protocol tests; never open any Pi UART or Windows COM port."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).parent))
from uart_bench import LineFramer, Validator, bench, ping_request


def wire(type_, **fields):
    return (json.dumps({"type": type_, "proto": 1, **fields}) + "\n").encode()


def main():
    # UART bytes often arrive in fragments separated by serial read timeouts.
    # We must parse only newline-terminated complete frames.
    framer = LineFramer()
    first = wire("heartbeat", seq=1, uptime_ms=1000)
    second = wire("heartbeat", seq=2, uptime_ms=2000)
    assert framer.feed(b"partial_power_on" + first) == []
    assert framer.synced is True
    assert framer.feed(second[:4]) == []
    assert framer.feed(second[4:18]) == []
    assert framer.feed(second[18:]) == [second]
    assert framer.pending == bytearray()
    assert framer.overlong_frames == 0
    third = wire("heartbeat", seq=3, uptime_ms=3000)
    assert framer.feed(third.replace(b"\n", b"\r\n")) == [
        third.replace(b"\n", b"\r\n")
    ]
    assert framer.feed(b"x" * (MAX_FRAME_TEST := 280) + b"\n") == []
    assert MAX_FRAME_TEST > 256 and framer.overlong_frames == 1
    assert framer.feed(wire("pong", nonce="AF12")) == [
        wire("pong", nonce="AF12")
    ]
    c = Validator()
    for i in range(1, 7):
        c.feed(wire("heartbeat", seq=i, uptime_ms=i * 1000))
    x = c.result(ping_requested=False, ping_sent=False,
                 seconds=20, port="/dev/ttyAMA0", baud=9600)
    assert x["status"] == "PASS_RX_ONLY"
    assert x["metrics"]["heartbeats"] == 6

    d = Validator("A12F")
    for i in range(10, 15):
        d.feed(wire("heartbeat", seq=i, uptime_ms=i * 1000))
    d.feed(wire("pong", nonce="A12F"))
    assert d.result(ping_requested=True, ping_sent=True,
                    seconds=20, port="/dev/ttyAMA0",
                    baud=9600)["status"] == "PASS_BIDIRECTIONAL"
    d.feed(wire("pong", nonce="BAD"))
    assert d.pong_nonce_mismatch == 1
    assert d.result(ping_requested=True, ping_sent=True, seconds=20,
                    port="/dev/ttyAMA0", baud=9600)["status"] == "FAIL_OR_INCONCLUSIVE"
    assert ping_request("A12F") == b"PING,A12F\n"
    for message in ("#start;", "PING,123", "PING,123456789ABCDEF01", "PING,a12f", ""):
        try:
            ping_request(message)
            raise AssertionError("unsafe_ping_request_not_rejected")
        except ValueError as err:
            assert "invalid_ping_nonce" in str(err)

    e = Validator()
    e.feed(wire("heartbeat", seq=1, uptime_ms=1000))
    e.feed(wire("heartbeat", seq=1, uptime_ms=1000))
    e.feed(wire("heartbeat", seq=4, uptime_ms=999))
    e.feed(b"{invalid\n")
    e.feed(b'{"type":"heartbeat"' + b"x" * 256 + b"\n")
    assert e.duplicates > 0 and e.gaps > 0 and e.malformed > 0
    assert e.uptime_errors > 0
    assert e.result(ping_requested=False, ping_sent=False, seconds=10,
                    port="/dev/ttyAMA0", baud=9600)["status"] == "FAIL_OR_INCONCLUSIVE"
    for port, baud, seconds, expected in (
        ("/dev/ttyUSB0", 9600, 20, "only_pi5_gpio_uart0"),
        ("/dev/ttyAMA0", 115200, 20, "requires_9600"),
        ("/dev/ttyAMA0", 9600, 100, "duration_must_be"),
        ("/dev/ttyAMA0", 9600, 10, "tx_probe_requires_ping_optin"),
    ):
        try:
            bench(port, baud, seconds, False,
                  probe_tx=expected == "tx_probe_requires_ping_optin")
            raise AssertionError("preflight_should_have_failed")
        except ValueError as err:
            assert expected in str(err)
    # Make sure no real device open in offline tests even when mocked.
    assert not any(k in sys.modules for k in ("RPi.GPIO", "gpiozero"))
    print("MEGA_PI_UART_TEST_OFFLINE_PASS")


if __name__ == "__main__":
    main()
