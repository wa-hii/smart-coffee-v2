#!/usr/bin/env python3
"""Ambil contoh resmi ArduinoISP untuk build programmer MEGA COM12.

Source BSD Arduino Examples pinned SHA256, disimpan HANYA di private/
yang Git-ignore. Tidak ada upload, serial port, atau firmware write.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from urllib.request import urlopen

from com12_mega_isp_preflight import OUT, check

SOURCE = ("https://raw.githubusercontent.com/arduino/arduino-examples/"
          "main/examples/11.ArduinoISP/ArduinoISP/ArduinoISP.ino")
EXPECTED = "9d6318e03dce7c12825fed3abe82a6c8a6d16842d2b38d64b278c37844d011e2"
DEST = OUT / "vendor" / "ArduinoISP.ino"


def fetch() -> dict:
    check()
    if DEST.is_file():
        content = DEST.read_bytes()
    else:
        with urlopen(SOURCE, timeout=12) as f:
            content = f.read(30000)
    actual = hashlib.sha256(content).hexdigest()
    if actual != EXPECTED:
        raise RuntimeError("ARDUINOISP_UPSTREAM_HASH_MISMATCH_NO_BUILD")
    if (b"#define BAUDRATE 19200" not in content or
            b"#define RESET 10" not in content or
            b"#include \"SPI.h\"" not in content):
        raise RuntimeError("ARDUINOISP_SOURCE_SAFETY_CONTRACT_MISMATCH")
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if not DEST.exists():
        DEST.write_bytes(content)
    report = {"origin": SOURCE, "license": "BSD-3-Clause",
              "sha256": actual, "file": str(DEST),
              "compile_only": True, "COM12_upload": False,
              "COM11_touched": False}
    (DEST.parent / "source_manifest.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf8")
    print("ARDUINOISP_OFFICIAL_SOURCE_VERIFIED", json.dumps(report))
    return report


if __name__ == "__main__":
    fetch()
