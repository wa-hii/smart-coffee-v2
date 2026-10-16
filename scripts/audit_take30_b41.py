"""Forensic read-only 30-cycle CSV QA: physical D-GAW_B41 acquisition.

Does not invent roast/origin certificates, run models, or touch serial ports.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS, CSV_COLUMNS
from validate_acquisition import classify_rows, validate_file

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / 'data/raw/D-GAW_B41.csv'
OUT = ROOT / 'results/b41_take30_audit_20261016'


def analyze():
    payload = SOURCE.read_bytes()
    file_hash = hashlib.sha256(payload).hexdigest()
    data = pd.read_csv(SOURCE)
    sensor, metadata, partial = classify_rows(data)
    valid = data.loc[sensor].copy()
    errs = validate_file(SOURCE, expected_cycles=30)
    if list(data.columns) != CSV_COLUMNS:
        raise ValueError('Schema mismatch')
    if errs:
        raise ValueError(f'Strict 30-cycle QA failed: {errs}')
    assert len(valid) == len(data) and len(valid) > 0
    valid['timestamp'] = pd.to_numeric(valid.timestamp)
    adc = valid[ADC_COLS].apply(pd.to_numeric, errors='coerce')
    delta_ms = valid.timestamp.diff().dropna()

    cycles, responses = [], []
    for run in range(1, 31):
        group = valid[valid.run_id.eq(run)]
        purge = group[group.phase.eq('purging')]
        collect = group[group.phase.eq('collecting')]
        assert not purge.empty and not collect.empty
        time_gap = int(collect.timestamp.iloc[0] - purge.timestamp.iloc[-1])
        cycles.append(dict(
            run=run, n_purging=len(purge), n_collecting=len(collect),
            n_total=len(group),
            purging_span_ms=int(purge.timestamp.iloc[-1] - purge.timestamp.iloc[0]),
            collecting_span_ms=int(collect.timestamp.iloc[-1] - collect.timestamp.iloc[0]),
            first_collect_gap_ms=time_gap,
            temperature_purge_mean=float(purge.temperature.mean()),
            temperature_collect_mean=float(collect.temperature.mean()),
            humidity_purge_mean=float(purge.humidity.mean()),
            humidity_collect_mean=float(collect.humidity.mean()),
        ))
        for channel in ADC_COLS:
            baseline = float(pd.to_numeric(purge[channel]).tail(5).median())
            c = pd.to_numeric(collect[channel])
            p = pd.to_numeric(purge[channel])
            responses.append(dict(
                run=run, sensor=channel,
                baseline_purge_tail_median=baseline,
                collect_mean=float(c.mean()),
                collect_max=float(c.max()),
                delta_mean_adc=float(c.mean()-baseline),
                delta_peak_adc=float(c.max()-baseline),
                normalized_delta_mean=float((c.mean()-baseline)/max(abs(baseline), 1)),
                first_purge_adc=float(p.iloc[0]),
                last_purge_adc=float(p.iloc[-1]),
            ))
    cycle = pd.DataFrame(cycles)
    response = pd.DataFrame(responses)
    sensors = []
    for channel in ADC_COLS:
        x = response.loc[response.sensor.eq(channel)].sort_values('run')
        first_base = float(x.baseline_purge_tail_median.iloc[0])
        last_base = float(x.baseline_purge_tail_median.iloc[-1])
        sensors.append(dict(
            sensor=channel, adc_min=int(adc[channel].min()), adc_max=int(adc[channel].max()),
            adc_range=int(adc[channel].max()-adc[channel].min()),
            baseline_first=first_base, baseline_last=last_base,
            baseline_drift_pct=float(100*(last_base-first_base)/max(abs(first_base),1)),
            first_collect_delta_mean=float(x.delta_mean_adc.iloc[0]),
            last_collect_delta_mean=float(x.delta_mean_adc.iloc[-1]),
            median_collect_delta_mean=float(x.delta_mean_adc.median()),
            median_collect_delta_peak=float(x.delta_peak_adc.median()),
            positive_collect_runs=int(x.delta_mean_adc.gt(0).sum()),
            negative_collect_runs=int(x.delta_mean_adc.lt(0).sum()),
            zero_collect_runs=int(x.delta_mean_adc.eq(0).sum()),
            max_collect_delta_peak=float(x.delta_peak_adc.max()),
            response_mean_std=float(x.delta_mean_adc.std(ddof=1)),
        ))
    stats = pd.DataFrame(sensors)
    t0 = float(valid.timestamp.iloc[0]); t1 = float(valid.timestamp.iloc[-1])
    summary = {
        'filename': SOURCE.name,
        'status': 'STRICT_30_CYCLE_QA_PASS_NOT_LABEL_VERIFIED',
        'sha256': file_hash, 'size_bytes':len(payload), 'csv_rows':len(data),
        'canonical_schema': True, 'strict_validator_errors':errs,
        'sample_id':str(valid.sample_id.iloc[0]),
        'roast_level_from_ui':str(valid.roast_level.iloc[0]),
        'origin_from_ui':str(valid.origin.iloc[0]),
        'batch_id':str(valid.batch_id.iloc[0]),
        'cycles':int(valid.run_id.nunique()),
        'sensor_rows':int(sensor.sum()), 'metadata_only_rows':int(metadata.sum()),
        'partial_sensor_rows':int(partial.sum()),
        'purging_rows':int(valid.phase.eq('purging').sum()),
        'collecting_rows':int(valid.phase.eq('collecting').sum()),
        'purging_min_max': [int(cycle.n_purging.min()),int(cycle.n_purging.max())],
        'collecting_min_max':[int(cycle.n_collecting.min()),int(cycle.n_collecting.max())],
        'duration_first_to_last_sample_s':float((t1-t0)/1000),
        'sampling_gap_ms':{'min':float(delta_ms.min()),'median':float(delta_ms.median()),
                           'p95':float(delta_ms.quantile(.95)),'max':float(delta_ms.max()),
                           'outside_900_1100_count':int((~delta_ms.between(900,1100)).sum())},
        'adc_null_cells':int(adc.isna().sum().sum()),
        'adc_zero_cells':int(adc.eq(0).sum().sum()),
        'adc_saturated_cells':int(adc.ge(32767).sum().sum()),
        'temperature':{'min':float(valid.temperature.min()),'max':float(valid.temperature.max()),
                       'mean':float(valid.temperature.mean()),'missing':int(valid.temperature.isna().sum())},
        'humidity':{'min':float(valid.humidity.min()),'max':float(valid.humidity.max()),
                    'mean':float(valid.humidity.mean()),'missing':int(valid.humidity.isna().sum())},
        'provenance_physical_lot_specimen_independence_verified':False,
        'roast_label_independently_verified':False,
        'blind_model_evaluation_allowed':False,
        'notes':[
            'Firmware timestamp is milliseconds since boot, not a wall clock.',
            'Phase row counts 25/5 are nominal at approximately 1 Hz, not exact stopwatch durations.',
            '30 cycles within one acquisition are repeated measures of one session, not independent samples.',
            'Raw ADC shifts and per-cycle delta peaks are diagnostics, not calibrated aroma concentration.',
        ],
    }
    return summary,cycle,response,stats


def main():
    if OUT.exists():
        raise FileExistsError(f'Refuse to overwrite results: {OUT}')
    summary,cycles,responses,sensors=analyze()
    OUT.mkdir(parents=True)
    cycles.to_csv(OUT/'cycle_quality.csv',index=False)
    responses.to_csv(OUT/'cycle_sensor_response.csv',index=False)
    sensors.to_csv(OUT/'sensor_quality_summary.csv',index=False)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print('SENSOR_METRICS')
    print(sensors.to_string(index=False))
    print('CYCLE_COUNTS')
    print(cycles[['run','n_purging','n_collecting','first_collect_gap_ms']].to_string(index=False))


if __name__=='__main__':main()
