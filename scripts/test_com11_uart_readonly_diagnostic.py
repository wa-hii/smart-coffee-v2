#!/usr/bin/env python3
"""Mock-only RX diagnostics: never use real COM11 or send serial bytes."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import com11_uart_readonly_diagnostic as app


class FakeSerial:
    data = b""
    created = []

    def __init__(self):
        self.is_open = False
        self.dtr = None
        self.rts = None
        self.exclusive = None
        self.created.append(self)

    def open(self):
        assert self.port == "COM11"
        assert self.dtr is False
        assert self.rts is False
        assert self.baudrate == 115200
        self.is_open = True

    def read(self, count):
        return self.data

    def write(self, _):
        raise AssertionError("NO_UART_TX_ALLOWED")

    def close(self):
        self.is_open = False


def run():
    with TemporaryDirectory() as tmp:
        with patch.object(app, "OUT_ROOT", Path(tmp)), \
             patch.object(app, "Serial", FakeSerial), \
             patch.object(app, "check_preflight",
                          return_value={"port": "COM11",
                                        "ftdi_serial": "A10KNJBLA"}):
            for data, expected in (
                (b"", "RX_ZERO_BYTES_INCONCLUSIVE"),
                (b'{"event":"FW_HELLO"}\n',
                 "RX_FIRMWARE_MARKER_SEEN_NOT_BOOTLOADER_PROOF"),
            ):
                FakeSerial.data = data
                with patch.object(app.time, "monotonic",
                                  side_effect=[0.0, 0.0, 10.0]):
                    result = app.run(8.0)
                assert result["status"] == expected
                assert result["uart_tx_bytes"] == 0
                assert result["flash_written"] is False
                assert result["eeprom_written"] is False
                assert FakeSerial.created[-1].is_open is False
    print("COM11_RX_ONLY_NO_FLASH_MOCK_QA_PASS")


if __name__ == "__main__":
    run()
