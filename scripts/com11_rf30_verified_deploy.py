#!/usr/bin/env python3
"""One bounded COM11 bootloader -> original backup -> RF30 upload attempt.

The only supported target is the second custom PCB's FT232RL serial A10KNJBLA.
Default is read-only (signature + backup). --upload requires verified complete
Flash/EEPROM readback of THIS PCB and an exact pinned RF30 candidate.
This script never uploads to an unidentified serial port or writes EEPROM.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from serial.tools import list_ports

from prepare_rf30_pi_restore_image import validate_pi_rf30_ihex
from svm30_b6_verify_readback import parse_intel_hex

ROOT = Path(__file__).resolve().parents[1]
PORT = "COM11"
USB_SERIAL = "A10KNJBLA"
EXPECTED_HEX_SHA = "26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6"
EXPECTED_SIGNATURE = "0x1e9801"
HEX = ROOT / "private/rf30_second_pcb_candidate/20261112_rf30_bootguard_v1/rf30_pi_return_candidate.hex"
OUT_ROOT = ROOT / "private/com11_second_pcb_deployment"
AVRDUDE = Path.home() / ".platformio/packages/tool-avrdude/avrdude.exe"
CONFIG = AVRDUDE.with_name("avrdude.conf")
COMMAND_BASE = ["-C", str(CONFIG), "-p", "m2560", "-c", "wiring", "-P", PORT, "-b", "115200"]
APPROVAL = "I_APPROVE_VERIFIED_COM11_SECOND_PCB_RF30_UPLOAD"


def digest(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def check_preflight(*, uploading: bool) -> dict:
    ports = [p for p in list_ports.comports()
             if p.device.upper() == PORT
             and (p.vid, p.pid) == (0x0403, 0x6001)
             and p.serial_number == USB_SERIAL]
    if len(ports) != 1:
        raise RuntimeError("COM11_FT232RL_IDENTITY_NOT_VERIFIED")
    if not (AVRDUDE.is_file() and CONFIG.is_file()):
        raise RuntimeError("AVRDUDE_OR_CONFIG_MISSING")
    if not HEX.is_file() or digest(HEX) != EXPECTED_HEX_SHA:
        raise RuntimeError("RF30_IMAGE_SHA_MISMATCH")
    image_details = validate_pi_rf30_ihex(HEX)
    incoming = ROOT / "data/raw/.incoming"
    if not incoming.is_dir() or any(incoming.iterdir()):
        raise RuntimeError("POSSIBLE_ACTIVE_ACQUISITION_INCOMING_NOT_EMPTY")
    powershell = (
        "Get-CimInstance Win32_Process | Where-Object {"
        " $_.Name -in @('python.exe','pythonw.exe','avrdude.exe') -and"
        " ($_.CommandLine -like '*lcd_acquisition_service.py*' -or"
        " $_.Name -eq 'avrdude.exe')"
        "} | Select-Object ProcessId | ConvertTo-Json -Compress")
    p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                        "-Command", powershell], capture_output=True, text=True,
                       timeout=12, errors="replace")
    if p.returncode or p.stdout.strip():
        raise RuntimeError("RECEIVER_OR_PROGRAMMER_ACTIVE_OR_UNKNOWN")
    return {"port": PORT, "ftdi_serial": USB_SERIAL,
            "upload_requested": uploading,
            "candidate_sha256": digest(HEX),
            "image": image_details}


def invoke(out: Path, name: str, extra: list[str], *, timeout: int) -> tuple[bool, str]:
    args = [str(AVRDUDE), *COMMAND_BASE, *extra]
    (out / (name + ".args.json")).write_text(
        json.dumps(args[1:], indent=2) + "\n", encoding="utf8")
    try:
        result = subprocess.run(args, cwd=out, capture_output=True,
                                text=True, errors="replace", timeout=timeout)
        output = result.stdout + "\n" + result.stderr
        code = result.returncode
    except subprocess.TimeoutExpired as exc:
        stdout = exc.stdout.decode("utf8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        stderr = exc.stderr.decode("utf8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        output = stdout + "\n" + stderr + "\nTIMEOUT_KILLED\n"
        code = "TIMEOUT"
    (out / (name + ".log")).write_text(
        "RESULT=" + str(code) + "\n" + output, encoding="utf8")
    return code == 0, output


def run(upload: bool, approval: str | None) -> int:
    if upload and approval != APPROVAL:
        raise PermissionError("SPECIFIC_SECOND_PCB_FLASH_APPROVAL_REQUIRED")
    preflight = check_preflight(uploading=upload)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out = OUT_ROOT / datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    out.mkdir(exist_ok=False)
    status = {
        "started_utc": datetime.now(timezone.utc).isoformat(),
        **preflight,
        "state": "BOOTLOADER_SIGNATURE_NOT_VERIFIED",
        "flash_written": False,
        "eeprom_written": False,
        "backup_verified": False,
        "firmware_uploaded": False,
        "output_dir": str(out),
    }
    report = out / "release_result.json"

    def save() -> None:
        report.write_text(json.dumps(status, indent=2) + "\n", encoding="utf8")
        print("COM11_RF30_RESULT", json.dumps(status, sort_keys=True), flush=True)

    save()
    success, log = invoke(out, "01_bootloader_probe", ["-n", "-v"], timeout=20)
    if not success or "Device signature = " + EXPECTED_SIGNATURE not in log:
        status["state"] = "BOOTLOADER_SIGNATURE_NOT_VERIFIED_NO_FLASH"
        save()
        return 3

    # Read original PCB-specific firmware and EEPROM before any flash write.
    success, log = invoke(out, "02_original_readback", [
        "-n", "-U", "flash:r:flash_readback.hex:i",
        "-U", "eeprom:r:eeprom_readback.hex:i"
    ], timeout=180)
    if not success or "Device signature = " + EXPECTED_SIGNATURE not in log:
        status["state"] = "SECOND_PCB_ORIGINAL_BACKUP_FAILED_NO_FLASH"
        save()
        return 4
    try:
        flash = parse_intel_hex(out / "flash_readback.hex", 262144,
                               allow_trimmed_erased_suffix=True)
        eeprom = parse_intel_hex(out / "eeprom_readback.hex", 4096)
    except (OSError, ValueError) as exc:
        status["state"] = "SECOND_PCB_ORIGINAL_BACKUP_INTEGRITY_FAILED_NO_FLASH"
        status["validation_reason"] = str(exc)
        save()
        return 5
    if flash["unrepresented_suffix_bytes"]:
        # Intel HEX exporters can omit a contiguous FF suffix. Since those
        # omitted bytes are not represented, it is not a *full* verified
        # original-chip backup suitable for unattended rollback.
        status["state"] = "ORIGINAL_FLASH_SUFFIX_NOT_FULLY_REPRESENTED_NO_FLASH"
        status["original_flash_unrepresented_suffix_bytes"] = flash[
            "unrepresented_suffix_bytes"]
        save()
        return 5
    status["backup_verified"] = True
    status["flash_backup_sha256"] = flash["file_sha256"]
    status["eeprom_backup_sha256"] = eeprom["file_sha256"]
    status["original_flash_unrepresented_suffix_bytes"] = flash["unrepresented_suffix_bytes"]
    status["state"] = "SECOND_PCB_ORIGINAL_BACKUP_VERIFIED"
    save()
    if not upload:
        return 0

    # Only application section in pinned HEX. -D preserves EEPROM/fuses and
    # disables an unrelated full-chip erase; AVR bootloader handles page erases.
    success, log = invoke(out, "03_rf30_upload", [
        "-D", "-U", "flash:w:" + str(HEX) + ":i"
    ], timeout=180)
    if not success or "Device signature = " + EXPECTED_SIGNATURE not in log:
        status["state"] = "RF30_UPLOAD_UNVERIFIED_STOP_AND_INSPECT"
        status["flash_written"] = "UNKNOWN_PARTIAL_POSSIBLE"
        save()
        return 6
    status["flash_written"] = True
    success, log = invoke(out, "04_rf30_verify", [
        "-n", "-U", "flash:v:" + str(HEX) + ":i"
    ], timeout=180)
    if not success:
        status["state"] = "RF30_FLASH_VERIFY_FAILED"
        save()
        return 7
    status["firmware_uploaded"] = True
    status["state"] = "RF30_FLASH_VERIFIED_NEXTION_PI_E2E_NOT_YET_TESTED"
    save()
    return 0


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--upload", action="store_true",
                        help="Only after signature and a validated PCB-specific backup")
    parser.add_argument("--approval", default=None)
    args = parser.parse_args()
    try:
        sys.exit(run(upload=args.upload, approval=args.approval))
    except (OSError, RuntimeError, PermissionError) as exc:
        print("COM11_RF30_PREFLIGHT_FAIL", str(exc), file=sys.stderr)
        sys.exit(2)
