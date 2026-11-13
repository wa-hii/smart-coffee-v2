#!/usr/bin/env python3
"""Read-only target ATmega2560 signature via ArduinoISP on COM12.

TIDAK DIPAKAI sampai ArduinoISP ada pada COM12 dan kabel SPI+RESET
telah dicek langsung oleh operator. Pencocokan target via USB COM11
tidak mungkin dilakukan lewat ISP, sehingga validitas wiring wajib
dikonfirmasi secara fisik. Tanpa --wiring-verified program selalu STOP.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess
import sys

from com12_mega_isp_preflight import AVRDUDE, OUT, PROGRAMMER_PORT, check


def signature(wiring_verified: bool) -> dict:
    if not wiring_verified:
        raise PermissionError("WIRING_D10_RESET_D50_MISO_D51_MOSI_D52_SCK_GND_BELUM_DISAHKAN")
    base = check(require_target=False)
    OUT.mkdir(parents=True, exist_ok=True)
    path = OUT / ("target_signature_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    path.mkdir(exist_ok=False)
    args = [str(AVRDUDE), "-C", str(AVRDUDE.with_name("avrdude.conf")),
            "-p", "m2560", "-c", "stk500v1", "-P", PROGRAMMER_PORT,
            "-b", "19200", "-n", "-v"]
    try:
        p = subprocess.run(args, capture_output=True, text=True,
                           errors="replace", timeout=20)
        out = (p.stdout or "") + "\n" + (p.stderr or "")
        code = p.returncode
    except subprocess.TimeoutExpired as exc:
        stdout, stderr = exc.stdout or b"", exc.stderr or b""
        out = ((stdout.decode("utf8", "replace") if isinstance(stdout, bytes) else stdout)
               + "\n" + (stderr.decode("utf8", "replace")
                            if isinstance(stderr, bytes) else stderr))
        code = "TIMEOUT"
    base.update({
        "result": "TARGET_SIGNATURE_0x1e9801_VERIFIED"
                  if code == 0 and "device signature = 0x1e9801" in out.lower()
                  else "TARGET_SIGNATURE_NOT_VERIFIED_STOP",
        "wiring_verified_by_operator": True,
        "stk500v1_baud": 19200,
        "avrdude_exit": code,
        "output_dir": str(path),
        "target_signature_verified": code == 0 and "device signature = 0x1e9801" in out.lower(),
        "flash_written": False,
        "eeprom_written": False,
        "bootloader_written": False,
    })
    (path / "read_only_signature.log").write_text(
        "EXIT=" + str(code) + "\n" + out, encoding="utf8")
    (path / "result.json").write_text(
        json.dumps(base, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print("COM12_ISP_TARGET_READ_ONLY", json.dumps(base, ensure_ascii=False), flush=True)
    return base


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wiring-verified", action="store_true",
                        help="Operator memastikan jumper SPI/RESET dan catu target aman")
    a = parser.parse_args()
    try:
        result = signature(a.wiring_verified)
        sys.exit(0 if result["target_signature_verified"] else 3)
    except (RuntimeError, PermissionError) as exc:
        print("COM12_ISP_FAIL_CLOSED", str(exc), file=sys.stderr)
        sys.exit(2)
