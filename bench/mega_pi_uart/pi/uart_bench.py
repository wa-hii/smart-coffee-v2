"""Read-only first, opt-in safe PING/PONG bench for Arduino Mega Serial1.

Isolated from Smart Coffee firmware and AI. No actuator commands or dataset.
The CLI never modifies Pi UART configuration. --ping only writes PING,<nonce>.
"""
from __future__ import annotations

import argparse
import json
import re
import secrets
import sys
import time
from pathlib import Path

MAX_FRAME = 256
PORT_DEFAULT = "/dev/ttyAMA0"  # Pi 5 configured GPIO14/15 uart0-pi5.


def ping_request(nonce: str) -> bytes:
    """The sole allow-listed UART transmission from Pi to bench Mega."""
    if re.fullmatch(r"[0-9A-F]{1,16}", nonce) is None:
        raise ValueError("invalid_ping_nonce")
    return ("PING," + nonce + "\n").encode("ascii")


class Validator:
    def __init__(self, nonce: str | None = None):
        self.nonce = nonce
        self.last_seq = None
        self.last_uptime = None
        self.heartbeat = 0
        self.pongs = 0
        self.malformed = 0
        self.gaps = 0
        self.duplicates = 0
        self.uptime_errors = 0
        self.unexpected = 0
        self.pong_nonce_mismatch = 0
        self.records: list[dict] = []

    def feed(self, raw: bytes) -> None:
        if not raw.endswith(b"\n") or len(raw) > MAX_FRAME:
            self.malformed += 1
            return
        try:
            message = json.loads(raw.decode("utf-8", errors="strict"))
        except (UnicodeError, ValueError):
            self.malformed += 1
            return
        if not isinstance(message, dict) or message.get("proto") != 1:
            self.unexpected += 1
            return
        if message.get("type") == "heartbeat":
            seq = message.get("seq")
            uptime = message.get("uptime_ms")
            if (type(seq) is not int or not 1 <= seq <= 4294967295
                    or type(uptime) is not int or not 0 <= uptime <= 4294967295):
                self.malformed += 1
                return
            if self.last_seq is not None:
                if seq <= self.last_seq:
                    self.duplicates += 1
                elif seq > self.last_seq + 1:
                    self.gaps += seq - self.last_seq - 1
            if self.last_uptime is not None and uptime <= self.last_uptime:
                self.uptime_errors += 1
            self.last_seq = seq
            self.last_uptime = uptime
            self.heartbeat += 1
            self.records.append({"type": "heartbeat", "seq": seq,
                                 "uptime_ms": uptime})
        elif message.get("type") == "pong":
            if self.nonce and message.get("nonce") == self.nonce:
                self.pongs += 1
                self.records.append({"type": "pong", "nonce_ok": True})
            else:
                self.pong_nonce_mismatch += 1
        else:
            self.unexpected += 1

    def result(self, *, ping_requested: bool, ping_sent: bool,
               seconds: int, port: str, baud: int) -> dict:
        rx_ok = (self.heartbeat >= 3 and self.malformed == 0 and
                 self.duplicates == 0 and self.gaps == 0 and
                 self.uptime_errors == 0 and self.unexpected == 0 and
                 self.pong_nonce_mismatch == 0)
        duplex_ok = rx_ok and ping_requested and ping_sent and self.pongs >= 1
        return {
            "status": "PASS_BIDIRECTIONAL" if duplex_ok else
                      "PASS_RX_ONLY" if rx_ok and not ping_requested else
                      "FAIL_OR_INCONCLUSIVE",
            "port": port, "baud": baud, "duration_limit_s": seconds,
            "physical_test": True, "model_invoked": False,
            "actuator_commands": 0, "firmware_flash_performed": False,
            "ping_requested": ping_requested, "ping_sent": ping_sent,
            "metrics": {
                "heartbeats": self.heartbeat, "pong_valid": self.pongs,
                "malformed": self.malformed, "missing_sequence": self.gaps,
                "duplicate_or_out_of_order": self.duplicates,
                "uptime_errors": self.uptime_errors,
                "unexpected_frames": self.unexpected,
                "pong_nonce_mismatch": self.pong_nonce_mismatch,
            },
            "records": self.records,
            "pass_rx": rx_ok,
            "pass_bidirectional": duplex_ok,
        }


def bench(port: str, baud: int, seconds: int, ping: bool,
          probe_tx: bool = False):
    # This is a bench-specific CLI: never open the production USB device.
    if port != PORT_DEFAULT:
        raise ValueError("only_pi5_gpio_uart0_allowed_not_usb_serial")
    if baud != 9600:
        raise ValueError("bench_firmware_requires_9600")
    if not 5 <= seconds <= 45:
        raise ValueError("duration_must_be_5_to_45")
    if probe_tx and not ping:
        raise ValueError("tx_probe_requires_ping_optin")
    if not Path(port).exists():
        raise FileNotFoundError("ttyAMA0_not_present")
    try:
        import serial
    except ImportError as err:
        raise RuntimeError("pyserial_missing") from err
    nonce = secrets.token_hex(4).upper() if ping else None
    checker = Validator(nonce)
    serial_port = serial.Serial(
        port=None, baudrate=baud, timeout=0.5,
        rtscts=False, dsrdtr=False, xonxoff=False, exclusive=True,
    )
    serial_port.dtr = False
    serial_port.rts = False
    ping_sent = False
    try:
        serial_port.port = port
        serial_port.open()
        started = time.monotonic()
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            raw = serial_port.read_until(b"\n", MAX_FRAME + 1)
            if raw:
                checker.feed(raw)
            # No TX during RX-only phase. In bidirectional test, exactly
            # one bounded benign application-level probe (PING) is allowed.
            # Explicitly requested diagnostic only: send one benign PING
            # even if RX is silent, to observe "PING ACK" on Mega USB debug.
            if (ping and not ping_sent and
                    (checker.heartbeat >= 2 or
                     (probe_tx and time.monotonic() - started >= 2))):
                serial_port.write(ping_request(nonce))
                serial_port.flush()
                ping_sent = True
            if checker.heartbeat >= 5 and (not ping or checker.pongs >= 1):
                break
    finally:
        serial_port.close()
    return checker.result(ping_requested=ping, ping_sent=ping_sent,
                          seconds=seconds, port=port, baud=baud)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=PORT_DEFAULT)
    parser.add_argument("--baud", type=int, default=9600)
    parser.add_argument("--duration", type=int, default=20)
    parser.add_argument("--ping", action="store_true",
                        help="After 2 verified RX heartbeats send ONLY PING,<nonce>")
    parser.add_argument("--probe-tx", action="store_true",
                        help="Diagnostic: one PING even when RX has no frames; requires --ping")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    # Fail before UART open on an existing/untrusted output.
    dest = args.output.resolve()
    if args.output.exists():
        raise FileExistsError("output_must_be_new")
    if str(dest).startswith("/dev/") or str(dest).startswith("/boot/"):
        raise ValueError("output_location_forbidden")
    result = bench(args.port, args.baud, args.duration,
                   args.ping, probe_tx=args.probe_tx)
    dest.parent.mkdir(parents=True, exist_ok=True)
    with dest.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, indent=2, ensure_ascii=False)
        stream.write("\n")
    print(json.dumps({k: v for k, v in result.items() if k != "records"}))
    return 0 if result["status"].startswith("PASS_") else 2


if __name__ == "__main__":
    sys.exit(main())
