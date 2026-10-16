"""Offline regression: USB auto-discovery, wait, DTR/RTS and safe paths."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from unittest.mock import Mock, patch

from serial import SerialException

import lcd_acquisition_service as app
from usb_autodetect import Discovery, SUPPORTED_USB_IDS, choose_port


def device(port, vid, pid, serial=None):
    return SimpleNamespace(device=port, vid=vid, pid=pid, serial_number=serial)


def main():
    ftdi5 = device('COM5', 0x0403, 0x6001, 'A10KMM3SA')
    ftdi7 = device('COM7', 0x0403, 0x6001, 'ANOTHER')
    unrelated = device('COM1', 0x9999, 0x0001)
    assert (0x0403, 0x6001) in SUPPORTED_USB_IDS
    assert choose_port([unrelated]).reason == 'usb_not_found'
    assert choose_port([unrelated, ftdi5]).port == 'COM5'
    assert choose_port([ftdi7]).port == 'COM7'
    assert choose_port([ftdi5, ftdi7]).port is None
    assert choose_port([ftdi5, ftdi7]).reason == 'usb_ambiguous_use_port_or_usb_serial'
    assert choose_port([ftdi5, ftdi7], serial_number='a10kmm3sa').port == 'COM5'
    assert choose_port([ftdi7, ftdi5, ftdi5]).candidates == ('COM5', 'COM7')
    assert choose_port([device('COM9', 0x1A86, 0x7523)]).port == 'COM9'

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        statuses = []
        receiver = app.AcquisitionService('auto', 115200, .01, Mock())
        def stop_on_sleep(_delay):
            receiver.request_stop()
        # An absent device must neither open COM nor fail to create data/raw.
        with patch.object(app, 'RAW_DIR', root/'data/raw'), \
             patch.object(app, 'INCOMING_DIR', root/'data/raw/.incoming'), \
             patch.object(app, 'INCOMPLETE_DIR', root/'data/raw/incomplete'), \
             patch.object(app, 'BASELINE_DIR', root/'data/baseline'), \
             patch.object(app, 'write_status', side_effect=lambda **kw: statuses.append(kw)), \
             patch.object(app, 'discover_port', return_value=Discovery(None, 'usb_not_found', ())), \
             patch.object(app, 'Serial', side_effect=AssertionError('No serial access expected')), \
             patch.object(app.time, 'sleep', side_effect=stop_on_sleep):
            receiver.run()
        assert (root/'data/raw').is_dir()
        assert (root/'data/raw/.incoming').is_dir()
        assert (root/'data/raw/incomplete').is_dir()
        assert (root/'data/baseline').is_dir()
        assert any(s.get('state') == 'waiting_for_device' for s in statuses)
        assert statuses[-1]['state'] == 'stopped'

    receiver = app.AcquisitionService('auto', 115200, 1, Mock())
    fake = Mock()
    with patch.object(app, 'Serial', return_value=fake):
        assert receiver.open_selected_serial('COM5') is fake
    assert fake.port == 'COM5' and fake.baudrate == 115200
    assert fake.dtr is False and fake.rts is False and fake.timeout == 1
    fake.open.assert_called_once_with()
    try:
        receiver.open_serial()
        raise AssertionError('Auto mode opened serial without device selection')
    except RuntimeError:
        pass

    # A disconnected COM5 can re-enumerate as COM7. No data are invented.
    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        rec = app.AcquisitionService('auto', 115200, .01, Mock())
        statuses = []
        ports_opened = []
        class FakeSerial:
            def __init__(self, port):
                self.port = port
                self.is_open = True
            def close(self):
                self.is_open = False
        def open_fake(port):
            ports_opened.append(port)
            return FakeSerial(port)
        def stream_fake(ser):
            if ser.port == 'COM5':
                raise SerialException('usb detached')
            rec.request_stop()
            yield {'event': 'FW_HELLO', 'build_id': 'baseline60-r0safe-20261016'}
        with patch.object(app, 'RAW_DIR', root/'data/raw'), \
             patch.object(app, 'INCOMING_DIR', root/'data/raw/.incoming'), \
             patch.object(app, 'INCOMPLETE_DIR', root/'data/raw/incomplete'), \
             patch.object(app, 'BASELINE_DIR', root/'data/baseline'), \
             patch.object(app, 'write_status', side_effect=lambda **kw: statuses.append(kw)), \
             patch.object(app, 'discover_port', side_effect=[Discovery('COM5','usb_matched',('COM5',)), Discovery('COM7','usb_matched',('COM7',))]), \
             patch.object(rec, 'open_selected_serial', side_effect=open_fake), \
             patch.object(app, 'serial_json_frames', side_effect=stream_fake), \
             patch.object(app.time, 'sleep', return_value=None):
            rec.run()
        assert ports_opened == ['COM5', 'COM7']
        assert any(x['state'] == 'waiting_for_port' and x['port'] == 'COM5' for x in statuses)
        assert any(x['state'] == 'connected' and x['port'] == 'COM7' for x in statuses)
    print('USB_AUTO_DISCOVERY_NO_HARDWARE_REGRESSION_PASS')


if __name__ == '__main__':
    main()
