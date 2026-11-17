#!/usr/bin/env python3
"""Uji mock SIGNON saja, tanpa hardware COM6."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
import com6_arduinoisp_runtime_check as app


class FakeSerial:
    def __init__(self):
        self.is_open = False
        self.commands = []

    def open(self):
        assert self.port == "COM6"
        assert self.baudrate == 19200
        assert self.dtr is False and self.rts is False
        self.is_open = True

    def reset_input_buffer(self):
        pass

    def write(self, raw):
        self.commands.append(raw)
        assert raw == b"\x30\x20"
        return 2

    def read(self, amount):
        assert amount == 2
        return b"\x14\x10"

    def close(self):
        self.is_open = False


def main():
    serial = FakeSerial()
    with TemporaryDirectory() as d:
        with patch.object(app, "check", return_value={"programmer_usb_vidpid": "1A86:7523"}), \
             patch.object(app, "OUT", Path(d)), \
             patch.object(app, "Serial", return_value=serial), \
             patch.object(app.time, "sleep", return_value=None):
            result = app.run()
            assert result["arduinoisp_stk500v1_runtime_verified"]
            assert result["target_com11_opened"] is False
            assert not result["target_flash_written"]
            assert serial.commands == [b"\x30\x20"]
    print("COM6_ARDUINOISP_STK500V1_SIGNON_MOCK_PASS")


if __name__ == "__main__":
    main()
