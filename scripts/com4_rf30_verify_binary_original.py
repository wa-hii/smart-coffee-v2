#!/usr/bin/env python3
"""Second COM4 original readback in raw binary, STRICTLY read-only.

Compare full logical 256KiB Flash and 4KiB EEPROM read via bootloader
against the prior independent Intel HEX read. This checks whether the
shortened Intel HEX was simply an FF suffix, but cannot disprove a
bootloader-imposed memory read protection. Never writes Flash or EEPROM.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from com4_rf30_verified_deploy import check_preflight
from com11_rf30_verified_deploy import AVRDUDE, CONFIG, ROOT, EXPECTED_SIGNATURE
from svm30_b6_verify_readback import parse_intel_hex

PARENT = ROOT / "private/com4_rf30_deployment/20261117_184947_198494"


def sha(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def run() -> dict:
    info = check_preflight(uploading=False)
    if (info["port"] != "COM4" or info["ftdi_serial"] != "A10KMZQJA"):
        raise RuntimeError("COM4_TARGET_WRONG_IDENTITY")
    if not (PARENT / "flash_readback.hex").is_file():
        raise RuntimeError("ORIGINAL_IHEX_BACKUP_MISSING")
    old_flash = parse_intel_hex(PARENT / "flash_readback.hex", 262144,
                               allow_trimmed_erased_suffix=True)
    old_eeprom = parse_intel_hex(PARENT / "eeprom_readback.hex", 4096)
    out = PARENT / ("binary_recheck_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    args = [str(AVRDUDE), "-C", str(CONFIG), "-p", "m2560", "-c", "wiring",
            "-P", "COM4", "-b", "115200", "-n", "-v",
            "-U", "flash:r:flash_full.bin:r", "-U", "eeprom:r:eeprom_full.bin:r"]
    report = {
        "created_at_utc": datetime.now(timezone.utc).isoformat(),
        "port": "COM4", "ftdi_serial": "A10KMZQJA",
        "read_only": True, "flash_written": False,
        "eeprom_written": False, "result": "NOT_VERIFIED",
        "first_hex_flash_unrepresented_suffix": old_flash["unrepresented_suffix_bytes"],
        "binary_recheck_dir": str(out),
    }
    try:
        done = subprocess.run(args, cwd=out, capture_output=True, text=True,
                              errors="replace", timeout=180)
        log = (done.stdout or "") + "\n" + (done.stderr or "")
        code = done.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        log = (stdout.decode("utf8", "replace") if isinstance(stdout, bytes) else stdout)
        log += "\n" + (stderr.decode("utf8", "replace") if isinstance(stderr, bytes) else stderr)
        code = "TIMEOUT"
    (out / "avrdude_readonly.log").write_text("EXIT=" + str(code) + "\n" + log, encoding="utf8")
    report["exit_code"] = code
    if code == 0 and "device signature = " + EXPECTED_SIGNATURE in log.lower():
        flash_path = out / "flash_full.bin"
        eeprom_path = out / "eeprom_full.bin"
        if flash_path.is_file() and eeprom_path.is_file():
            flash = flash_path.read_bytes()
            eeprom = eeprom_path.read_bytes()
            report.update({
                "flash_binary_bytes": len(flash),
                "eeprom_binary_bytes": len(eeprom),
                "flash_binary_sha256": sha(flash),
                "eeprom_binary_sha256": sha(eeprom),
                "flash_matches_previous_hex_with_ff_suffix_assumption":
                    len(flash) == 262144 and sha(flash) == old_flash["data_sha256"],
                "eeprom_matches_previous_hex":
                    len(eeprom) == 4096 and sha(eeprom) == old_eeprom["data_sha256"],
                "unobservable_lock_bit_protection_possible": True,
            })
            if (report["flash_matches_previous_hex_with_ff_suffix_assumption"] and
                    report["eeprom_matches_previous_hex"]):
                report["result"] = "FULL_LOGICAL_ADDRESS_SPACE_READBACK_MATCHES_BOTH_FORMATS"
    (out / "binary_recheck_result.json").write_text(
        json.dumps(report, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print("COM4_BINARY_READBACK_RECHECK", json.dumps(report, sort_keys=True), flush=True)
    return report


if __name__ == "__main__":
    try:
        outcome = run()
        raise SystemExit(
            0 if outcome["result"] == "FULL_LOGICAL_ADDRESS_SPACE_READBACK_MATCHES_BOTH_FORMATS" else 3)
    except (OSError, RuntimeError, ValueError) as exc:
        print("COM4_BINARY_RECHECK_ABORT", str(exc), file=sys.stderr)
        raise SystemExit(2)
