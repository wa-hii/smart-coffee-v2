"""No-hardware: malformed frame at row 129 must NOT abort later 30 cycles.

Production-grade data still requires 900 genuine, validated sensor frames.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import lcd_acquisition_service as app
from acquisition_schema import ADC_COLS
from test_acquisition_integrity import make_complete_run
from validate_acquisition import validate_file


def emit_sample(row) -> dict:
    sample = {
        'phase': str(row['phase']), 'cycle': int(row['run_id']),
        'sample_idx': int(row['sample_idx']),
        'timestamp': int(row['timestamp']),
        'temperature_c': float(row['temperature']),
        'humidity_rh': float(row['humidity']),
    }
    sample.update({col: int(row[col]) for col in ADC_COLS})
    return sample


def start_event(batch='B60'):
    return {
        'event': 'ACQ_START', 'mode': 'labeled_data', 'phase': 'purging',
        'cycle': 1, 'cycles_total': 30, 'purge_s': 25, 'collect_s': 5,
        'sample_id': 'L-CAT', 'roast_level': 'light',
        'origin_code': 'CAT', 'batch_id': batch,
        'filename': f'L-CAT_{batch}.csv',
    }


def complete_event():
    return {'event': 'ACQ_COMPLETE', 'cycles': 30, 'total_samples': 900,
            'elapsed_active_ms': 900_002,
            'target_active_ms': 900_000, 'paused_ms': 0}


def verify_best_effort_case(root: Path):
    app.configure_device_storage('ALAT_3', root=root)
    logger = Mock()
    svc = app.AcquisitionService('COM7', 115200, 1, logger,
                                 salvage_on_frame_error=True)
    svc.handle_event(start_event('B60'))
    rows = make_complete_run(30)
    for n, (_, row) in enumerate(rows.iterrows()):
        if n == 128:
            svc.handle_event({'event': 'TRANSPORT_ERROR',
                              'reason': 'malformed_json',
                              'detail': 'invalid_json_or_encoding',
                              'frame_bytes': 257, 'fault_class': 'json_syntax'})
            assert svc.session is not None and svc.session.rows == 128
            continue
        payload = emit_sample(row)
        svc.handle_event(payload)
        if n == 200:
            svc.handle_event(payload)  # same valid sensor frame again
    assert svc.session is not None and svc.session.rows == 899
    svc.handle_event(complete_event())
    assert svc.session is None
    assert not list(app.RAW_DIR.glob('*.csv'))
    paths = list(app.INCOMPLETE_DIR.glob('*_INCOMPLETE.csv'))
    assert len(paths) == 1
    with paths[0].open(newline='', encoding='utf-8') as stream:
        saved = list(csv.DictReader(stream))
    assert len(saved) == 899
    assert saved[-1]['run_id'] == '30'
    assert saved[-1]['phase'] == 'collecting'
    assert saved[-1]['sample_idx'] == '5'
    assert any('sample_idx tidak kontigu' in s for s in
               validate_file(paths[0], expected_cycles=30))
    quality = json.loads(paths[0].with_suffix('.quality.json').read_text(encoding='utf-8'))
    assert quality['quality_status'] == 'incomplete_not_for_training'
    assert quality['trainable_as_complete_30_cycle_dataset'] is False
    assert quality['received_valid_sensor_rows'] == 899
    assert quality['missing_vs_900'] == 1
    assert quality['firmware_reported_sensor_samples'] == 900
    assert quality['ignored_frame_or_sensor_issues'] == {
        'serial_malformed_json': 1, 'duplicate_sensor_index': 1,
    }

    # Separate consecutive run with no losses still publishes 900 true rows.
    svc.handle_event(start_event('B61'))
    for n, (_, row) in enumerate(rows.iterrows()):
        payload = emit_sample(row)
        svc.handle_event(payload)
        if n == 300:
            svc.handle_event(payload)
    assert svc.session is not None and svc.session.rows == 900
    svc.handle_event(complete_event())
    assert svc.session is None
    out = app.RAW_DIR / 'L-CAT_B61.csv'
    assert out.exists() and not validate_file(out, expected_cycles=30)
    quality = json.loads(out.with_suffix('.quality.json').read_text(encoding='utf-8'))
    assert quality['quality_status'] == 'validated_complete'
    assert quality['received_valid_sensor_rows'] == 900
    assert quality['ignored_frame_or_sensor_issues'] == {'duplicate_sensor_index': 1}


def main():
    with TemporaryDirectory() as tmp:
        verify_best_effort_case(Path(tmp))
    print('SALVAGE_MALFORMED_257B_CONTINUE_UNTIL_COMPLETE_NO_FAKE_900_AND_DUPLICATE_PASS')


if __name__ == '__main__':
    main()
