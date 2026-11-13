#!/usr/bin/env python3
"""Backup read-only MCU Arduino Mega CH340 COM12 SEBELUM mengganti sketch.

Tidak pernah membaca/mengubah PCB E-Nose COM11. Output bersifat privat.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
import subprocess
from pathlib import Path
import sys

from com12_mega_isp_preflight import AVRDUDE, OUT, PROGRAMMER_PORT, check
from svm30_b6_verify_readback import parse_intel_hex


def backup() -> dict:
    status = check()
    OUT.mkdir(parents=True, exist_ok=True)
    target = OUT / ("programmer_original_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    target.mkdir(exist_ok=False)
    argv = [str(AVRDUDE), "-C", str(AVRDUDE.with_name("avrdude.conf")),
            "-p", "m2560", "-c", "wiring", "-P", PROGRAMMER_PORT, "-b", "115200",
            "-n", "-v", "-U", "flash:r:flash_readback.hex:i",
            "-U", "eeprom:r:eeprom_readback.hex:i"]
    status.update({"backup_dir": str(target), "readback_attempted": True,
                   "readback_verified": False, "restore_ability_confirmed": False})
    try:
        p = subprocess.run(argv, cwd=target, capture_output=True, text=True,
                           errors="replace", timeout=175)
        raw = (p.stdout or "") + "\n" + (p.stderr or "")
        exit_code = p.returncode
    except subprocess.TimeoutExpired as exc:
        out = exc.stdout or b""
        err = exc.stderr or b""
        raw = (out.decode("utf8", "replace") if isinstance(out, bytes) else out)
        raw += "\n" + (err.decode("utf8", "replace")
                       if isinstance(err, bytes) else err)
        exit_code = "TIMEOUT"
    (target / "avrdude_readonly.log").write_text(raw, encoding="utf8")
    status["avrdude_exit_code"] = exit_code
    if exit_code == 0 and "Device signature = 0x1e9801" in raw:
        try:
            records = {}
            for name, size in (("flash_readback.hex", 262144),
                               ("eeprom_readback.hex", 4096)):
                records[name] = parse_intel_hex(
                    target / name, size,
                    allow_trimmed_erased_suffix=(name == "flash_readback.hex"))
            status["files"] = records
            status["readback_verified"] = (
                records["flash_readback.hex"]["unrepresented_suffix_bytes"] == 0 and
                records["eeprom_readback.hex"]["unrepresented_suffix_bytes"] == 0)
        except (ValueError, OSError) as exc:
            status["error"] = str(exc)
    (target / "backup_result.json").write_text(
        json.dumps(status, ensure_ascii=False, indent=2) + "\n", encoding="utf8")
    print("COM12_ORIGINAL_PROGRAMMER_BACKUP", json.dumps({
        "readback_verified": status["readback_verified"],
        "avrdude_exit_code": exit_code,
        "backup_dir": str(target),
        "files": {k: {"address_coverage_bytes": v["address_coverage_bytes"],
                      "unrepresented_suffix_bytes": v["unrepresented_suffix_bytes"],
                      "sha256": v["file_sha256"]}
                  for k, v in status.get("files", {}).items()},
        "target_com11_touched": False,
        "flash_or_eeprom_written": False,
        "error": status.get("error"),
    }, ensure_ascii=False), flush=True)
    return status


if __name__ == "__main__":
    result = backup()
    sys.exit(0 if result["readback_verified"] else 3)
