"""Read-only GPIO-UART/FTDI topology inventory for Raspberry Pi 5.

This does NOT prove a physical UART connection to ATmega2560:
TTL voltage, wiring and ATmega USART ownership require a human check.
No UART/USB port open, no GPIO config writes, no privilege escalation.
"""

from __future__ import annotations

import glob
import json
from pathlib import Path
import re
import shutil
import subprocess


def read_text(path: str) -> str | None:
    try:
        return Path(path).read_text(encoding="utf-8", errors="replace")
    except (OSError, UnicodeError):
        return None


def inspect_pin(pin: int) -> str:
    """Invoke pinctrl get N only; never invoke set or configuration commands."""
    if shutil.which("pinctrl") is None:
        return "pinctrl_not_available"
    try:
        result = subprocess.run(
            ["pinctrl", "get", str(pin)], text=True, capture_output=True,
            timeout=3, check=False,
        )
        return result.stdout.strip() if result.returncode == 0 else "read_failed"
    except (OSError, subprocess.TimeoutExpired):
        return "read_failed"


def config_uart_lines(config: str | None) -> list[str]:
    if config is None:
        return []
    return [
        line.strip() for line in config.splitlines()
        if re.match(r"^\s*(?:dtoverlay=uart[\w-]*|dtparam=uart[\w-]*=)", line)
        and not line.lstrip().startswith("#")
    ]


def inspect() -> dict:
    symlinks = {}
    for name in ("/dev/serial0", "/dev/serial1"):
        link = Path(name)
        if link.is_symlink():
            symlinks[name] = str(link.readlink())
    by_id = []
    for value in sorted(glob.glob("/dev/serial/by-id/*")):
        item = Path(value)
        if item.is_symlink():
            by_id.append({"path": value, "target": str(item.readlink())})
    enumerated = [
        port for prefix in ("/dev/ttyAMA*", "/dev/ttyUSB*", "/dev/ttyACM*")
        for port in sorted(glob.glob(prefix))
    ]
    cmdline = read_text("/proc/cmdline") or ""
    console_tokens = [
        tok for tok in cmdline.split()
        if tok.startswith("console=") or tok == "plymouth.ignore-serial-consoles"
    ]
    return {
        "type": "stage7_uart_topology_readonly.v1",
        "device_paths_enumerated_not_opened": enumerated,
        "serial_symlinks": symlinks,
        "usb_serial_by_id": by_id,
        "gpio14_function_readonly": inspect_pin(14),
        "gpio15_function_readonly": inspect_pin(15),
        "uart_boot_config_readonly": config_uart_lines(
            read_text("/boot/firmware/config.txt")
        ),
        "console_arguments": console_tokens,
        "candidate_routes_are_not_proof_of_atmega_link": True,
        "requires_ttl_voltage_and_physical_pinout_confirmation": True,
        "needs_explicit_permission_before_port_open": True,
        "atmega_firmware_serial1_bridge_implemented": False,
        "hardware_uart_payload_validated": False,
        "action": "read_only_no_serial_open_no_gpio_write",
    }


if __name__ == "__main__":
    print(json.dumps(inspect(), ensure_ascii=False, indent=2))
