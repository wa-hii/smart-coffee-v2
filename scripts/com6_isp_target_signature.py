#!/usr/bin/env python3
"""Guarded target ISP signature over COM6, never performs writes.

Executable only AFTER ArduinoISP sketch is actually uploaded to COM6 AND
the operator independently verifies target wiring, power and stopped receiver.
COM11 USB enumeration alone cannot prove physical SPI connections.
"""
from __future__ import annotations

import argparse
from datetime import datetime
import json
from pathlib import Path
import subprocess

from com6_mega_isp_preflight import check, OUT, AVRDUDE, PROGRAMMER_PORT


def target_receiver_active() -> bool:
    """Fail-closed if checking Windows process ownership is unavailable."""
    query = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -in @('python.exe','pythonw.exe') -and "
        "$_.CommandLine -like '*lcd_acquisition_service.py*' "
        "} | Select-Object -ExpandProperty ProcessId"
    )
    try:
        p = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", query],
            capture_output=True, text=True, errors="replace", timeout=12)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError("RECEIVER_STATUS_UNAVAILABLE_STOP") from exc
    if p.returncode:
        raise RuntimeError("RECEIVER_STATUS_COMMAND_FAILED_STOP")
    return bool(p.stdout.strip())


def execute(*, arduinoisp_installed: bool, wiring_verified: bool,
            receiver_stopped: bool) -> dict:
    if not (arduinoisp_installed and wiring_verified and receiver_stopped):
        raise PermissionError(
            "NEED_COM6_ARDUINOISP_INSTALLED_AND_SAFE_ISP_WIRING_AND_RECEIVER_STOPPED")
    if target_receiver_active():
        raise RuntimeError("COM11_ACQUISITION_RECEIVER_ACTIVE_STOP")
    # Target USB COM11 may be intentionally unplugged during ISP if it risks
    # backfeeding/autoreset; never require target USB to perform target SPI.
    result = check(require_target_usb=False)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ("target_signature_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    path.mkdir(exist_ok=False)
    cmd = [str(AVRDUDE), "-C", str(AVRDUDE.with_name("avrdude.conf")),
           "-p", "m2560", "-c", "stk500v1", "-P", PROGRAMMER_PORT,
           "-b", "19200", "-n", "-v"]
    try:
        p = subprocess.run(cmd, capture_output=True, text=True,
                           errors="replace", timeout=22)
        log = (p.stdout or "") + "\n" + (p.stderr or "")
        code = p.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        log = ((stdout.decode("utf8", "replace") if isinstance(stdout, bytes) else stdout)
               + "\n" +
               (stderr.decode("utf8", "replace") if isinstance(stderr, bytes) else stderr))
        code = "TIMEOUT"
    verified = code == 0 and "device signature = 0x1e9801" in log.lower()
    result.update({
        "target_signature_verified": verified,
        "result": "TARGET_MCU_SIGNATURE_PASS" if verified else "TARGET_MCU_SIGNATURE_STOP",
        "avrdude_exit": code,
        "arduinoisp_installed_confirmed_by_operator": True,
        "wiring_and_power_confirmed_by_operator": True,
        "receiver_stopped_confirmed_by_operator": True,
        "target_flash_written": False,
        "target_eeprom_written": False,
    })
    (path / "probe.log").write_text(log, encoding="utf8")
    (path / "result.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf8")
    return result


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--arduinoisp-installed", action="store_true")
    p.add_argument("--wiring-verified", action="store_true")
    p.add_argument("--receiver-stopped", action="store_true")
    a = p.parse_args()
    try:
        status = execute(arduinoisp_installed=a.arduinoisp_installed,
                         wiring_verified=a.wiring_verified,
                         receiver_stopped=a.receiver_stopped)
        print("COM6_ISP_TARGET_PROBE", json.dumps(status, sort_keys=True))
        raise SystemExit(0 if status["target_signature_verified"] else 3)
    except (RuntimeError, PermissionError) as exc:
        print("COM6_ISP_TARGET_STOP", str(exc))
        raise SystemExit(2)
