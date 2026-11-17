#!/usr/bin/env python3
"""Safe COM4 RF30 deployment: exact FTDI identity -> signature -> backup -> flash.

The image was built for a *different* PCB (the previous COM11 board).
We therefore do not use normal PlatformIO upload blindly: first attempt
full readback of the COM4 device and fail closed if its original firmware
cannot be recovered and verified. COM11 receiver may stay running ONLY if
its process arguments pin it specifically to the different FTDI A10KNJBLA.
"""
from __future__ import annotations

import json
import subprocess
import sys

from serial.tools import list_ports

import com11_rf30_verified_deploy as deploy

PORT = "COM4"
FTDI_SERIAL = "A10KMZQJA"
APPROVAL = "I_APPROVE_RF30_COM4_AFTER_VERIFIED_ORIGINAL_BACKUP"


def check_preflight(*, uploading: bool) -> dict:
    found = [p for p in list_ports.comports()
             if p.device.upper() == PORT
             and (p.vid, p.pid) == (0x0403, 0x6001)
             and p.serial_number == FTDI_SERIAL]
    if len(found) != 1:
        raise RuntimeError("COM4_FT232RL_IDENTITY_NOT_VERIFIED")
    if not (deploy.AVRDUDE.is_file() and deploy.CONFIG.is_file()):
        raise RuntimeError("AVRDUDE_MISSING")
    if not deploy.HEX.is_file() or deploy.digest(deploy.HEX) != deploy.EXPECTED_HEX_SHA:
        raise RuntimeError("RF30_SOURCE_IMAGE_HASH_MISMATCH")
    details = deploy.validate_pi_rf30_ihex(deploy.HEX)
    incoming = deploy.ROOT / "data/raw/.incoming"
    if not incoming.is_dir() or any(incoming.iterdir()):
        raise RuntimeError("ACTIVE_DATA_ACQUISITION_INCOMING_FILES")

    # Do not interfere with the known, pinned, different USB receiver.
    query = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -in @('python.exe','pythonw.exe','avrdude.exe') -and "
        "($_.Name -eq 'avrdude.exe' -or $_.CommandLine -match "
        "'lcd_acquisition_service.py|multi_device_receiver.py|3_collect_data.py') "
        "} | Select-Object Name,CommandLine | ConvertTo-Json -Compress"
    )
    p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive", "-Command", query],
                       capture_output=True, text=True, errors="replace", timeout=12)
    if p.returncode:
        raise RuntimeError("PROCESS_OWNERSHIP_CHECK_FAILED")
    if p.stdout.strip():
        process_data = json.loads(p.stdout)
        if isinstance(process_data, dict):
            process_data = [process_data]
        for row in process_data:
            cmd = row.get("CommandLine") or ""
            # Only a receiver explicitly pinned to a physically DIFFERENT
            # FTDI device is safe to leave running during COM4 USB operations.
            if (row.get("Name", "").lower() in ("python.exe", "pythonw.exe")
                    and "lcd_acquisition_service.py" in cmd
                    and "--usb-serial A10KNJBLA" in cmd
                    and "--port auto" in cmd):
                continue
            raise RuntimeError("OTHER_POSSIBLE_RECEIVER_OR_PROGRAMMER_ACTIVE")

    return {
        "port": PORT,
        "ftdi_serial": FTDI_SERIAL,
        "upload_requested": uploading,
        "candidate_sha256": deploy.digest(deploy.HEX),
        "image": details,
        "known_com11_receiver_is_pinned_to_other_device": True,
        "hardware_compatibility_physically_verified": False,
    }


def main() -> int:
    # The shared original guarded pipeline strictly checks signature,
    # exact candidate SHA and *complete* flash/eeprom original readback
    # before any write. It never writes EEPROM or fuses.
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true")
    parser.add_argument("--approval", default=None)
    args = parser.parse_args()

    deploy.PORT = PORT
    deploy.USB_SERIAL = FTDI_SERIAL
    deploy.APPROVAL = APPROVAL
    deploy.OUT_ROOT = deploy.ROOT / "private/com4_rf30_deployment"
    deploy.COMMAND_BASE = ["-C", str(deploy.CONFIG), "-p", "m2560",
                           "-c", "wiring", "-P", PORT, "-b", "115200"]
    deploy.check_preflight = check_preflight
    try:
        return deploy.run(args.upload, args.approval)
    except (RuntimeError, PermissionError, OSError) as exc:
        print("COM4_RF30_PREFLIGHT_STOP", str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
