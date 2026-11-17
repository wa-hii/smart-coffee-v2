#!/usr/bin/env python3
"""Flash pinned RF30 app to known FTDI COM4 after full-original recovery backup.

Must have exact pre-verified ATmega2560 identity, original full 256KiB Flash
plus 4KiB EEPROM backup from THIS device, a physically checked FF suffix
via separate terminal dump, and known prior COM4 E-Nose firmware provenance.
Never writes fuses, EEPROM or COM11. Does not start acquisition or actuators.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import sys

from com4_rf30_verified_deploy import check_preflight, PORT, FTDI_SERIAL
from com4_rf30_verify_binary_original import PARENT
from com11_rf30_verified_deploy import AVRDUDE, CONFIG, HEX, EXPECTED_HEX_SHA

EXPECTED_FLASH_SHA = "23bbe8db52de49136164a4ecdef9edfd61ca3dbe266e78fb19fee69955e43a89"
EXPECTED_EEPROM_SHA = "1591bf837dc368617fbc4f3460800b01255c1c34b2b3e1bbe72c2e8e06ce8e87"
EXPECTED_SIGNATURE = "0x1e9801"


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def check_release() -> dict:
    status = check_preflight(uploading=True)
    if (status["port"], status["ftdi_serial"]) != ("COM4", "A10KMZQJA"):
        raise RuntimeError("WRONG_TARGET_DEVICE")
    if digest(HEX) != EXPECTED_HEX_SHA:
        raise RuntimeError("CANDIDATE_IMAGE_CHANGED")
    manifests = list(PARENT.glob("terminal_suffix_*/backup_verified.json"))
    if len(manifests) != 1:
        raise RuntimeError("FULL_ORIGINAL_BACKUP_NOT_UNIQUE")
    manifest_path = manifests[0]
    manifest = json.loads(manifest_path.read_text(encoding="utf8"))
    if (manifest.get("status") != "RECOVERY_BACKUP_FULL_LOGICAL_FLASH_AND_EEPROM_VERIFIED"
            or manifest.get("target_port") != PORT
            or manifest.get("ftdi_serial") != FTDI_SERIAL
            or manifest.get("signature") != EXPECTED_SIGNATURE
            or manifest.get("terminal_suffix_physically_read_bytes") != 738
            or manifest.get("terminal_suffix_all_ff") is not True
            or manifest.get("first_hex_address_coverage") != 261406
            or manifest.get("second_binary_address_coverage") != 261406):
        raise RuntimeError("ORIGINAL_RECOVERY_MANIFEST_INCONSISTENT")
    flash = manifest_path.parent / "original_flash_262144_fully_checked.bin"
    eeprom = manifest_path.parent / "original_eeprom_4096_checked.bin"
    if (flash.stat().st_size != 262144 or digest(flash) != EXPECTED_FLASH_SHA
            or eeprom.stat().st_size != 4096 or digest(eeprom) != EXPECTED_EEPROM_SHA):
        raise RuntimeError("RECOVERY_BACKUP_HASH_OR_SIZE_MISMATCH")
    # COM4 is the previously documented E-Nose device with 12-page Nextion,
    # four ADS1115 and 10 sensors; compare source hardware contracts before
    # choosing RF30 application. This is NOT proof of identical PCB revision.
    history = (PARENT.parents[2] / "docs/reports/2026-10-17_NEXTION_TAKE12_COM4_FLASH_AND_EDITOR_SAVE_RECOVERY.md")
    # PARENT.parents[2] is repository root (PARENT: root/private/.../run)
    if not history.is_file() or FTDI_SERIAL not in history.read_text(encoding="utf8"):
        raise RuntimeError("KNOWN_COM4_ENOSE_PROVENANCE_MISSING")
    status.update({
        "original_recovery_flash_sha256": digest(flash),
        "original_recovery_eeprom_sha256": digest(eeprom),
        "physical_board_revision_independently_verified": False,
        "prior_com4_e_nose_firmware_history": True,
    })
    return status


def avr(out: Path, label: str, tail: list[str], timeout: int) -> tuple[bool, str]:
    cmd = [str(AVRDUDE), "-C", str(CONFIG), "-p", "m2560",
           "-c", "wiring", "-P", "COM4", "-b", "115200", *tail]
    (out / (label + ".args.json")).write_text(
        json.dumps(cmd[1:], indent=2) + "\n", encoding="utf8")
    try:
        p = subprocess.run(cmd, cwd=out, capture_output=True, text=True,
                           errors="replace", timeout=timeout)
        log = (p.stdout or "") + "\n" + (p.stderr or "")
        code = p.returncode
    except subprocess.TimeoutExpired as exc:
        so, se = exc.stdout or b"", exc.stderr or b""
        log = (so.decode("utf8", "replace") if isinstance(so, bytes) else so)
        log += "\n" + (se.decode("utf8", "replace") if isinstance(se, bytes) else se)
        code = "TIMEOUT"
    (out / (label + ".log")).write_text(
        "EXIT=" + str(code) + "\n" + log, encoding="utf8")
    return code == 0 and "device signature = " + EXPECTED_SIGNATURE in log.lower(), log


def run() -> int:
    pre = check_release()
    out = PARENT / ("rf30_release_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    status = {
        **pre,
        "started_utc": datetime.now(timezone.utc).isoformat(),
        "state": "PREFLIGHT_VALIDATED_BEFORE_NEW_SIGNATURE",
        "target_flash_written": False,
        "target_eeprom_written": False,
        "new_firmware_verified": False,
        "log_dir": str(out),
    }

    def save():
        (out / "release_result.json").write_text(
            json.dumps(status, indent=2, ensure_ascii=False) + "\n",
            encoding="utf8")
        print("COM4_RF30_RELEASE", json.dumps(status, sort_keys=True), flush=True)

    save()
    valid, log = avr(out, "01_signature", ["-n", "-v"], 20)
    if not valid:
        status["state"] = "SIGNATURE_FAILED_NO_WRITE"
        save()
        return 3
    status["state"] = "COM4_SIGNATURE_AND_RECOVERY_BACKUP_VERIFIED"
    save()
    # -D prevents extra chip erase; write application only, not EEPROM/fuses.
    valid, log = avr(out, "02_rf30_upload", ["-D", "-U", f"flash:w:{HEX}:i"], 180)
    if not valid:
        status["state"] = "UPLOAD_FAILED_PARTIAL_WRITE_POSSIBLE"
        status["target_flash_written"] = "UNKNOWN_PARTIAL_POSSIBLE"
        save()
        return 4
    status["target_flash_written"] = True
    status["state"] = "RF30_WRITE_DONE_VERIFY_PENDING"
    save()
    valid, log = avr(out, "03_rf30_verify", ["-n", "-U", f"flash:v:{HEX}:i"], 180)
    if not valid:
        status["state"] = "VERIFY_FAILED_DO_NOT_ASSUME_RELEASE_SUCCESS"
        save()
        return 5
    status["new_firmware_verified"] = True
    status["state"] = "RF30_APP_VERIFIED_ON_COM4_HMI_SENSOR_E2E_UNTESTED"
    save()
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(run())
    except (OSError, RuntimeError, ValueError) as exc:
        print("COM4_RF30_RELEASE_STOP", str(exc), file=sys.stderr)
        raise SystemExit(2)
