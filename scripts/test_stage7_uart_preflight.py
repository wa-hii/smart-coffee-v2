"""Ensure UART inventory is entirely passive and makes no payload claims."""

from unittest.mock import patch
from stage7_uart_preflight import config_uart_lines, inspect, inspect_pin


def main() -> None:
    lines = """# dtoverlay=uart1
dtoverlay=uart0-pi5
dtparam=uart0=on
dtoverlay=vc4-kms-v3d
"""
    assert config_uart_lines(lines) == [
        "dtoverlay=uart0-pi5", "dtparam=uart0=on"
    ]
    assert config_uart_lines(None) == []
    # Guard the only allowed external GPIO command.
    class Result:
        returncode = 0
        stdout = "14: a4 | hi // GPIO14 = TXD0"

    with patch("stage7_uart_preflight.shutil.which", return_value="/usr/bin/pinctrl"):
        with patch("stage7_uart_preflight.subprocess.run", return_value=Result()) as fn:
            assert "TXD0" in inspect_pin(14)
            assert fn.call_args.args[0] == ["pinctrl", "get", "14"]
    report = inspect()
    assert report["action"] == "read_only_no_serial_open_no_gpio_write"
    assert report["hardware_uart_payload_validated"] is False
    assert report["needs_explicit_permission_before_port_open"] is True
    assert report["atmega_firmware_serial1_bridge_implemented"] is False
    assert report["candidate_routes_are_not_proof_of_atmega_link"] is True
    print("STAGE7_UART_PREFLIGHT_OFFLINE_PASS")


if __name__ == "__main__":
    main()
