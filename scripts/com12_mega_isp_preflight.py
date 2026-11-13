#!/usr/bin/env python3
"""Pemeriksaan read-only Arduino Mega 2560 CH340 COM12 sebagai calon ISP.

COM12: board programmer CH340 (VID:PID 1A86:7523).
COM11: target PCB kedua FT232RL (0403:6001, serial A10KNJBLA).
Jangan gunakan COM11 untuk ArduinoISP atau ROM writer berbasis COM12.
Default hanya mencetak identitas USB; --probe-bootloader melakukan satu
AVRDUDE -n -v dengan timeout 16 detik, TANPA EEPROM/Flash write.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys
from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "private/com12_arduino_isp"
PROGRAMMER_PORT = "COM12"
TARGET_PORT = "COM11"
TARGET_SERIAL = "A10KNJBLA"
AVRDUDE = Path.home() / ".platformio/packages/tool-avrdude/avrdude.exe"


def check(*, require_target: bool = True) -> dict:
    programmer = [p for p in list_ports.comports()
                  if p.device.upper() == PROGRAMMER_PORT
                  and (p.vid, p.pid) == (0x1A86, 0x7523)]
    target = [p for p in list_ports.comports()
              if p.device.upper() == TARGET_PORT
              and (p.vid, p.pid) == (0x0403, 0x6001)
              and p.serial_number == TARGET_SERIAL]
    if len(programmer) != 1:
        raise RuntimeError("COM12_CH340_IDENTITY_NOT_VERIFIED")
    if len(target) != 1 and (require_target or any(
        p.device.upper() == TARGET_PORT for p in list_ports.comports())):
        raise RuntimeError("COM11_TARGET_FT232RL_IDENTITY_NOT_VERIFIED")
    if not AVRDUDE.is_file() or not AVRDUDE.with_name("avrdude.conf").is_file():
        raise RuntimeError("AVRDUDE_MISSING")
    return {
        "programmer_port": PROGRAMMER_PORT,
        "programmer_usb": "CH340 1A86:7523",
        "programmer_mcu_verified": False,
        "target_port": TARGET_PORT,
        "target_ft232rl_serial": TARGET_SERIAL,
        "target_ft232rl_usb_attached": len(target) == 1,
        "target_mcu_verified": False,
        "usb_devices_distinct": True,
        "target_flash_written": False,
        "target_eeprom_written": False,
        "programmer_sketch_uploaded": False,
    }


def probe() -> dict:
    status = check()
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ("bootloader_probe_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    path.mkdir(exist_ok=False)
    args = [str(AVRDUDE), "-C", str(AVRDUDE.with_name("avrdude.conf")),
            "-p", "m2560", "-c", "wiring", "-P", PROGRAMMER_PORT,
            "-b", "115200", "-n", "-v"]
    status["bootloader_probe_attempted"] = True
    try:
        result = subprocess.run(args, capture_output=True, text=True,
                                errors="replace", timeout=16)
        log = (result.stdout or "") + "\n" + (result.stderr or "")
        code = result.returncode
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or b""
        err = exc.stderr or b""
        log = (out.decode("utf8", "replace") if isinstance(out, bytes) else out)
        log += "\n" + (err.decode("utf8", "replace")
                           if isinstance(err, bytes) else err)
        code = "TIMEOUT"
    status["programmer_mcu_verified"] = (
        code == 0 and "device signature = 0x1e9801" in log.lower())
    status["bootloader_probe_status"] = (
        "MEGA2560_BOOTLOADER_PASS" if status["programmer_mcu_verified"]
        else "MEGA2560_BOOTLOADER_NOT_VERIFIED")
    status["avrdude_exit"] = code
    (path / "probe.log").write_text("EXIT=" + str(code) + "\n" + log, encoding="utf8")
    (path / "result.json").write_text(json.dumps(status, indent=2) + "\n", encoding="utf8")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-bootloader", action="store_true")
    args = parser.parse_args()
    try:
        outcome = probe() if args.probe_bootloader else check()
        print("COM12_PROGRAMMER_READ_ONLY", json.dumps(outcome, sort_keys=True))
        sys.exit(0 if not args.probe_bootloader or outcome["programmer_mcu_verified"] else 3)
    except (OSError, RuntimeError) as exc:
        print("COM12_PROGRAMMER_FAIL_CLOSED", str(exc), file=sys.stderr)
        sys.exit(2)
