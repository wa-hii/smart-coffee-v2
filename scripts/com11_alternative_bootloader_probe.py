#!/usr/bin/env python3
"""Bounded no-write alternate AVR bootloader profiles on onboard FT232RL COM11.

Exact USB identity and idle Windows receiver are mandatory. This script uses
only `-n -v`: no flash writes, chip erase, EEPROM writes or application TX
commands. Opening the port can still pulse physical RESET via DTR/RTS.
"""
from __future__ import annotations

from datetime import datetime, timezone
import json
from pathlib import Path
import subprocess

from com11_rf30_verified_deploy import (
    AVRDUDE, CONFIG, OUT_ROOT, check_preflight, EXPECTED_SIGNATURE)


# Other plausible bootloader variants after Mega2560 wiring/115200 already
# failed. Strictly read-only and bounded. Not an ISP configuration.
PROFILES = (("arduino", "115200"), ("wiring", "57600"))


def run(*, profiles=PROFILES, exec_fn=subprocess.run) -> dict:
    preflight = check_preflight(uploading=False)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out = OUT_ROOT / ("alternative_probe_" + datetime.now().strftime(
        "%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    results = []
    report = {"started_utc": datetime.now(timezone.utc).isoformat(),
              "ftdi_port": preflight["port"],
              "ftdi_serial": preflight["ftdi_serial"],
              "profiles": results,
              "upload_executed": False,
              "flash_written": False,
              "eeprom_written": False,
              "signature_verified": False,
              "status": "NO_RESPONSE_YET"}
    report_path = out / "probe_result.json"
    try:
        for programmer, baud in profiles:
            if (programmer, baud) not in PROFILES:
                raise ValueError("UNAPPROVED_BOOTLOADER_PROFILE")
            args = [str(AVRDUDE), "-C", str(CONFIG), "-p", "m2560",
                    "-c", programmer, "-P", "COM11", "-b", baud, "-n", "-v"]
            status = "FAILED"
            try:
                done = exec_fn(args, capture_output=True, text=True,
                               errors="replace", timeout=14)
                text = (done.stdout or "") + "\n" + (done.stderr or "")
                rc = done.returncode
            except subprocess.TimeoutExpired as e:
                text = ((e.stdout or b"").decode("utf8", "replace")
                        if isinstance(e.stdout, bytes) else (e.stdout or ""))
                text += "\n" + ((e.stderr or b"").decode("utf8", "replace")
                                 if isinstance(e.stderr, bytes) else (e.stderr or ""))
                rc = "TIMEOUT_KILLED"
            if rc == 0 and "Device signature = " + EXPECTED_SIGNATURE in text:
                status = "SIGNATURE_VERIFIED"
            (out / f"probe_{programmer}_{baud}.log").write_text(
                "args=" + json.dumps(args[1:]) + "\n"
                + "return_code=" + str(rc) + "\n" + text,
                encoding="utf8")
            results.append({"programmer": programmer, "baud": int(baud),
                            "status": status, "exit_code": rc})
            if status == "SIGNATURE_VERIFIED":
                report["signature_verified"] = True
                report["status"] = "PROGRAMMER_PROFILE_FOUND_READ_ONLY"
                break
        if not report["signature_verified"]:
            report["status"] = "NO_ALTERNATE_BOOTLOADER_SIGNATURE_NO_FLASH"
    finally:
        report_path.write_text(json.dumps(report, indent=2) + "\n",
                               encoding="utf8")
    print("COM11_ALTERNATE_PROBE", json.dumps(report, sort_keys=True))
    return report


if __name__ == "__main__":
    result = run()
    raise SystemExit(0 if result["signature_verified"] else 3)
