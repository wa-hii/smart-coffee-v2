"""Stage 7 Pi host adapter: offline replay or explicitly authorized serial RX.

DEFAULT IS OFFLINE. No model fitting/inference, no actuator messages, and
never writes to the MCU. USB serial open may reset the MCU through DTR;
the hardware mode is disabled unless individually authorized at the CLI.

Offline example:
  python scripts/stage7_pi_adapter.py replay-csv --input data/raw/D-GAW_B33.csv \
    --output results/pi_stage7/replay.json

The v1 ACK/NACK envelope remains a simulation, not a firmware feature.
"""

from __future__ import annotations

import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Iterable

from acquisition_schema import (
    ADC_COLS, is_sensor_payload, sensor_payload_rejection_reason,
)
from stage6_release_gate import evaluate as stage6_decision
from stage7_bridge import (
    MAX_LINE_BYTES,
    LegacySessionBridge,
    decode_line,
    FrameError,
    replay_csv,
)

ROOT = Path(__file__).resolve().parents[1]
LIVE_OPT_IN = "I_APPROVE_USB_SERIAL_READONLY"
SAFE_PORT = re.compile(
    r"^/dev/(?:serial/by-id/[A-Za-z0-9_.:+-]+|ttyACM[0-9]+|ttyUSB[0-9]+)$"
)
MAX_STREAM_SECONDS = 180

# Constant, privacy-safe diagnostic categories. Never persist rejected values.
_SENSOR_SHAPE_KEYS = frozenset((
    "phase", "cycle", "sample_idx", "timestamp", *ADC_COLS,
))
_SENSOR_REJECTION_CODES = frozenset((
    "invalid phase", "invalid timestamp", "invalid cycle",
    "invalid sample_idx", *(f"invalid {key}" for key in ADC_COLS),
))
_SENSOR_PHASE_CATEGORIES = frozenset((
    "idle", "paused", "complete", "purging", "collecting",
))
_NEXTION_EVENT_CATEGORIES = frozenset((
    "EVT:AI_START", "EVT:AI_CANCEL", "EVT:HMI_READY",
    "EVT:HOME", "EVT:TEST_START", "EVT:DATA_START",
))


def sensor_like_rejection_code(obj: dict) -> str | None:
    """Group a full-shape rejected sensor frame without copying its values."""
    if not _SENSOR_SHAPE_KEYS.issubset(obj):
        return None
    # Reason suffixes may contain raw values, so allow-list only fixed codes.
    prefix = sensor_payload_rejection_reason(obj).split(":", 1)[0]
    if prefix in _SENSOR_REJECTION_CODES:
        return prefix.replace(" ", "_")
    return "other_sensor_shape_invalid"


def sensor_like_phase_category(obj: dict) -> str | None:
    """Fixed phase enum only for full-shaped frames (no raw phase leakage)."""
    if not _SENSOR_SHAPE_KEYS.issubset(obj):
        return None
    value = obj.get("phase")
    if type(value) is str and value in _SENSOR_PHASE_CATEGORIES:
        return value
    return "unknown_or_noncanonical"


def nextion_event_category(obj: dict) -> str | None:
    """Diagnose HMI-to-MCU input using only a fixed event allowlist."""
    if "nextion_event" not in obj:
        return None
    value = obj["nextion_event"]
    if type(value) is str and value in _NEXTION_EVENT_CATEGORIES:
        return value
    return "OTHER_NEXTION_EVENT"


def json_key_signature(obj: dict) -> tuple[str, ...]:
    """Bounded field-name fingerprint only; never copy sensor field values."""
    paths: list[str] = []
    for key, value in obj.items():
        if len(paths) >= 32:
            break
        # Use fixed placeholders instead of arbitrary untrusted key text.
        name = key if re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,39}", key) else "OTHER_KEY"
        paths.append(name)
        if isinstance(value, dict):
            for nested in value:
                if len(paths) >= 32:
                    break
                child = (nested if re.fullmatch(
                    r"[A-Za-z][A-Za-z0-9_]{0,39}", nested
                ) else "OTHER_KEY")
                paths.append(name + "." + child)
    return tuple(sorted(set(paths)))


class SerialLineFramer:
    """Reassemble newline-delimited MCU frames across read() timeouts.

    Retains the first complete line (which could be ACQ_START);
    discards an oversized line until its next newline.
    """

    def __init__(self):
        self.buffer = bytearray()
        self.overflow = False
        self.oversized_lines = 0

    def feed(self, chunk: bytes) -> list[bytes]:
        if not isinstance(chunk, bytes):
            raise TypeError("serial_data_must_be_bytes")
        lines = []
        for b in chunk:
            if self.overflow:
                if b == 10:
                    self.overflow = False
                continue
            if len(self.buffer) >= MAX_LINE_BYTES:
                self.buffer.clear()
                self.oversized_lines += 1
                self.overflow = b != 10
                continue
            self.buffer.append(b)
            if b == 10:
                lines.append(bytes(self.buffer))
                self.buffer.clear()
        return lines


def receive_serial_chunks(chunks: Iterable[bytes], *,
                          max_seconds: int = MAX_STREAM_SECONDS,
                          monotonic=time.monotonic,
                          bridge: LegacySessionBridge | None = None) -> dict:
    """Parse a UART byte stream without treating read timeouts as newlines.

    Diagnostics persist only frame categories/counts, not sensor readings.
    """
    if not 1 <= max_seconds <= MAX_STREAM_SECONDS:
        raise ValueError("max_duration_outside_1_180_seconds")
    tracker = bridge if bridge is not None else make_bridge()
    framer = SerialLineFramer()
    started = monotonic()
    last_frame = started
    chunks_seen = 0
    bytes_seen = 0
    complete_lines = 0
    malformed = 0
    sensors = 0
    other_json = 0
    other_json_shapes: Counter[tuple[str, ...]] = Counter()
    sensor_like_rejections: Counter[str] = Counter()
    sensor_like_phase_categories: Counter[str] = Counter()
    nextion_event_categories: Counter[str] = Counter()
    start_contract_outcomes: Counter[str] = Counter()
    other_json_shapes_untracked = 0
    wire_events: Counter[str] = Counter()
    known_events = {
        "ACQ_START", "ACQ_COMPLETE", "ACQ_STOP",
        "PHASE_CHANGE", "ACQ_PAUSE", "ACQ_RESUME", "INFERENCE",
    }
    for chunk in chunks:
        now = monotonic()
        if now - started >= max_seconds:
            if tracker.active is not None:
                tracker.abort("max_runtime_expired")
            break
        if not chunk:
            tracker.timeout_if_idle(elapsed_seconds=now - last_frame)
        else:
            chunks_seen += 1
            bytes_seen += len(chunk)
            for line in framer.feed(chunk):
                last_frame = now
                complete_lines += 1
                event = None  # Never reuse previous event after malformed JSON.
                try:
                    obj = decode_line(line)
                except FrameError:
                    malformed += 1
                else:
                    # Count every complete-shape sensor phase, including
                    # valid frames, so active G3 phase evidence is visible.
                    if not obj.get("event"):
                        phase_category = sensor_like_phase_category(obj)
                        if phase_category is not None:
                            sensor_like_phase_categories[phase_category] += 1
                    hmi_category = nextion_event_category(obj)
                    if hmi_category is not None:
                        nextion_event_categories[hmi_category] += 1
                    event = obj.get("event")
                    if isinstance(event, str):
                        wire_events[event if event in known_events
                                    else "OTHER_EVENT"] += 1
                    elif is_sensor_payload(obj):
                        sensors += 1
                    else:
                        other_json += 1
                        rejection = sensor_like_rejection_code(obj)
                        if rejection is not None:
                            sensor_like_rejections[rejection] += 1
                        sig = json_key_signature(obj)
                        if sig in other_json_shapes or len(other_json_shapes) < 8:
                            other_json_shapes[sig] += 1
                        else:
                            other_json_shapes_untracked += 1
                # A physical Pi listener is SINGLE-SESSION. The underlying
                # bridge supports successive legacy sessions, but a second
                # START during one active capture must fail closed rather
                # than silently preempt and possibly accept a later run.
                if event == "ACQ_START" and tracker.active is not None:
                    tracker.abort("duplicate_start_while_active")
                    bridge_events = [{"type": "DISCARDED",
                                      "reason": "duplicate_start_while_active"}]
                else:
                    bridge_events = tracker.feed(line)
                if isinstance(event, str) and event == "ACQ_START":
                    if any(item.get("type") == "SESSION_STARTED"
                           for item in bridge_events):
                        start_contract_outcomes["accepted"] += 1
                    elif any(item.get("reason") == "ai_test_label_leakage"
                             for item in bridge_events):
                        start_contract_outcomes["ai_test_label_leakage"] += 1
                    elif any(item.get("reason") == "bad_start_contract"
                             for item in bridge_events):
                        start_contract_outcomes["bad_start_contract"] += 1
                    elif any(item.get("reason") == "duplicate_start_while_active"
                             for item in bridge_events):
                        start_contract_outcomes["duplicate_start_while_active"] += 1
                    else:
                        start_contract_outcomes["other_rejection"] += 1
                if tracker.last_final is not None and tracker.active is None:
                    break
        if tracker.last_final is not None and tracker.active is None:
            break
    if tracker.active is not None:
        tracker.abort("stream_eof_or_disconnect")
    return {
        "transport": "passive_readonly",
        "input_frames_read": complete_lines,
        "diagnostics": {
            "serial_nonempty_chunks": chunks_seen,
            "serial_bytes_received": bytes_seen,
            "complete_newline_frames": complete_lines,
            "partial_tail_bytes_discarded": len(framer.buffer),
            "oversized_lines_discarded": framer.oversized_lines,
            "malformed_json_lines": malformed,
            "valid_sensor_frames_seen": sensors,
            "other_json_lines": other_json,
            "other_json_key_signatures": [
                {"keys": list(keys), "lines": count}
                for keys, count in sorted(
                    other_json_shapes.items(),
                    key=lambda item: (-item[1], item[0]),
                )
            ],
            "other_json_untracked_shape_lines": other_json_shapes_untracked,
            "sensor_like_invalid_frames_by_reason": dict(sorted(
                sensor_like_rejections.items()
            )),
            "sensor_like_phase_categories": dict(sorted(
                sensor_like_phase_categories.items()
            )),
            "nextion_event_categories": dict(sorted(
                nextion_event_categories.items()
            )),
            "acq_start_contract_outcomes": dict(sorted(
                start_contract_outcomes.items()
            )),
            "json_signature_contents": "field_names_only_no_values",
            "wire_events_seen": dict(wire_events),
            "raw_sensor_values_persisted": False,
            "listener_transmitted_bytes": 0,
        },
        "final": tracker.last_final or {
            "type": "SESSION_FINAL", "quality": "NOT_STARTED",
            "status": "N/A", "reason": "no_completed_session",
            "sent_to_atmega": False,
            "actuator_commands_sent": 0,
            "model_invoked": False,
        },
        "terminal_event_count": sum(
            event["type"] == "SESSION_FINAL" for event in tracker.events
        ),
        "side_effects": "no_mcu_write_no_actuator_no_model",
    }


def require_no_model_promotion() -> dict:
    decision = stage6_decision()
    if (decision.get("model_promotion_allowed") is not False or
            decision.get("runtime_ai_test_result") != "N/A"):
        raise ValueError("stage6_gate_does_not_allow_safe_replay")
    return decision


def save_report(path: Path, result: dict, *, input_path: Path | None = None) -> None:
    target = path.resolve()
    raw = (ROOT / "data" / "raw").resolve()
    if target == raw or raw in target.parents:
        raise ValueError("cannot_write_to_project_raw")
    if input_path is not None and target == input_path.resolve():
        raise ValueError("cannot_overwrite_input")
    if path.exists():
        raise FileExistsError("output_already_exists_use_new_name")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as output:
        json.dump(result, output, ensure_ascii=False, indent=2, allow_nan=False)
        output.write("\n")


def make_bridge() -> LegacySessionBridge:
    return LegacySessionBridge()


def receive_lines(lines: Iterable[bytes | str], *,
                  max_seconds: int = MAX_STREAM_SECONDS,
                  monotonic=time.monotonic,
                  bridge: LegacySessionBridge | None = None) -> dict:
    """One passive reader, no writes to any transport, fail-closed at EOF.

    Inter-frame timeout is checked whenever the iterator yields; for a
    blocking stream use an underlying finite read timeout (pyserial: 1s).
    """
    if not 1 <= max_seconds <= MAX_STREAM_SECONDS:
        raise ValueError("max_duration_outside_1_180_seconds")
    tracker = bridge or make_bridge()
    start = monotonic()
    last_rx = start
    total = 0
    for line in lines:
        now = monotonic()
        if now - start >= max_seconds:
            tracker.abort("max_runtime_expired")
            break
        if line:
            last_rx = now
            total += 1
            tracker.feed(line)
        else:
            tracker.timeout_if_idle(elapsed_seconds=now - last_rx)
        if tracker.last_final is not None and tracker.active is None:
            # No implicit second session in this single-run Pi CLI.
            break
    if tracker.active:
        tracker.abort("stream_eof_or_disconnect")
    return {
        "transport": "passive_readonly",
        "input_frames_read": total,
        "final": tracker.last_final or {
            "type": "SESSION_FINAL", "quality": "NOT_STARTED",
            "status": "N/A", "reason": "no_completed_session",
            "sent_to_atmega": False,
            "actuator_commands_sent": 0,
            "model_invoked": False,
        },
        "terminal_event_count": sum(
            event["type"] == "SESSION_FINAL" for event in tracker.events
        ),
        "side_effects": "no_mcu_write_no_actuator_no_model",
    }


def replay_real_csv(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    result = replay_csv(path)
    result["mode"] = "replay-csv"
    result["hardware_serial_opened"] = False
    return result


def replay_jsonl(path: Path) -> dict:
    if not path.is_file():
        raise FileNotFoundError(path)
    raw_sha = hashlib.sha256(path.read_bytes()).hexdigest()
    with path.open("rb") as source:
        result = receive_lines(source)
    return {
        "mode": "replay-jsonl",
        "source_file_name": path.name,
        "source_sha256": raw_sha,
        "hardware_serial_opened": False,
        **result,
    }


def validate_live_args(port: str, acknowledgment: str, baud: int) -> None:
    if acknowledgment != LIVE_OPT_IN:
        raise ValueError("live_serial_not_authorized")
    if not SAFE_PORT.fullmatch(port):
        raise ValueError("unsupported_or_unsafe_serial_port")
    if baud != 115200:
        raise ValueError("legacy_firmware_requires_baud_115200")


def serial_readonly(port: str, acknowledgment: str, baud: int,
                    duration: int) -> dict:
    """PREPARED ONLY: do not invoke without future bench authorization.

    Even read-only USB opens may reset ATmega via auto-reset wiring.
    """
    validate_live_args(port, acknowledgment, baud)
    if not 1 <= duration <= MAX_STREAM_SECONDS:
        raise ValueError("invalid_live_duration")
    try:
        import serial
    except ImportError as err:
        raise RuntimeError("pyserial_missing_in_venv") from err
    # Keep DTR/RTS low before opening, but USB auto-reset behavior is
    # board dependent; this is NOT an assurance of a reset-free open.
    # Linux/Pi: attempt POSIX advisory exclusive lock. This helps avoid
    # another cooperating pyserial owner, but cannot replace fuser/lsof
    # preflight, physical supervision, or DTR/RTS auto-reset testing.
    port_obj = serial.Serial(
        port=None, baudrate=baud, timeout=1,
        rtscts=False, dsrdtr=False, exclusive=True,
    )
    port_obj.dtr = False
    port_obj.rts = False
    try:
        port_obj.port = port
        port_obj.open()

        def incoming():
            while True:
                # Hard bound prevents a stream without newlines from
                # growing an unbounded receive buffer in a live bench.
                yield port_obj.read_until(b"\n", MAX_LINE_BYTES + 1)

        result = receive_serial_chunks(incoming(), max_seconds=duration)
        return {"mode": "serial-readonly", "hardware_serial_opened": True,
                "port": port, **result}
    finally:
        port_obj.close()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    modes = parser.add_subparsers(dest="mode", required=True)
    for mode in ("replay-csv", "replay-jsonl"):
        sub = modes.add_parser(mode)
        sub.add_argument("--input", type=Path, required=True)
        sub.add_argument("--output", type=Path, required=True)
    live = modes.add_parser("serial-readonly")
    live.add_argument("--port", required=True)
    live.add_argument("--baud", type=int, default=115200)
    live.add_argument("--duration", type=int, default=180)
    live.add_argument("--acknowledgment", default="")
    live.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    decision = require_no_model_promotion()
    # Fail before opening any serial port, including for already-existing
    # result paths or paths pointing into the immutable local raw dataset.
    raw = (ROOT / "data/raw").resolve()
    destination = args.output.resolve()
    if args.output.exists():
        raise FileExistsError("output_already_exists_use_new_name")
    if destination == raw or raw in destination.parents:
        raise ValueError("cannot_write_to_project_raw")
    if args.mode != "serial-readonly" and destination == args.input.resolve():
        raise ValueError("cannot_overwrite_input")
    if args.mode == "replay-csv":
        data = replay_real_csv(args.input)
    elif args.mode == "replay-jsonl":
        data = replay_jsonl(args.input)
    else:
        data = serial_readonly(
            args.port, args.acknowledgment, args.baud, args.duration
        )
    data["release_gate"] = decision["status"]
    data["model_promotion_allowed"] = False
    if args.mode != "serial-readonly":
        data["host"] = "offline_replay_only"
    save_report(
        args.output, data,
        input_path=args.input if args.mode != "serial-readonly" else None,
    )
    terminal = data.get("bridge", data.get("final", {}))
    print("STAGE7_PI_ADAPTER_" + terminal.get("quality", "UNKNOWN"))
    print("RESULT=" + terminal.get("status", "N/A"))
    return 0 if terminal.get("quality") == "COMPLETE_QA" else 2


if __name__ == "__main__":
    sys.exit(main())
