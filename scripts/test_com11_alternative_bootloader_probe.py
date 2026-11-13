#!/usr/bin/env python3
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import patch
import json

import com11_alternative_bootloader_probe as app


def test():
    with TemporaryDirectory() as tmp:
        def fake_preflight(*, uploading):
            assert not uploading
            return {"port": "COM11", "ftdi_serial": "A10KNJBLA"}

        def fail(cmd, **kwargs):
            assert "-n" in cmd and "-v" in cmd and "flash:w:" not in str(cmd)
            return SimpleNamespace(returncode=1, stdout="",
                                   stderr="stk500_getsync(): not in sync")
        def success(cmd, **kwargs):
            assert "-n" in cmd and "-v" in cmd
            return SimpleNamespace(returncode=0, stdout="",
                                   stderr="Device signature = 0x1e9801")
        with patch.object(app, "OUT_ROOT", Path(tmp)), \
             patch.object(app, "check_preflight", side_effect=fake_preflight):
            bad = app.run(exec_fn=fail)
            assert bad["status"] == "NO_ALTERNATE_BOOTLOADER_SIGNATURE_NO_FLASH"
            assert len(bad["profiles"]) == 2
            assert not bad["flash_written"] and not bad["eeprom_written"]
            good = app.run(exec_fn=success)
            assert good["status"] == "PROGRAMMER_PROFILE_FOUND_READ_ONLY"
            assert len(good["profiles"]) == 1
            assert good["signature_verified"]
            try:
                app.run(profiles=(("usbasp", "57600"),), exec_fn=success)
            except ValueError:
                pass
            else:
                raise AssertionError("UNAPPROVED_PROFILE_NOT_REJECTED")
    print("COM11_ALTERNATIVE_BOOTLOADER_NO_WRITE_QA_PASS")


if __name__ == "__main__":
    test()
