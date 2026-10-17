"""Windows host preflight. Does NOT open USB/COM, drive hardware or flash MCU."""
from __future__ import annotations

import importlib
import os
from pathlib import Path
import platform
import sys
import tempfile

ROOT = Path(__file__).resolve().parents[1]


def run(root: Path = ROOT, *, check_packages: bool = True) -> list[str]:
    problems = []
    print('Smart Coffee E-Nose Receiver: startup diagnostic')
    print('OS:', platform.platform())
    print('Python:', sys.version.split()[0], sys.executable)
    print('Architecture:', platform.architecture()[0])
    print('Install folder:', root)
    if sys.version_info < (3, 10):
        problems.append('Python 3.10 or newer is required.')
    if sys.maxsize <= 2**32:
        problems.append('64-bit Python is required for prebuilt NumPy/Pandas packages.')
    if not (root / 'scripts/lcd_acquisition_service.py').is_file():
        problems.append('Incomplete ZIP extraction: receiver service file is missing.')
    if check_packages:
        for module in ('serial', 'numpy', 'pandas'):
            try:
                pkg = importlib.import_module(module)
                print('Dependency', module, getattr(pkg, '__version__', 'installed'))
            except Exception as exc:
                problems.append(f'Dependency {module} unavailable: {type(exc).__name__}: {exc}')
    # Check future CSV/log write permissions WITHOUT opening any serial port.
    for folder in (root / 'data/raw', root / 'data/baseline', root / 'logs'):
        try:
            folder.mkdir(parents=True, exist_ok=True)
            with tempfile.NamedTemporaryFile(dir=folder, prefix='.receiver_preflight_', delete=True):
                pass
            print('Folder writable:', folder)
        except OSError as exc:
            problems.append(f'Folder not writable: {folder}: {exc}')
    if check_packages:
        try:
            from serial.tools import list_ports
            from usb_autodetect import choose_port
            devices = list(list_ports.comports())
            for dev in devices:
                print(f'COM port: {dev.device} | {dev.description} | {dev.vid}:{dev.pid}')
            result = choose_port(devices)
            print('Auto port selection:', result.port or 'none', result.reason,
                  ', '.join(result.candidates))
            if result.reason == 'usb_ambiguous_use_port_or_usb_serial':
                print('NOTE: More than one supported USB adapter found; specify --port or --usb-serial.')
            elif result.reason == 'usb_not_found':
                print('NOTE: No supported USB adapter yet. Receiver can wait for USB after startup.')
        except Exception as exc:
            problems.append(f'COM discovery failed: {type(exc).__name__}: {exc}')
    if problems:
        print('\nPREFLIGHT FAILED:')
        for problem in problems:
            print('ERROR:', problem)
    else:
        print('\nPREFLIGHT PASS. This does not prove the 30-cycle hardware capture works.')
    return problems


if __name__ == '__main__':
    raise SystemExit(1 if run() else 0)
