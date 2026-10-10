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
import hashlib
import json
from pathlib import Path
import re
import sys
import time
from typing import Iterable

from stage6_release_gate import evaluate as stage6_decision
from stage7_bridge import (
    MAX_LINE_BYTES,
    LegacySessionBridge,
    replay_csv,
)

ROOT = Path(__file__).resolve().parents[1]
LIVE_OPT_IN = "I_APPROVE_USB_SERIAL_READONLY"
SAFE_PORT = re.compile(
    r"^/dev/(?:serial/by-id/[A-Za-z0-9_.:+-]+|ttyACM[0-9]+|ttyUSB[0-9]+)$"
)
MAX_STREAM_SECONDS = 180


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

        result = receive_lines(incoming(), max_seconds=duration)
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
