#!/usr/bin/env python3
"""COM11 profile checks; strict USB identity test without opening COM."""
from __future__ import annotations

import configparser
from contextlib import redirect_stdout
from io import StringIO
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
import json

from usb_autodetect import choose_port
import check_usb_receiver

ROOT = Path(__file__).resolve().parents[1]


def run() -> None:
    cfg = configparser.ConfigParser()
    cfg.read(ROOT / "platformio.ini", encoding="utf8")
    for env in ("env:mega2560", "env:nextion_test"):
        assert cfg[env]["upload_port"].upper() == "COM11", env
        assert cfg[env]["monitor_port"].upper() == "COM11", env
        assert int(cfg[env]["monitor_speed"]) == 115200

    ports = [
        SimpleNamespace(device="COM11", description="USB Serial Port",
                        vid=0x0403, pid=0x6001, serial_number="A10KNJBLA"),
        SimpleNamespace(device="COM5", description="OLD PCB",
                        vid=0x0403, pid=0x6001, serial_number="A10KMM3SA"),
    ]
    def discover(*, serial_number=None):
        return choose_port(ports, serial_number=serial_number)

    for port, serial, expected_status, expected_rc in [
        ("COM11", "A10KNJBLA", "PASS_USB_BRIDGE_ONLY", 0),
        ("COM5", "A10KNJBLA", "TARGET_PORT_OR_USB_SERIAL_MISMATCH", 2),
        ("COM11", "A10KMM3SA", "TARGET_PORT_OR_USB_SERIAL_MISMATCH", 2),
        ("COM11", "UNKNOWN", "TARGET_PORT_OR_USB_SERIAL_MISMATCH", 2),
    ]:
        output = StringIO()
        with patch.object(check_usb_receiver.list_ports, "comports", return_value=ports), \
             patch.object(check_usb_receiver, "discover_port", side_effect=discover), \
             redirect_stdout(output):
            rc = check_usb_receiver.main([
                "--expect-port", port, "--usb-serial", serial])
        result = json.loads(output.getvalue())
        assert (result["status"], rc) == (expected_status, expected_rc)
        assert result["serial_port_opened"] is False
        assert result["mcu_bootloader_verified"] is False

    legacy = (ROOT / "scripts/svm30_b6_readonly_backup.py").read_text(encoding="utf8")
    assert 'FTDI_SERIAL = "A10KMM3SA"' in legacy
    assert 'COM5' in legacy

    installer = (ROOT / "windows_receiver/install_autostart.ps1").read_text(encoding="utf8")
    assert "$UsbSerial" in installer and "$SkipLaunch" in installer
    legacy_installer = (ROOT / "scripts/install_lcd_autosave.ps1").read_text(encoding="utf8")
    assert "A10KNJBLA" in legacy_installer and "--usb-serial" in legacy_installer
    print("ACTIVE_COM11_USB_IDENTITY_AND_PLATFORMIO_CONFIG_QA_PASS")


if __name__ == "__main__":
    run()
