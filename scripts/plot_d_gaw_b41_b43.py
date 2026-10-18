"""Reproducible, read-only D-GAW B41/B42/B43 sensor plots (30 cycles).

No smoothing, interpolation, resampling, timestamp rewriting, or source-file
modification. Artifacts are created once in an isolated results directory.
"""
from __future__ import annotations

import csv
import hashlib
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from validate_acquisition import classify_rows, validate_file

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data' / 'raw'
OUT = ROOT / 'results' / 'plots_D-GAW_B41_B42_B43_20261017'
BATCHES = ('B41', 'B42', 'B43')
PHASES = ('purging', 'collecting')
SENSORS = tuple(ADC_COLS)


def load_inputs():
    inputs = {}
    provenance = []
    for batch in BATCHES:
        path = RAW / f'D-GAW_{batch}.csv'
        if not path.is_file():
            raise FileNotFoundError(path)
        errors = validate_file(path, expected_cycles=30)
        if errors:
            raise ValueError(f'{path.name}: ' + ' | '.join(errors))
        df = pd.read_csv(path, low_memory=False)
        sensor, event, partial = classify_rows(df)
        if not sensor.all() or event.any() or partial.any():
            raise ValueError(f'{path.name}: event / partial rows must be separately audited')
        if df[list(SENSORS)].isna().any().any() or df[list(SENSORS)].apply(pd.to_numeric, errors='coerce').isna().any().any():
            raise ValueError(f'{path.name}: invalid ADC data')
        expected = {'sample_id': 'D-GAW', 'batch_id': batch,
                    'roast_level': 'dark', 'origin': 'Arabika Gayo Wine'}
        for key, value in expected.items():
            if not df[key].eq(value).all():
                raise ValueError(f'{path.name}: unexpected metadata {key}')
        df['elapsed_s'] = (pd.to_numeric(df['timestamp']) - int(df.timestamp.iloc[0])) / 1000.0
        # Explicit t0: the LAST RAW ADC sample in cycle 1's first purging.
        # Do not substitute a foreign batch's baseline and do not call this
        # a verified clean-air reference.
        purge = df.loc[(df.run_id == 1) & (df.phase == 'purging')]
        collect = df.loc[(df.run_id == 1) & (df.phase == 'collecting')]
        if len(purge) < 23 or collect.empty or purge.index[-1] >= collect.index[0]:
            raise ValueError(f'{path.name}: t0 phase sequence invalid')
        t0_idx = purge.index[-1]
        df['relative_to_t0_s'] = (df.timestamp - df.loc[t0_idx, 'timestamp']) / 1000.0
        inputs[batch] = (path, df, t0_idx)
        phase_counts = df.groupby('phase').size().to_dict()
        provenance.append({
            'batch': batch, 'file': str(path.relative_to(ROOT)),
            'sha256': hashlib.sha256(path.read_bytes()).hexdigest(),
            'row_count': len(df), 'cycle_count': int(df.run_id.nunique()),
            'purging_rows': int(phase_counts.get('purging', 0)),
            'collecting_rows': int(phase_counts.get('collecting', 0)),
            'first_timestamp_ms': int(df.timestamp.iloc[0]),
            'last_timestamp_ms': int(df.timestamp.iloc[-1]),
            'span_timestamp_s': float(df.elapsed_s.iloc[-1]),
            't0_first_cycle_last_purge_sample_idx': int(df.loc[t0_idx,'sample_idx']),
            't0_relative_to_first_sample_s': float(df.loc[t0_idx, 'elapsed_s']),
            'missing_adc_cells': int(df[list(SENSORS)].isna().sum().sum()),
            'validated_30cycles': True,
        })
    return inputs, provenance


def save(fig, path, index, category, sensor=''):
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(path, dpi=160, facecolor='white')
    plt.close(fig)
    index.append({'category': category, 'sensor': sensor,
                  'file': str(path.relative_to(ROOT))})


def style(ax, ylabel='ADC mentah'):
    ax.set_ylabel(ylabel)
    ax.set_xlabel('Waktu relatif dari sampel pertama (detik)')
    ax.grid(alpha=.2)


def main():
    # Validate everything before creating files; never overwrite existing QA.
    inputs, provenance = load_inputs()
    if OUT.exists():
        raise FileExistsError(f'Refusing to overwrite prior plot results: {OUT}')
    OUT.mkdir(parents=True)
    index = []
    cycle_rows = []

    for batch, (_, df, _) in inputs.items():
        for cycle, frame in df.groupby('run_id', sort=True):
            purging = frame.loc[frame.phase == 'purging']
            collecting = frame.loc[frame.phase == 'collecting']
            if purging.empty or collecting.empty:
                raise ValueError(f'{batch} cycle {cycle}: missing phase')
            tail = purging.tail(min(5, len(purging)))
            for sensor in SENSORS:
                baseline = float(tail[sensor].median())
                coll_mean = float(collecting[sensor].mean())
                cycle_rows.append({
                    'batch': batch, 'cycle': int(cycle), 'sensor': sensor,
                    'purge_count': len(purging), 'collect_count': len(collecting),
                    'purge_tail5_median_adc': baseline,
                    'collect_mean_adc': coll_mean,
                    'collect_max_adc': float(collecting[sensor].max()),
                    'collect_delta_from_purge_tail5_adc': coll_mean-baseline,
                })
        for sensor in SENSORS:
            fig, ax = plt.subplots(figsize=(12, 4.8))
            ax.plot(df.elapsed_s, df[sensor], linewidth=.8)
            for _, group in df.loc[df.phase == 'collecting'].groupby('run_id'):
                # Highlight observed collecting sensor window; the exact
                # physical valve-switch time is not in the CSV.
                ax.axvspan(group.elapsed_s.iloc[0],group.elapsed_s.iloc[-1],
                           alpha=.07, color='tab:orange', linewidth=0)
            ax.set_title(f'D-GAW {batch} | {sensor} | 30 siklus | purging + collecting')
            style(ax)
            save(fig, OUT/'01_per_batch_per_sensor'/batch/f'{batch}_{sensor}.png',
                 index,'01_per_batch_per_sensor',sensor)

    response = pd.DataFrame.from_records(cycle_rows)
    for sensor in SENSORS:
        fig, ax = plt.subplots(figsize=(12, 4.8))
        for batch, (_, df, _) in inputs.items():
            ax.plot(df.elapsed_s, df[sensor], linewidth=.9,
                    label=f'{batch} (n={len(df)}, span {df.elapsed_s.iloc[-1]:.0f}s)')
        ax.set_title(f'D-GAW dark roast | perbandingan B41–B43 | {sensor}')
        style(ax)
        ax.legend(fontsize=9)
        save(fig, OUT/'02_cross_batch_raw'/f'D-GAW_B41-B43_{sensor}_raw.png',
             index,'02_cross_batch_raw',sensor)

        fig, ax = plt.subplots(figsize=(12, 4.8))
        for batch, (_, df, t0) in inputs.items():
            y = df[sensor].to_numpy(dtype=float) - float(df.loc[t0,sensor])
            ax.plot(df.relative_to_t0_s, y, linewidth=.9, label=batch)
            assert np.isclose(y[t0], 0) and np.isclose(df.relative_to_t0_s.iloc[t0],0)
        ax.axvline(0,color='gray',ls='--',lw=1,alpha=.7)
        ax.axhline(0,color='gray',ls=':',lw=1,alpha=.7)
        ax.set_title(f'D-GAW | {sensor} | t0 = sampel purging terakhir siklus 1')
        ax.set_xlabel('Detik terhadap t0 masing-masing batch (berdasarkan timestamp asli)')
        ax.set_ylabel('ΔADC = ADC(t) − ADC(t0)')
        ax.grid(alpha=.2)
        ax.legend()
        save(fig, OUT/'03_cross_batch_t0_normalized'/f'D-GAW_B41-B43_{sensor}_t0.png',
             index,'03_cross_batch_t0_normalized',sensor)

        fig, ax = plt.subplots(figsize=(11, 4.8))
        for batch in BATCHES:
            group = response[(response.batch == batch) & (response.sensor == sensor)]
            ax.plot(group.cycle,group.collect_delta_from_purge_tail5_adc,
                    marker='.',ms=4,lw=1.1,label=batch)
        ax.axhline(0,color='gray',lw=1,ls=':')
        ax.set(title=f'D-GAW | {sensor} | Collecting mean − purging tail-5 median',
               xlabel='Siklus 1–30',ylabel='Perubahan ADC terhadap purging lokal')
        ax.set_xticks([1,5,10,15,20,25,30])
        ax.grid(alpha=.2)
        ax.legend()
        save(fig,OUT/'04_cycle_response'/f'D-GAW_B41-B43_{sensor}_cycle_delta.png',
             index,'04_cycle_response',sensor)

    for field, label in (('temperature','Suhu (°C)'),('humidity','Kelembapan relatif (%RH)')):
        fig,ax=plt.subplots(figsize=(12,4.8))
        for batch,(_,df,_) in inputs.items():
            ax.plot(df.elapsed_s,df[field],linewidth=1,label=batch)
        ax.set(title=f'D-GAW B41–B43 | {label}',xlabel='Detik sejak sampel pertama',ylabel=label)
        ax.grid(alpha=.2)
        ax.legend()
        save(fig,OUT/'05_environment'/f'D-GAW_B41-B43_{field}.png',index,'05_environment',field)

    fig,ax=plt.subplots(figsize=(11,4.8))
    for batch,(_,df,_) in inputs.items():
        first=df.loc[df.phase == 'purging'].groupby('run_id',sort=True).elapsed_s.min()
        delta=first.diff().dropna()
        ax.plot(delta.index,delta.values,marker='.',lw=1,label=batch)
    ax.axhline(30,color='gray',ls='--',lw=1,label='Target per siklus: 30 detik')
    ax.set(title='D-GAW B41–B43 | interval awal purging antarsiklus',
           xlabel='Siklus (2–30)',ylabel='Selang awal siklus (detik)')
    ax.grid(alpha=.2)
    ax.legend()
    save(fig,OUT/'06_timing'/ 'D-GAW_B41-B43_cycle_start_interval.png',index,'06_timing')

    # Machine-readable QA and provenance. These are derived summaries, not
    # replacements for source CSV or calibrated-sensor measurements.
    with (OUT/'plot_index.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=['category','sensor','file'])
        writer.writeheader();writer.writerows(index)
    response.to_csv(OUT/'cycle_response_metrics.csv',index=False)
    with (OUT/'input_provenance.csv').open('w',newline='',encoding='utf-8') as handle:
        writer=csv.DictWriter(handle,fieldnames=list(provenance[0]))
        writer.writeheader();writer.writerows(provenance)
    summary={
        'batch_files':[p['file'] for p in provenance],
        'total_plots':len(index),
        'plot_counts':{name:sum(row['category']==name for row in index)
                       for name in sorted({r['category'] for r in index})},
        'sensors':list(SENSORS),
        't0':'last sensor sample of first purging of EACH batch, NOT an independent clean-air baseline',
        'x_raw':'elapsed seconds from each batch first sample, derived from unmodified timestamp',
        'sampling':'no interpolation, smoothing, resampling, filling or cycle warping',
        'cycle_response':'collecting mean minus median of last five samples of that cycle purging',
        'comparison_warning':'B41/B42/B43 differ in firmware timing and sample counts. Do not interpret differences as coffee roast differences or direct proof of hardware repeatability.',
        'original_raw_csv_modified':False,
        'input_provenance':provenance,
    }
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    (OUT/'README.md').write_text(
        '# D-GAW B41–B43 — 30-cycle plotting\n\n'
        'Raw inputs: `data/raw/D-GAW_B41.csv`, `D-GAW_B42.csv`, `D-GAW_B43.csv`.\n\n'
        'Plots: `01_per_batch_per_sensor` (30), `02_cross_batch_raw` (10), '
        '`03_cross_batch_t0_normalized` (10), `04_cycle_response` (10), '
        '`05_environment` (2), `06_timing` (1).\n\n'
        'The plots preserve raw ADCs and original timestamps; there is NO interpolation, smoothing, or resampling. '
        'For t0 plots, t0=last purging sensor sample of cycle 1 per batch, not a separate clean-air measurement. '
        'Collecting highlighting is based on observed sensor timestamps, not precise actuator timestamps. '
        'Cycle-response delta is collecting mean minus last-five-purging median. '
        'Because acquisition timing varies between B41, B42, and B43, cross-batch comparisons are exploratory.\n\n'
        'Read `input_provenance.csv`, `plot_index.csv`, `cycle_response_metrics.csv`, `summary.json` for full audit.\n',
        encoding='utf-8')

    # Independent post-run assertions and content-hash checks.
    assert len(index)==63, len(index)
    assert response.shape[0]==3*30*10
    assert sorted(OUT.rglob('*.png')) and len(list(OUT.rglob('*.png')))==len(index)
    for batch,(path,_,_) in inputs.items():
        digest=hashlib.sha256(path.read_bytes()).hexdigest()
        assert digest==next(row['sha256'] for row in provenance if row['batch']==batch)
    print(json.dumps({'status':'PASS','output':str(OUT),'plots':len(index),
                     'batch_rows':{r['batch']:r['row_count'] for r in provenance},
                     'raw_unchanged':True},indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
