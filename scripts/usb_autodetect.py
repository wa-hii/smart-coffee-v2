"""Read-only USB COM discovery for the Smart Coffee E-Nose collector.

Never sends commands or resets any device. An ambiguous match fails closed.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from serial.tools import list_ports

# USB bridges found on the custom E-Nose board and common Mega2560 boards.
# Match *both* vendor and product; never guess from arbitrary COM port numbers.
SUPPORTED_USB_IDS = frozenset({
    (0x0403, 0x6001),  # FTDI FT232R, custom PCB
    (0x2341, 0x0042),  # Arduino Mega2560 USB interface
    (0x2A03, 0x0042),  # Arduino.org Mega2560
    (0x1A86, 0x7523),  # CH340/CH341 bridge on some clones
    (0x10C4, 0xEA60),  # CP210x USB bridge
})


@dataclass(frozen=True)
class Discovery:
    port: str | None
    reason: str
    candidates: tuple[str, ...]


def choose_port(devices: Iterable, *, serial_number: str | None = None) -> Discovery:
    """Choose one known USB adapter; do not attach to unknown/ambiguous devices.

    With multiple E-Nose-like USB ports, operator must choose via --port or
    --usb-serial. A VID:PID alone is a transport hint, not firmware identity.
    """
    eligible = []
    for dev in devices:
        if (getattr(dev, 'vid', None), getattr(dev, 'pid', None)) not in SUPPORTED_USB_IDS:
            continue
        number = getattr(dev, 'serial_number', None)
        if serial_number is not None and str(number or '').casefold() != serial_number.casefold():
            continue
        port = str(getattr(dev, 'device', '') or '')
        if port:
            eligible.append(port)
    candidates = tuple(sorted(set(eligible), key=lambda x: (x.casefold(), x)))
    if not candidates:
        return Discovery(None, 'usb_not_found', candidates)
    if len(candidates) > 1:
        return Discovery(None, 'usb_ambiguous_use_port_or_usb_serial', candidates)
    return Discovery(candidates[0], 'usb_matched', candidates)


def discover_port(*, serial_number: str | None = None) -> Discovery:
    return choose_port(list_ports.comports(), serial_number=serial_number)
