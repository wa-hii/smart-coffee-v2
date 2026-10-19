"""One passive Windows laptop receiver for three independent E-Nose instruments.

No serial connection is opened unless --start is explicitly supplied.
Each instrument uses a child process, independent CSV/baseline/log/status,
and is pinned by USB serial number when the bridge exposes one.
"""
from __future__ import annotations

import argparse
from dataclasses import dataclass
import multiprocessing
import os
from pathlib import Path
import signal
import subprocess
import sys
import threading
import time

from serial.tools import list_ports

import lcd_acquisition_service as app
from usb_autodetect import SUPPORTED_USB_IDS


@dataclass(frozen=True)
class Device:
    label: str
    initial_port: str
    usb_serial: str | None
    hwid: str


def legacy_receiver_pids() -> list[int]:
    """Read-only detection of old direct receivers that ignore the v4 mutex."""
    if os.name != 'nt':
        return []
    command = ('$ErrorActionPreference="Stop"; '
               'Get-CimInstance Win32_Process | Where-Object { '
               '($_.Name -eq "python.exe" -or $_.Name -eq "pythonw.exe") '
               '-and $_.CommandLine -like "*lcd_acquisition_service.py*" '
               '} | ForEach-Object { $_.ProcessId }')
    done = subprocess.run(['powershell', '-NoProfile', '-Command', command],
                          capture_output=True, text=True, timeout=20,
                          check=False)
    if done.returncode:
        raise RuntimeError('Cannot inspect existing listeners safely: ' +
                           done.stderr.strip())
    return [int(x.strip()) for x in done.stdout.splitlines() if x.strip()]


def validate_ports(port_names: list[str], devices: list | None = None) -> list[Device]:
    """Fail closed on missing COM, USB adapter mismatch, or duplicate identity."""
    import re

    if not 1 <= len(port_names) <= 3:
        raise ValueError('Select between 1 and 3 devices')
    requested = [p.upper() for p in port_names]
    if any(not re.fullmatch(r'COM[1-9][0-9]*', p) for p in requested):
        raise ValueError('Use Windows COM names, e.g. COM5 COM6 COM7')
    if len(set(requested)) != len(requested):
        raise ValueError('Each device needs a DISTINCT COM port')
    available = {p.device.upper(): p for p in (list_ports.comports() if devices is None else devices)}
    found = []
    serials = set()
    for index, port in enumerate(requested, start=1):
        dev = available.get(port)
        if dev is None:
            raise ValueError(f'{port} not found on this laptop (read-only detection)')
        if (dev.vid, dev.pid) not in SUPPORTED_USB_IDS:
            raise ValueError(f'{port} does not have a supported E-Nose USB adapter')
        serial = str(dev.serial_number).strip() if dev.serial_number else None
        if serial:
            if serial.casefold() in serials:
                raise ValueError(f'Duplicate USB serial number {serial} for {port}')
            serials.add(serial.casefold())
        found.append(Device(f'ALAT_{index}', port, serial,
                            f'{dev.vid:04X}:{dev.pid:04X}'))
    return found


def receiver_worker(device: Device, stop_event, salvage_on_frame_error: bool = False) -> None:
    """Runs entirely in own process; never shares mutable app globals."""
    app.configure_device_storage(device.label)
    logger = app.configure_logging()
    # If a USB serial is available, follow THIS instrument after COM renumbering.
    # When absent, keep a fixed port and tell operator to verify after reconnect.
    port = 'auto' if device.usb_serial else device.initial_port
    service = app.AcquisitionService(port, 115200, 2.0, logger,
                                     usb_serial=device.usb_serial,
                                     salvage_on_frame_error=salvage_on_frame_error)

    def request_stop(*_args):
        service.request_stop()

    signal.signal(signal.SIGINT, request_stop)
    if hasattr(signal, 'SIGTERM'):
        signal.signal(signal.SIGTERM, request_stop)
    watcher = threading.Thread(target=lambda: (stop_event.wait(), request_stop()),
                               daemon=True)
    watcher.start()
    logger.info('MULTI DEVICE %s first_port=%s USB=%s RAW=%s',
                device.label, device.initial_port, device.usb_serial or 'unavailable', app.RAW_DIR)
    try:
        service.run()
    except Exception:
        logger.exception('MULTI worker fatal error')
        raise


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ports', nargs='+', default=['COM5', 'COM6', 'COM7'],
                        help='COM ports of the physically identified ALAT_1, ALAT_2, ALAT_3')
    parser.add_argument('--start', action='store_true',
                        help='Actually open all COMs (default: READ-ONLY preflight)')
    parser.add_argument('--salvage-on-frame-error', action='store_true',
                        help='Keep collecting after bad JSON/duplicate index; '
                             'publish only strictly verified 900-valid-row datasets. '
                             'Otherwise quarantine with quality JSON sidecar.')
    args = parser.parse_args(argv)
    try:
        devices = validate_ports(args.ports)
    except ValueError as exc:
        print(f'PREFLIGHT FAIL: {exc}', file=sys.stderr)
        return 2
    print('Read-only COM-to-instrument mapping:', flush=True)
    for device in devices:
        print(f'  {device.label} -> {device.initial_port} USB={device.usb_serial or "UNKNOWN"} '
              f'({device.hwid}) -> data/raw/devices/{device.label}/', flush=True)
        if not device.usb_serial:
            print(f'  WARNING: {device.initial_port} lacks serial ID: verify physical instrument '
                  'after every unplug/replug.', flush=True)
    if not args.start:
        print('PREFLIGHT PASS (no COM opened). Use --start when all instruments are IDLE.',
              flush=True)
        return 0

    try:
        conflicts = legacy_receiver_pids()
    except (RuntimeError, subprocess.TimeoutExpired) as exc:
        print(f'PREFLIGHT FAIL: {exc}', file=sys.stderr)
        return 2
    if conflicts:
        print('PREFLIGHT FAIL: existing single-device receivers detected '
              f'(PIDs {conflicts}). Do not launch competing listeners. '
              'When all devices are IDLE, close the old receivers and disable '
              'their autostart shortcuts first.', file=sys.stderr)
        return 2

    # A parent process holds the SAME lock and legacy V4 named mutex as the
    # single-device listener; children never acquire global singleton locks.
    # This prevents concurrent v4 single/multi instances, even from other
    # installation roots. Older v3 listeners cannot participate in the mutex.
    root_lock = None
    host_lock = None
    workers = []
    ctx = multiprocessing.get_context('spawn')
    stop = ctx.Event()
    try:
        root_lock = app.acquire_process_lock()
        host_lock = app.acquire_host_instance_lock()
        for dev in devices:
            process = ctx.Process(target=receiver_worker,
                                  args=(dev, stop, args.salvage_on_frame_error),
                                  name=f'ENose-{dev.label}')
            process.start()
            workers.append(process)
        print('Receivers started. Wait for every status=connected BEFORE Take Data.', flush=True)
        if args.salvage_on_frame_error:
            print('SALVAGE MODE: bad frames will NOT abort 30 cycles; files with '
                  'fewer than 900 valid rows are INCOMPLETE, not training-ready.',
                  flush=True)
        print('Status per instrument: logs/devices/ALAT_N/acquisition_service.status.json',
              flush=True)
        print('Keep this terminal open throughout acquisition. Ctrl+C only when IDLE.',
              flush=True)
        reported = set()
        while any(p.is_alive() for p in workers):
            for p in workers:
                if not p.is_alive() and p.name not in reported:
                    print(f'WARNING: {p.name} stopped (exit code {p.exitcode}); '
                          'inspect this device log; other devices continue.',
                          file=sys.stderr, flush=True)
                    reported.add(p.name)
            time.sleep(1)
        return 1 if any(p.exitcode != 0 for p in workers) else 0
    except KeyboardInterrupt:
        print('STOP requested. Preserve partial acquisitions; closing receivers...',flush=True)
        return 130
    except (RuntimeError, OSError) as exc:
        print(f'RECEIVER CONFLICT: {exc}', file=sys.stderr)
        print('Another receiver may be active. Do NOT force-stop during Take Data.',
              file=sys.stderr)
        return 2
    finally:
        stop.set()
        for p in workers:
            p.join(timeout=15)
            if p.is_alive():
                print(f'WARNING: {p.name} did not exit; do not restart it over an active COM.',
                      file=sys.stderr)
        app.release_host_instance_lock(host_lock)
        if root_lock is not None:
            root_lock.close()


if __name__ == '__main__':
    multiprocessing.freeze_support()
    raise SystemExit(main())
