#!/usr/bin/env python3
"""Pi-only read-only verification of paired persistent listener/bridge files.

Does not deserialize the joblib model or open UART/USB.
"""
from __future__ import annotations

import argparse
import hashlib
import inspect
import json
from pathlib import Path

import rf30_pi_result_bridge
from rf500_pi_persistent_listener import PORT, verify_bridge_compatibility, verify_host


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serial-live", type=Path, default=PORT)
    args = parser.parse_args()
    work = Path(__file__).resolve().parent
    # The exact same folder as the persistent listener MUST contain its bridge.
    verify_bridge_compatibility()
    if Path(rf30_pi_result_bridge.__file__).resolve().parent != work:
        raise RuntimeError("STALE_RF30_BRIDGE_IMPORT_NOT_ISOLATED")
    if "predictor" not in inspect.signature(
        rf30_pi_result_bridge.HostSession.feed).parameters:
        raise RuntimeError("PREDICTOR_PARAMETER_MISSING")
    base = Path.home() / "smart-coffee-stage7/rf30_staging"
    model = base / "final_model.joblib"
    metadata = base / "final_model_info.json"
    verify_host(args.serial_live, model, metadata)
    details = {
        "status": "PERSISTENT_BRIDGE_AND_MODEL_READ_ONLY_PREFLIGHT_PASS",
        "bridge_module": str(Path(rf30_pi_result_bridge.__file__).resolve()),
        "bridge_sha256": hashlib.sha256(
            (work / "rf30_pi_result_bridge.py").read_bytes()).hexdigest(),
        "model_sha256": hashlib.sha256(model.read_bytes()).hexdigest(),
        "api_predictor_param": True,
        "target_usb": str(args.serial_live),
        "serial_opened": False,
        "model_deserialized": False,
        "firmware_touched": False,
    }
    print("RF500_PI_BRIDGE_PREFLIGHT", json.dumps(details, sort_keys=True), flush=True)


if __name__ == "__main__":
    main()
