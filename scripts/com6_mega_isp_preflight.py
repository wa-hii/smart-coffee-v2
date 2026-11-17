#!/usr/bin/env python3
"""Read-only preflight programmer COM6 dan target FT232RL COM11.

Tidak menulis firmware. --probe-bootloader memeriksa signature MCU
Arduino Mega PROGRAMMER melalui bootloader COM6, bukan MCU PCB E-Nose.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess

from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]
PROGRAMMER_PORT = "COM6"
TARGET_PORT = "COM11"
TARGET_FTDI_SERIAL = "A10KNJBLA"
OUT = ROOT / "private" / "com6_mega_isp"
AVRDUDE = Path.home() / ".platformio" / "packages" / "tool-avrdude" / "avrdude.exe"


def check(*, require_target_usb: bool = True) -> dict:
    ports = list(list_ports.comports())
    mega = [p for p in ports if p.device.upper() == PROGRAMMER_PORT
            and (p.vid, p.pid) == (0x1A86, 0x7523)]
    target = [p for p in ports if p.device.upper() == TARGET_PORT
              and (p.vid, p.pid) == (0x0403, 0x6001)
              and p.serial_number == TARGET_FTDI_SERIAL]
    if len(mega) != 1:
        raise RuntimeError("COM6_CH340_PROGRAMMER_USB_NOT_VERIFIED")
    port11_present = any(p.device.upper() == TARGET_PORT for p in ports)
    if (len(target) != 1 and port11_present) or (require_target_usb and not target):
        raise RuntimeError("COM11_FT232RL_TARGET_USB_NOT_VERIFIED")
    if not AVRDUDE.is_file() or not AVRDUDE.with_name("avrdude.conf").is_file():
        raise RuntimeError("AVRDUDE_MISSING")
    return {
        "programmer_port": PROGRAMMER_PORT,
        "programmer_usb_vidpid": "1A86:7523",
        "programmer_mcu_verified": False,
        "target_port": TARGET_PORT,
        "target_ftdi_serial": TARGET_FTDI_SERIAL,
        "target_usb_attached": len(target) == 1,
        "target_mcu_verified": False,
        "programmer_sketch_uploaded": False,
        "target_flash_written": False,
        "target_eeprom_written": False,
    }


def probe() -> dict:
    status = check()
    OUT.mkdir(parents=True, exist_ok=True)
    folder = OUT / ("programmer_bootloader_" +
                    datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    folder.mkdir(exist_ok=False)
    args = [str(AVRDUDE), "-C", str(AVRDUDE.with_name("avrdude.conf")),
            "-p", "m2560", "-c", "wiring", "-P", PROGRAMMER_PORT,
            "-b", "115200", "-n", "-v"]
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           errors="replace", timeout=20)
        log = (p.stdout or "") + "\n" + (p.stderr or "")
        code = p.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        log = ((stdout.decode("utf8", "replace") if isinstance(stdout, bytes) else stdout)
               + "\n" +
               (stderr.decode("utf8", "replace") if isinstance(stderr, bytes) else stderr))
        code = "TIMEOUT"
    status["programmer_mcu_verified"] = (
        code == 0 and "device signature = 0x1e9801" in log.lower())
    status["result"] = (
        "COM6_PROGRAMMER_SIGNATURE_PASS" if status["programmer_mcu_verified"]
        else "COM6_PROGRAMMER_SIGNATURE_FAILED")
    status["avrdude_exit"] = code
    (folder / "read_only_bootloader.log").write_text(log, encoding="utf8")
    (folder / "result.json").write_text(
        json.dumps(status, indent=2) + "\n", encoding="utf8")
    return status


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--probe-bootloader", action="store_true")
    args = parser.parse_args()
    try:
        out = probe() if args.probe_bootloader else check()
        print("COM6_ARDUINOISP_PREFLIGHT", json.dumps(out, sort_keys=True))
        raise SystemExit(0 if not args.probe_bootloader or out["programmer_mcu_verified"] else 3)
    except RuntimeError as exc:
        print("COM6_ARDUINOISP_STOP", str(exc))
        raise SystemExit(2)
