"""No-COM regression for safe diagnostics on partial, complete and disconnected."""
from pathlib import Path
import tempfile
from types import SimpleNamespace
import json

from diagnose_three_receivers import inspect_root


def main():
    with tempfile.TemporaryDirectory() as temp:
        root = Path(temp)
        log1 = root / 'logs/devices/ALAT_1'
        log1.mkdir(parents=True)
        (log1/'acquisition_service.status.json').write_text(json.dumps({
            'state': 'connected', 'port': 'COM5', 'pid': 101
        }), encoding='utf-8')
        (log1/'acquisition_service.log').write_text(
            'INFO | ACQ START sample=M-GRB batch=B61\n'
            'INFO | ACQ COMPLETE file=M-GRB_B61.csv rows=900\n',encoding='utf-8')
        valid = root/'data/raw/devices/ALAT_1/M-GRB_B61.csv'
        valid.parent.mkdir(parents=True)
        valid.write_text('fixture,only\n',encoding='utf-8')

        log3 = root/'logs/devices/ALAT_3'
        log3.mkdir(parents=True)
        (log3/'acquisition_service.status.json').write_text(json.dumps({
            'state': 'waiting_for_device', 'port': None, 'pid': 303
        }), encoding='utf-8')
        (log3/'acquisition_service.log').write_text(
            'INFO | ACQ START sample=L-MING batch=B52\n'
            'WARNING | COM connection unavailable; retry 2s\n'
            'WARNING | ACQ INCOMPLETE reason=serial disconnected rows=597\n',
            encoding='utf-8')
        partial = root/'data/raw/devices/ALAT_3/incomplete/L-MING_B52_INCOMPLETE.csv'
        partial.parent.mkdir(parents=True)
        partial.write_text('fixture,only\n',encoding='utf-8')
        mocked_ports = [SimpleNamespace(device='COM5',serial_number='USB_5',
                                        vid=0x0403,pid=0x6001)]
        report = inspect_root(root, ports=mocked_ports)
        assert report['devices']['ALAT_1']['status']['state'] == 'connected'
        assert report['devices']['ALAT_1']['final_csv'][0]['name'] == valid.name
        assert report['devices']['ALAT_2']['status']['state'] == 'status_missing'
        assert report['devices']['ALAT_3']['incomplete_csv'][0]['name'] == partial.name
        assert any('597' in line for line in report['devices']['ALAT_3']['recent_events'])
        assert report['usb_ports'][0]['serial'] == 'USB_5'
        assert valid.exists() and partial.exists()
    print('THREE_RECEIVERS_READ_ONLY_INCIDENT_DIAG_PASS')


if __name__ == '__main__':
    main()
