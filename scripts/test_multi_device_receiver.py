"""Three instruments in parallel, identical sample/batch, without opening COM."""
from __future__ import annotations

import multiprocessing
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import Mock, patch

from multi_device_receiver import main as multi_main, validate_ports
from validate_acquisition import validate_file


def simulated_instrument(temp: str, index: int):
    import lcd_acquisition_service as app
    from test_acquisition_integrity import make_complete_run

    device = f'ALAT_{index}'
    app.configure_device_storage(device, root=Path(temp))
    assert app.RAW_DIR == Path(temp) / 'data/raw/devices' / device
    assert app.LOG_DIR == Path(temp) / 'logs/devices' / device
    logger = Mock()
    meta = {'sample_id': 'D-GAW', 'roast_level': 'dark',
            'origin_code': 'GAW', 'batch_id': 'B99',
            'filename': 'D-GAW_B99.csv'}
    service = app.AcquisitionService('COM' + str(4 + index), 115200, 0.1, logger)
    service.handle_event({'event': 'ACQ_START', 'mode': 'labeled_data',
                          'cycles_total': 30, 'purge_s': 25, 'collect_s': 5,
                          'cycle': 1, 'phase': 'purging', **meta})
    assert service.session is not None
    service.session.file.close()
    df = make_complete_run(30)
    df['adc_tgs822'] += index * 500
    df.to_csv(service.session.partial_path, index=False)
    service.session.rows = 900
    service.handle_event({'event': 'ACQ_COMPLETE', 'cycles': 30,
                          'total_samples': 900, 'elapsed_active_ms': 900_012,
                          'target_active_ms': 900_000, 'paused_ms': 0})
    assert service.session is None
    assert not logger.error.called, logger.error.call_args_list
    out = app.RAW_DIR / 'D-GAW_B99.csv'
    assert not validate_file(out, expected_cycles=30)
    app.write_status(state='completed_simulation', port=service.port)


def main():
    adapters = [SimpleNamespace(device=f'COM{n}', vid=0x0403, pid=0x6001,
                                serial_number=f'FTDI-{n}') for n in (5, 6, 7)]
    result = validate_ports(['com5', 'com6', 'com7'], adapters)
    assert [(x.label, x.initial_port, x.usb_serial) for x in result] == [
        ('ALAT_1', 'COM5', 'FTDI-5'), ('ALAT_2', 'COM6', 'FTDI-6'),
        ('ALAT_3', 'COM7', 'FTDI-7')]
    for ports, mock_ports in [(['COM5','COM5'], adapters),
                              (['COM5','COM8'], adapters),
                              (['COM5','COM6','COM7','COM8'], adapters),
                              (['COM5','LPT1'], adapters),
                              (['COM5','COM6'], [
                                  SimpleNamespace(device='COM5',vid=0x0403,pid=0x6001,
                                                  serial_number='DUPLICATE'),
                                  SimpleNamespace(device='COM6',vid=0x0403,pid=0x6001,
                                                  serial_number='duplicate')]),
                              (['COM5'], [SimpleNamespace(device='COM5',vid=0,pid=0,
                                                          serial_number='x')])]:
        try:
            validate_ports(ports, mock_ports)
        except ValueError:
            pass
        else:
            raise AssertionError(f'Unsafe mapping accepted: {ports}')
    with patch('multi_device_receiver.validate_ports', return_value=result), \
         patch('multi_device_receiver.legacy_receiver_pids', return_value=[12345]), \
         patch('multi_device_receiver.app.acquire_process_lock',
               side_effect=AssertionError('Must refuse legacy conflict before locking')):
        assert multi_main(['--ports', 'COM5', 'COM6', 'COM7', '--start']) == 2
    with patch('multi_device_receiver.validate_ports', return_value=result), \
         patch('multi_device_receiver.legacy_receiver_pids',
               side_effect=AssertionError('Read-only check must not enumerate processes')):
        assert multi_main(['--ports', 'COM5', 'COM6', 'COM7']) == 0
    with tempfile.TemporaryDirectory() as tmp:
        ctx = multiprocessing.get_context('spawn')
        processes = [ctx.Process(target=simulated_instrument, args=(tmp, i))
                     for i in (1,2,3)]
        for p in processes:
            p.start()
        for p in processes:
            p.join(timeout=40)
            assert p.exitcode == 0, f'Child test failed: {p.name}, {p.exitcode}'
        import pandas as pd
        stamps = []
        for i in (1,2,3):
            root = Path(tmp) / 'data/raw/devices' / f'ALAT_{i}'
            files = list(root.glob('*.csv'))
            assert len(files) == 1 and files[0].name == 'D-GAW_B99.csv'
            assert not validate_file(files[0], expected_cycles=30)
            values = pd.read_csv(files[0])['adc_tgs822']
            stamps.append(int(values.iloc[0]))
            assert (Path(tmp)/'logs/devices'/f'ALAT_{i}'/
                    'acquisition_service.status.json').exists()
        assert len(set(stamps)) == 3, 'Samples from distinct instruments mixed'
    print('MULTI_3_DEVICE_PARALLEL_900_SAMPLES_NO_COM_NO_CLOBBER_PASS')


if __name__ == '__main__':
    multiprocessing.freeze_support()
    main()
