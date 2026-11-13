#!/usr/bin/env python3
"""Satu handshake NON-KONTROL #status; ke PCB kedua, dengan guard keselamatan.

Source yang ditinjau: src/main.cpp processCommand('#status') -> printWelcome().
Tidak ada perintah START/STOP/SCAN, update HMI, kalibrasi, aktuator, maupun flash.
Catatan: firmware PCB fisik belum dapat dibuktikan cocok dengan repo sehingga
hasil tidak boleh dianggap verifikasi keamanan image yang terpasang.
"""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import subprocess
import time
from serial import Serial

PORT_LINK = Path("/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KNJBL-if00-port0")
PORT_TARGET = Path("/dev/ttyUSB0")
BAUD = 115200
HANDSHAKE = b"#status;"
UNSAFE_MARKERS = (b"undervoltage", b"brownout", b"overheat", b"watchdog reset")


def shell(*cmd: str) -> subprocess.CompletedProcess:
    return subprocess.run(cmd, capture_output=True, text=True,
                          errors="replace", timeout=8, check=False)


def preflight() -> None:
    if not PORT_LINK.is_symlink() or PORT_LINK.resolve() != PORT_TARGET:
        raise RuntimeError("FT232R_USB_ID_TIDAK_COCOK")
    if shell("vcgencmd", "get_throttled").stdout.strip() != "throttled=0x0":
        raise RuntimeError("CATU_PI_BELUM_LOLOS_0x0")
    p = shell("fuser", str(PORT_TARGET))
    if p.returncode not in (1,):
        raise RuntimeError("PORT_DIPAKAI_ATAU_FUSER_GAGAL")


def kernel_usb() -> list[str]:
    p = shell("journalctl", "-k", "-b", "--no-pager", "-n", "200")
    if p.returncode:
        return []
    return [line for line in p.stdout.splitlines()
            if "usb 3-1:" in line or "ttyUSB0" in line]


def run(outdir: Path, read_seconds: int = 12) -> dict:
    if not 4 <= read_seconds <= 15:
        raise ValueError("HANDSHAKE_READ_TIME_INVALID")
    preflight()
    outdir.mkdir(parents=True, exist_ok=False)
    before_usb = kernel_usb()
    rx = bytearray()
    tx_count = 0
    started = time.monotonic()
    error = None
    status = "NOT_STARTED"
    uart = Serial()
    uart.port = str(PORT_LINK)
    uart.baudrate = BAUD
    uart.timeout = 0.3
    uart.write_timeout = 0.8
    uart.dtr = False
    uart.rts = False
    uart.xonxoff = False
    uart.rtscts = False
    uart.dsrdtr = False
    try:
        uart.open()
        # Guard: one exact, documented non-control status request ONLY.
        tx_count = uart.write(HANDSHAKE)
        if tx_count != len(HANDSHAKE):
            raise IOError("STATUS_REQUEST_INCOMPLETE")
        status = "DONE"
        while time.monotonic() - started < read_seconds:
            if not PORT_LINK.is_symlink() or PORT_LINK.resolve() != PORT_TARGET:
                status = "STOP_USB_DISCONNECT"
                break
            block = uart.read(256)
            if block:
                rx.extend(block)
                low = bytes(rx).lower()
                if any(marker in low for marker in UNSAFE_MARKERS):
                    status = "STOP_UNSAFE_SERIAL_LOG"
                    break
                if len(rx) >= 64_000:
                    status = "STOP_RX_LIMIT"
                    break
    except Exception as exc:
        status = "ERROR"
        error = f"{type(exc).__name__}: {str(exc)[:180]}"
    finally:
        if uart.is_open:
            uart.close()
    after_usb = kernel_usb()
    new_usb = [line for line in after_usb if line not in before_usb]
    if any("disconnect" in line.lower() for line in new_usb):
        status = "STOP_NEW_USB_DISCONNECT"
    result = {
        "time_utc": datetime.now(timezone.utc).isoformat(),
        "status": status,
        "usb_serial": "A10KNJBL",
        "baud": BAUD,
        "command": HANDSHAKE.decode("ascii"),
        "command_non_control_source": "src/main.cpp:1389-1411",
        "dtr_rts_false_before_open": True,
        "possible_transient_dtr_glitch": True,
        "command_transmitted_count": 1 if tx_count == len(HANDSHAKE) else 0,
        "uart_tx_bytes": tx_count,
        "uart_rx_bytes": len(rx),
        "rx_sha256": hashlib.sha256(rx).hexdigest(),
        "response_welcome_seen": b"Smart Coffee E-NOSE v2" in rx,
        "response_info_seen": b"Sistem siap." in rx,
        "rx_printable_excerpt": bytes(rx[:350]).decode("utf-8", "replace"),
        "mcu_flash_identity_verified": False,
        "mcu_programmed": False,
        "eeprom_written": False,
        "actuator_commands_sent": False,
        "kernel_new_usb_events": new_usb[-6:],
        "post_throttle": shell("vcgencmd", "get_throttled").stdout.strip(),
        "error": error,
    }
    (outdir / "uart_rx_raw.bin").write_bytes(bytes(rx))
    (outdir / "result.json").write_text(
        json.dumps(result, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8")
    print("PCB_KEDUA_STATUS_HANDSHAKE " +
          json.dumps(result, ensure_ascii=False, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, required=True)
    parser.add_argument("--seconds", type=int, default=12)
    args = parser.parse_args()
    result = run(args.outdir, args.seconds)
    raise SystemExit(0 if result["status"] == "DONE" else 2)
