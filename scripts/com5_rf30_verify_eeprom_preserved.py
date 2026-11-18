#!/usr/bin/env python3
"""Read-only check that COM5 EEPROM was unchanged by RF30 Flash upload.

COM5 must be exact FTDI A10KMM3SA; no EEPROM or Flash writes.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
import sys
from pathlib import Path

from com5_rf30_guarded_migrate import (
    OUT_ROOT, SERIAL, EEPROM_CAP, preflight, call_avrdude, sha_file,
)
from svm30_b6_verify_readback import parse_intel_hex

BACKUP_DIR = OUT_ROOT / "backup_20261118_152056_053864"


def run():
    info = preflight()
    original = json.loads((BACKUP_DIR / "manifest.json").read_text(encoding="utf8"))
    if (info["ftdi_serial"] != SERIAL or original.get("backup_verified") is not True
            or original.get("ftdi_serial") != SERIAL):
        raise RuntimeError("COM5_BACKUP_NOT_VALID_FOR_EEPROM_COMPARISON")
    out = OUT_ROOT / ("eeprom_after_rf30_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(parents=True, exist_ok=False)
    result = {"ftdi_serial": SERIAL, "port": "COM5",
              "eeprom_written_by_this_script": False,
              "flash_written_by_this_script": False,
              "backup_original_eeprom_sha256": original.get("original_eeprom_sha256"),
              "status": "READ_NOT_COMPLETE"}
    ok, _ = call_avrdude(
        out, "01_eeprom_readonly", ["-n", "-U", "eeprom:r:after_flash_eeprom.hex:i"],
        timeout=65)
    if ok:
        eeprom = parse_intel_hex(out / "after_flash_eeprom.hex", EEPROM_CAP)
        result.update({
            "readback_eeprom_sha256": eeprom["data_sha256"],
            "readback_eeprom_hex_sha256": sha_file(out / "after_flash_eeprom.hex"),
            "status": "EEPROM_UNCHANGED_PASS" if
                eeprom["data_sha256"] == original.get("original_eeprom_sha256")
                else "EEPROM_CHANGED_MISMATCH",
        })
    else:
        result["status"] = "EEPROM_READ_FAILED"
    (out / "result.json").write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print("COM5_RF30_EEPROM_POSTCHECK", json.dumps(result, sort_keys=True), flush=True)
    return 0 if result["status"] == "EEPROM_UNCHANGED_PASS" else 3


if __name__ == "__main__":
    try:
        sys.exit(run())
    except (ValueError, OSError, RuntimeError) as exc:
        print("COM5_RF30_EEPROM_POSTCHECK_STOP", str(exc), file=sys.stderr)
        sys.exit(2)
