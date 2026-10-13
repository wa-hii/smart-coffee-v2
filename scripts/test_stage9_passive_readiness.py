"""Stage 9 non-invasive identity assessment: pure data tests on all OS."""

from __future__ import annotations

from copy import deepcopy

from stage9_passive_readiness import assess


def main():
    baseline = {
        "platform": "linux", "port_is_character_device": True,
        "by_id_target": "/dev/ttyUSB0",
        "udev_identity": {
            "ID_SERIAL_SHORT": "A10KMM3S", "ID_VENDOR_ID": "0403",
            "ID_MODEL_ID": "6001", "ID_USB_DRIVER": "ftdi_sio",
        },
        "port_owner": "NO_VISIBLE_OWNER", "throttled": "throttled=0x0",
    }
    assert assess(baseline) == "PASS_PASSIVE_IDENTITY_ONLY_HARDWARE_E2E_NOT_TESTED"
    wrong = [
        ("port_is_character_device", False),
        ("by_id_target", "/dev/ttyUSB1"),
        ("port_owner", "OCCUPIED"),
        ("port_owner", "UNKNOWN"),
        ("throttled", "throttled=0x1"),
        ("udev_identity", {**baseline["udev_identity"],
                           "ID_SERIAL_SHORT": "ANOTHER_DEVICE"}),
        ("udev_identity", {**baseline["udev_identity"],
                           "ID_USB_DRIVER": "another_driver"}),
    ]
    for key, value in wrong:
        variant = deepcopy(baseline)
        variant[key] = value
        assert assess(variant) == "BLOCKED_PASSIVE_READINESS_CHECK"
    assert assess({**baseline, "platform": "win32"}) == (
        "UNSUPPORTED_HOST_NOT_TESTED"
    )
    print("STAGE9_PASSIVE_FT232R_IDENTITY_QA_PASS")


if __name__ == "__main__":
    main()
