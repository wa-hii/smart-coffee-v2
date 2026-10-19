"""Offline regression: malformed vs oversized JSON without physical COM I/O."""
from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock, patch

import lcd_acquisition_service as service_module
from serial_wire import MAX_LINE_BYTES, serial_json_frames
from test_acquisition_payload import make_sensor_payload


class FakePort:
    def __init__(self, chunks):
        self.chunks = iter(chunks)

    def read(self, _size):
        return next(self.chunks)


def main():
    frames = serial_json_frames(FakePort([
        b'{"event":"ACQ_START"}\n',
        b'{"bad":\n',
        b'{"sample_idx":1,"sample_idx":2}\n',
        b'{"temperature_c":NaN}\n',
        b'x' * (MAX_LINE_BYTES + 50) + b'\n',
    ]))
    assert next(frames) == {'event': 'ACQ_START'}
    bad = next(frames)
    assert bad['reason'] == 'malformed_json'
    assert bad['detail'] == 'invalid_json_or_encoding'
    assert bad['frame_bytes'] == len(b'{"bad":\n')
    assert bad['fault_class'] == 'json_syntax'
    assert bad['json_error_message'] == 'Expecting value'
    assert bad['json_error_at_end'] is True
    assert bad['ends_with_brace'] is False
    duplicate = next(frames)
    assert duplicate['reason'] == 'malformed_json'
    assert duplicate['detail'] == 'duplicate_json_key'
    nonfinite = next(frames)
    assert nonfinite['detail'] == 'nonfinite_json_number'
    too_long = next(frames)
    assert too_long['reason'] == 'oversized_line'
    assert too_long['limit_bytes'] == MAX_LINE_BYTES

    # Four distinct 272-byte faults: ordinary corrupt syntax, truncated
    # sensor JSON, invalid UTF-8, and a valid-looking object with invalid
    # bytes. None may be accepted by the strict sensor CSV receiver.
    one_line = b'{"adc_tgs822":1533,"sample_idx":12,"cycle":14,"phase":"purging"}'
    malformed_272 = (one_line[:-1] + b',' + b' ' * (271 - len(one_line)) + b'\n')
    assert len(malformed_272) == 272
    faults = serial_json_frames(FakePort([
        malformed_272,
        b'{"adc_tgs822":1533,"sample_idx":12,\n',
        b'{"adc_tgs822":"\xff"}\n',
    ]))
    bad272 = next(faults)
    assert bad272['fault_class'] == 'json_syntax'
    assert bad272['frame_bytes'] == 272
    assert bad272['json_error_pos'] > 0
    assert bad272['ends_with_brace'] is False
    truncated = next(faults)
    assert truncated['fault_class'] == 'json_syntax'
    assert truncated['json_error_at_end'] is True
    utf8 = next(faults)
    assert utf8['fault_class'] == 'invalid_utf8'
    assert utf8['invalid_byte_offset'] > 0

    with TemporaryDirectory() as tmp:
        root = Path(tmp)
        with patch.object(service_module, 'RAW_DIR', root / 'raw'), \
             patch.object(service_module, 'INCOMING_DIR', root / 'raw/.incoming'), \
             patch.object(service_module, 'INCOMPLETE_DIR', root / 'raw/incomplete'):
            logger = Mock()
            service = service_module.AcquisitionService('COM_TEST_MOCK', 115200, 1, logger)
            event = {'event': 'ACQ_START', 'mode': 'labeled_data',
                     'sample_id': 'L-TOR', 'roast_level': 'light',
                     'origin_code': 'TOR', 'batch_id': 'B61',
                     'filename': 'L-TOR_B61.csv', 'cycles_total': 30,
                     'purge_s': 25, 'collect_s': 5,
                     'cycle': 1, 'phase': 'purging'}
            service.handle_event(event)
            assert service.session is not None
            service.handle_event(make_sensor_payload())
            assert service.session.rows == 1
            service.handle_event(bad)
            assert service.session is None
            assert len(list((root / 'raw/incomplete').glob('*INCOMPLETE.csv'))) == 1
            assert not list((root / 'raw').glob('*.csv'))
            assert any('SERIAL FRAME REJECTED' in str(x) for x in logger.error.call_args_list)
            # New capture can start normally; no special persistent failure flag.
            service.handle_event(event)
            assert service.session is not None
            service.handle_event({'event': 'ACQ_STOP'})
            assert service.session is None
    print('SERIAL_FRAME_REASON_AND_FAIL_CLOSED_DIAGNOSTICS_PASS')


if __name__ == '__main__':
    main()
