#!/usr/bin/env python3
"""Offline contract test for bounded RF30 boot and Nextion startup.

This is source-only QA: it never opens serial, resets an MCU or accesses I2C.
It cannot prove that an unknown physical PCB runs this firmware.
"""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = (ROOT / "src/main.cpp").read_text(encoding="utf8")
PROFILE = (ROOT / "scripts/platformio_rf30_bench.ini").read_text(encoding="utf8")


def run() -> None:
    setup = MAIN.split("void setup() {", 1)[1].split("\nvoid loop() {", 1)[0]
    assert "-DENABLE_PI_RF30_RETURN=1" in PROFILE
    assert "upload_port" not in PROFILE and "upload_protocol" not in PROFILE
    assert "nextion.begin(NEXTION_BAUD);" in setup
    assert "actuator.begin();" in setup
    assert (
        "#if SMART_COFFEE_STANDALONE_SVM30 || ENABLE_PI_RF30_RETURN\n"
        "  Wire.begin();\n"
        "  Wire.setWireTimeout(25000UL, true);\n"
        "#else\n"
        "  // Diagnostik: scan I2C bus terlebih dahulu\n"
        "  scanI2C();\n"
        "#endif"
    ) in setup
    assert setup.index("Wire.setWireTimeout(25000UL, true)") < (
        setup.index("sensors.begin()"))
    assert setup.index("actuator.begin();") < setup.index("sensors.begin()")
    assert setup.index("sensors.begin()") < setup.index("taskSerial.enable();")

    serial_callback = MAIN.split("void serialCallback() {", 1)[1].split(
        "\nvoid uiCallback() {", 1)[0]
    assert 'nextion.poll(handleNextionEvent);' in serial_callback
    assert 'showNextionPage("pHome");' in serial_callback
    assert "millis() - nextionBootMs >= 3000UL" in serial_callback
    assert "void restoreNextionPageAfterBoot()" in MAIN
    assert 'strcmp(event, "EVT:HMI_READY")' in MAIN
    print("RF30_BOUNDED_BOOT_NEXTION_SOURCE_CONTRACT_PASS")


if __name__ == "__main__":
    run()
