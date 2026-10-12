"""Bounded, passive UART byte diagnostic for the isolated Mega testbed.

Do not use this on other ports or a production Smart Coffee device.
Does not write to serial, GPIO, MCU, EEPROM, firmware or model.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

PORT = "/dev/ttyAMA0"


def run(duration: int, limit: int) -> dict:
    if not 2 <= duration <= 15 or not 1 <= limit <= 256:
        raise ValueError("bounded_diagnostic_only")
    import serial
    uart = serial.Serial(
        port=None, baudrate=9600, timeout=0.25,
        bytesize=serial.EIGHTBITS, parity=serial.PARITY_NONE,
        stopbits=serial.STOPBITS_ONE, exclusive=True,
        xonxoff=False, rtscts=False, dsrdtr=False,
    )
    uart.dtr = False
    uart.rts = False
    bytes_received = bytearray()
    reads = 0
    try:
        uart.port = PORT
        uart.open()
        end = time.monotonic() + duration
        while time.monotonic() < end and len(bytes_received) < limit:
            piece = uart.read(min(32, limit - len(bytes_received)))
            reads += 1
            bytes_received.extend(piece)
    finally:
        uart.close()
    data = bytes(bytes_received)
    return {
        "status": "CAPTURE_ONLY_NO_VALIDATION",
        "port": PORT, "baud": 9600, "rx_only": True,
        "max_duration_s": duration, "limit_bytes": limit,
        "read_calls": reads, "total_bytes": len(data),
        "hex": data.hex(" "),
        "ascii_visible": "".join(chr(c) if 32 <= c <= 126 else
                                 "\\n" if c == 10 else
                                 "\\r" if c == 13 else "." for c in data),
        "newline_count": data.count(b"\n"),
        "uart_tx_bytes": 0,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--duration", type=int, default=8)
    parser.add_argument("--limit-bytes", type=int, default=256)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("diagnostic_output_exists")
    result = run(args.duration, args.limit_bytes)
    print(json.dumps(result))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as file:
        json.dump(result, file, indent=2)
        file.write("\n")


if __name__ == "__main__":
    main()
