"""Read-only Raspberry Pi 5 host inventory, safe to run over SSH.

No serial access, sudo, pip installation, network scan, service restart,
GPIO manipulation, or writes. JSON stdout can be reviewed before deployment.

    ssh <user>@<pi-host> 'python3 -' < scripts/stage7_pi_preflight.py
"""

from __future__ import annotations

import glob
import json
import os
from pathlib import Path
import platform
import shutil
import subprocess
import sys


def inspect() -> dict:
    model_file = Path("/proc/device-tree/model")
    model = (model_file.read_bytes().rstrip(b"\x00").decode(
        "utf-8", errors="replace"
    ) if model_file.is_file() else "not_readable")
    ports = []
    for pattern in (
        "/dev/serial/by-id/*", "/dev/serial/by-path/*", "/dev/ttyACM*",
        "/dev/ttyUSB*",
    ):
        for name in sorted(glob.glob(pattern)):
            if name not in ports:
                ports.append(name)
    throttled = "not_available"
    if shutil.which("vcgencmd"):
        try:
            result = subprocess.run(
                ["vcgencmd", "get_throttled"],
                capture_output=True, text=True, timeout=2, check=False,
            )
            throttled = (
                result.stdout.strip() if result.returncode == 0 else "read_failed"
            )
        except (OSError, subprocess.TimeoutExpired):
            throttled = "read_failed"
    return {
        "type": "stage7_pi_read_only_preflight.v1",
        "platform": sys.platform,
        "kernel": platform.release(),
        "arch": platform.machine(),
        "python": platform.python_version(),
        "device_model": model,
        "serial_device_candidates_not_opened": ports,
        "vcgencmd_throttled_readonly": throttled,
        "model_ready": False,
        "host_bridge_running": False,
        "atmega_link_tested": False,
        "hardware_communication_verified": False,
        "pi5_model_claim_supported": "Raspberry Pi 5" in model,
        "actions": "read_only_no_serial_open_no_gpio_no_network_scan",
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), indent=2, ensure_ascii=False))
