"""Offline ZIP extraction/import smoke test: no serial, no installer executed."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / 'dist/Smart_Coffee_ENose_USB_Receiver_Windows.zip'


def main():
    with ZipFile(ZIP) as archive:
        assert archive.testzip() is None
        with TemporaryDirectory() as temp:
            archive.extractall(temp)
            app = Path(temp) / 'SmartCoffee_Receiver'
            assert (app / 'windows_receiver/INSTALL_ON_THIS_LAPTOP.bat').exists()
            assert (app / 'windows_receiver/install_autostart.ps1').exists()
            imports = ['lcd_acquisition_service', 'serial_wire',
                       'usb_autodetect', 'baseline_recording',
                       'baseline_quality', 'validate_acquisition',
                       'stage7_bridge', 'stage6_release_gate']
            script = ('import sys; sys.path.insert(0, sys.argv[1]); '
                      + '; '.join('__import__(' + repr(x) + ')' for x in imports)
                      + '; print("BUNDLE_IMPORTS_OK")')
            done = subprocess.run([sys.executable, '-c', script, str(app/'scripts')],
                                  cwd=app, capture_output=True, text=True,
                                  timeout=30, check=False)
            assert done.returncode == 0, done.stderr
            assert 'BUNDLE_IMPORTS_OK' in done.stdout
            assert not (app/'data/raw').exists(), 'bundle must not ship personal data'
    print('PORTABLE_RECEIVER_ZIP_EXTRACTION_AND_IMPORT_PASS')


if __name__ == '__main__':
    main()
