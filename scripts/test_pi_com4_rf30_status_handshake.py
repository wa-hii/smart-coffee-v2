#!/usr/bin/env python3
"""Offline mock tests ensure the Pi COM4 handshake sends ONLY #status;."""
from tempfile import TemporaryDirectory
from pathlib import Path
from unittest.mock import patch

import pi_com4_rf30_status_handshake as app


class FakePort:
    def __init__(self):
        self.is_open = False
        self.writes = []

    def open(self):
        assert self.port == str(app.LINK)
        assert self.baudrate == 115200
        assert self.dtr is False and self.rts is False
        self.is_open = True

    def write(self, payload):
        assert payload == b"#status;"
        self.writes.append(payload)
        return len(payload)

    def read(self, amount):
        assert amount == 256
        return b'Welcome Smart Coffee E-NOSE v2. Sistem siap.\r\n'

    def close(self):
        self.is_open = False


class FakeLink:
    def __str__(self):
        return "/dev/serial/by-id/usb-FTDI_FT232R_USB_UART_A10KMZQJ-if00-port0"

    def is_symlink(self):
        return True

    def resolve(self):
        return app.TARGET


def main():
    port = FakePort()
    with TemporaryDirectory() as d:
        out = Path(d) / "safe-test"
        with patch.object(app, "preflight", return_value={"verified": True}), \
             patch.object(app, "Serial", return_value=port), \
             patch.object(app.time, "sleep", return_value=None), \
             patch.object(app.time, "monotonic", side_effect=[0, 1, 21]), \
             patch.object(app, "LINK", FakeLink()):
            result = app.run(out, 12)
            assert result["tx_bytes"] == 8
            assert result["welcome_response_seen"]
            assert port.writes == [b"#status;"]
            assert not port.is_open
    print("PI_COM4_STATUS_COMMAND_ONLY_MOCK_PASS")


if __name__ == "__main__":
    main()
