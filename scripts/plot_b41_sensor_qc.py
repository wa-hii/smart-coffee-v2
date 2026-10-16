"""Render non-destructive per-channel B41 purge/collect drift diagnostics."""
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import pandas as pd

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/b41_take30_audit_20261016'

def main():
    target=OUT/'plots'
    if target.exists():
        raise FileExistsError('Do not overwrite previously rendered plots')
    data=pd.read_csv(OUT/'cycle_sensor_response.csv')
    assert len(data)==300 and data.run.nunique()==30
    target.mkdir(parents=True)
    for name,frame in data.groupby('sensor'):
        frame=frame.sort_values('run')
        fig,ax=plt.subplots(figsize=(10,4.5))
        ax.plot(frame.run,frame.baseline_purge_tail_median,marker='.',lw=1.25,label='Baseline (median 5 purging terakhir)')
        ax.plot(frame.run,frame.collect_mean,marker='.',lw=1.25,label='Collecting mean')
        ax.plot(frame.run,frame.collect_max,alpha=.5,lw=.8,label='Collecting max')
        ax.set(title=f'D-GAW B41 · 30 siklus · {name}',xlabel='Siklus (1–30)',ylabel='ADC mentah')
        ax.grid(alpha=.25);ax.legend(fontsize=8)
        fig.tight_layout();fig.savefig(target/f'{name}_cycle_drift.png',dpi=145);plt.close(fig)
    print('B41_SENSOR_PLOTS_PASS',len(list(target.glob('*.png'))))

if __name__=='__main__':main()
