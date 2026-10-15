"""Reproducible sensor plots; raw-only, no interpolation or model fitting.

Four families: batch/sensor; within-batch roast; cross-batch roast;
within-batch roast with L-CAW reference at t=0 (only when L-CAW exists).
"""
from __future__ import annotations

import csv
import hashlib
import json
import re
from collections import defaultdict
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / 'data/raw'
B40 = RAW / 'irfan_baseline_B36_B40'
OUT = ROOT / 'results/plots_final'
BATCHES = ['B32','B33','B34','B35','B36','B40']
ROAST = {'D':'dark','M':'medium','L':'light'}
SENSORS = ['adc_tgs822','adc_mq135','adc_mq3','adc_tgs2611','adc_tgs2620',
           'adc_tgs2600','adc_tgs2602','adc_mq8','adc_tgs813','adc_tgs816']
RE = re.compile(r'^([DML])-([A-Z0-9]+)_B(32|33|34|35|36|40)\.csv$')


def load(path):
    data=pd.read_csv(path,low_memory=False)
    needed={'run_id','phase','sample_idx','sample_id','roast_level','origin','batch_id',*SENSORS}
    if not needed.issubset(data.columns):
        return None,'missing_columns'
    # Legacy acquisition writes empty sensor rows as phase-change markers.
    # Drop ONLY wholly empty ADC events; never interpolate partial readings.
    marker=data[SENSORS].isna().all(axis=1)
    data=data.loc[~marker].copy()
    if data.empty or data[SENSORS].isna().any().any():
        return None,'missing_sensor_rows'
    if not data['phase'].isin(['purging','collecting']).all():
        return None,'invalid_phase'
    run=pd.to_numeric(data.run_id,errors='coerce')
    idx=pd.to_numeric(data.sample_idx,errors='coerce')
    if run.isna().any() or idx.isna().any():
        return None,'invalid_run_or_index'
    data=data.assign(run_id=run.astype(int),sample_idx=idx.astype(int))
    unique=sorted(data.run_id.unique())
    expected=40 if '_B40.csv' in path.name else 5
    if unique!=list(range(1,expected+1)):
        return None,'incomplete_cycles'
    for (_,phase),group in data.groupby(['run_id','phase'],sort=False):
        ix=group.sample_idx.to_numpy()
        if len(ix)<4 or not np.array_equal(ix,np.arange(1,len(ix)+1)):
            return None,'missing_or_noncontiguous_samples'
    for runid,group in data.groupby('run_id'):
        if not (group.phase.eq('purging').any() and group.phase.eq('collecting').any()):
            return None,'incomplete_cycle_phases'
    if data[['sample_id','roast_level','origin','batch_id']].nunique().max()>1:
        return None,'unstable_metadata'
    for name in SENSORS:
        values=pd.to_numeric(data[name],errors='coerce')
        if not np.isfinite(values).all():
            return None,'nonfinite_sensor_values'
        data[name]=values.astype(float)
    data['plot_index']=np.arange(len(data))
    return data,None


def chart(lines,title,dest,baseline=None):
    fig,ax=plt.subplots(figsize=(10,4.5))
    if baseline is not None:
        ax.axhline(baseline,ls='--',lw=1,color='grey',label='Baseline referensi')
        ax.scatter([0],[baseline],color='black',s=22,zorder=5,label='t0 baseline')
    for label,x,y in lines:
        ax.plot(x,y,lw=0.9,alpha=0.85,label=label)
    ax.set_title(title,fontsize=10)
    ax.set_xlabel('Indeks akuisisi berurutan (bukan detik terkalibrasi)')
    ax.set_ylabel('ADC mentah')
    ax.grid(alpha=.2)
    ax.legend(fontsize=7,loc='best',ncol=2)
    fig.tight_layout()
    dest.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(dest,dpi=105)
    plt.close(fig)


def main():
    if OUT.exists():
        raise FileExistsError('Refuse overwrite plots: '+str(OUT))
    files={}; skipped=[]
    source=list(RAW.glob('*.csv'))+list(B40.glob('*.csv'))
    for path in sorted(source):
        match=RE.match(path.name)
        if not match:continue
        level,origin,batch=match.groups();batch='B'+batch
        if path.parent==B40 and batch!='B40':continue
        if path.parent==RAW and batch=='B40':continue
        if origin=='CAW':continue  # control only, never treat as coffee
        data,reason=load(path)
        if reason:
            skipped.append({'file':str(path.relative_to(ROOT)),'reason':reason})
            continue
        files[(batch,origin,level)]=(path,data)
    baselines={}
    for batch in BATCHES:
        path=(B40/'BASELINE_B40.csv') if batch=='B40' else (RAW/f'L-CAW_{batch}.csv')
        if path.exists():
            # B40 baseline has 40 runs; other designated controls have five.
            d,reason=load(path)
            if not reason:baselines[batch]=(path,d)
            else:skipped.append({'file':str(path.relative_to(ROOT)),'reason':'baseline_'+reason})
    written=[]
    def save(group,batch,origin,level,sensor,lines,baseline=None):
        folder=(batch if group in ('01_sensor_per_batch','02_roast_same_origin_batch','04_roast_same_origin_baseline_t0') else 'B32-B36')
        dest=OUT/group/folder/f'{batch}_{origin}_{level}_{sensor}.png'
        chart(lines,f'{group.replace("_"," ")} | {batch} | {origin} | {level} | {sensor}',dest,baseline)
        written.append({'group':group,'path':str(dest.relative_to(ROOT)),'batch':batch,
                        'origin':origin,'roast':level,'sensor':sensor})
    # 1: each sensor in each batch: one plot per sensor with all eligible samples.
    for batch in BATCHES:
        subset=[(o,l,d) for (b,o,l),(_,d) in sorted(files.items()) if b==batch]
        for sensor in SENSORS:
            lines=[(f'{l}-{o}',d.plot_index,d[sensor]) for o,l,d in subset]
            if lines:save('01_sensor_per_batch',batch,'ALL','ALL',sensor,lines)
    # 2: within batch+origin, compare roast levels.
    origins=sorted({o for _,o,_ in files})
    for batch in BATCHES:
        for origin in origins:
            pair=[(l,files[(batch,origin,l)][1]) for l in ROAST if (batch,origin,l) in files]
            if len(pair)<2:continue
            for sensor in SENSORS:
                save('02_roast_same_origin_batch',batch,origin,'DML',sensor,
                     [(ROAST[l],d.plot_index,d[sensor]) for l,d in pair])
    # 3: same origin+roast across batches, 2+ available.
    for origin in origins:
        for level in ROAST:
            # Main cross-batch comparison: all valid B32, B33, B34, B35, B36.
            pair=[(b,files[(b,origin,level)][1]) for b in BATCHES if b!='B40' and (b,origin,level) in files]
            if len(pair)<2:continue
            for sensor in SENSORS:
                save('03_same_origin_roast_cross_batch','B32-B36',origin,level,sensor,
                     [(b,d.plot_index,d[sensor]) for b,d in pair])
    # 4: t0 uses requested batch-specific reference: L-CAW B33..B36 / BASELINE_B40.
    for batch in BATCHES:
        if batch not in baselines:continue
        ref=baselines[batch][1]
        for origin in origins:
            pair=[(l,files[(batch,origin,l)][1]) for l in ROAST if (batch,origin,l) in files]
            if len(pair)<2:continue
            for sensor in SENSORS:
                collecting=ref.loc[ref.phase=='collecting',sensor]
                value=float(collecting.median())
                save('04_roast_same_origin_baseline_t0',batch,origin,'DML',sensor,
                     [(ROAST[l],d.plot_index+1,d[sensor]) for l,d in pair],baseline=value)
    OUT.mkdir(parents=True,exist_ok=True)
    with (OUT/'plot_index.csv').open('w',newline='',encoding='utf-8') as f:
        writer=csv.DictWriter(f,fieldnames=['group','path','batch','origin','roast','sensor'])
        writer.writeheader();writer.writerows(written)
    (OUT/'skipped.csv').write_text('file,reason\n'+''.join(
        f'{r["file"]},{r["reason"]}\n' for r in skipped),encoding='utf-8')
    summary={'total_png':len(written),'by_group':{x:sum(z['group']==x for z in written)
      for x in sorted({z['group'] for z in written})},'eligible_coffee_csv':len(files),
      'baseline_LCAW_available':sorted(baselines),
      'excluded_incomplete':skipped,
      'baseline_policy':'L-CAW B33-B36; BASELINE_B40 for B40; B32 t0 skipped if no approved baseline',
      'time_axis':'sample ordinal; no assumed seconds',
      't0_definition':'at x=0 use median collecting ADC from designated batch reference; subsequent x are raw data sample ordinals',
      'raw_modified':False}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
