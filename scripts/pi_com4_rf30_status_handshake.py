#!/usr/bin/env python3
"""Safe Pi5 -> ATmega2560 COM4-equivalent firmware handshake over FT232RL.

Only permitted serial command is #status; (no actuation, calibration, start,
stop, scan or RF result). This command is implemented in source firmware as
a welcome/status dump. No GPIOs or MCU firmware are changed. Opening USB
serial might transiently assert DTR in the FTDI driver, so the MCU may reset.

Run on Pi 5 in a Python environment with pyserial 3.5:
  python pi_com4_rf30_status_handshake.py --outdir PRIVATE_NEW_DIRECTORY
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys
import time

from serial import Serial

LINK = Path("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMZQJ-if00-port0")
TARGET = Path("/dev/ttyUSB0")
CMD = b"#status;"
EXPECTED_BUILD = "take30-ai30-rfhost-20261110"
UNSAFE_MARKERS = (b"undervoltage", b"brownout", b"overheat")


def shell(*args: str) -> subprocess.CompletedProcess:
    return subprocess.run(args, capture_output=True, text=True,
                          errors="replace", timeout=8, check=False)


def preflight() -> dict:
    if not LINK.is_symlink() or LINK.resolve() != TARGET:
        raise RuntimeError("WRONG_PI_FTDI_A10KMZQJ_OR_TTYUSB_MAPPING")
    power = shell("vcgencmd", "get_throttled")
    if power.returncode or power.stdout.strip() != "throttled=0x0":
        raise RuntimeError("PI_POWER_THROTTLED_OR_UNKNOWN")
    owners = shell("fuser", str(TARGET))
    if owners.returncode != 1 or owners.stdout.strip() or owners.stderr.strip():
        raise RuntimeError("SERIAL_BUSY_OR_FUSER_UNAVAILABLE")
    return {"ftdi_by_id": str(LINK), "resolved_tty": str(TARGET),
            "power_throttled": power.stdout.strip()}


def run(outdir: Path, seconds: int = 12) -> dict:
    if not 5 <= seconds <= 20:
        raise ValueError("READ_WINDOW_OUT_OF_RANGE")
    pre = preflight()
    outdir.mkdir(parents=True, exist_ok=False)
    raw = bytearray()
    tx_bytes = 0
    fault = None
    status = "NOT_STARTED"
    port = Serial()
    port.port = str(LINK)
    port.baudrate = 115200
    port.timeout = 0.3
    port.write_timeout = 0.8
    port.dtr = False
    port.rts = False
    port.rtscts = False
    port.dsrdtr = False
    port.xonxoff = False
    try:
        port.open()
        # Captures boot print if opening the serial port auto-resets MCU.
        time.sleep(2.5)
        tx_bytes = port.write(CMD)
        if tx_bytes != len(CMD):
            raise RuntimeError("SHORT_STATUS_COMMAND_TX")
        status = "READING"
        end = time.monotonic() + seconds
        while time.monotonic() < end:
            if not LINK.is_symlink() or LINK.resolve() != TARGET:
                status = "USB_DETACHED_STOP"
                break
            block = port.read(256)
            if block:
                raw.extend(block)
                if any(marker in bytes(raw).lower() for marker in UNSAFE_MARKERS):
                    status = "DEVICE_POWER_FAULT_STOP"
                    break
                if len(raw) >= 64000:
                    status = "EXCESSIVE_UART_OUTPUT_STOP"
                    break
        else:
            status = "READ_COMPLETE"
    except Exception as exc:
        fault = type(exc).__name__ + ": " + str(exc)[:180]
        status = "ERROR"
    finally:
        if port.is_open:
            port.close()
    result = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "port": str(LINK),
        "ftdi_serial": "A10KMZQJ",
        "baud": 115200,
        "handshake": CMD.decode("ascii"),
        "tx_bytes": tx_bytes,
        "rx_bytes": len(raw),
        "rx_sha256": hashlib.sha256(raw).hexdigest(),
        "fw_hello_seen": b'"event":"FW_HELLO"' in raw,
        "welcome_response_seen": b"Smart Coffee E-NOSE v2" in raw,
        "system_ready_seen": b"Sistem siap" in raw,
        "ads1115_4_of_4_seen": b"ADS1115 terdeteksi: 4/4" in raw,
        "expected_firmware_build_id_observed": EXPECTED_BUILD.encode("ascii") in raw,
        "calibration_missing_reported": b"belum dikalibrasi" in raw or b"Kalibrasi belum ada" in raw,
        "no_acquisition_started": True,
        "no_actuator_commands_sent": True,
        "no_eeprom_or_flash_write": True,
        "possible_ftdi_dtr_reset_on_open": True,
        "error": fault,
        "preflight": pre,
        "output_dir": str(outdir),
    }
    (outdir / "uart_raw.bin").write_bytes(raw)
    (outdir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("PI_COM4_RF30_STATUS", json.dumps(result, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--outdir", type=Path, required=True)
    p.add_argument("--seconds", type=int, default=12)
    args = p.parse_args()
    try:
        outcome = run(args.outdir, args.seconds)
        sys.exit(0 if outcome["status"] == "READ_COMPLETE" and
                 outcome["welcome_response_seen"] else 3)
    except (OSError, ValueError, RuntimeError) as exc:
        print("PI_COM4_RF30_STATUS_STOP", str(exc), file=sys.stderr)
        sys.exit(2)
