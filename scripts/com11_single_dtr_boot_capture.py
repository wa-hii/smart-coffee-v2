#!/usr/bin/env python3
"""Satu pulse DTR terkendali untuk membaca boot UART0 PCB kedua via COM11.

HANYA digunakan atas instruksi operator untuk diagnosis bootloader. DTR#
FT232RL harus benar-benar terhubung ke RESET ATmega agar reset terjadi;
hasil RX=0 tidak membuktikan reset berhasil. Tidak ada serial TX, EEPROM,
flash, GPIO eksternal atau kontrol aktuator dari skrip ini.
"""
from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import time
from serial import Serial

from com11_rf30_verified_deploy import OUT_ROOT, PORT, check_preflight


def capture(seconds: int = 12) -> dict:
    if seconds != 12:
        raise ValueError("DURASI_RESET_PROBE_HARUS_12S")
    pre = check_preflight(uploading=False)
    OUT_ROOT.mkdir(parents=True, exist_ok=True)
    out = OUT_ROOT / ("dtr_boot_capture_" +
                      datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    out.mkdir(exist_ok=False)
    result = {
        "port": PORT,
        "usb_serial": pre["ftdi_serial"],
        "baud": 115200,
        "dtr_pulse_count": 0,
        "uart_tx_bytes": 0,
        "rx_bytes": 0,
        "rx_sha256": None,
        "fw_hello_seen": False,
        "bootloader_signature_verified": False,
        "flash_written": False,
        "eeprom_written": False,
        "status": "NOT_RUN",
        "risk": "Driver can glitch DTR at open; reset can change MCU startup state",
    }
    raw = bytearray()
    port = Serial()
    port.port = PORT
    port.baudrate = 115200
    port.timeout = 0.25
    port.write_timeout = 0
    port.dtr = False
    port.rts = False
    port.rtscts = False
    port.dsrdtr = False
    port.xonxoff = False
    try:
        port.open()
        time.sleep(0.45)
        # pyserial DTR True asserts DTR#, which is active LOW on FT232RL.
        # It may trigger ATmega RESET *only* if appropriate auto-reset
        # capacitor/PCB routing exists.
        port.dtr = True
        result["dtr_pulse_count"] = 1
        time.sleep(0.14)
        port.dtr = False
        end = time.monotonic() + seconds
        result["status"] = "RX_COMPLETED"
        while time.monotonic() < end:
            chunk = port.read(256)
            if chunk:
                raw.extend(chunk)
                low = bytes(raw).lower()
                if any(s in low for s in (
                    b"undervoltage", b"brownout", b"overheat",
                    b"watchdog reset", b"wdt reset"
                )):
                    result["status"] = "STOP_UNSAFE_LOG"
                    break
                if low.count(b"fw_hello") >= 3:
                    result["status"] = "STOP_REPEAT_BOOT_MARKERS"
                    break
                if len(raw) >= 48000:
                    result["status"] = "STOP_RX_LIMIT"
                    break
    except Exception as exc:
        result["status"] = "PORT_ERROR"
        result["error"] = type(exc).__name__ + ": " + str(exc)[:180]
    finally:
        if port.is_open:
            port.dtr = False
            port.close()
        result["rx_bytes"] = len(raw)
        result["rx_sha256"] = hashlib.sha256(raw).hexdigest()
        result["fw_hello_seen"] = b"FW_HELLO" in raw
        (out / "rx_raw.bin").write_bytes(raw)
        (out / "result.json").write_text(
            json.dumps(result, ensure_ascii=False, indent=2) + "\n",
            encoding="utf8")
    print("COM11_DTR_BOOT_CAPTURE", json.dumps(result, ensure_ascii=False))
    return result


if __name__ == "__main__":
    result = capture()
    raise SystemExit(0 if result["status"] == "RX_COMPLETED" else 2)
