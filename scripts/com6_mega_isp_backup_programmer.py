#!/usr/bin/env python3
"""Attempt read-only backup of Mega programmer COM6 before ArduinoISP overwrite.

Bootloader memory readbacks can be all FF or incomplete even on healthy
ATmega2560. Such results MUST NOT authorize overwriting its current sketch.
"""
from com6_mega_isp_preflight import PROGRAMMER_PORT, OUT, check
from com12_mega_isp_backup_programmer import backup


if __name__ == "__main__":
    result = backup(port=PROGRAMMER_PORT, output_root=OUT, preflight=check)
    raise SystemExit(0 if result["readback_verified"] else 3)
