#!/usr/bin/env python3
"""Offline Intel HEX integrity checks for read-only B6 ATmega2560 backups.

Never connects to COM/USB, never writes flash/EEPROM.
Use this to validate full readback coverage before claiming recovery-ready.
"""
from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def parse_intel_hex(path: Path, expected_bytes: int,
                    *, allow_trimmed_erased_suffix: bool = False) -> dict:
    if not path.is_file() or not path.stat().st_size:
        raise ValueError("BACKUP_FILE_MISSING")
    seen = bytearray(expected_bytes)
    values = bytearray(expected_bytes)
    high16 = 0
    segment = 0
    eof = False
    lines = 0
    records = Counter()
    for line in path.read_text(encoding="ascii").splitlines():
        lines += 1
        if eof:
            raise ValueError("DATA_AFTER_EOF")
        if not line.startswith(":") or len(line) % 2 != 1:
            raise ValueError("INVALID_IHEX_LINE")
        try:
            b = bytes.fromhex(line[1:])
        except ValueError as exc:
            raise ValueError("NON_HEX_CHARACTER") from exc
        if len(b) < 5 or b[0] != len(b) - 5 or sum(b) % 256 != 0:
            raise ValueError("IHEX_RECORD_CHECKSUM_OR_SIZE_FAILURE")
        size = b[0]
        addr = (b[1] << 8) | b[2]
        kind = b[3]
        payload = b[4:-1]
        records[kind] += 1
        if kind == 0:
            base = (high16 << 16) + (segment << 4) + addr
            if base + size > expected_bytes:
                raise ValueError("DATA_OUTSIDE_MEMORY")
            for index, value in enumerate(payload):
                where = base + index
                if seen[where]:
                    raise ValueError("DUPLICATE_ADDRESS")
                seen[where] = 1
                values[where] = value
        elif kind == 1:
            if size or addr:
                raise ValueError("MALFORMED_EOF")
            eof = True
        elif kind == 4:
            if size != 2 or addr != 0:
                raise ValueError("INVALID_EXT_LINEAR_ADDRESS")
            high16 = int.from_bytes(payload, "big")
            segment = 0
        elif kind == 2:
            if size != 2 or addr != 0:
                raise ValueError("INVALID_EXT_SEGMENT_ADDRESS")
            segment = int.from_bytes(payload, "big")
            high16 = 0
        elif kind in (3, 5):
            if size != 4:
                raise ValueError("INVALID_START_ADDRESS")
        else:
            raise ValueError("UNKNOWN_IHEX_RECORD_KIND")
    if not eof:
        raise ValueError("NO_EOF")
    covered = seen.count(1)
    missing_suffix = 0
    if covered != expected_bytes:
        if not allow_trimmed_erased_suffix:
            raise ValueError(f"INCOMPLETE_READBACK:{covered}/{expected_bytes}")
        # avrdude Intel HEX exporter can trim trailing 0xFF bytes. This is
        # an assumption, not proof of actual memory contents. A hole in the
        # middle is never allowed (nor a missing reset vector at address 0).
        if not seen[0] or 0 in seen[:covered] or 1 in seen[covered:]:
            raise ValueError("NON_SUFFIX_HOLE_IN_READBACK")
        missing_suffix = expected_bytes - covered
        # For hash convenience only, the UNOBSERVED suffix is filled FF.
        # Never interpret it as physically measured.
        values[covered:] = b"\xff" * missing_suffix
    non_erased = sum(byte != 0xFF for byte in values)
    if non_erased == 0:
        raise ValueError("ALL_FF_READBACK_NOT_RECOVERABLE")
    return {
        "file": path.name,
        "file_bytes": path.stat().st_size,
        "file_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
        "memory_bytes": expected_bytes,
        "address_coverage_bytes": covered,
        "unrepresented_suffix_bytes": missing_suffix,
        "unrepresented_suffix_assumed_ff_not_measured": bool(missing_suffix),
        "ihex_records": lines,
        "ihex_record_types": dict(records),
        "data_bytes_non_ff": non_erased,
        "data_sha256": hashlib.sha256(values).hexdigest(),
        "first_16_bytes_hex": values[:16].hex(),
        "last_16_bytes_hex": values[-16:].hex(),
    }


def verify(directory: Path) -> dict:
    manifest = json.loads((directory / "backup_manifest.json").read_text(
        encoding="utf8"))
    log = (directory / "avrdude_readonly.log").read_text(
        encoding="utf8", errors="replace")
    if manifest.get("avrdude_exit_code") != 0:
        raise ValueError("AVRDUDE_DID_NOT_EXIT_ZERO")
    if ("Device signature = 0x1e9801" not in log or
            "reading flash memory:" not in log or
            "reading eeprom memory:" not in log):
        raise ValueError("TARGET_SIGNATURE_OR_MEMORY_READ_NOT_VERIFIED")
    if "-n" not in manifest.get("avrdude_args_excluding_executable", []):
        raise ValueError("NO_WRITE_OPTION_NOT_USED")
    if any(":w:" in option or option == "-e"
           for option in manifest["avrdude_args_excluding_executable"]):
        raise ValueError("WRITE_OR_ERASE_OPTION_DETECTED")
    files = {}
    for name, expected in (("flash_readback.hex", 262144),
                           ("eeprom_readback.hex", 4096)):
        path = directory / name
        result = parse_intel_hex(path, expected,
                                 allow_trimmed_erased_suffix=name.startswith("flash"))
        if (result["file_sha256"] !=
                manifest.get("files", {}).get(name, {}).get("sha256")):
            raise ValueError("BACKUP_HASH_MISMATCH")
        files[name] = result
    return {
        "validated_at": datetime.now(timezone.utc).isoformat(),
        "status": "OFFLINE_INTEGRITY_PASS_WITH_FLASH_TRIMMED_SUFFIX"
                  if files["flash_readback.hex"]["unrepresented_suffix_bytes"]
                  else "OFFLINE_INTEGRITY_FULL_COVERAGE_PASS",
        "device_signature": "0x1e9801",
        "read_only": True,
        "com_port_opened_during_validation": False,
        "flash_or_eeprom_written": False,
        "restorability_tested_on_hardware": False,
        "trailing_flash_erased_ff_not_measured": bool(
            files["flash_readback.hex"]["unrepresented_suffix_bytes"]),
        "original_backup_dir": str(directory),
        "files": files,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args()
    d = args.backup_dir.resolve()
    if d.parent != (ROOT / "private" / "b6_com5_readback").resolve():
        raise ValueError("ONLY_PRIVATE_B6_BACKUP_SUBDIR_ALLOWED")
    result = verify(d)
    output = d / "ihex_integrity_report.json"
    if output.exists():
        raise FileExistsError("DO_NOT_OVERWRITE_EXISTING_REPORT")
    output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf8")
    print("B6_READBACK_OFFLINE_INTEGRITY",
          json.dumps({
              "status": result["status"],
              "device_signature": result["device_signature"],
              "flash": result["files"]["flash_readback.hex"],
              "eeprom": result["files"]["eeprom_readback.hex"],
              "wrote_to_device": False,
          }), flush=True)


if __name__ == "__main__":
    main()
