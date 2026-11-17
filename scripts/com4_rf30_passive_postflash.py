#!/usr/bin/env python3
"""Passive UART0 capture after COM4 RF30 flash (NO UART TX or actuator commands).

Opening FT232RL can reset the ATmega via DTR hardware; this script does not
explicitly toggle DTR or send commands. Never opens COM11.
"""
from __future__ import annotations

from datetime import datetime, timezone
import argparse
import json
from pathlib import Path
import sys
import time

from serial import Serial
from com4_rf30_verified_deploy import check_preflight
from com4_rf30_verify_binary_original import PARENT


def run(*, dtr_reset_once: bool = False) -> dict:
    preflight = check_preflight(uploading=False)
    if preflight["port"] != "COM4" or preflight["ftdi_serial"] != "A10KMZQJA":
        raise RuntimeError("COM4_WRONG_TARGET")
    out = PARENT / ("postflash_passive_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    port = Serial()
    port.port = "COM4"
    port.baudrate = 115200
    port.timeout = 0.35
    port.write_timeout = 0.35
    port.dtr = False
    port.rts = False
    port.rtscts = False
    port.dsrdtr = False
    buffer = bytearray()
    result = {
        "port": "COM4", "ftdi_serial": "A10KMZQJA",
        "baud": 115200, "uart_tx_bytes": 0,
        "target_flash_written_by_this_script": False,
        "receiver_com11_touched": False,
        "elapsed_window_seconds": 11,
        "boot_events_observed": [],
        "dtr_reset_once": dtr_reset_once,
        "dtr_asserted_ms": 0,
        "status": "NOT_STARTED",
    }
    try:
        port.open()
        if dtr_reset_once:
            # Single controlled DTR pulse; only resets MCU if the FT232R
            # DTR line is physically connected to the reset circuit.
            port.dtr = True
            time.sleep(0.14)
            port.dtr = False
            result["dtr_asserted_ms"] = 140
        stop = time.monotonic() + 11
        while time.monotonic() < stop and len(buffer) < 65536:
            data = port.read(min(256, 65536 - len(buffer)))
            if data:
                buffer.extend(data)
        decoded = buffer.decode("utf8", "replace")
        for token in ("FW_HELLO", "Smart Coffee E-NOSE", "nextion", "Sensor init gagal",
                      "pHome", "ACQ_START", "RF30"):
            if token in decoded:
                result["boot_events_observed"].append(token)
        result["status"] = "PASSIVE_RX_CAPTURED" if buffer else "PASSIVE_RX_EMPTY"
    except Exception as exc:
        result["status"] = "COM4_PASSIVE_SERIAL_ERROR"
        result["error"] = str(exc)[:180]
    finally:
        if port.is_open:
            port.close()
    (out / "uart0_raw.bin").write_bytes(buffer)
    result["uart_rx_bytes"] = len(buffer)
    result["uart_excerpt"] = buffer.decode("utf8", "replace")[:2400]
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print("COM4_RF30_PASSIVE_POSTFLASH", json.dumps(result, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    try:
        parser = argparse.ArgumentParser(description=__doc__)
        parser.add_argument("--dtr-reset-once", action="store_true")
        args = parser.parse_args()
        run(dtr_reset_once=args.dtr_reset_once)
    except (OSError, RuntimeError, ValueError) as exc:
        print("COM4_RF30_PASSIVE_STOP", str(exc), file=sys.stderr)
        raise SystemExit(2)
