"""Preflight must remain read-only and truthful off Raspberry Pi."""

from stage7_pi_preflight import inspect


def main():
    data = inspect()
    assert data["type"] == "stage7_pi_read_only_preflight.v1"
    assert data["host_bridge_running"] is False
    assert data["hardware_communication_verified"] is False
    assert data["atmega_link_tested"] is False
    assert data["actions"] == "read_only_no_serial_open_no_gpio_no_network_scan"
    if data["device_model"] == "not_readable":
        assert data["pi5_model_claim_supported"] is False
    print("STAGE7_PI_PREFLIGHT_QA_PASS")


if __name__ == "__main__":
    main()
