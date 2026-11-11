#!/usr/bin/env python3
"""Non-invasive Windows B6 release gate for the standalone SVM30 ATmega.

This script NEVER opens COM, sends bytes, flashes firmware, sends DTR,
stops a receiver, touches actuators, or resets hardware. It inspects only
OS device enumeration, current receiver status, local release manifest and
presence of verified recovery snapshots.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_MODEL = "d71e74a037860b0c7d7da241c448dcda65a2b736c343577a62307baed3cb1e33"
EXPECTED_PORT = "COM5"
EXPECTED_FTDI = "A10KMM3SA"


def _read_json(path: Path) -> dict:
    try:
        content = json.loads(path.read_text(encoding="utf8"))
        return content if isinstance(content, dict) else {}
    except (OSError, ValueError):
        return {}


def _receiver_pid_alive(pid: object) -> bool:
    # Use Win32 process metadata, NOT serial port probing.
    if not isinstance(pid, int) or pid < 1:
        return False
    script = (
        f"Get-CimInstance Win32_Process -Filter 'ProcessId = {pid}' "
        "| Select-Object -ExpandProperty ProcessId"
    )
    try:
        result = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", script],
            capture_output=True, text=True, timeout=12, check=False,
        )
        return result.returncode == 0 and str(pid) in result.stdout.split()
    except (OSError, subprocess.TimeoutExpired):
        # Uncertain is never permission to seize a serial port.
        return True


def assess(snapshot: dict) -> list[str]:
    """Compute safety blockers; this is NOT an upload authorization."""
    blockers = []
    if snapshot.get("com5_matches_ftdi") is not True:
        blockers.append("COM5_IDENTITY_UNVERIFIED")
    if snapshot.get("receiver_owns_com5") is not False:
        blockers.append("COM5_RECEIVER_ACTIVE_OR_UNKNOWN")
    if snapshot.get("model_integrity") is not True:
        blockers.append("MODEL_HASH_UNVERIFIED")
    if snapshot.get("firmware_integrity") is not True:
        blockers.append("FIRMWARE_HASH_UNVERIFIED")
    if snapshot.get("physical_boot_to_phome_verified") is not True:
        blockers.append("NEXTION_BOOT_NOT_VERIFIED")
    if snapshot.get("flash_and_eeprom_backups_verified") is not True:
        blockers.append("NO_VERIFIED_FLASH_EEPROM_BACKUP")
    if snapshot.get("programmer_and_power_sop_verified") is not True:
        blockers.append("PROGRAMMER_POWER_SOP_NOT_VERIFIED")
    if snapshot.get("specific_upload_approval") is not True:
        blockers.append("SPECIFIC_UPLOAD_APPROVAL_MISSING")
    return blockers


def _validated_readback(directory: Path | None) -> tuple[bool, str]:
    if directory is None:
        return False, "NOT_PROVIDED"
    d = directory.resolve()
    if d.parent != (ROOT / "private" / "b6_com5_readback").resolve():
        return False, "INVALID_PRIVATE_BACKUP_LOCATION"
    try:
        from svm30_b6_verify_readback import verify
        result = verify(d)
        flash = result["files"]["flash_readback.hex"]
        eeprom = result["files"]["eeprom_readback.hex"]
        if (flash["address_coverage_bytes"] < 261406 or
                eeprom["address_coverage_bytes"] != 4096 or
                result["device_signature"] != "0x1e9801"):
            return False, "BACKUP_COVERAGE_INSUFFICIENT"
        if flash["unrepresented_suffix_bytes"]:
            return True, (
                "BACKUP_HASH_AND_IHEX_VALID_BUT_ERASED_SUFFIX_NOT_MEASURED:"
                + str(flash["unrepresented_suffix_bytes"])
            )
        return True, "BACKUP_HASH_AND_IHEX_FULLY_REPRESENTED"
    except (OSError, ValueError, KeyError, TypeError):
        return False, "BACKUP_OFFLINE_VERIFICATION_FAILED"


def inspect(*, operator_reported_phome: bool = False,
            verified_readback_dir: Path | None = None) -> dict:
    # Safe Windows enumeration does not call Serial(), open(), or avrdude.
    from serial.tools import list_ports

    ports = [
        dict(device=p.device, serial_number=p.serial_number,
             vid=p.vid, pid=p.pid, description=p.description)
        for p in list_ports.comports()
    ]
    port_matches = [p for p in ports if p["device"].upper() == EXPECTED_PORT]
    correct_port = (
        len(port_matches) == 1
        and port_matches[0]["serial_number"] == EXPECTED_FTDI
        and port_matches[0]["vid"] == 0x0403
        and port_matches[0]["pid"] == 0x6001
    )
    receiver = _read_json(ROOT / "logs/acquisition_service.status.json")
    pid_alive = _receiver_pid_alive(receiver.get("pid"))
    # Connected status may be stale; treat unconfirmed ownership as blocked.
    receiver_owns = (
        receiver.get("port", "").upper() == EXPECTED_PORT and
        receiver.get("state") in {"connected", "recording", "capturing"}
        and pid_alive
    )

    private = ROOT / "private"
    manifest = _read_json(private / "svm30_standalone_firmware_manifest.json")
    image = private / "svm30_standalone_firmware.hex"
    model = private / "embedded_svm30_model.h"
    model_ok = (
        model.is_file()
        and manifest.get("model_sha256") == EXPECTED_MODEL
        and manifest.get("model_features") == 30
        and manifest.get("model_support_vectors") == 125
    )
    image_ok = (
        image.is_file()
        and manifest.get("profile") == "svm30_standalone"
        and manifest.get("status") == "COMPILE_ONLY_NOT_FLASHED"
        and hashlib.sha256(image.read_bytes()).hexdigest()
            == manifest.get("firmware_hex_sha256")
    )
    backup_ok, backup_note = _validated_readback(verified_readback_dir)
    return dict(
        checked_at=datetime.now(timezone.utc).isoformat(),
        expected_device=EXPECTED_PORT,
        expected_ftdi=EXPECTED_FTDI,
        physical_port_identity=port_matches,
        com5_matches_ftdi=correct_port,
        receiver_status=receiver,
        receiver_pid_alive=pid_alive,
        receiver_owns_com5=receiver_owns if receiver else None,
        model_integrity=model_ok,
        firmware_integrity=image_ok,
        firmware_sha256=manifest.get("firmware_hex_sha256"),
        # Operator confirmation is a valid preliminary B0 observation,
        # NOT a serial/HMI bench measurement or a programming approval.
        physical_boot_to_phome_verified=operator_reported_phome,
        nextion_boot_evidence=(
            "OPERATOR_REPORTED_PHOME_NOT_INSTRUMENTED"
            if operator_reported_phome else "NOT_CONFIRMED"
        ),
        nextion_technical_bench_verified=False,
        flash_and_eeprom_backups_verified=backup_ok,
        readback_integrity_note=backup_note,
        backup_restore_tested=False,
        programmer_and_power_sop_verified=False,
        specific_upload_approval=False,
        port_opened=False,
        bytes_written_to_port=0,
        reset_triggered=False,
        firmware_flashed=False,
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, default=None)
    parser.add_argument(
        "--operator-reported-phome", action="store_true",
        help="Operator explicitly reports pHome. Does not authorize serial or flashing."
    )
    parser.add_argument(
        "--verified-readback-dir", type=Path, default=None,
        help="Check existing Flash/EEPROM backup offline; never opens COM5."
    )
    args = parser.parse_args()
    report = inspect(
        operator_reported_phome=args.operator_reported_phome,
        verified_readback_dir=args.verified_readback_dir)
    report["blockers"] = assess(report)
    report["decision"] = "NO_GO" if report["blockers"] else "REVIEW_REQUIRED"
    if args.output:
        if args.output.exists():
            raise FileExistsError("refuse_overwrite_existing_b6_snapshot")
        if (args.output.resolve().parent != (ROOT / "private").resolve()
                or args.output.suffix != ".json"):
            raise ValueError("only_private_json_reports_allowed")
        args.output.write_text(json.dumps(report, indent=2)+"\n", encoding="utf8")
    print("SVM30_B6_PASSIVE_PREFLIGHT", json.dumps({
        k: report[k] for k in (
            "decision", "com5_matches_ftdi", "receiver_owns_com5",
            "model_integrity", "firmware_integrity", "blockers",
            "nextion_boot_evidence", "readback_integrity_note",
            "port_opened", "firmware_flashed")
    }))
    return 0 if not report["blockers"] else 2


if __name__ == "__main__":
    raise SystemExit(main())
