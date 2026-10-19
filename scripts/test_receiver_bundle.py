"""Offline ZIP extraction/import smoke test: no serial, no installer executed."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path
from tempfile import TemporaryDirectory
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
ZIP = ROOT / 'dist/Smart_Coffee_ENose_USB_Receiver_Windows_v9_SalvageContinue.zip'


def main():
    with ZipFile(ZIP) as archive:
        assert archive.testzip() is None
        with TemporaryDirectory() as temp:
            archive.extractall(temp)
            app = Path(temp) / 'SmartCoffee_Receiver'
            assert (app / 'windows_receiver/INSTALL_ON_THIS_LAPTOP.bat').exists()
            assert (app / 'windows_receiver/install_autostart.ps1').exists()
            assert (app / 'windows_receiver/DIAGNOSE_WINDOWS_10.bat').exists()
            assert (app / 'windows_receiver/START_RECEIVER_DEBUG.bat').exists()
            assert (app / 'windows_receiver/DIAGNOSE_ACTIVE_RECEIVERS.ps1').exists()
            assert (app / 'windows_receiver/INSTALL_THREE_ON_THIS_LAPTOP.bat').exists()
            assert (app / 'windows_receiver/START_THREE_ENOSE_COM5_COM6_COM7.bat').exists()
            assert (app / 'windows_receiver/README_THREE_DEVICES.md').exists()
            assert (app / 'windows_receiver/DIAGNOSE_THREE_SESSIONS.bat').exists()
            assert (app / 'scripts/multi_device_receiver.py').exists()
            assert (app / 'scripts/diagnose_three_receivers.py').exists()
            assert (app / 'scripts/receiver_preflight.py').exists()
            receiver=(app / 'scripts/lcd_acquisition_service.py').read_text(encoding='utf-8')
            assert 'elapsed_active_ms' in receiver and 'target_active_ms' in receiver
            assert 'ACQ_TIMING_FAULT' in receiver and 'active duration out of tolerance' in receiver
            assert 'acquire_host_instance_lock' in receiver
            assert 'data_raw_dir' in receiver
            assert 'SERIAL FRAME REJECTED' in receiver
            assert 'salvage_on_frame_error' in receiver
            framer=(app / 'scripts/serial_wire.py').read_text(encoding='utf-8')
            assert 'json_error_pos' in framer and 'fault_class' in framer
            launcher=(app / 'windows_receiver/START_THREE_ENOSE_COM5_COM6_COM7.bat').read_text(encoding='utf-8')
            assert '--salvage-on-frame-error' in launcher
            imports = ['lcd_acquisition_service', 'multi_device_receiver', 'diagnose_three_receivers', 'recover_receiver_completed_csv', 'serial_wire',
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
            # Execute preflight in a separate process, inside temporary bundle.
            diag = subprocess.run([sys.executable, str(app/'scripts/receiver_preflight.py')],
                                  cwd=app, capture_output=True, text=True,
                                  timeout=30, check=False)
            assert diag.returncode == 0, diag.stdout + '\n' + diag.stderr
            assert 'PREFLIGHT PASS' in diag.stdout
            assert (app/'data/raw').is_dir()
    print('PORTABLE_RECEIVER_ZIP_EXTRACTION_AND_IMPORT_PASS')


if __name__ == '__main__':
    main()
