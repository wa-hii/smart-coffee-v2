#!/usr/bin/env python3
"""No-hardware tests for RF500 Pi staging readiness and fail-closed gates."""
from __future__ import annotations

import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import pi_rf30_pi5_readiness as target


def main() -> None:
    with TemporaryDirectory() as temp:
        root = Path(temp)
        stage = root / "rf30_staging"
        stage.mkdir()
        usb = root / "dev/serial/by-id"
        usb.mkdir(parents=True)
        for name in ("roast_rf30_pi_inference.py",
                     "roast_rf30_pi_stream_replay.py",
                     "rf30_pi_result_bridge.py"):
            (stage / name).write_text("# staging test\n", encoding="utf8")
        model = stage / "final_model.joblib"
        model.write_bytes(b"fake_model")
        (stage / "final_model_info.json").write_text(json.dumps({
            "model": "RandomForestClassifier",
            "n_estimators": 500,
            "features": target.FEATURES,
            "classes": ["dark", "light", "medium"],
        }), encoding="utf8")
        with patch.object(target, "MODEL_SHA", target.hashlib.sha256(b"fake_model").hexdigest()), \
             patch.object(target.metadata, "version",
                          side_effect=lambda x: {"scikit-learn": "1.7.2",
                                                 "numpy": "2.5.4",
                                                 "joblib": "1.6.0",
                                                 "pyserial": "3.5"}[x]):
            missing = target.check(stage, usb, target.ORIGINAL_PI_FTDI_SERIAL)
            assert "EXPECTED_PI_FTDI_BY_ID_NOT_CONNECTED" in missing["blockers"]
            assert not missing["live_activation_allowed"]
            fake = root / "dev/ttyUSB0"
            fake.write_bytes(b"")
            link = usb / (
                "usb-FTDI_FT232R_USB_UART_" +
                target.ORIGINAL_PI_FTDI_SERIAL + "-if00-port0")
            link.symlink_to(fake)
            ready = target.check(stage, usb, target.ORIGINAL_PI_FTDI_SERIAL)
            assert ready["status"] == "HOST_STAGED_NOT_MCU_VERIFIED"
            assert not ready["blockers"]
            assert not ready["live_activation_allowed"]
            (stage / "final_model_info.json").write_text("{}", encoding="utf8")
            bad = target.check(stage, usb, target.ORIGINAL_PI_FTDI_SERIAL)
            assert "RF_MODEL_METADATA_INCOMPATIBLE" in bad["blockers"]
    print("PI_RF30_READINESS_FAIL_CLOSED_TEST_PASS")


if __name__ == "__main__":
    main()
