#!/usr/bin/env python3
"""Offline safety test for candidate images of an unverified second PCB."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import prepare_rf30_second_pcb_candidate as candidate


def run() -> None:
    for invalid in ("", "../escape", "20261112", "20261112_../escape"):
        try:
            candidate.prepare(invalid)
        except ValueError as e:
            assert "INVALID_BUNDLE_NAME" in str(e), str(e)
        else:
            raise AssertionError("unsafe bundle name accepted")

    # Test with temporary compiler fixtures, not with untracked/private
    # artifacts. This must work on a clean repository checkout too.
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        build = root / "build"
        build.mkdir()
        (build / "firmware.elf").write_bytes(
            candidate.EXPECTED_BUILD_ID.encode("ascii") +
            b"AI_AWAITING_RESULT AI_RESULT_ACK")
        (build / "firmware.hex").write_bytes(b":00000001FF\n")
        memory = {
            "flash_payload_bytes": 35770,
            "highest_address": 35769,
            "application_limit_bytes": 253952,
        }
        with (
            patch.object(candidate, "BASE", root / "private"),
            patch.object(candidate, "BUILD", build),
            patch.object(candidate, "validate_pi_rf30_ihex", return_value=memory),
        ):
            report = candidate.prepare("20261112_test_bundle")
            path = candidate.BASE / "20261112_test_bundle"
            assert path.is_dir()
            image = path / "rf30_pi_return_candidate.hex"
            saved = json.loads((path / "image_manifest.json").read_text(
                encoding="utf8"))
            assert report == saved
            assert saved["firmware_sha256"] == candidate.digest(image)
            assert saved["flash_region"] == memory
            assert saved["new_pcb_flash_backup_verified"] is False
            assert saved["new_pcb_eeprom_backup_verified"] is False
            assert saved["old_com5_svm30_image_suitable_as_rollback"] is False
            assert saved["firmware_uploaded"] is False
            assert saved["serial_opened"] is False
            assert saved["eeprom_written"] is False
            assert saved["requires_physical_sop_and_specific_upload_approval"]
            try:
                candidate.prepare(path.name)
            except FileExistsError as e:
                assert "REFUSE_OVERWRITE" in str(e)
            else:
                raise AssertionError("overwriting the existing image was allowed")
    print("SECOND_PCB_RF30_CANDIDATE_OFFLINE_SAFETY_QA_PASS")


if __name__ == "__main__":
    run()
