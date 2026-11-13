#!/usr/bin/env python3
"""QA jalur COM12 programmer vs COM11 target, tanpa membuka USB."""
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import hashlib

import com12_mega_isp_preflight as pre
import com12_mega_isp_target_signature as target
import fetch_com12_arduinoisp_official as vendor


def port(device, vid, pid, serial_number):
    return SimpleNamespace(device=device, vid=vid, pid=pid,
                           serial_number=serial_number)


def run():
    fake = [port("COM12", 0x1A86, 0x7523, None),
            port("COM11", 0x0403, 0x6001, "A10KNJBLA")]
    with patch.object(pre.list_ports, "comports", return_value=fake), \
         patch.object(Path, "is_file", return_value=True):
        good = pre.check()
        assert good["programmer_port"] == "COM12"
        assert good["target_port"] == "COM11"
        assert good["usb_devices_distinct"]
        assert good["target_ft232rl_usb_attached"]
    with patch.object(pre.list_ports, "comports", return_value=[
         port("COM12", 0x0403, 0x6001, "A10KNJBLA"),
         port("COM11", 0x1A86, 0x7523, None)]):
        try:
            pre.check()
        except RuntimeError:
            pass
        else:
            raise AssertionError("PORT_SWAPPED_MUST_FAIL")
    try:
        target.signature(False)
    except PermissionError:
        pass
    else:
        raise AssertionError("ISP_TARGET_PROBE_REQUIRES_OPERATOR_WIRING")
    cfg = (pre.ROOT / "scripts/platformio_com12_arduinoisp.ini").read_text()
    wrapper = (pre.ROOT / "diagnostics/com12_arduinoisp/src/main.cpp").read_text()
    assert "upload_port = COM12" in cfg and "upload_port = COM11" not in cfg
    assert "#if RESET != 10" in wrapper
    assert "ARDUINOISP_PIN_MISO != MISO" in wrapper
    assert "#if BAUDRATE != 19200" in wrapper
    assert vendor.DEST.is_file()
    assert hashlib.sha256(vendor.DEST.read_bytes()).hexdigest() == vendor.EXPECTED
    print("COM12_PROGRAMMER_COM11_TARGET_ISP_GUARDS_QA_PASS")


if __name__ == "__main__":
    run()
