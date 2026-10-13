"""G2 guarded, bounded passive USB serial probe for the Smart Coffee PCB.

Offline by default. NEVER runs pumps, valves, Nextion commands, calibration,
or production AI. Opening USB UART may nevertheless pulse DTR/reset the MCU.
Use only with an operator present, device IDLE and an explicit G2 decision.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from acquisition_schema import ADC_COLS, is_sensor_payload

EXPECTED_BY_ID = (
    "/dev/serial/by-id/"
    "usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0"
)
ACK = "I_APPROVE_CUSTOM_PCB_USB_RX_G2"
MAX_LINE = 4096
MAX_DURATION = 30


class BoundedLines:
    """Reassemble newline-terminated frames from arbitrarily split reads.

    Drop initial partial frame; timeout does not count as a malformed JSON
    frame. Drop oversized lines safely and resynchronize at next newline.
    """

    def __init__(self):
        self.synchronized = False
        self.overflow = False
        self.discarded_long = 0
        self.pending = bytearray()

    def feed(self, chunk: bytes) -> list[bytes]:
        result: list[bytes] = []
        for b in chunk:
            if not self.synchronized:
                if b == 10:
                    self.synchronized = True
                continue
            if self.overflow:
                if b == 10:
                    self.overflow = False
                continue
            if len(self.pending) >= MAX_LINE:
                self.pending.clear()
                self.discarded_long += 1
                self.overflow = (b != 10)
                continue
            self.pending.append(b)
            if b == 10:
                result.append(bytes(self.pending))
                self.pending.clear()
        return result


class ClassifiedFrames:
    def __init__(self):
        self.total = 0
        self.classes: Counter[str] = Counter()
        self.preview: list[dict] = []
        self.first_digest: str | None = None
        self.last_digest: str | None = None

    def feed(self, line: bytes):
        self.total += 1
        digest = hashlib.sha256(line).hexdigest()
        if self.first_digest is None:
            self.first_digest = digest
        self.last_digest = digest
        try:
            # Strictly disallow ambiguous duplicate keys and NaN/Infinity.
            def unique(pairs):
                out = {}
                for k, v in pairs:
                    if k in out:
                        raise ValueError("duplicate_key")
                    out[k] = v
                return out
            def reject_nonfinite(_value):
                raise ValueError("nonfinite_number")
            parsed = json.loads(
                line.decode("utf-8", errors="strict"),
                object_pairs_hook=unique,
                parse_constant=reject_nonfinite,
            )
            if not isinstance(parsed, dict):
                category = "non_object_json"
            elif is_sensor_payload(parsed):
                category = "valid_sensor_sample"
            elif "event" in parsed and isinstance(parsed["event"], str):
                category = "event_" + parsed["event"][:32]
            elif "warn" in parsed:
                category = "warning"
            elif "nextion" in parsed:
                category = "nextion_info"
            elif "i2c_found" in parsed:
                category = "i2c_found"
            elif "i2c_scan_done" in parsed:
                category = "i2c_scan_done"
            else:
                category = "other_json"
        except (UnicodeError, ValueError, TypeError):
            category = "invalid_json"
        self.classes[category] += 1
        # Structured metadata only; no user/sample contents stored.
        if len(self.preview) < 10:
            self.preview.append({
                "line_index": self.total,
                "kind": category,
                "sha256": digest,
                "byte_length": len(line),
            })

    def result(self, *, duration: int, bytes_read: int,
               overflow: int, opened: bool) -> dict:
        sensor_frames = self.classes["valid_sensor_sample"]
        return {
            "status": ("VALID_SENSOR_DATA_SEEN" if sensor_frames else
                       "STRUCTURED_SERIAL_FRAMES_SEEN" if
                       self.total and not self.classes["invalid_json"] else
                       "SERIAL_DATA_INCONCLUSIVE"),
            "transport": "FT232R_USB_SERIAL_PASSIVE_G2",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "port": EXPECTED_BY_ID,
            "baud": 115200,
            "duration_limit_s": duration,
            "hardware_serial_opened": opened,
            "bytes_received": bytes_read,
            "lines_complete": self.total,
            "line_classes": dict(self.classes),
            "discarded_oversize_lines": overflow,
            "first_frame_sha256": self.first_digest,
            "last_frame_sha256": self.last_digest,
            "frame_metadata_preview": self.preview,
            "user_commands_sent": 0,
            "actuator_commands_sent": 0,
            "model_invoked": False,
            "acquisition_triggered": False,
            "risk_note": "Opening serial may reset MCU via DTR on custom PCB",
        }


def validate_gate(ack: str, idle: str, supervised: str, duration: int,
                  port: str, output: Path) -> None:
    if ack != ACK:
        raise ValueError("explicit_G2_approval_missing")
    if idle != "I_CONFIRM_IDLE":
        raise ValueError("idle_state_not_confirmed")
    if supervised != "I_AM_ONSITE":
        raise ValueError("onsite_supervision_not_confirmed")
    if port != EXPECTED_BY_ID:
        raise ValueError("only_known_FT232R_board_allowed")
    if not 5 <= duration <= MAX_DURATION:
        raise ValueError("duration_outside_5_to_30_seconds")
    dest = output.resolve()
    if output.exists():
        raise FileExistsError("refuse_to_overwrite_evidence")
    if (str(dest).startswith("/dev/") or str(dest).startswith("/boot/")
            or "/data/raw/" in str(dest).replace("\\", "/")):
        raise ValueError("unsafe_output_location")


def capture(port: str, duration: int) -> dict:
    import serial
    tty = serial.Serial(
        port=None, baudrate=115200, timeout=0.25,
        bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE, rtscts=False, dsrdtr=False,
        xonxoff=False, exclusive=True,
    )
    tty.dtr = False
    tty.rts = False
    reader = BoundedLines()
    metrics = ClassifiedFrames()
    received = 0
    try:
        tty.port = port
        tty.open()
        end = time.monotonic() + duration
        while time.monotonic() < end:
            chunk = tty.read(128)
            if not chunk:
                continue
            received += len(chunk)
            for line in reader.feed(chunk):
                metrics.feed(line)
    finally:
        tty.close()
    return metrics.result(
        duration=duration, bytes_read=received,
        overflow=reader.discarded_long, opened=True,
    )


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default=EXPECTED_BY_ID)
    parser.add_argument("--duration", type=int, default=12)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--acknowledgment", default="")
    parser.add_argument("--idle", default="")
    parser.add_argument("--supervised", default="")
    args = parser.parse_args(argv)
    validate_gate(args.acknowledgment, args.idle, args.supervised,
                  args.duration, args.port, args.output)
    if not Path(args.port).exists():
        raise FileNotFoundError("USB_FT232R_not_present")
    result = capture(args.port, args.duration)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, ensure_ascii=False)
        handle.write("\n")
    print(json.dumps(result, ensure_ascii=False))
    return 0 if result["lines_complete"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
