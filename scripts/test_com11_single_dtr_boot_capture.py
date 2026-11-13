#!/usr/bin/env python3
"""Offline mocked test; no actual COM port or reset operation."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

import com11_single_dtr_boot_capture as app


class FakePort:
    def __init__(self):
        self.is_open = False
        self.pulses = 0
        self._dtr = None
    @property
    def dtr(self):
        return self._dtr
    @dtr.setter
    def dtr(self, val):
        if val is True:
            self.pulses += 1
        self._dtr = val
    def open(self):
        assert self.dtr is False and self.rts is False
        assert self.baudrate == 115200
        self.is_open = True
    def read(self, amount):
        return b'{"event":"FW_HELLO","build_id":"test"}\n'
    def write(self, _data):
        raise AssertionError("UART TX prohibited")
    def close(self):
        self.is_open = False


def run():
    fake = FakePort()
    with TemporaryDirectory() as dir:
        with patch.object(app, "OUT_ROOT", Path(dir)), \
             patch.object(app, "check_preflight",
                          return_value={"ftdi_serial": "A10KNJBLA"}), \
             patch.object(app, "Serial", return_value=fake), \
             patch.object(app.time, "sleep", return_value=None), \
             patch.object(app.time, "monotonic",
                          side_effect=[0.0, 0.0, 13.0]):
            result = app.capture()
            assert result["status"] == "RX_COMPLETED"
            assert result["dtr_pulse_count"] == fake.pulses == 1
            assert result["uart_tx_bytes"] == 0
            assert result["flash_written"] is False
            assert result["eeprom_written"] is False
            assert result["fw_hello_seen"]
            assert fake.is_open is False and fake.dtr is False
    print("COM11_SINGLE_DTR_BOOT_CAPTURE_MOCK_PASS")


if __name__ == "__main__":
    run()
