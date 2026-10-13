"""Passive Pi5/FT232R identity gate. NO SERIAL OPEN, output is NOT hardware E2E.

Only reads udev metadata, a device symlink, file metadata and Pi throttle
status. fuser is a read-only, limited-visibility owner check. No sudo, USB
control transfers, pyserial, serial.read, GPIO, firmware flash or actuation.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import subprocess
import sys

EXPECTED_SERIAL = "A10KMM3S"
EXPECTED_USB_ID = ("0403", "6001")
BY_ID = Path("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMM3S-if00-port0")
RAW = (Path(__file__).resolve().parents[1] / "data/raw").resolve()


def run_readonly(argv: list[str]) -> tuple[int | None, str]:
    try:
        proc = subprocess.run(argv, capture_output=True, text=True,
                              timeout=3, check=False)
    except (FileNotFoundError, OSError, subprocess.TimeoutExpired):
        return None, ""
    return proc.returncode, proc.stdout.strip()


def assess(data: dict) -> str:
    if data.get("platform") != "linux":
        return "UNSUPPORTED_HOST_NOT_TESTED"
    if (not data.get("port_is_character_device") or
            data.get("by_id_target") != "/dev/ttyUSB0" or
            data.get("udev_identity") != {
                "ID_SERIAL_SHORT": EXPECTED_SERIAL,
                "ID_VENDOR_ID": EXPECTED_USB_ID[0],
                "ID_MODEL_ID": EXPECTED_USB_ID[1],
                "ID_USB_DRIVER": "ftdi_sio",
            } or data.get("port_owner") != "NO_VISIBLE_OWNER" or
            data.get("throttled") != "throttled=0x0"):
        return "BLOCKED_PASSIVE_READINESS_CHECK"
    return "PASS_PASSIVE_IDENTITY_ONLY_HARDWARE_E2E_NOT_TESTED"


def inspect() -> dict:
    data = {
        "type": "stage9_ft232r_passive_readiness.v1",
        "platform": "linux" if sys.platform.startswith("linux") else sys.platform,
        "expected_serial": EXPECTED_SERIAL,
        "expected_usb_vid_pid": "0403:6001",
        "port_is_character_device": False,
        "by_id_target": None,
        "udev_identity": {},
        "port_owner": "NOT_CHECKED",
        "throttled": "NOT_CHECKED",
        "checks_only": "sysfs_udev_fuser_vcgencmd_no_usb_port_open",
        "physical_power_backfeed_tested": False,
        "mcu_binary_version_verified": False,
        "gpio_uart_wiring_verified": False,
        "nextion_live_command_verified": False,
        "five_cycle_actuation_verified": False,
        "g3_live_release_allowed": False,
        "model_promotion_allowed": False,
    }
    if data["platform"] != "linux":
        data["status"] = assess(data)
        return data
    port = Path("/dev/ttyUSB0")
    data["port_is_character_device"] = port.is_char_device()
    if BY_ID.is_symlink():
        data["by_id_target"] = str(BY_ID.resolve())
    code, output = run_readonly([
        "udevadm", "info", "-q", "property", "-n", str(port),
    ])
    if code == 0:
        props = dict(line.split("=", 1) for line in output.splitlines()
                     if "=" in line)
        data["udev_identity"] = {
            key: props.get(key, "NOT_FOUND") for key in
            ("ID_SERIAL_SHORT", "ID_VENDOR_ID", "ID_MODEL_ID",
             "ID_USB_DRIVER")
        }
    code, _ = run_readonly(["fuser", str(port)])
    data["port_owner"] = (
        "NO_VISIBLE_OWNER" if code == 1 else
        "OCCUPIED" if code == 0 else "UNKNOWN"
    )
    code, throttle = run_readonly(["vcgencmd", "get_throttled"])
    data["throttled"] = throttle if code == 0 else "UNAVAILABLE"
    data["status"] = assess(data)
    return data


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("passive_evidence_exists")
    out = args.output.resolve()
    if out == RAW or RAW in out.parents:
        raise ValueError("cannot_write_into_data_raw")
    result = inspect()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as dest:
        json.dump(result, dest, indent=2, ensure_ascii=False)
        dest.write("\n")
    print(result["status"])
    # Pass only passive identity checks, never a physical Stage9 gate.
    return 0 if result["status"].startswith("PASS_PASSIVE_") else 2


if __name__ == "__main__":
    raise SystemExit(main())
