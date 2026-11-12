#!/usr/bin/env python3
"""Read-only Pi 5 RF500 staging and USB readiness before restoring Pi mode.

No serial open, DTR reset, MCU write, joblib.load, systemd changes, or
actuators. Run with the isolated Pi RF30 virtualenv using SSH stdin.
"""
from __future__ import annotations

import argparse
import hashlib
from importlib import metadata
import json
from pathlib import Path
import platform

MODEL_SHA = "b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d"
FEATURES = ["tgs822_max_mean", "tgs822_purging_mean_mean", "mq8_max_mean"]
ORIGINAL_PI_FTDI_SERIAL = "A10KNJBL"
FW_BUILD_ID = "take30-ai30-rfhost-20261110"


def check(stage: Path, usb_by_id: Path, expected_serial: str) -> dict:
    problems: list[str] = []
    model_path = stage / "final_model.joblib"
    meta_path = stage / "final_model_info.json"
    model_hash = None
    if not model_path.is_file():
        problems.append("RF_MODEL_NOT_STAGED")
    else:
        model_hash = hashlib.sha256(model_path.read_bytes()).hexdigest()
        if model_hash != MODEL_SHA:
            problems.append("RF_MODEL_SHA_MISMATCH")
    try:
        model_meta = json.loads(meta_path.read_text(encoding="utf8"))
    except (ValueError, OSError):
        model_meta = {}
        problems.append("RF_MODEL_METADATA_MISSING")
    if model_meta != {} and not (
        model_meta.get("model") == "RandomForestClassifier"
        and model_meta.get("n_estimators") == 500
        and model_meta.get("features") == FEATURES
        and set(model_meta.get("classes", [])) == {"dark", "light", "medium"}
    ):
        problems.append("RF_MODEL_METADATA_INCOMPATIBLE")
    if not model_meta and "RF_MODEL_METADATA_MISSING" not in problems:
        problems.append("RF_MODEL_METADATA_INCOMPATIBLE")
    expected_files = (
        "roast_rf30_pi_inference.py",
        "roast_rf30_pi_stream_replay.py",
        "rf30_pi_result_bridge.py",
    )
    missing_modules = [name for name in expected_files if not (stage / name).is_file()]
    if missing_modules:
        problems.append("RF_PI_BRIDGE_NOT_STAGED")

    versions = {}
    for name in ("scikit-learn", "numpy", "joblib", "pyserial"):
        try:
            versions[name] = metadata.version(name)
        except metadata.PackageNotFoundError:
            versions[name] = "NOT_INSTALLED"
    if versions["scikit-learn"] != "1.7.2":
        problems.append("SKLEARN_VERSION_INCOMPATIBLE")
    if versions["pyserial"] != "3.5":
        problems.append("PYSERIAL_NOT_READY_IN_ISOLATED_VENV")

    candidates = []
    if usb_by_id.is_dir():
        for path in sorted(usb_by_id.iterdir()):
            if path.is_symlink() and path.name.startswith("usb-FTDI_FT232R_USB_UART_"):
                candidates.append({
                    "name": path.name,
                    "resolved_target": str(path.resolve()),
                    "connected": path.exists(),
                })
    matches = [
        p for p in candidates
        if expected_serial in p["name"] and p["connected"]
        and Path(p["resolved_target"]).name.startswith("ttyUSB")
    ]
    if len(matches) != 1:
        problems.append("EXPECTED_PI_FTDI_BY_ID_NOT_CONNECTED")
    return {
        "status": "HOST_READINESS_BLOCKED" if problems else "HOST_STAGED_NOT_MCU_VERIFIED",
        "host_arch": platform.machine(),
        "rf_model_sha256": model_hash,
        "rf_model_hash_verified": model_hash == MODEL_SHA,
        "rf_model_features": FEATURES,
        "rf_model_provenance_prospectively_validated": False,
        "python_packages": versions,
        "staging_modules_missing": missing_modules,
        "expected_ftdi_serial": expected_serial,
        "usb_ftdi_candidates": candidates,
        "usable_serial_by_id": matches[0]["name"] if len(matches) == 1 else None,
        "expected_firmware_build_id": FW_BUILD_ID,
        "mcu_firmware_build_id_verified": False,
        "hardware_serial_opened": False,
        "model_deserialized": False,
        "device_flashed": False,
        "pump_or_valve_touched": False,
        "live_activation_allowed": False,
        "blockers": problems,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--stage", type=Path,
                        default=Path.home() / "smart-coffee-stage7" / "rf30_staging")
    parser.add_argument("--usb-by-id", type=Path, default=Path("/dev/serial/by-id"))
    parser.add_argument("--expected-serial", default=ORIGINAL_PI_FTDI_SERIAL)
    args = parser.parse_args()
    result = check(args.stage, args.usb_by_id, args.expected_serial)
    print("RF30_PI_READINESS", json.dumps(result, ensure_ascii=True), flush=True)


if __name__ == "__main__":
    main()
