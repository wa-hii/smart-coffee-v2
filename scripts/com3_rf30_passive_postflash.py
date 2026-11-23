#!/usr/bin/env python3
"""Passive UART0 boot validation for E-Nose COM3 A10KN6X9A after RF30 flash.

Only a single bounded DTR reset is allowed; 0 UART TX bytes.
Does not start acquisition, calibrate, drive pump/valve or modify EEPROM.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import sys
import time

from serial import Serial
from com3_commit37095_guarded_deploy import OUT, PORT, SERIAL, verify_target


def check_boot() -> int:
    check = verify_target()
    if check["port"] != "COM3" or check["usb_serial"] != SERIAL:
        raise RuntimeError("WRONG_FTDI_BOARD_STOP")
    out = OUT / ("postflash_boot_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(parents=True, exist_ok=False)
    conn = Serial(port=None, baudrate=115200, timeout=0.35, write_timeout=0.35)
    conn.port = PORT
    conn.rtscts = False
    conn.dsrdtr = False
    conn.dtr = False
    conn.rts = False
    report = {
        "target_port": PORT,
        "ftdi_serial": SERIAL,
        "baud": 115200,
        "dtr_reset_once": True,
        "dtr_pulse_ms": 140,
        "uart_tx_bytes": 0,
        "flash_or_eeprom_written": False,
        "result": "BOOT_NOT_CHECKED",
    }
    buf = bytearray()
    try:
        conn.open()
        conn.dtr = True
        time.sleep(0.14)
        conn.dtr = False
        deadline = time.monotonic() + 11
        while time.monotonic() < deadline and len(buf) < 65536:
            buf.extend(conn.read(min(256, 65536 - len(buf))))
    except (OSError, RuntimeError) as exc:
        report["result"] = "SERIAL_OPEN_OR_READ_FAILED"
        report["error"] = str(exc)[:180]
    finally:
        if conn.is_open:
            conn.close()
    content = buf.decode("utf8", "replace")
    hello = None
    for line in content.splitlines():
        try:
            value = json.loads(line)
        except (ValueError, TypeError):
            continue
        if isinstance(value, dict) and value.get("event") == "FW_HELLO":
            hello = value
            break
    report.update({
        "uart_rx_bytes": len(buf),
        "fw_hello": hello,
        "expected_fw_build_id_observed":
            bool(hello and hello.get("build_id") == "take30-ai30-rfhost-20261110"),
        "nextion_serial2_9600_reported": "Serial2" in content and "9600" in content,
        "ads1115_4_of_4_reported": "ADS1115 terdeteksi: 4/4" in content,
        "system_ready_reported": "Sistem siap" in content,
        "uart_excerpt": content[:2800],
    })
    if report["result"] != "SERIAL_OPEN_OR_READ_FAILED":
        report["result"] = (
            "RF30_BOOT_UART_CONFIRMED" if report["expected_fw_build_id_observed"]
            else "RF30_BOOT_UART_NOT_CONFIRMED"
        )
    (out / "boot_uart_raw.bin").write_bytes(buf)
    (out / "result.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print("COM3_POSTFLASH_PASSIVE", json.dumps(report, ensure_ascii=False),
          flush=True)
    return 0 if report["result"] == "RF30_BOOT_UART_CONFIRMED" else 3


if __name__ == "__main__":
    try:
        sys.exit(check_boot())
    except (OSError, RuntimeError, ValueError) as exc:
        print("COM3_POSTFLASH_STOP", str(exc), file=sys.stderr)
        sys.exit(2)
