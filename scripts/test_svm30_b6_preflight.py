"""Pure mock tests for B6 no-touch readiness gating."""
from __future__ import annotations

from svm30_b6_preflight import assess, _validated_readback
from pathlib import Path


def test():
    good = dict(
        com5_matches_ftdi=True, receiver_owns_com5=False,
        model_integrity=True, firmware_integrity=True,
        physical_boot_to_phome_verified=True,
        flash_and_eeprom_backups_verified=True,
        programmer_and_power_sop_verified=True,
        specific_upload_approval=True,
    )
    assert assess(good) == []
    for key in good:
        bad = dict(good)
        bad[key] = False if key != "receiver_owns_com5" else True
        assert assess(bad), key
        if key == "receiver_owns_com5":
            bad[key] = None
            assert "COM5_RECEIVER_ACTIVE_OR_UNKNOWN" in assess(bad)
    assert len(assess({})) == 8
    assert _validated_readback(None) == (False, "NOT_PROVIDED")
    assert _validated_readback(Path("logs")) == (
        False, "INVALID_PRIVATE_BACKUP_LOCATION")
    # A report of pHome does not remove serial/backup/flash blockers.
    observer = dict(good)
    observer["receiver_owns_com5"] = True
    observer["flash_and_eeprom_backups_verified"] = False
    observer["programmer_and_power_sop_verified"] = False
    observer["specific_upload_approval"] = False
    remaining = assess(observer)
    assert "NEXTION_BOOT_NOT_VERIFIED" not in remaining
    assert len(remaining) == 4
    print("SVM30_B6_PASSIVE_PREFLIGHT_GATE_TEST_PASS",
          {"gates": 8, "serial_opened": False, "flash_performed": False})


if __name__ == "__main__":
    test()
