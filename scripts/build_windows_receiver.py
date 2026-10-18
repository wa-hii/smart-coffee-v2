"""Package a small portable Windows E-Nose USB collector, without old data."""
from pathlib import Path
from zipfile import ZipFile, ZIP_DEFLATED

ROOT = Path(__file__).resolve().parents[1]
DEST = ROOT / 'dist/Smart_Coffee_ENose_USB_Receiver_Windows_v4_SingleInstance.zip'
FILES = [
    'requirements_listener.txt',
    'windows_receiver/INSTALL_ON_THIS_LAPTOP.bat',
    'windows_receiver/REMOVE_AUTOSTART.bat',
    'windows_receiver/TEST_PORT_DETECTION.bat',
    'windows_receiver/DIAGNOSE_WINDOWS_10.bat',
    'windows_receiver/START_RECEIVER_DEBUG.bat',
    'windows_receiver/DIAGNOSE_ACTIVE_RECEIVERS.bat',
    'windows_receiver/DIAGNOSE_ACTIVE_RECEIVERS.ps1',
    'windows_receiver/install_autostart.ps1',
    'windows_receiver/README_WINDOWS_RECEIVER.md',
    'scripts/lcd_acquisition_service.py',
    'scripts/usb_autodetect.py',
    'scripts/check_usb_receiver.py',
    'scripts/receiver_preflight.py',
    'scripts/recover_receiver_completed_csv.py',
    'scripts/acquisition_schema.py',
    'scripts/baseline_recording.py',
    'scripts/baseline_quality.py',
    'scripts/validate_acquisition.py',
    'scripts/serial_wire.py',
    'scripts/stage7_bridge.py',
    'scripts/stage6_release_gate.py',
]


def main():
    for name in FILES:
        if not (ROOT/name).is_file():
            raise FileNotFoundError(name)
    DEST.parent.mkdir(parents=True, exist_ok=True)
    if DEST.exists():
        raise FileExistsError(f'Refusing overwrite of existing ZIP: {DEST}')
    with ZipFile(DEST, 'x', compression=ZIP_DEFLATED) as z:
        for name in FILES:
            z.write(ROOT/name, arcname=f'SmartCoffee_Receiver/{name}')
    with ZipFile(DEST) as z:
        assert len(z.namelist()) == len(FILES) and z.testzip() is None
    print('RECEIVER_ZIP_PASS', DEST.relative_to(ROOT), len(FILES), 'files', DEST.stat().st_size, 'bytes')


if __name__ == '__main__':
    main()
