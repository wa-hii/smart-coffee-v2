#!/usr/bin/env python3
"""Package a built Pi-return RandomForest MCU image without uploading it.

This is NOT a flashing command.  It checks RF30 flags, UART return marker,
flash addresses, and keeps the current SVM30 image as a private rollback.
Only writes a gitignored, uniquely identified local release bundle.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parents[1]
OUTPUT_ROOT = ROOT / "private" / "rf30_pi_restore_image"
EXPECTED_MODEL_SHA = "b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d"
EXPECTED_BUILD_ID = "take30-ai30-rfhost-20261110"
APPLICATION_LIMIT = 253952


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def validate_pi_rf30_ihex(path: Path) -> dict:
    """Reject bad checksum, duplicate, out-of-range and missing app vectors."""
    base = 0
    seen: set[int] = set()
    eof = False
    for line in path.read_text(encoding="ascii").splitlines():
        if eof or not line.startswith(":") or len(line) % 2 != 1:
            raise ValueError("INVALID_INTEL_HEX_LINE")
        record = bytes.fromhex(line[1:])
        if (len(record) < 5 or record[0] != len(record) - 5
                or sum(record) % 256):
            raise ValueError("INVALID_INTEL_HEX_CHECKSUM_OR_SIZE")
        count = record[0]
        offset = (record[1] << 8) | record[2]
        kind = record[3]
        if kind == 4:
            if count != 2 or offset:
                raise ValueError("INVALID_EXTENDED_ADDRESS")
            base = int.from_bytes(record[4:-1], "big") << 16
        elif kind == 0:
            start = base + offset
            if start + count > APPLICATION_LIMIT:
                raise ValueError("BOOTLOADER_ADDRESS_NOT_ALLOWED")
            for address in range(start, start + count):
                if address in seen:
                    raise ValueError("DUPLICATE_FLASH_ADDRESS")
                seen.add(address)
        elif kind == 1:
            if count or offset:
                raise ValueError("INVALID_EOF")
            eof = True
        else:
            raise ValueError("UNSUPPORTED_IHEX_RECORD")
    if not eof or not seen or min(seen) != 0 or len(seen) < 30000:
        raise ValueError("RF30_APPLICATION_IMAGE_INCOMPLETE")
    return {"flash_payload_bytes": len(seen),
            "highest_address": max(seen),
            "application_limit_bytes": APPLICATION_LIMIT}


def prepare(out: Path) -> dict:
    if out.exists():
        raise FileExistsError("REFUSE_REPLACE_PREPARED_FIRMWARE")
    cfg = ROOT / "scripts" / "platformio_rf30_bench.ini"
    flags = cfg.read_text(encoding="utf8")
    if "-DENABLE_PI_RF30_RETURN=1" not in flags or (
        "-DSMART_COFFEE_STANDALONE_SVM30=1" in flags
    ):
        raise RuntimeError("PI_RF30_BUILD_FLAGS_NOT_VERIFIED")
    source = ROOT / ".pio" / "build" / "rf30_return_bench"
    elf = source / "firmware.elf"
    firmware = source / "firmware.hex"
    if not elf.is_file() or not firmware.is_file():
        raise RuntimeError("RF30_BUILD_MISSING_COMPILE_FIRST")
    data = elf.read_bytes()
    if (
        EXPECTED_BUILD_ID.encode() not in data
        or b"AI_AWAITING_RESULT" not in data
        or b"AI_RESULT_ACK" not in data
        or b"standalone-svm30-bench-20261111" in data
    ):
        raise RuntimeError("RF30_RETURN_PROTOCOL_NOT_FOUND_IN_ELF")
    image_layout = validate_pi_rf30_ihex(firmware)
    current_svm = ROOT / "private" / "b6_com5_svm30_deployment" / "svm30_candidate.hex"
    if not current_svm.is_file() or digest(current_svm) != (
        "6d6b45f0bfcfda0c14b9cd6de1e9a32479e92ab3ee1cccd8e69dce3d530eeba2"
    ):
        raise RuntimeError("CURRENT_SVM30_ROLLBACK_IMAGE_UNVERIFIED")
    if out.resolve().parent != OUTPUT_ROOT.resolve():
        raise ValueError("RF30_IMAGE_MUST_BE_PREPARED_IN_PRIVATE_BUNDLE")
    out.mkdir(parents=True)
    saved = out / "rf30_pi_return_candidate.hex"
    shutil.copy2(firmware, saved)
    if digest(saved) != digest(firmware):
        raise RuntimeError("FIRMWARE_COPY_HASH_MISMATCH")
    report = {
        "prepared_at_utc": datetime.now(timezone.utc).isoformat(),
        "status": "RF30_PI_RETURN_COMPILED_IMAGE_READY_NO_FLASH",
        "board": "ATmega2560",
        "host_architecture": "ATmega Serial0 -> FT232R -> Raspberry Pi 5; Serial2 -> Nextion",
        "profile": "rf30_return_bench",
        "flag_ENABLE_PI_RF30_RETURN": 1,
        "flag_SMART_COFFEE_STANDALONE_SVM30": 0,
        "fw_build_id": EXPECTED_BUILD_ID,
        "rf_model_expected_sha256_on_pi": EXPECTED_MODEL_SHA,
        "candidate_hex_sha256": digest(saved),
        "candidate_hex_file_bytes": saved.stat().st_size,
        "candidate_memory": image_layout,
        "svm30_previous_on_device_sha256": digest(current_svm),
        "svm30_original_backup_dir": "private/b6_com5_readback/20261111_170948",
        "runtime_pi_usb_serial_verified": False,
        "on_device_firmware_changed": False,
        "pi_serial_opened": False,
        "mcu_flash_written": False,
        "eeprom_written": False,
        "flash_or_rollback_tested_on_device": False,
    }
    (out / "image_manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8")
    print("PI_RF30_CANDIDATE_IMAGE_PREPARED", json.dumps(report), flush=True)
    return report


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--build-tag", default="20261112",
                        help="Private output name suffix, refusing overwrites")
    args = parser.parse_args()
    if not args.build_tag.isdecimal() or len(args.build_tag) != 8:
        raise ValueError("BUILD_TAG_MUST_BE_YYYYMMDD")
    prepare(OUTPUT_ROOT / args.build_tag)


if __name__ == "__main__":
    main()
