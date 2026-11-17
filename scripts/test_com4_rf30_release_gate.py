#!/usr/bin/env python3
"""Offline negative tests for strict COM4 RF30 release gate; never opens serial."""
from unittest.mock import patch

import com4_rf30_release_from_verified_backup as release


def require_runtime_error(action, label):
    try:
        action()
    except RuntimeError:
        return
    raise AssertionError(f"EXPECTED_STOP_{label}")


def run():
    good = {
        "port": "COM4", "ftdi_serial": "A10KMZQJA",
        "upload_requested": True, "candidate_sha256": release.EXPECTED_HEX_SHA,
    }
    wrong_port = {**good, "port": "COM11"}
    wrong_serial = {**good, "ftdi_serial": "A10KNJBLA"}
    with patch.object(release, "check_preflight", return_value=wrong_port):
        require_runtime_error(release.check_release, "COM11_PORT_NOT_COM4")
    with patch.object(release, "check_preflight", return_value=wrong_serial):
        require_runtime_error(release.check_release, "FTDI_SERIAL_MISMATCH")
    with patch.object(release, "check_preflight", return_value=good), \
         patch.object(release, "digest", return_value="0" * 64):
        require_runtime_error(release.check_release, "CANDIDATE_HASH_NOT_PINNED")
    assert release.EXPECTED_FLASH_SHA != release.EXPECTED_EEPROM_SHA
    assert release.EXPECTED_SIGNATURE == "0x1e9801"
    print("COM4_RF30_RELEASE_WRONG_PORT_SERIAL_IMAGE_FAIL_CLOSED_PASS")


if __name__ == "__main__":
    run()
