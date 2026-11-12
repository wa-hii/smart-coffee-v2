#!/usr/bin/env python3
"""Mock-only test that the second-PCB deployment gate fails closed."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pi_rf30_second_pcb_release_gate as target


def run() -> None:
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        stage = root / "rf30_staging"
        second = stage / "second_pcb_20261112_bootguard_v1"
        second.mkdir(parents=True)
        (second / "toolchain/extracted/usr/bin").mkdir(parents=True)
        (second / "toolchain/extracted/usr/bin/avrdude").write_bytes(b"test")
        (stage / "final_model.joblib").write_bytes(b"model")
        (second / "rf30_pi_return_candidate.hex").write_bytes(b"firmware")
        (second / "image_manifest.json").write_text(json.dumps({
            "firmware_sha256": hashlib.sha256(b"firmware").hexdigest(),
            "new_pcb_flash_backup_verified": False,
            "new_pcb_eeprom_backup_verified": False,
            "firmware_uploaded": False,
        }), encoding="utf8")
        dev = root / "dev"
        dev.mkdir()
        (dev / "ttyUSB0").touch()
        byid = dev / "usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0"
        byid.symlink_to(dev / "ttyUSB0")
        with patch.object(target, "MODEL_SHA",
                          hashlib.sha256(b"model").hexdigest()), \
             patch.object(target, "IMAGE_SHA",
                          hashlib.sha256(b"firmware").hexdigest()), \
             patch.object(target, "command", return_value={
                 "code": 1, "stdout": "throttled=0x0"}):
            report = target.gate(stage, byid, dev)
            assert report["model_sha256_verified"]
            assert report["rf30_candidate_sha256_verified"]
            assert report["ftdi_attached_to_ttyUSB0"]
            assert report["pi_avrdude_locally_staged"]
            assert report["flash_allowed"] is False
            assert "SECOND_PCB_FLASH_AND_EEPROM_BACKUP_NOT_VERIFIED" in report[
                "blockers"]
            assert "SAME_SESSION_MCU_PROGRAMMER_SIGNATURE_NOT_VERIFIED" in report[
                "blockers"]
            assert report["serial_opened"] is False
            assert report["flash_or_eeprom_written"] is False
            assert report["bridge_started"] is False
    print("SECOND_PCB_RF30_FAIL_CLOSED_RELEASE_GATE_QA_PASS")


if __name__ == "__main__":
    run()
