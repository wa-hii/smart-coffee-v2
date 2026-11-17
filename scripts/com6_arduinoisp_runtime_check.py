#!/usr/bin/env python3
"""Uji runtime ArduinoISP COM6 menggunakan STK500v1 SIGNON saja.

Tidak menjalankan ENTER_PROGMODE, mengaktifkan SPI target, mengakses COM11,
memprogram chip, atau menggerakkan aktuator. Pembukaan COM6 dapat memicu
reset Mega melalui auto-reset CH340; tunggu bootloader selesai sebelum signon.
"""
from __future__ import annotations

from datetime import datetime
import json
from pathlib import Path
import time

from serial import Serial
from com6_mega_isp_preflight import check, OUT, PROGRAMMER_PORT

SIGNON = b"\x30\x20"  # '0' + CRC_EOP in official ArduinoISP
EXPECTED = b"\x14\x10"  # STK_INSYNC + STK_OK


def run() -> dict:
    identity = check()
    OUT.mkdir(parents=True, exist_ok=True)
    directory = OUT / ("arduinoisp_signon_" +
                       datetime.now().strftime("%Y%m%d_%H%M%S_%f"))
    directory.mkdir(exist_ok=False)
    result = {
        "programmer_port": PROGRAMMER_PORT,
        "identity": identity["programmer_usb_vidpid"],
        "baud": 19200,
        "command_hex": SIGNON.hex(),
        "expected_hex": EXPECTED.hex(),
        "uart_tx_bytes": 0,
        "uart_rx_hex": "",
        "arduinoisp_stk500v1_runtime_verified": False,
        "target_com11_opened": False,
        "target_flash_written": False,
        "target_eeprom_written": False,
        "isp_target_entered_programming_mode": False,
        "status": "NOT_STARTED",
    }
    port = Serial()
    port.port = PROGRAMMER_PORT
    port.baudrate = 19200
    port.timeout = 1.3
    port.write_timeout = 1.3
    port.dtr = False
    port.rts = False
    port.rtscts = False
    port.dsrdtr = False
    raw = b""
    try:
        port.open()
        # Bootloader Mega may run after reset on open. Allow it to
        # time out without issuing any programmer/target command.
        time.sleep(3.0)
        port.reset_input_buffer()
        result["uart_tx_bytes"] = port.write(SIGNON)
        raw = port.read(2)
        result["uart_rx_hex"] = raw.hex()
        result["arduinoisp_stk500v1_runtime_verified"] = raw == EXPECTED
        result["status"] = ("ARDUINOISP_SIGNON_PASS" if raw == EXPECTED
                            else "ARDUINOISP_SIGNON_NOT_CONFIRMED")
    except Exception as exc:
        result["status"] = "COM6_SERIAL_ERROR"
        result["error"] = type(exc).__name__ + ": " + str(exc)[:160]
    finally:
        if port.is_open:
            port.close()
    (directory / "result.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf8")
    print("COM6_ARDUINOISP_RUNTIME", json.dumps(result, sort_keys=True), flush=True)
    return result


if __name__ == "__main__":
    final = run()
    raise SystemExit(0 if final["arduinoisp_stk500v1_runtime_verified"] else 3)
