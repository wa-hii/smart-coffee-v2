#!/usr/bin/env python3
"""Safely flash exact commit 37095d0f RF30 build to FT232RL COM3 ATmega2560.

--backup verifies fresh full-chip flash+EEPROM readback, including erased FF
suffix physically dumped via avrdude terminal. --flash requires that exact
verified backup and a locally rebuilt, SHA-pinned, COM4-proven RF30 image.
No EEPROM, fuse, lockbit, HMI, or actuator commands are written.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
from hashlib import sha256
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from serial.tools import list_ports
from intelhex import IntelHex
from svm30_b6_verify_readback import parse_intel_hex
from prepare_rf30_pi_restore_image import validate_pi_rf30_ihex

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "private/com3_commit_37095d0f"
COMMIT = "37095d0fddb3be818405729a818e6cbf33cc9a0c"
PORT = "COM3"
SERIAL = "A10KN6X9A"
SIGNATURE = "0x1e9801"
IMAGE = Path(r"D:\ENOSE\_rf30_COM3_37095d0f\build\.pio\build\mega2560\firmware.hex")
PROVEN = ROOT / "private/rf30_second_pcb_candidate/20261112_rf30_bootguard_v1/rf30_pi_return_candidate.hex"
EXPECTED_SHA = "26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6"
AVRDUDE = Path.home() / ".platformio/packages/tool-avrdude/avrdude.exe"
CONF = AVRDUDE.with_name("avrdude.conf")
FULL_FLASH = 262144
FULL_EEPROM = 4096
APPROVAL = "I_APPROVE_COM3_A10KN6X9A_COMMIT37095_RF30_FLASH_WITH_VERIFIED_BACKUP"


def digest(path: Path) -> str:
    return sha256(path.read_bytes()).hexdigest()


def verify_target() -> dict:
    ports = [p for p in list_ports.comports()
             if (p.device.upper(), p.vid, p.pid, p.serial_number)
             == (PORT, 0x0403, 0x6001, SERIAL)]
    if len(ports) != 1:
        raise RuntimeError("COM3_FT232RL_SERIAL_IDENTITY_NOT_MATCHED")
    if not (AVRDUDE.is_file() and CONF.is_file()):
        raise RuntimeError("AVRDUDE_NOT_AVAILABLE")
    if not (IMAGE.is_file() and PROVEN.is_file()):
        raise RuntimeError("RF30_BUILT_OR_PROVEN_IMAGE_NOT_AVAILABLE")
    if digest(IMAGE) != EXPECTED_SHA or digest(PROVEN) != EXPECTED_SHA:
        raise RuntimeError("FIRMWARE_SHA256_NOT_EXACT_COM4_PROVEN_BUILD")
    image_info = validate_pi_rf30_ihex(IMAGE)
    # Reject a stale checkout/other commit; source archive is verified
    # separately with all tracked source files from git archive.
    p = subprocess.run(["git", "rev-parse", COMMIT],
                       capture_output=True, text=True, cwd=ROOT, timeout=10)
    if p.returncode or p.stdout.strip() != COMMIT:
        raise RuntimeError("COMMIT_37095_NOT_PRESENT")
    staging = ROOT / "data/raw/.incoming"
    if not staging.is_dir() or any(staging.iterdir()):
        raise RuntimeError("POSSIBLE_ACTIVE_ACQUISITION_STAGING_NOT_EMPTY")
    # The only allowed process is the receiver pinned to a different FTDI
    # serial A10KNJBLA (historical COM11 board), not the COM3 target.
    script = (
        "Get-CimInstance Win32_Process | Where-Object { "
        "$_.Name -in @('python.exe','pythonw.exe','avrdude.exe') -and "
        "($_.Name -eq 'avrdude.exe' -or "
        "$_.CommandLine -match 'lcd_acquisition_service.py|multi_device_receiver.py|3_collect_data.py') "
        "} | Select-Object Name,CommandLine | ConvertTo-Json -Compress"
    )
    p = subprocess.run(["powershell", "-NoProfile", "-NonInteractive",
                        "-Command", script], capture_output=True,
                       text=True, errors="replace", timeout=14)
    if p.returncode:
        raise RuntimeError("CANNOT_VERIFY_USB_PROCESS_OWNERSHIP")
    if p.stdout.strip():
        processes = json.loads(p.stdout)
        if isinstance(processes, dict):
            processes = [processes]
        for item in processes:
            cmd = item.get("CommandLine") or ""
            if (item.get("Name", "").lower() in ("python.exe", "pythonw.exe") and
                    "lcd_acquisition_service.py" in cmd and
                    "--usb-serial A10KNJBLA" in cmd and
                    "--port auto" in cmd):
                continue
            raise RuntimeError("UNKNOWN_RECEIVER_OR_PROGRAMMER_MAY_OWN_COM3")
    return {
        "port": PORT, "usb_serial": SERIAL, "signature": SIGNATURE,
        "source_commit": COMMIT, "rf30_image_sha256": EXPECTED_SHA,
        "rf30_image": image_info,
        "receiver_other_board_only": True,
    }


def avrdude(folder: Path, label: str, extra: list[str], timeout=200,
            stdin: str | None = None) -> tuple[bool, str]:
    args = [
        str(AVRDUDE), "-C", str(CONF), "-p", "m2560", "-c", "wiring",
        "-P", PORT, "-b", "115200", *extra,
    ]
    (folder / (label + ".args.json")).write_text(
        json.dumps(args[1:], indent=2) + "\n", encoding="utf8")
    try:
        p = subprocess.run(args, cwd=folder, input=stdin, capture_output=True,
                           text=True, errors="replace", timeout=timeout)
        code = p.returncode
        output = p.stdout + "\n" + p.stderr
    except subprocess.TimeoutExpired as exc:
        code = 124
        out = exc.stdout.decode("utf8", "replace") if isinstance(exc.stdout, bytes) else (exc.stdout or "")
        err = exc.stderr.decode("utf8", "replace") if isinstance(exc.stderr, bytes) else (exc.stderr or "")
        output = out + "\n" + err + "\nTIMEOUT"
    (folder / (label + ".log")).write_text(
        f"exit={code}\n{output}", encoding="utf8")
    good_signature = "device signature = " + SIGNATURE in output.lower()
    return (code == 0 and good_signature), output


def verify_trimmed_suffix(folder: Path, coverage: int) -> int:
    suffix = FULL_FLASH - coverage
    if suffix < 0 or suffix > 4096:
        raise RuntimeError("UNEXPECTED_FLASH_SUFFIX_LENGTH")
    if suffix == 0:
        return 0
    ok, log = avrdude(folder, "03_suffix_terminal_readonly", ["-t"],
                      timeout=50,
                      stdin=f"dump flash 0x{coverage:x} {suffix}\nquit\n")
    if not ok:
        raise RuntimeError("SUFFIX_PHYSICAL_DUMP_FAILED")
    seen = bytearray()
    next_address = coverage
    for line in log.splitlines():
        # AVRDUDE terminal prints: 03fd1e  ff ff... |ASCII|
        m = re.match(r"^([0-9a-fA-F]{5,6})\s+(.+?)\s*\|", line.strip())
        if not m:
            continue
        addr = int(m.group(1), 16)
        vals = bytes.fromhex(m.group(2))
        if addr != next_address or not vals or addr + len(vals) > FULL_FLASH:
            raise RuntimeError("SUFFIX_DUMP_NONCONTIGUOUS")
        seen.extend(vals)
        next_address += len(vals)
    if len(seen) != suffix or any(x != 0xFF for x in seen):
        raise RuntimeError("SUFFIX_NOT_PHYSICALLY_CONFIRMED_ERASED")
    return suffix


def backup() -> int:
    cfg = verify_target()
    folder = OUT / ("backup_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    folder.mkdir(parents=True, exist_ok=False)
    result = {
        **cfg, "state": "NOT_VERIFIED_NO_WRITES",
        "backup_verified": False, "flash_written": False,
        "eeprom_written": False,
        "saved_utc": datetime.now(timezone.utc).isoformat(),
    }
    def save():
        (folder / "manifest.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf8")
        print("COM3_GUARDED", json.dumps({"folder": str(folder), **result}),
              flush=True)
    save()
    ok, _ = avrdude(folder, "01_signature_readonly", ["-n", "-v"], timeout=28)
    if not ok:
        result["state"] = "SIGNATURE_FAILED_NO_FLASH"; save(); return 3
    ok, _ = avrdude(folder, "02_read_original_flash_and_eeprom", [
        "-n", "-U", "flash:r:original_flash.hex:i",
        "-U", "eeprom:r:original_eeprom.hex:i"], timeout=210)
    if not ok:
        result["state"] = "BACKUP_READ_FAILED_NO_FLASH"; save(); return 4
    try:
        flash = parse_intel_hex(folder / "original_flash.hex", FULL_FLASH,
                                allow_trimmed_erased_suffix=True)
        eeprom = parse_intel_hex(folder / "original_eeprom.hex", FULL_EEPROM)
        covered = flash["address_coverage_bytes"]
        checked_ff = verify_trimmed_suffix(folder, covered)
        full = bytes(IntelHex(str(folder / "original_flash.hex")).tobinarray(
            start=0, size=FULL_FLASH, pad=0xFF))
        full_eeprom = bytes(IntelHex(str(folder / "original_eeprom.hex")).tobinarray(
            start=0, size=FULL_EEPROM, pad=0xFF))
        if (digest_bytes(full) != flash["data_sha256"] or
                digest_bytes(full_eeprom) != eeprom["data_sha256"]):
            raise RuntimeError("READBACK_SHA256_MISMATCH")
        (folder / "original_flash_full_262144.bin").write_bytes(full)
        (folder / "original_eeprom_full_4096.bin").write_bytes(full_eeprom)
    except (ValueError, OSError, RuntimeError) as exc:
        result["state"] = "BACKUP_VALIDATION_FAILED_NO_FLASH"
        result["reason"] = str(exc)[:250]; save(); return 5
    result.update({
        "state": "COM3_ORIGINAL_FLASH_EEPROM_VERIFIED",
        "backup_verified": True, "original_flash_sha256": digest_bytes(full),
        "original_eeprom_sha256": digest_bytes(full_eeprom),
        "original_flash_bytes": len(full),
        "original_eeprom_bytes": len(full_eeprom),
        "trimmed_ff_suffix_verified_bytes": checked_ff,
        "original_firmware_identity": "NOT_ASSUMED",
        "restore_physically_tested": False,
    })
    save()
    return 0


def digest_bytes(value: bytes) -> str:
    return sha256(value).hexdigest()


def flash(backup_folder: Path) -> int:
    cfg = verify_target()
    if backup_folder.parent.resolve() != OUT.resolve():
        raise RuntimeError("BACKUP_NOT_FROM_COM3_PRIVATE_FOLDER")
    manifest = json.loads((backup_folder / "manifest.json").read_text(encoding="utf8"))
    if (manifest.get("state") != "COM3_ORIGINAL_FLASH_EEPROM_VERIFIED" or
            manifest.get("backup_verified") is not True or
            manifest.get("usb_serial") != SERIAL or
            manifest.get("source_commit") != COMMIT or
            manifest.get("rf30_image_sha256") != EXPECTED_SHA):
        raise RuntimeError("COM3_SPECIFIC_BACKUP_NOT_VERIFIED")
    f_backup = backup_folder / "original_flash_full_262144.bin"
    e_backup = backup_folder / "original_eeprom_full_4096.bin"
    if (f_backup.stat().st_size != FULL_FLASH or
            e_backup.stat().st_size != FULL_EEPROM or
            digest(f_backup) != manifest.get("original_flash_sha256") or
            digest(e_backup) != manifest.get("original_eeprom_sha256")):
        raise RuntimeError("COM3_BACKUP_CHANGED_OR_CORRUPTED")

    folder = OUT / ("flash_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    folder.mkdir(parents=True, exist_ok=False)
    result = {
        **cfg, "state": "NO_FLASH_YET", "original_backup": str(backup_folder),
        "flash_written": False, "eeprom_written": False,
        "flash_independent_verify": False, "eeprom_preserved": None,
    }
    def save():
        (folder / "manifest.json").write_text(
            json.dumps(result, indent=2) + "\n", encoding="utf8")
        print("COM3_FLASH_STATUS", json.dumps(result, sort_keys=True), flush=True)
    save()
    ok, _ = avrdude(folder, "01_signature", ["-n", "-v"], timeout=28)
    if not ok:
        result["state"] = "SIGNATURE_FAILED_NO_FLASH"; save(); return 6
    ok, _ = avrdude(folder, "02_write_rf30_flash_only", [
        "-D", "-U", f"flash:w:{IMAGE}:i"], timeout=185)
    if not ok:
        result["state"] = "FLASH_WRITE_FAILED_PARTIAL_POSSIBLE"
        result["flash_written"] = "UNKNOWN_PARTIAL_POSSIBLE"
        save(); return 7
    result["flash_written"] = True
    result["state"] = "FLASH_WRITTEN_PENDING_INDEPENDENT_VERIFY"
    save()
    ok, log = avrdude(folder, "03_verify_flash_independent", [
        "-n", "-U", f"flash:v:{IMAGE}:i"], timeout=185)
    if not ok or "bytes of flash verified" not in log.lower():
        result["state"] = "FLASH_VERIFY_FAILED"; save(); return 8
    result["flash_independent_verify"] = True
    ok, _ = avrdude(folder, "04_eeprom_readback_postflash", [
        "-n", "-U", "eeprom:r:eeprom_postflash.hex:i"], timeout=90)
    if not ok:
        result["state"] = "FLASH_PASS_EEPROM_READ_FAILED"; save(); return 9
    current = parse_intel_hex(folder / "eeprom_postflash.hex", FULL_EEPROM)
    if current["data_sha256"] != manifest["original_eeprom_sha256"]:
        result["state"] = "FLASH_PASS_EEPROM_CHANGED_WARNING"
        result["eeprom_preserved"] = False; save(); return 10
    result["state"] = "COM3_RF30_FLASH_VERIFY_AND_EEPROM_PRESERVATION_PASS_BOOT_PENDING"
    result["eeprom_preserved"] = True
    save()
    return 0


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backup", action="store_true")
    mode.add_argument("--flash", type=Path, metavar="COM3_VERIFIED_BACKUP_DIR")
    p.add_argument("--approval")
    args = p.parse_args()
    try:
        if args.backup:
            return backup()
        if args.approval != APPROVAL:
            raise RuntimeError("COM3_FLASH_APPROVAL_NOT_SUPPLIED")
        return flash(args.flash)
    except (RuntimeError, ValueError, OSError, KeyError) as exc:
        print("COM3_FLASH_STOP", type(exc).__name__, str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())
