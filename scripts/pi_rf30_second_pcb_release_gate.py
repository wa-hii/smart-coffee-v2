#!/usr/bin/env python3
"""Read-only deployment gate for the SECOND custom ATmega2560 PCB.

This script never opens a serial port, runs AVRDUDE, flashes a chip, or starts
the RF500 bridge. It checks the real Pi staging, the selected FT232R identity,
and whether any VERIFIED original-board backup has been supplied.

No output of this gate is permission to flash: a same-session programmer
signature check and onsite SOP remain mandatory.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

STAGE = Path.home() / "smart-coffee-stage7" / "rf30_staging"
SECOND = STAGE / "second_pcb_20261112_bootguard_v1"
FTDI_ID = "A10KNJBL"
BY_ID = Path("/dev/serial/by-id") / (
    "usb-FTDI_FT232R_USB_UART_" + FTDI_ID + "-if00-port0")
MODEL_SHA = "b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d"
IMAGE_SHA = "26833b3cda23d65bae6b33b796331efa0f803071aa283e592ab6fffabeafebb6"
OLD_BOARD_BACKUP_MARKER = "b6_com5_readback"


def sha(path: Path) -> str | None:
    if not path.is_file() or path.is_symlink():
        return None
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def command(*argv: str) -> dict:
    try:
        res = subprocess.run(argv, capture_output=True, text=True,
                             errors="replace", timeout=5, check=False)
        return {"code": res.returncode, "stdout": res.stdout.strip()[:500]}
    except (OSError, subprocess.TimeoutExpired):
        return {"code": None, "stdout": ""}


def gate(stage: Path = STAGE, by_id: Path = BY_ID,
         device_root: Path = Path("/dev")) -> dict:
    second = stage / "second_pcb_20261112_bootguard_v1"
    candidate = second / "rf30_pi_return_candidate.hex"
    model = stage / "final_model.joblib"
    manifest_file = second / "image_manifest.json"
    errors = []

    image_sha = sha(candidate)
    model_sha = sha(model)
    if image_sha != IMAGE_SHA:
        errors.append("RF30_CANDIDATE_SHA_MISSING_OR_MISMATCH")
    if model_sha != MODEL_SHA:
        errors.append("RF500_MODEL_SHA_MISSING_OR_MISMATCH")

    try:
        manifest = json.loads(manifest_file.read_text(encoding="utf8"))
    except (OSError, ValueError):
        manifest = {}
    if (manifest.get("firmware_sha256") != IMAGE_SHA or
            manifest.get("new_pcb_flash_backup_verified") is not False or
            manifest.get("new_pcb_eeprom_backup_verified") is not False or
            manifest.get("firmware_uploaded") is not False):
        errors.append("SECOND_PCB_CANDIDATE_MANIFEST_INVALID")

    expected_port = device_root / "ttyUSB0"
    connected = by_id.is_symlink() and by_id.resolve() == expected_port
    if not connected:
        errors.append("EXPECTED_FT232R_NOT_CONNECTED")

    avrdude = second / "toolchain/extracted/usr/bin/avrdude"
    if not avrdude.is_file():
        errors.append("PI_AVRDUDE_STAGING_MISSING")

    # A different PCB requires independent Flash AND EEPROM readbacks.
    # A nearby old-board backup or a new .hex firmware candidate is not enough.
    backups = [
        p for p in second.glob("second_pcb_original_backup_*/backup_manifest.json")
        if OLD_BOARD_BACKUP_MARKER not in str(p)
    ]
    valid_backup = False
    for file in backups:
        try:
            item = json.loads(file.read_text(encoding="utf8"))
        except (OSError, ValueError):
            continue
        flash = file.parent / "flash_readback.hex"
        eeprom = file.parent / "eeprom_readback.hex"
        if (item.get("ftdi_serial") == FTDI_ID and
                item.get("device_signature") == "0x1e9801" and
                item.get("readback_verified") is True and
                item.get("flash_sha256") == sha(flash) and
                item.get("eeprom_sha256") == sha(eeprom) and
                sha(flash) is not None and sha(eeprom) is not None):
            valid_backup = True
            break
    if not valid_backup:
        errors.append("SECOND_PCB_FLASH_AND_EEPROM_BACKUP_NOT_VERIFIED")

    # USB presence is not MCU communication. A previously failed bootloader
    # test cannot be converted to an affirmative signature verification.
    errors.append("SAME_SESSION_MCU_PROGRAMMER_SIGNATURE_NOT_VERIFIED")

    power = command("vcgencmd", "get_throttled")
    if power.get("stdout") != "throttled=0x0":
        errors.append("PI_POWER_STATUS_NOT_CLEAN")
    owners = command("fuser", str(expected_port)) if connected else {
        "code": None, "stdout": ""}
    if owners.get("code") == 0:
        errors.append("SERIAL_PORT_IN_USE")

    return {
        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        "status": "NO_GO_PHYSICAL_DEPLOYMENT",
        "ftdi_serial_expected": FTDI_ID,
        "ftdi_attached_to_ttyUSB0": connected,
        "model_sha256_verified": model_sha == MODEL_SHA,
        "rf30_candidate_sha256_verified": image_sha == IMAGE_SHA,
        "pi_avrdude_locally_staged": avrdude.is_file(),
        "pi_get_throttled": power.get("stdout"),
        "second_pcb_original_backup_verified": valid_backup,
        "read_only": True,
        "serial_opened": False,
        "mcu_reset_attempted": False,
        "flash_or_eeprom_written": False,
        "bridge_started": False,
        "flash_allowed": False,
        "blockers": errors,
    }


if __name__ == "__main__":
    print("SECOND_PCB_RF30_GATE", json.dumps(gate(), sort_keys=True))
