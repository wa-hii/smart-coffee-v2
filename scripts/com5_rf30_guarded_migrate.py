#!/usr/bin/env python3
"""Migrate historical COM5 E-Nose SVM30 to COM4-proven Pi-host RF30.

Two explicit phases:
  --backup: read-only current Flash/EEPROM + physically measure trimmed FF
            suffix. Verify currently installed SVM30 candidate if available.
  --flash: only after verified backup and known SVM30 board provenance,
           write 35,770 application bytes, then independently verify.

COM5 is pinned to FTDI A10KMM3SA, ATmega2560 signature 0x1e9801.
No EEPROM writes, no fuse, lockbit or Nextion TFT writes, no actuator commands.
Original backups and terminal logs remain private (Git ignored).
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import re
import subprocess
import sys

from serial.tools import list_ports
from svm30_b6_verify_readback import parse_intel_hex
from prepare_rf30_pi_restore_image import validate_pi_rf30_ihex
from com11_rf30_verified_deploy import AVRDUDE, CONFIG, HEX, EXPECTED_HEX_SHA

ROOT = Path(__file__).resolve().parents[1]
OUT_ROOT = ROOT / "private/com5_rf30_migration"
PORT = "COM5"
SERIAL = "A10KMM3SA"
SIGNATURE = "0x1e9801"
EXPECTED_SVM_SHA = "6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2"
OLD_SVM = ROOT / "private/svm30_standalone_firmware.hex"
PREVIOUS_SVM_MANIFEST = ROOT / "private/b6_com5_svm30_deployment/deployment_manifest.json"
HISTORY = ROOT / "docs/reports/2026-11-11_B6_COM5_SVM30_FLASH_VERIFIED.md"
APPROVAL = "I_APPROVE_RF30_MIGRATE_COM5_WITH_VERIFIED_SVM30_BACKUP"
FLASH_CAP = 262144
EEPROM_CAP = 4096


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def sha_file(path: Path) -> str:
    return sha(path.read_bytes())


def preflight() -> dict:
    ports = [p for p in list_ports.comports()
             if (p.device.upper(), p.vid, p.pid, p.serial_number) ==
             (PORT, 0x0403, 0x6001, SERIAL)]
    if len(ports) != 1:
        raise RuntimeError("COM5_FTDI_SERIAL_A10KMM3SA_NOT_FOUND")
    if not AVRDUDE.is_file() or not CONFIG.is_file():
        raise RuntimeError("AVRDUDE_CONFIG_NOT_AVAILABLE")
    if sha_file(HEX) != EXPECTED_HEX_SHA:
        raise RuntimeError("RF30_COM4_CANDIDATE_SHA256_DIFFERENT")
    image = validate_pi_rf30_ihex(HEX)
    if not OLD_SVM.is_file() or sha_file(OLD_SVM) != EXPECTED_SVM_SHA:
        raise RuntimeError("ORIGINAL_COM5_SVM30_IMAGE_NOT_AVAILABLE")
    if not HISTORY.is_file() or SERIAL not in HISTORY.read_text(encoding="utf8"):
        raise RuntimeError("COM5_HISTORIC_ENOSE_PROVENANCE_MISSING")
    if not PREVIOUS_SVM_MANIFEST.is_file():
        raise RuntimeError("COM5_HISTORIC_SVM30_DEPLOYMENT_MISSING")
    old = json.loads(PREVIOUS_SVM_MANIFEST.read_text(encoding="utf8"))
    if not (str(old.get("port", old.get("target_port", "COM5"))).upper() == PORT or
            SERIAL in PREVIOUS_SVM_MANIFEST.read_text(encoding="utf8")):
        # Manifest schema may differ; the historical report is independently pinned.
        raise RuntimeError("COM5_SVM30_PREVIOUS_MANIFEST_WRONG_TARGET")
    incoming = ROOT / "data/raw/.incoming"
    if not incoming.is_dir() or any(incoming.iterdir()):
        raise RuntimeError("ACTIVE_OR_UNKNOWN_INCOMING_ACQUISITION")
    p = subprocess.run(
        ["powershell", "-NoProfile", "-NonInteractive", "-Command",
         "Get-CimInstance Win32_Process | Where-Object { "
         "$_.Name -in @('python.exe','pythonw.exe','avrdude.exe') -and "
         "($_.Name -eq 'avrdude.exe' -or "
         "$_.CommandLine -match 'lcd_acquisition_service.py|multi_device_receiver.py|3_collect_data.py') "
         "} | Select-Object Name,CommandLine | ConvertTo-Json -Compress"],
        capture_output=True, text=True, timeout=12, errors="replace")
    if p.returncode:
        raise RuntimeError("PROCESS_CHECK_UNAVAILABLE")
    if p.stdout.strip():
        running = json.loads(p.stdout)
        if isinstance(running, dict):
            running = [running]
        for process in running:
            cmd = process.get("CommandLine") or ""
            if (process.get("Name", "").lower() in ("python.exe", "pythonw.exe")
                    and "lcd_acquisition_service.py" in cmd
                    and "--usb-serial A10KNJBLA" in cmd
                    and "--port auto" in cmd):
                continue
            raise RuntimeError("OTHER_RECEIVER_OR_AVRDUDE_MAY_OWN_COM5")
    return {"port": PORT, "ftdi_serial": SERIAL,
            "signature_expected": SIGNATURE,
            "rf30_hex_sha256": EXPECTED_HEX_SHA,
            "svm30_hex_sha256": EXPECTED_SVM_SHA,
            "rf30_image": image,
            "prior_historic_com5_svm30_report": str(HISTORY)}


def call_avrdude(out: Path, label: str, tail: list[str], *, timeout: int,
                 stdin: str | None = None) -> tuple[bool, str]:
    args = [str(AVRDUDE), "-C", str(CONFIG), "-p", "m2560",
            "-c", "wiring", "-P", PORT, "-b", "115200", *tail]
    (out / (label + ".args.json")).write_text(
        json.dumps(args[1:], indent=2) + "\n", encoding="utf8")
    try:
        p = subprocess.run(args, cwd=out, input=stdin, capture_output=True,
                           text=True, errors="replace", timeout=timeout)
        content = p.stdout + "\n" + p.stderr
        code = p.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        content = (stdout.decode("utf8", "replace") if isinstance(stdout, bytes) else stdout)
        content += "\n" + (stderr.decode("utf8", "replace") if isinstance(stderr, bytes) else stderr)
        content += "\nTIMEOUT_KILLED\n"
        code = "TIMEOUT"
    (out / (label + ".log")).write_text(
        "EXIT=" + str(code) + "\n" + content, encoding="utf8")
    success = code == 0 and "device signature = " + SIGNATURE in content.lower()
    return success, content


def backup() -> int:
    info = preflight()
    out = OUT_ROOT / ("backup_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(parents=True, exist_ok=False)
    manifest = {**info, "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                "state": "NOT_VERIFIED_NO_FLASH", "flash_written": False,
                "eeprom_written": False, "backup_verified": False,
                "directory": str(out)}
    def save():
        (out / "manifest.json").write_text(
            json.dumps(manifest, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
        print("COM5_BACKUP_STATE", json.dumps(manifest, sort_keys=True), flush=True)
    save()
    okay, _ = call_avrdude(out, "01_signature", ["-n", "-v"], timeout=25)
    if not okay:
        manifest["state"] = "COM5_SIGNATURE_FAILED_NO_FLASH"; save(); return 3
    okay, _ = call_avrdude(
        out, "02_original_readback",
        ["-n", "-U", "flash:r:original_flash.hex:i",
         "-U", "eeprom:r:original_eeprom.hex:i"], timeout=180)
    if not okay:
        manifest["state"] = "ORIGINAL_MEMORY_READ_FAILED_NO_FLASH"; save(); return 4
    try:
        flash = parse_intel_hex(out / "original_flash.hex", FLASH_CAP,
                                allow_trimmed_erased_suffix=True)
        eeprom = parse_intel_hex(out / "original_eeprom.hex", EEPROM_CAP)
    except (OSError, ValueError) as exc:
        manifest["state"] = "ORIGINAL_MEMORY_INTEGRITY_FAILED_NO_FLASH"
        manifest["error"] = str(exc); save(); return 5
    start = flash["address_coverage_bytes"]
    remainder = FLASH_CAP - start
    if remainder < 0 or remainder > 4096:
        manifest["state"] = "UNEXPECTED_FLASH_TRAILING_GAP_NO_FLASH"
        manifest["unrepresented_bytes"] = remainder; save(); return 5
    if remainder:
        okay, log = call_avrdude(
            out, "03_terminal_verify_suffix", ["-t"], timeout=40,
            stdin=f"dump flash 0x{start:x} {remainder}\nquit\n")
        if not okay:
            manifest["state"] = "TRAILING_FLASH_NOT_PHYSICALLY_READ_NO_FLASH"
            save(); return 5
        expected_next = start
        seen = bytearray()
        for line in log.splitlines():
            m = re.match(r"^([0-9a-fA-F]{5,6})\s+(.+?)\s*\|", line.strip())
            if not m:
                continue
            where = int(m.group(1), 16)
            raw = bytes.fromhex(m.group(2))
            if where != expected_next or not raw or where + len(raw) > FLASH_CAP:
                manifest["state"] = "TRAILING_FLASH_BAD_ADDRESS_NO_FLASH"
                save(); return 5
            seen.extend(raw)
            expected_next += len(raw)
        if len(seen) != remainder or any(byte != 0xFF for byte in seen):
            manifest["state"] = "TRAILING_FLASH_NOT_FULLY_FF_NO_FLASH"
            save(); return 5
    # New backup is of the current SVM30 firmware; ensure currently
    # installed APPLICATION matches historical firmware (not only the MCU).
    okay, log = call_avrdude(out, "04_verify_existing_svm30", [
        "-n", "-U", "flash:v:" + str(OLD_SVM) + ":i"
    ], timeout=180)
    if not okay or "verified" not in log.lower():
        manifest["state"] = "CURRENT_FIRMWARE_NOT_HISTORIC_SVM30_NO_FLASH"
        save(); return 6
    # Complete memory image: IHEX parser includes FF values for suffix,
    # which have now been confirmed physically via avrdude terminal.
    from intelhex import IntelHex
    ihex = IntelHex(str(out / "original_flash.hex"))
    full = bytes(ihex.tobinarray(start=0, size=FLASH_CAP, pad=0xFF))
    if sha(full) != flash["data_sha256"]:
        manifest["state"] = "FLASH_RECONSTRUCTION_HASH_MISMATCH_NO_FLASH"
        save(); return 5
    (out / "original_flash_full_262144.bin").write_bytes(full)
    ihex_e = IntelHex(str(out / "original_eeprom.hex"))
    full_e = bytes(ihex_e.tobinarray(start=0, size=EEPROM_CAP, pad=0xFF))
    if sha(full_e) != eeprom["data_sha256"]:
        manifest["state"] = "EEPROM_RECONSTRUCTION_HASH_MISMATCH_NO_FLASH"
        save(); return 5
    (out / "original_eeprom_full_4096.bin").write_bytes(full_e)
    manifest.update({
        "state": "CURRENT_COM5_SVM30_ORIGINAL_BACKUP_VERIFIED",
        "backup_verified": True,
        "current_original_svm30_application_verified": True,
        "original_flash_sha256": sha(full),
        "original_eeprom_sha256": sha(full_e),
        "flash_size": len(full),
        "eeprom_size": len(full_e),
        "suffix_verified_ff_bytes": remainder,
        "flash_hex_sha256": flash["file_sha256"],
        "eeprom_hex_sha256": eeprom["file_sha256"],
        "restoration_physically_tested": False,
    })
    save()
    return 0


def flash(out: Path) -> int:
    info = preflight()
    path = out / "manifest.json"
    record = json.loads(path.read_text(encoding="utf8"))
    if (record.get("state") != "CURRENT_COM5_SVM30_ORIGINAL_BACKUP_VERIFIED" or
            record.get("backup_verified") is not True or
            record.get("current_original_svm30_application_verified") is not True or
            record.get("ftdi_serial") != SERIAL or
            record.get("port") != PORT or
            record.get("rf30_hex_sha256") != EXPECTED_HEX_SHA):
        raise RuntimeError("COM5_PRE_FLASH_BACKUP_OR_TARGET_MISMATCH")
    flash_back = out / "original_flash_full_262144.bin"
    eeprom_back = out / "original_eeprom_full_4096.bin"
    if (flash_back.stat().st_size != FLASH_CAP or
            eeprom_back.stat().st_size != EEPROM_CAP or
            sha_file(flash_back) != record.get("original_flash_sha256") or
            sha_file(eeprom_back) != record.get("original_eeprom_sha256")):
        raise RuntimeError("COM5_ORIGINAL_BACKUP_HASH_NOT_VALID")
    release = {**info, "backup_dir": str(out),
               "backup_flash_sha256": record["original_flash_sha256"],
               "backup_eeprom_sha256": record["original_eeprom_sha256"],
               "state": "NO_FLASH_YET", "flash_written": False,
               "eeprom_written": False, "independent_verify": False}
    work = OUT_ROOT / ("flash_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    work.mkdir(parents=True, exist_ok=False)
    def save():
        (work / "release_result.json").write_text(json.dumps(
            release, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
        print("COM5_RF30_FLASH_STATE", json.dumps(release, sort_keys=True), flush=True)
    save()
    okay, _ = call_avrdude(work, "01_signature", ["-n", "-v"], timeout=25)
    if not okay:
        release["state"] = "SIGNATURE_FAILED_NO_FLASH"; save(); return 7
    okay, _ = call_avrdude(work, "02_flash_rf30", [
        "-D", "-U", "flash:w:" + str(HEX) + ":i"
    ], timeout=180)
    if not okay:
        release["state"] = "FLASH_FAILED_POSSIBLE_PARTIAL_WRITE"
        release["flash_written"] = "UNKNOWN_PARTIAL_POSSIBLE"
        save(); return 8
    release["flash_written"] = True
    release["state"] = "RF30_APPLICATION_WRITTEN_VERIFY_PENDING"
    save()
    okay, log = call_avrdude(work, "03_independent_verify", [
        "-n", "-U", "flash:v:" + str(HEX) + ":i"
    ], timeout=180)
    if not okay or "verified" not in log.lower():
        release["state"] = "RF30_INDEPENDENT_VERIFY_FAILED"
        save(); return 9
    release["independent_verify"] = True
    release["state"] = "RF30_COM5_FLASH_AND_VERIFY_PASS_HMI_PI_TEST_PENDING"
    save()
    return 0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--backup", action="store_true")
    mode.add_argument("--flash", type=Path, metavar="VERIFIED_BACKUP_DIR")
    p.add_argument("--approval", default=None)
    args = p.parse_args()
    try:
        if args.backup:
            sys.exit(backup())
        if args.approval != APPROVAL:
            raise RuntimeError("COM5_SPECIFIC_USER_UPLOAD_APPROVAL_REQUIRED")
        if args.flash.parent.resolve() != OUT_ROOT.resolve():
            raise RuntimeError("BACKUP_FOLDER_NOT_IN_COM5_PRIVATE_DIR")
        sys.exit(flash(args.flash))
    except (OSError, ValueError, RuntimeError) as exc:
        print("COM5_RF30_MIGRATION_STOP", str(exc), file=sys.stderr)
        sys.exit(2)
