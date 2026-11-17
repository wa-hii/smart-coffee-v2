#!/usr/bin/env python3
"""Verify COM4 original backup: two memory reads plus terminal FF suffix.

Read-only device operations. The 738 FF suffix is physically read with
AVRDUDE terminal 'dump flash'; it is NOT blindly fabricated. Then complete
logical 262144-byte Flash image for safe rollback. EEPROM must match both
independent reads. Refuse if any byte/address is inconsistent.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import re
import subprocess
import sys

from com4_rf30_verified_deploy import check_preflight
from com4_rf30_verify_binary_original import PARENT
from com11_rf30_verified_deploy import AVRDUDE, CONFIG, EXPECTED_SIGNATURE
from svm30_b6_verify_readback import parse_intel_hex

FLASH_CAP = 262144
EEPROM_CAP = 4096


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def run() -> dict:
    info = check_preflight(uploading=False)
    if (info["port"], info["ftdi_serial"]) != ("COM4", "A10KMZQJA"):
        raise RuntimeError("COM4_DEVICE_IDENTITY_MISMATCH")
    previous = parse_intel_hex(PARENT / "flash_readback.hex", FLASH_CAP,
                               allow_trimmed_erased_suffix=True)
    prev_eeprom = parse_intel_hex(PARENT / "eeprom_readback.hex", EEPROM_CAP)
    matches = sorted(PARENT.glob("binary_recheck_*/binary_recheck_result.json"))
    if len(matches) != 1:
        raise RuntimeError("BINARY_RECHECK_NOT_UNIQUE")
    report = json.loads(matches[0].read_text(encoding="utf8"))
    if report.get("exit_code") != 0:
        raise RuntimeError("SECOND_READ_DID_NOT_SUCCEED")
    second_dir = matches[0].parent
    raw_flash = (second_dir / "flash_full.bin").read_bytes()
    raw_eeprom = (second_dir / "eeprom_full.bin").read_bytes()
    if (len(raw_flash) != previous["address_coverage_bytes"] or
            len(raw_eeprom) != EEPROM_CAP or
            sha(raw_eeprom) != prev_eeprom["data_sha256"]):
        raise RuntimeError("FIRST_SECOND_BACKUP_OR_EEPROM_MISMATCH")
    suffix_offset = len(raw_flash)
    missing = FLASH_CAP - suffix_offset
    if not 0 < missing <= 4096:
        raise RuntimeError("UNEXPECTED_FLASH_SUFFIX_SIZE")

    args = [str(AVRDUDE), "-C", str(CONFIG), "-p", "m2560",
            "-c", "wiring", "-P", "COM4", "-b", "115200",
            "-t"]
    terminal_command = f"dump flash 0x{suffix_offset:x} {missing}\nquit\n"
    out = PARENT / ("terminal_suffix_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    try:
        p = subprocess.run(args, input=terminal_command,
                           capture_output=True, text=True, errors="replace",
                           timeout=35)
        output = (p.stdout or "") + "\n" + (p.stderr or "")
    except subprocess.TimeoutExpired:
        raise RuntimeError("TERMINAL_SUFFIX_DUMP_TIMEOUT")
    (out / "avrdude_terminal_dump.log").write_text(output, encoding="utf8")
    if p.returncode or "device signature = " + EXPECTED_SIGNATURE not in output.lower():
        raise RuntimeError("TERMINAL_SIGNATURE_NOT_VERIFIED")

    collected = bytearray()
    next_address = suffix_offset
    for line in output.splitlines():
        row = re.match(r"^([0-9a-fA-F]{5,6})\s+(.+?)\s*\|", line.strip())
        if not row:
            continue
        where = int(row.group(1), 16)
        raw = bytes.fromhex(row.group(2))
        if where != next_address:
            raise RuntimeError("TERMINAL_DUMP_ADDRESS_HOLE_OR_DUPLICATE")
        if len(raw) == 0 or where + len(raw) > FLASH_CAP:
            raise RuntimeError("TERMINAL_DUMP_SIZE_INVALID")
        collected.extend(raw)
        next_address += len(raw)
    if len(collected) != missing or any(byte != 0xFF for byte in collected):
        raise RuntimeError("TERMINAL_SUFFIX_NOT_FULL_LENGTH_OR_NOT_FF")
    complete_flash = raw_flash + collected
    if sha(complete_flash) != previous["data_sha256"]:
        raise RuntimeError("HEX_BINARY_TERMINAL_FULL_FLASH_HASH_MISMATCH")
    (out / "original_flash_262144_fully_checked.bin").write_bytes(complete_flash)
    (out / "original_eeprom_4096_checked.bin").write_bytes(raw_eeprom)
    result = {
        "status": "RECOVERY_BACKUP_FULL_LOGICAL_FLASH_AND_EEPROM_VERIFIED",
        "target_port": "COM4", "ftdi_serial": "A10KMZQJA",
        "signature": EXPECTED_SIGNATURE,
        "first_hex_address_coverage": previous["address_coverage_bytes"],
        "second_binary_address_coverage": len(raw_flash),
        "terminal_suffix_start": suffix_offset,
        "terminal_suffix_physically_read_bytes": len(collected),
        "terminal_suffix_all_ff": True,
        "original_flash_bytes": len(complete_flash),
        "original_flash_sha256": sha(complete_flash),
        "original_eeprom_bytes": len(raw_eeprom),
        "original_eeprom_sha256": sha(raw_eeprom),
        "flash_or_eeprom_written_to_device": False,
        "bootloader_read_protection_not_independently_tested": True,
        "restorability_on_hardware_not_tested": True,
        "output_dir": str(out),
    }
    (out / "backup_verified.json").write_text(
        json.dumps(result, indent=2) + "\n", encoding="utf8")
    print("COM4_RECOVERY_BACKUP", json.dumps(result, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    try:
        run()
    except (ValueError, RuntimeError, OSError) as exc:
        print("COM4_RECOVERY_BACKUP_STOP", str(exc), file=sys.stderr)
        raise SystemExit(3)
