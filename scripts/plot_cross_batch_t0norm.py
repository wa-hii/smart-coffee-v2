"""Cross-batch B32-B36 plots anchored to final sample of first purging.

Original plots and raw CSV remain untouched. Every trace retains five complete
purge/collect cycles; only the horizontal and vertical origins shift.
"""
from __future__ import annotations

import csv
import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

from plot_batch_32_36_40 import RAW, ROOT, SENSORS, ROAST, RE, load

OUT = ROOT / 'results/plots_final_t0norm/03_same_origin_roast_cross_batch_t0norm'
BATCHES = ('B32', 'B33', 'B34', 'B35', 'B36')


def normalize_first_purge(data, sensor):
    first = data.loc[(data.run_id == 1) & (data.phase == 'purging')]
    collecting = data.loc[(data.run_id == 1) & (data.phase == 'collecting')]
    if len(first) < 25 or collecting.empty:
        return None, 'first_cycle_purging_below_25_or_collecting_missing'
    # Explicit t0 = last purging sensor reading before first collecting.
    if first.index.max() >= collecting.index.min():
        return None, 'first_cycle_phase_order_invalid'
    anchor_row = data.index.get_loc(first.index[-1])
    x = np.arange(len(data)) - anchor_row
    y = data[sensor].to_numpy(dtype=float) - float(first.iloc[-1][sensor])
    if not (x[anchor_row] == 0 and np.isclose(y[anchor_row], 0)):
        return None, 'normalization_failed'
    return (x, y, float(first.iloc[-1][sensor]), len(first)), None


def main():
    if OUT.parent.exists():
        raise FileExistsError('Refusing overwrite of existing t0norm plots')
    datasets, skipped = {}, []
    for path in sorted(RAW.glob('*.csv')):
        m = RE.fullmatch(path.name)
        if not m: continue
        level, origin, number = m.groups()
        batch = 'B' + number
        if batch not in BATCHES or origin == 'CAW': continue
        data, reason = load(path)
        if reason:
            skipped.append(dict(file=str(path.relative_to(ROOT)), reason=reason))
            continue
        datasets[batch, origin, level] = data
    OUT.mkdir(parents=True)
    written, series_records = [], []
    origins = sorted({o for _, o, _ in datasets})
    for origin in origins:
        for level in ROAST:
            entries = [(batch, datasets[batch, origin, level]) for batch in BATCHES
                       if (batch, origin, level) in datasets]
            if len(entries) < 2: continue
            for sensor in SENSORS:
                traces = []
                for batch, data in entries:
                    norm, reason = normalize_first_purge(data, sensor)
                    if reason:
                        skipped.append(dict(file=f'{batch}_{origin}_{level}_{sensor}', reason=reason))
                        continue
                    x, y, anchor, n = norm
                    traces.append((batch, x, y))
                    series_records.append(dict(origin=origin, roast=level, sensor=sensor,
                                               batch=batch, baseline_adc_t0=anchor,
                                               first_purge_samples=n, first_collect_x=int(x[n]),
                                               peak_delta_adc=float(y.max()),
                                               first_collect_peak_delta_adc=float(y[n:n+5].max())))
                if len(traces) < 2: continue
                fig, ax = plt.subplots(figsize=(11, 4.8))
                for batch, x, y in traces:
                    ax.plot(x, y, lw=1, label=batch)
                ax.axvline(0, linestyle='--', color='grey', lw=1, alpha=.8)
                ax.axhline(0, linestyle=':', color='grey', lw=1, alpha=.8)
                ax.set(xlabel='Indeks sampel relatif terhadap akhir purging pertama (t0 = 0)',
                       ylabel='ΔADC = ADC − ADC(t0)',
                       title=f'Cross-batch B32–B36 | {origin} | {ROAST[level]} | {sensor} | t0 normalized')
                ax.grid(alpha=.2)
                ax.legend(title='Batch', fontsize=8)
                fig.tight_layout()
                filename=f'B32-B36_{origin}_{level}_{sensor}_t0norm.png'
                fig.savefig(OUT/filename, dpi=160)
                plt.close(fig)
                written.append(dict(path=str((OUT/filename).relative_to(ROOT)), origin=origin,
                                    roast=level, sensor=sensor, series_batches=';'.join(t[0] for t in traces),
                                    number_of_series=len(traces)))
    with (OUT.parent/'plot_index.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f, fieldnames=['path','origin','roast','sensor','series_batches','number_of_series'])
        writer.writeheader();writer.writerows(written)
    with (OUT.parent/'series_diagnostics.csv').open('w', newline='', encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['origin','roast','sensor','batch','baseline_adc_t0',
                 'first_purge_samples','first_collect_x','peak_delta_adc','first_collect_peak_delta_adc'])
        writer.writeheader();writer.writerows(series_records)
    with (OUT.parent/'skipped.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['file','reason']);writer.writeheader();writer.writerows(skipped)
    summary={'plots':len(written),'valid_input_csv':len(datasets),
             'skipped':len(skipped),'total_series':len(series_records),
             'all_batches_expected':list(BATCHES),
             't0':'last sensor sample of purging in run 1; collecting begins at positive x',
             'y':'ADC - ADC(t0), no interpolation; retains all acquisition samples',
             'x':'sample ordinal shifted so first purge last point is 0; not verified seconds',
             'prior_plots_preserved':True,'raw_edited':False}
    (OUT.parent/'summary.json').write_text(json.dumps(summary, indent=2)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2))


if __name__=='__main__': main()
