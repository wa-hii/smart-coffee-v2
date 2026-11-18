#!/usr/bin/env python3
"""Read-only COM5 RF30 boot capture; optional one bounded DTR reset.

Does not send a status command, start data collection, calibrate sensors,
write EEPROM or Flash, or drive actuators. Opening FT232RL may assert DTR.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
import time

from serial import Serial
from com5_rf30_guarded_migrate import OUT_ROOT, preflight


def run(*, dtr_reset_once: bool = False) -> dict:
    info = preflight()
    if (info["port"], info["ftdi_serial"]) != ("COM5", "A10KMM3SA"):
        raise RuntimeError("NOT_EXPECTED_COM5_BOARD")
    out = OUT_ROOT / ("postflash_passive_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(parents=True, exist_ok=False)
    conn = Serial()
    conn.port = "COM5"
    conn.baudrate = 115200
    conn.timeout = 0.35
    conn.write_timeout = 0.35
    conn.dtr = False
    conn.rts = False
    conn.dsrdtr = False
    conn.rtscts = False
    result = {
        "port": "COM5", "ftdi_serial": "A10KMM3SA", "baud": 115200,
        "uart_tx_bytes": 0, "dtr_reset_once": dtr_reset_once,
        "read_window_seconds": 11, "flash_or_eeprom_written": False,
    }
    received = bytearray()
    try:
        conn.open()
        if dtr_reset_once:
            conn.dtr = True
            time.sleep(0.14)
            conn.dtr = False
        end = time.monotonic() + 11
        while time.monotonic() < end and len(received) < 65536:
            received.extend(conn.read(min(256, 65536 - len(received))))
        decoded = received.decode("utf8", "replace")
        result.update({
            "uart_rx_bytes": len(received),
            "fw_hello_seen": '"event":"FW_HELLO"' in decoded,
            "rf30_build_id_observed": "take30-ai30-rfhost-20261110" in decoded,
            "nextion_serial2_9600_seen": "Serial2" in decoded and "9600" in decoded,
            "ads1115_4_of_4_seen": "ADS1115 terdeteksi: 4/4" in decoded,
            "system_ready_seen": "Sistem siap" in decoded,
            "status": "RX_BOOT_TEXT_RECEIVED" if received else "NO_PASSIVE_UART_OUTPUT",
            "uart_excerpt": decoded[:1900],
        })
    except Exception as exc:
        result.update({"status": "PASSIVE_SERIAL_ERROR",
                       "error": type(exc).__name__ + ":" + str(exc)[:180]})
    finally:
        if conn.is_open:
            conn.close()
    (out / "uart_raw.bin").write_bytes(received)
    (out / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("COM5_RF30_POSTFLASH", json.dumps(result, ensure_ascii=False, sort_keys=True),
          flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dtr-reset-once", action="store_true")
    args = parser.parse_args()
    try:
        result = run(dtr_reset_once=args.dtr_reset_once)
        raise SystemExit(0 if result["status"] == "RX_BOOT_TEXT_RECEIVED" else 3)
    except (OSError, ValueError, RuntimeError) as exc:
        print("COM5_RF30_POSTFLASH_STOP", str(exc), file=sys.stderr)
        raise SystemExit(2)
