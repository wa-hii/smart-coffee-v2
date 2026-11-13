#!/usr/bin/env python3
"""One guarded COM11 FT232RL RX-only idle diagnostic, no serial TX.

Opens a serial port at 115200 with DTR and RTS requested deasserted.
The Windows driver can still transiently pulse DTR on open; this is not a
guarantee that an externally connected MCU will not reset.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time

from serial import Serial
from com11_rf30_verified_deploy import OUT_ROOT, PORT, check_preflight


def run(duration_s: float = 8.0) -> dict:
    if not 0.5 <= duration_s <= 8.0:
        raise ValueError("RX_DURATION_OUT_OF_BOUNDS")
    preflight = check_preflight(uploading=False)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out = OUT_ROOT / ("rx_readonly_" +
                      datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    result = {
        "status": "RX_PROBE_NOT_RUN",
        "port": preflight["port"],
        "ftdi_serial": preflight["ftdi_serial"],
        "duration_s": duration_s,
        "rx_bytes": 0,
        "uart_tx_bytes": 0,
        "flash_written": False,
        "eeprom_written": False,
        "reset_pulse_excluded": False,
        "rx_sha256": None,
        "fw_hello_seen": False,
        "mcu_signature_verified": False,
    }
    chunks = []
    try:
        ser = Serial()
        ser.port = PORT
        ser.baudrate = 115200
        ser.timeout = 0.25
        ser.dtr = False
        ser.rts = False
        ser.exclusive = True if hasattr(ser, "exclusive") else None
        try:
            ser.open()
            end = time.monotonic() + duration_s
            while time.monotonic() < end:
                chunks.append(ser.read(512))
        finally:
            if ser.is_open:
                ser.close()
        rx = b"".join(chunks)
        result["rx_bytes"] = len(rx)
        result["rx_sha256"] = hashlib.sha256(rx).hexdigest()
        result["fw_hello_seen"] = b"FW_HELLO" in rx
        result["status"] = (
            "RX_FIRMWARE_MARKER_SEEN_NOT_BOOTLOADER_PROOF"
            if result["fw_hello_seen"] else
            "RX_DATA_NO_FIRMWARE_MARKER" if rx else
            "RX_ZERO_BYTES_INCONCLUSIVE"
        )
    except Exception as e:
        result["status"] = "RX_PORT_ERROR"
        result["error_class"] = type(e).__name__
        result["error_text"] = str(e)[:240]
    finally:
        (out / "probe_result.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf8")
    print("COM11_UART_RX_READONLY", json.dumps(result, sort_keys=True))
    return result


if __name__ == "__main__":
    run()
