#!/usr/bin/env python3
"""Prepare a compile-only RF30 image for a DIFFERENT, unverified PCB.

Do not assume that the old COM5/SVM30 backup or model is installed on this
board. This tool validates the firmware image, saves a uniquely named private
candidate bundle, and NEVER opens serial, uploads, or accesses EEPROM.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import re
import shutil

from prepare_rf30_pi_restore_image import (
    EXPECTED_BUILD_ID, EXPECTED_MODEL_SHA, ROOT,
    digest, validate_pi_rf30_ihex,
)

BASE = ROOT / "private" / "rf30_second_pcb_candidate"
BUILD = ROOT / ".pio" / "build" / "rf30_return_bench"


def prepare(bundle_name: str) -> dict:
    if not re.fullmatch(r"20[0-9]{6}_[A-Za-z0-9][A-Za-z0-9_-]{0,47}",
                        bundle_name):
        raise ValueError("INVALID_BUNDLE_NAME")
    bundle = BASE / bundle_name
    if bundle.exists():
        raise FileExistsError("REFUSE_OVERWRITE_FIRMWARE_BUNDLE")
    profile = (ROOT / "scripts" / "platformio_rf30_bench.ini").read_text(
        encoding="utf8")
    if ("-DENABLE_PI_RF30_RETURN=1" not in profile or
            "-DSMART_COFFEE_STANDALONE_SVM30=1" in profile):
        raise ValueError("RF30_PI_RETURN_PROFILE_INVALID")
    elf, image = BUILD / "firmware.elf", BUILD / "firmware.hex"
    if not elf.is_file() or not image.is_file():
        raise FileNotFoundError("COMPILE_RF30_RETURN_BENCH_FIRST")
    elf_bytes = elf.read_bytes()
    for marker in (
        EXPECTED_BUILD_ID.encode("ascii"),
        b"AI_AWAITING_RESULT",
        b"AI_RESULT_ACK",
    ):
        if marker not in elf_bytes:
            raise ValueError("EXPECTED_RF30_FIRMWARE_MARKER_MISSING")
    if b"standalone-svm30-bench-20261111" in elf_bytes:
        raise ValueError("WRONG_STANDALONE_FIRMWARE")

    region = validate_pi_rf30_ihex(image)
    image_digest = digest(image)
    BASE.mkdir(parents=True, exist_ok=True)
    bundle.mkdir(exist_ok=False)
    destination = bundle / "rf30_pi_return_candidate.hex"
    shutil.copyfile(image, destination)
    if digest(destination) != image_digest:
        raise RuntimeError("BUNDLE_COPY_SHA_MISMATCH")
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(),
        "status": "CANDIDATE_ONLY_NO_NEW_PCB_BACKUP_NO_FLASH",
        "purpose": "RF500 Pi-return on a different, currently unidentified ATmega2560 PCB",
        "profile": "rf30_return_bench",
        "firmware_build_id": EXPECTED_BUILD_ID,
        "firmware_sha256": image_digest,
        "flash_region": region,
        "model_expected_sha256_on_pi": EXPECTED_MODEL_SHA,
        "new_pcb_firmware_identified": False,
        "new_pcb_flash_backup_verified": False,
        "new_pcb_eeprom_backup_verified": False,
        "new_pcb_bootloader_verified": False,
        "new_pcb_wiring_and_power_verified": False,
        "old_com5_svm30_image_suitable_as_rollback": False,
        "firmware_uploaded": False,
        "serial_opened": False,
        "eeprom_written": False,
        "requires_physical_sop_and_specific_upload_approval": True,
    }
    (bundle / "image_manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf8")
    return manifest


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle-name", default="20261112_rf30_bootguard_v1")
    result = prepare(parser.parse_args().bundle_name)
    print("SECOND_PCB_CANDIDATE_PREPARED", json.dumps(result, ensure_ascii=True))
