#!/usr/bin/env python3
"""Tes offline guard handshake non-kontrol PCB kedua."""
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch

import pi_second_pcb_status_handshake as mod


class FakeUart:
    calls = []
    def __init__(self):
        self.is_open = False

    def open(self):
        assert self.dtr is False and self.rts is False
        assert self.baudrate == 115200
        self.is_open = True

    def write(self, payload):
        assert payload == b"#status;"
        self.calls.append(payload)
        return len(payload)

    def read(self, amount):
        return b""

    def close(self):
        self.is_open = False


def run():
    assert mod.HANDSHAKE == b"#status;"
    with TemporaryDirectory() as temp:
        with patch.object(mod, "preflight", return_value=None), \
             patch.object(mod, "kernel_usb", return_value=[]), \
             patch.object(mod, "shell", return_value=SimpleNamespace(stdout="throttled=0x0")), \
             patch.object(mod, "Serial", FakeUart), \
             patch.object(mod.time, "monotonic", side_effect=[1.0, 20.0]):
            result = mod.run(Path(temp) / "one", read_seconds=5)
            assert result["status"] == "DONE"
            assert result["uart_tx_bytes"] == 8
            assert result["actuator_commands_sent"] is False
            assert result["mcu_programmed"] is False
            assert FakeUart.calls == [b"#status;"]
    print("PI_SECOND_PCB_ONE_STATUS_NONCONTROL_HANDSHAKE_MOCK_PASS")


if __name__ == "__main__":
    run()
