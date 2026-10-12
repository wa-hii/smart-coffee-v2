"""Observe isolated Mega USB Serial COM6 without sending any commands.

Opening the COM port usually toggles DTR and may reset the Mega TESTBED.
Use only on the Mega bench port, never on production hardware.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", default="COM6")
    parser.add_argument("--seconds", type=int, default=30)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.port != "COM6":
        raise ValueError("only_verified_testbed_COM6_allowed")
    if not 5 <= args.seconds <= 45:
        raise ValueError("seconds_outside_safe_range")
    if args.output.exists():
        raise FileExistsError("existing_output_refused")

    import serial
    port = serial.Serial(args.port, 115200, timeout=0.5)
    print("USB_DEBUG_MONITOR_STARTED", flush=True)
    heartbeat_lines = 0
    ping_ack_lines = 0
    selected = []
    start = time.monotonic()
    try:
        while time.monotonic() - start < args.seconds:
            raw = port.readline()
            if not raw:
                continue
            line = raw.decode("ascii", "replace").strip()
            if line.startswith("HEARTBEAT "):
                heartbeat_lines += 1
            if "PING ACK" in line:
                ping_ack_lines += 1
                selected.append(line)
            elif len(selected) < 4:
                selected.append(line)
    finally:
        port.close()
    result = {
        "mode": "USB_DEBUG_READ_ONLY",
        "port": args.port,
        "duration_s": args.seconds,
        "heartbeat_lines": heartbeat_lines,
        "ping_ack_lines": ping_ack_lines,
        "selected_lines": selected,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n",
                           encoding="utf-8")
    print("USB_DEBUG_MONITOR_RESULT " + json.dumps(result), flush=True)


if __name__ == "__main__":
    main()
