#!/usr/bin/env python3
"""One bounded B6 Flash+EEPROM backup from a verified COM5 FT232R ATmega2560.

Requires explicit operator approval for a DTR/bootloader reset.  Does not
upload code, erase, write EEPROM or touch Nextion/valve controls. All backup
files and logs remain under gitignored private/b6_com5_readback/.
This requires an existing Arduino-compatible STK500v2 bootloader wired to
Serial0 with an appropriate RESET/DTR route; it does NOT prove that route.
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

from serial.tools import list_ports

ROOT = Path(__file__).resolve().parents[1]
BACKUP_ROOT = ROOT / "private" / "b6_com5_readback"
FTDI_SERIAL = "A10KMM3SA"
APPROVAL = "I_APPROVE_ONE_COM5_READONLY_BOOTLOADER_BACKUP_WITH_RESET"
PID_OLD_RECEIVER = 14628


def _hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def no_receiver_running() -> bool:
    # Passive Windows process inventory; never touch COM here.
    code = (
        "Get-CimInstance Win32_Process | Where-Object {"
        " $_.Name -in @('python.exe','pythonw.exe') -and "
        " $_.CommandLine -like '*lcd_acquisition_service.py*' "
        "} | Select-Object ProcessId,CommandLine | ConvertTo-Json -Compress"
    )
    p = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command", code],
        capture_output=True, text=True, timeout=16, errors="replace",
    )
    return p.returncode == 0 and not p.stdout.strip()


def preflight() -> dict:
    ports = [
        p for p in list_ports.comports()
        if p.device.upper() == "COM5"
        and p.vid == 0x0403 and p.pid == 0x6001
        and p.serial_number == FTDI_SERIAL
    ]
    if len(ports) != 1:
        raise RuntimeError("COM5_ADAPTOR_IDENTITY_NOT_CONFIRMED")
    incoming = ROOT / "data" / "raw" / ".incoming"
    if not incoming.is_dir() or any(incoming.iterdir()):
        raise RuntimeError("ACTIVE_OR_UNVERIFIED_RECEIVER_PARTIAL_SESSION")
    if not no_receiver_running():
        raise RuntimeError("RECEIVER_STILL_RUNNING_OR_STATUS_UNKNOWN")
    exe = Path.home() / ".platformio" / "packages" / "tool-avrdude" / "avrdude.exe"
    conf = exe.with_name("avrdude.conf")
    if not exe.is_file() or not conf.is_file():
        raise RuntimeError("AVRDUDE_AND_CONFIG_MISSING")
    return {
        "ftdi_serial": FTDI_SERIAL,
        "port": "COM5",
        "board_assumption": "ATmega2560 Arduino STK500v2 bootloader on Serial0",
        "avrdude_path": str(exe),
        "avrdude_config": str(conf),
    }


def run(approval: str, duration_s: int) -> int:
    if approval != APPROVAL:
        raise ValueError("EXPLICIT_BOOTLOADER_RESET_AND_READ_APPROVAL_MISSING")
    if not (30 <= duration_s <= 180):
        raise ValueError("MAX_DURATION_NOT_ALLOWED")
    base = preflight()
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    token = datetime.now().strftime("%Y%m%d_%H%M%S")
    out = BACKUP_ROOT / token
    out.mkdir(exist_ok=False)
    exe = Path(base["avrdude_path"])
    conf = Path(base["avrdude_config"])
    command = [
        str(exe),
        "-C", str(conf),
        "-p", "m2560",
        "-c", "wiring",
        "-P", "COM5",
        "-b", "115200",
        "-n",                     # avrdude NO-WRITE gate
        "-U", "flash:r:flash_readback.hex:i",
        "-U", "eeprom:r:eeprom_readback.hex:i",
    ]
    # Explicit immutable whitelist: any write/erase option is fatal.
    if any(":w:" in t or t == "-e" or t == "-D" for t in command):
        raise RuntimeError("WRITE_OR_ERASE_OPTION_FORBIDDEN")
    manifest = {
        **base,
        "started_at": datetime.now(timezone.utc).isoformat(),
        "intent": "READ_ONLY_FLASH_AND_EEPROM",
        "avrdude_args_excluding_executable": command[1:],
        "receiver_stopped": True,
        "usb_dtr_reset_possible": True,
        "eeprom_written": False,
        "flash_written": False,
        "firmware_uploaded": False,
        "complete_backup": False,
        "attempts": 1,
    }
    summary_path = out / "backup_manifest.json"
    summary_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    started = time.monotonic()
    try:
        proc = subprocess.run(
            command, cwd=out, capture_output=True, text=True,
            timeout=duration_s, errors="replace",
        )
        manifest["avrdude_exit_code"] = proc.returncode
        log = "STDOUT\n" + proc.stdout + "\nSTDERR\n" + proc.stderr
    except subprocess.TimeoutExpired as exc:
        manifest["avrdude_exit_code"] = "TIMEOUT"
        log = "TIMEOUT_EXCEEDED\n" + str(exc)
    manifest["duration_s"] = round(time.monotonic() - started, 2)
    (out / "avrdude_readonly.log").write_text(log, encoding="utf8")
    manifest["files"] = {
        name: {
            "exists": (out / name).is_file(),
            "bytes_on_disk": (out / name).stat().st_size if
            (out / name).is_file() else 0,
            "sha256": _hash(out / name) if
            (out / name).is_file() else None,
        }
        for name in ("flash_readback.hex", "eeprom_readback.hex")
    }
    manifest["complete_backup"] = (
        manifest["avrdude_exit_code"] == 0 and
        all(v["bytes_on_disk"] > 0 for v in manifest["files"].values())
    )
    manifest["finished_at"] = datetime.now(timezone.utc).isoformat()
    summary_path.write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    print("B6_COM5_READONLY_BACKUP",
          json.dumps({
              "status": "READBACK_FINISHED" if manifest["complete_backup"]
              else "READBACK_INCOMPLETE_NO_RETRY",
              "backup_complete": manifest["complete_backup"],
              "avrdude_exit_code": manifest["avrdude_exit_code"],
              "duration_s": manifest["duration_s"],
              "files": manifest["files"],
              "out_dir": str(out),
              "flash_written": False,
              "eeprom_written": False,
          }), flush=True)
    if not manifest["complete_backup"]:
        print("DIAGNOSTIC_LOG_TAIL",
              log.encode("ascii", "backslashreplace").decode()[-2500:],
              flush=True)
    return 0 if manifest["complete_backup"] else 3


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--approve", required=True)
    parser.add_argument("--timeout", type=int, default=110)
    args = parser.parse_args()
    return run(args.approve, args.timeout)


if __name__ == "__main__":
    raise SystemExit(main())
