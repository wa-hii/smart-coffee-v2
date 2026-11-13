#!/usr/bin/env python3
"""Negative and happy-path mocks; never touches real USB, chip, or files."""
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch
from contextlib import redirect_stdout
from io import StringIO

import com11_rf30_verified_deploy as app


def fake_preflight(*, uploading):
    return {"port": "COM11", "ftdi_serial": "A10KNJBLA",
            "image": {"flash_payload_bytes": 35770},
            "upload_requested": uploading}


def good_parse(path, expected_bytes, **_):
    return {"file_sha256": "a" * 64, "unrepresented_suffix_bytes": 0}


def run():
    with TemporaryDirectory() as temp:
        base = Path(temp)
        signature = "Device signature = 0x1e9801"
        with patch.object(app, "OUT_ROOT", base), \
             patch.object(app, "check_preflight", side_effect=fake_preflight), \
             patch.object(app, "parse_intel_hex", side_effect=good_parse):
            attempts = []

            def no_bootloader(_, name, extra, **kwargs):
                attempts.append((name, extra))
                return False, "stk500v2_ReceiveMessage(): timeout"

            with patch.object(app, "invoke", side_effect=no_bootloader):
                assert app.run(False, None) == 3
                assert [a[0] for a in attempts] == ["01_bootloader_probe"]

            try:
                app.run(True, None)
            except PermissionError:
                pass
            else:
                raise AssertionError("UPLOAD_WITHOUT_APPROVAL_MUST_FAIL")

            def backup_failed(_, name, extra, **kwargs):
                attempts.append((name, extra))
                if name == "01_bootloader_probe":
                    return True, signature
                return False, "readback failed"

            attempts.clear()
            with patch.object(app, "invoke", side_effect=backup_failed):
                assert app.run(True, app.APPROVAL) == 4
                assert [a[0] for a in attempts] == [
                    "01_bootloader_probe", "02_original_readback"]
                assert not any(":w:" in arg for _, args in attempts for arg in args)

            def happy(_, name, extra, **kwargs):
                attempts.append((name, extra))
                return True, signature

            attempts.clear()
            with patch.object(app, "invoke", side_effect=happy):
                assert app.run(True, app.APPROVAL) == 0
                assert [a[0] for a in attempts] == [
                    "01_bootloader_probe", "02_original_readback",
                    "03_rf30_upload", "04_rf30_verify"]
                assert len([arg for _, args in attempts
                            for arg in args if ":w:" in arg]) == 1

            def unsafe_erase(_, name, extra, **kwargs):
                raise AssertionError("Not supposed to reach AVRDude")

            attempts.clear()
            with patch.object(app, "invoke", side_effect=unsafe_erase):
                with patch.object(app, "check_preflight",
                                  side_effect=RuntimeError("WRONG_FTDI_SERIAL")):
                    try:
                        app.run(True, app.APPROVAL)
                    except RuntimeError:
                        pass
                    else:
                        raise AssertionError("UNVERIFIED_DEVICE_MUST_FAIL")

            # A file with an unrepresented FF suffix may preserve the HEX
            # data we saw, but it is NOT a complete, proven-original image.
            attempts.clear()
            def incomplete_flash(path, expected_bytes, **kwargs):
                data = good_parse(path, expected_bytes, **kwargs)
                if expected_bytes == 262144:
                    data["unrepresented_suffix_bytes"] = 15
                return data
            with patch.object(app, "parse_intel_hex", side_effect=incomplete_flash), \
                 patch.object(app, "invoke", side_effect=happy), \
                 redirect_stdout(StringIO()):
                assert app.run(True, app.APPROVAL) == 5
                assert [a[0] for a in attempts] == [
                    "01_bootloader_probe", "02_original_readback"]
    print("COM11_RF30_SIGNATURE_BACKUP_UPLOAD_FAIL_CLOSED_MOCK_PASS")


if __name__ == "__main__":
    run()
