#!/usr/bin/env python3
"""Offline QA COM6 programmer / COM11 target identity and fail-closed gates."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import com6_mega_isp_preflight as pre
import com6_isp_target_signature as target


def port(device, vid, pid, serial=None):
    return SimpleNamespace(device=device, vid=vid, pid=pid,
                           serial_number=serial)


def must_fail(fn, error_type):
    try:
        fn()
    except error_type:
        return
    raise AssertionError(f"EXPECTED_FAIL_CLOSED_{error_type.__name__}")


def run():
    good = [port("COM6", 0x1A86, 0x7523),
            port("COM11", 0x0403, 0x6001, "A10KNJBLA")]
    with patch.object(pre.list_ports, "comports", return_value=good):
        identity = pre.check()
        assert identity["programmer_port"] == "COM6"
        assert identity["target_port"] == "COM11"
        assert not identity["programmer_sketch_uploaded"]
        assert identity["target_usb_attached"]
    with patch.object(pre.list_ports, "comports", return_value=[good[0]]):
        no_target = pre.check(require_target_usb=False)
        assert no_target["target_usb_attached"] is False
        must_fail(pre.check, RuntimeError)
    swapped = [port("COM11", 0x1A86, 0x7523),
               port("COM6", 0x0403, 0x6001, "A10KNJBLA")]
    with patch.object(pre.list_ports, "comports", return_value=swapped):
        must_fail(pre.check, RuntimeError)
    must_fail(lambda: target.execute(arduinoisp_installed=False,
                                    wiring_verified=True, receiver_stopped=True),
              PermissionError)
    must_fail(lambda: target.execute(arduinoisp_installed=True,
                                    wiring_verified=False, receiver_stopped=True),
              PermissionError)
    must_fail(lambda: target.execute(arduinoisp_installed=True,
                                    wiring_verified=True, receiver_stopped=False),
              PermissionError)
    with patch.object(target, "target_receiver_active", return_value=True):
        must_fail(lambda: target.execute(arduinoisp_installed=True,
                                        wiring_verified=True, receiver_stopped=True),
                  RuntimeError)
    with TemporaryDirectory() as folder:
        # Successful USB discovery does not prove actual SPI connection.
        with patch.object(pre.list_ports, "comports", return_value=good), \
             patch.object(target, "target_receiver_active", return_value=False), \
             patch.object(target, "OUT", Path(folder)), \
             patch.object(target.subprocess, "run", return_value=SimpleNamespace(
                 stdout="", stderr="avrdude: target not connected", returncode=1)):
            result = target.execute(arduinoisp_installed=True,
                                    wiring_verified=True, receiver_stopped=True)
            assert result["result"] == "TARGET_MCU_SIGNATURE_STOP"
            assert result["target_mcu_verified"] is False
            assert not result["target_flash_written"]
    config = (pre.ROOT / "scripts/platformio_com6_arduinoisp.ini").read_text(
        encoding="utf8")
    assert "upload_port = COM6" in config
    assert "upload_port = COM11" not in config
    assert '"stk500v1"' in (pre.ROOT / "scripts/com6_isp_target_signature.py").read_text(
        encoding="utf8")
    print("COM6_ARDUINOISP_AND_TARGET_PROTECTION_QA_PASS")


if __name__ == "__main__":
    run()
