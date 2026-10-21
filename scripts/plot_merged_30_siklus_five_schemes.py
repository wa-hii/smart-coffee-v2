"""Five families of validated 30-cycle E-Nose sensor plots, no CSV edits.

This script reads the post-merge 01_VALID_GABUNGAN folder, which now has the
new M-MING_B65.csv. Every CSV is independently re-audited, its SHA-256 saved,
and duplicate signals rejected before plotting. Plots use all 900 actual
measurements (no smoothing, resampling, interpolation or fabricated data).

Run: python scripts/plot_merged_30_siklus_five_schemes.py --workers 4
Smoke: python scripts/plot_merged_30_siklus_five_schemes.py --smoke --out DIR
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
from functools import lru_cache
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import sys

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from audit_dataset_30_siklus import audit_one, categorize
from merge_new_30_siklus_audit import checksum, signal_fingerprint, OUTPUT as MERGE
from plot_valid_30_siklus_audit import ROAST_COLOR, ROAST_NAMES, COLOR_CYCLE, SENSOR_LABELS


ROOT = Path(__file__).resolve().parents[1]
SRC = MERGE/'01_VALID_GABUNGAN'
OUT = ROOT/'results/plots_30_siklus_merged_20261021_112csv_5skema'
FOLDERS = {
    'per_batch':'01_sensor_per_batch',
    'roast_same_origin_batch':'02_roast_same_origin_batch',
    'origin_roast_cross_batch':'03_same_origin_roast_cross_batch',
    'roast_same_origin_batch_t0':'04_roast_same_origin_batch_t0',
    'origin_roast_cross_batch_t0':'05_same_origin_roast_cross_batch_t0_norm',
}
NAMES = {
    'per_batch':'01 · Sensor setiap rekaman / batch',
    'roast_same_origin_batch':'02 · Roast berbeda, origin + batch sama',
    'origin_roast_cross_batch':'03 · Origin + roast sama, lintas batch',
    'roast_same_origin_batch_t0':'04 · Roast berbeda, origin + batch sama, ΔADC t0',
    'origin_roast_cross_batch_t0':'05 · Origin + roast sama, lintas batch, ΔADC t0',
}


def scan_valid_source(source:Path)->list[dict]:
    files=sorted(source.glob('*.csv'))
    if not files:
        raise ValueError('Empty source folder: '+str(source))
    known_hashes={}
    known_signals={}
    result=[]
    for file in files:
        sha=checksum(file)
        a,_=audit_one(file,sha)
        label=categorize(a)
        if label!='VALID' or '_INCOMPLETE' in file.stem.upper():
            raise ValueError(f'Refusing invalid CSV: {file.name} {label} {a["anomalies"]}')
        signal=signal_fingerprint(file)
        if sha in known_hashes or signal in known_signals:
            raise ValueError(f'Duplicate valid CSV: {file.name} matches '
                             f'{known_hashes.get(sha,known_signals.get(signal))}')
        known_hashes[sha]=file.name
        known_signals[signal]=file.name
        sample=a['sample_ids'];batch=a['batch_ids']; roast=a['roast_levels']
        if not sample or '-' not in sample:
            raise ValueError(f'No sample code: {file.name}')
        level,origin=sample.split('-',1)
        if level not in ROAST_NAMES or roast.lower()!=ROAST_NAMES[level].lower():
            raise ValueError(f'Inconsistent roast: {file.name}')
        # Each recording has 900 valid samples with first 25 purging, next 5
        # collecting; audit validated *all* 30 cycles and their timestamps.
        result.append({'filename':file.name,'sha256':sha,
                       'signal_sha256':signal,'sample':sample,
                       'batch':batch,'level':level,'origin_code':origin,
                       'rows':a['rows'],'cycles':a['cycles_detected'],
                       'duration_s':a['span_estimate_seconds'],
                       'origin':None,'source_path':str(file.resolve())})
    return result


def group_records(records:list[dict]):
    roast=defaultdict(list)
    batch=defaultdict(list)
    for r in records:
        roast[(r['origin_code'],r['batch'])].append(r)
        batch[(r['origin_code'],r['level'])].append(r)
    roast={k:sorted(v,key=lambda r:(('L','M','D').index(r['level']),r['filename']))
           for k,v in sorted(roast.items()) if len({x['level'] for x in v})>=2}
    batch={k:sorted(v,key=lambda r:(int(r['batch'][1:]),r['filename']))
           for k,v in sorted(batch.items()) if len({x['batch'] for x in v})>=2}
    return roast,batch


@lru_cache(maxsize=128)
def _cached_read(path_str:str):
    # 112 × 900 rows per worker; strictly read-only source.
    d=pd.read_csv(path_str,low_memory=False)
    if len(d)!=900:
        raise RuntimeError('Source row count changed: '+path_str)
    p=d.loc[(d.run_id==1)&(d.phase=='purging')]
    c=d.loc[(d.run_id==1)&(d.phase=='collecting')]
    if (p.sample_idx.tolist()!=list(range(1,26)) or
            c.sample_idx.tolist()!=list(range(1,6)) or p.index[-1]>=c.index[0]):
        raise RuntimeError('t0 anchor mismatch: '+path_str)
    return d, int(p.index[-1]), float(p.timestamp.iloc[-1])


def plot_task(task:dict)->str:
    family=task['family'];sensor=task['sensor']
    normalize=family.endswith('_t0')
    per=family=='per_batch'
    compare_roast=family in ('roast_same_origin_batch','roast_same_origin_batch_t0')
    fig,ax=plt.subplots(figsize=(9.3,3.55 if per else 4.05),dpi=88)
    # 30 collecting windows as *one* artist; avoids 30 separate patches/plot.
    for i,rec in enumerate(task['records']):
        df,anchor,t0_time=_cached_read(rec['source_path'])
        ts=df.timestamp.to_numpy(dtype=float)
        x=(ts-(t0_time if normalize else ts[0]))/1000.0
        values=df[sensor].to_numpy(dtype=float)
        anchor_value=values[anchor]
        y=values-anchor_value if normalize else values
        if per:
            color=ROAST_COLOR[rec['level']]
            label=rec['filename']
        elif compare_roast:
            color=ROAST_COLOR[rec['level']]
            label=f'{ROAST_NAMES[rec["level"]]} · {rec["filename"]}'
        else:
            color=COLOR_CYCLE[i%len(COLOR_CYCLE)]
            label=rec['filename']
        linestyle=('-','--',':','-.')[i%4] if compare_roast else '-'
        ax.plot(x,y,color=color,linewidth=.95,alpha=.91,
                label=label,linestyle=linestyle)
    ymin,ymax=ax.get_ylim()
    offset=-24 if normalize else 0
    ax.broken_barh([(30*c+25+offset,5) for c in range(30)],
                   (ymin,ymax-ymin),facecolors='#E09B3A',alpha=.065,
                   linewidths=0,zorder=0)
    ax.set_ylim(ymin,ymax)
    if normalize:
        ax.axvline(0,color='#555',linestyle='--',linewidth=.8)
        ax.axhline(0,color='#777',linestyle=':',linewidth=.6)
    if per:
        r=task['records'][0]
        title=f'{r["sample"]} · {r["batch"]} · {r["filename"]}'
    elif compare_roast:
        title=(f'Origin {task["origin"]} · Batch {task["batch"]} · roast comparison'
               + (' ΔADC(t0)' if normalize else ''))
    else:
        title=(f'Origin {task["origin"]} · {ROAST_NAMES[task["level"]]} · cross batch'
               + (' ΔADC(t0)' if normalize else ''))
    ax.set_title(title+' | '+SENSOR_LABELS[sensor],fontsize=9.2,pad=10)
    ax.set_xlabel('Detik relatif terhadap t0 purging awal' if normalize else
                  'Detik sejak awal tiap pengambilan',fontsize=8)
    ax.set_ylabel('ΔADC = ADC − ADC(t0)' if normalize else 'ADC (raw)',fontsize=8)
    ax.tick_params(labelsize=7.2)
    ax.grid(alpha=.19,linewidth=.45)
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.set_xlim(-26,877 if normalize else 900) if normalize else ax.set_xlim(-2,900)
    ax.xaxis.set_major_locator(MultipleLocator(60))
    if not per:
        ax.legend(loc='upper center',bbox_to_anchor=(.5,-.24),
                  ncol=min(4,len(task['records'])),fontsize=6.9,frameon=False)
        fig.subplots_adjust(left=.085,right=.985,top=.88,bottom=.29)
    else:
        fig.subplots_adjust(left=.085,right=.985,top=.88,bottom=.17)
    dest=Path(task['output'])
    fig.savefig(dest,dpi=115,facecolor='white')
    plt.close(fig)
    return str(dest)


def save_csv(path:Path,rows:list[dict],fields:list[str]):
    with path.open('w',newline='',encoding='utf-8-sig') as fp:
        wr=csv.DictWriter(fp,fieldnames=fields,extrasaction='ignore')
        wr.writeheader();wr.writerows(rows)


def gallery(out:Path,plot_index:list[dict],csv_count:int):
    data=[{'f':p['family'],'g':p['group'],'s':SENSOR_LABELS[p['sensor']],
           'img':Path(p['plot_path']).relative_to(out).as_posix(),
           'sources':p['inputs']} for p in plot_index]
    names=json.dumps(NAMES,ensure_ascii=False).replace('<','\\u003c')
    objects=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    doc='''<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>E-Nose 30 siklus — 5 skema grafik</title><style>
body{font-family:system-ui,Segoe UI,sans-serif;background:#f6f7f9;color:#253041;max-width:1500px;margin:auto;padding:20px}
h1{font-size:1.65rem}.sub{color:#657186;font-size:.94rem}
.filters{display:flex;gap:12px;flex-wrap:wrap;background:white;border:1px solid #e2e6ec;padding:16px;border-radius:12px;margin:18px 0}
label{flex:1;min-width:160px;display:grid;gap:6px;font-size:.83rem;font-weight:600}
select,input{min-height:36px;background:white;border:1px solid #b9c4d1;border-radius:6px;padding:7px;color:#253041}
.grid{display:grid;grid-template-columns:repeat(auto-fill,minmax(min(100%,440px),1fr));gap:14px}
.plot{background:white;border:1px solid #e0e5eb;border-radius:10px;overflow:hidden}
.plot img{width:100%;display:block}.meta{padding:12px;border-top:1px solid #e2e6ed;font-size:.82rem;overflow-wrap:anywhere}
.meta strong{display:block;font-size:.92rem}.meta small{color:#66768a}
@media(prefers-color-scheme:dark){body{background:#131922;color:#e6e8ed}.filters,.plot{background:#212936;border-color:#3d4552}.meta{border-color:#3d4552}.meta small,.sub{color:#b4bac5}select,input{background:#141a23;color:#eee;border-color:#596371}}
</style></head><body>
<h1>Smart Coffee E-Nose — Grafik 30 Siklus</h1>
<p class="sub">__TOTAL__ CSV valid · 900 sampel setiap CSV · 10 sensor · 5 skema · t0 pada akhir purging pertama (sample_idx 25, sebelum collecting t26). Klik grafik untuk PNG penuh.</p>
<div class="filters"><label>Skema<select id="fam"></select></label><label>Grup<select id="grp"></select></label><label>Sensor<select id="sens"></select></label><label>Cari<input id="search" placeholder="MING, B65, tgs822"></label></div>
<p id="count" class="sub"></p><div id="plots" class="grid"></div>
<p class="sub">Untuk provenance: lihat README.md, plot_index.csv, input_provenance.csv dan summary.json dalam folder yang sama.</p>
<script>const data=__DATA__,labels=__NAMES__;
const fam=document.getElementById('fam'),grp=document.getElementById('grp'),sens=document.getElementById('sens'),q=document.getElementById('search'),box=document.getElementById('plots');
function opts(el,arr,all){const old=el.value;el.replaceChildren(new Option(all,''));arr.forEach(x=>el.append(new Option(x,x)));if(arr.includes(old))el.value=old;}
opts(fam,Object.keys(labels),'Semua skema');for(let i=1;i<fam.options.length;i++)fam.options[i].textContent=labels[fam.options[i].value];
fam.value='roast_same_origin_batch';
function changeGroup(){const rows=data.filter(d=>!fam.value||d.f===fam.value);opts(grp,[...new Set(rows.map(d=>d.g))].sort(),'Semua grup');opts(sens,[...new Set(rows.map(d=>d.s))].sort(),'Semua sensor');render();}
function render(){const term=q.value.trim().toLowerCase();const rows=data.filter(d=>(!fam.value||d.f===fam.value)&&(!grp.value||d.g===grp.value)&&(!sens.value||d.s===sens.value)&&(!term||(d.sources+' '+d.g+' '+d.s).toLowerCase().includes(term)));document.getElementById('count').textContent=`${rows.length} dari ${data.length} grafik`;box.replaceChildren();for(const d of rows){const article=document.createElement('article');article.className='plot';const link=document.createElement('a');link.href=d.img;link.target='_blank';const im=document.createElement('img');im.src=d.img;im.loading='lazy';im.alt=d.g+' '+d.s;link.append(im);const text=document.createElement('div');text.className='meta';const b=document.createElement('strong');b.textContent=d.g+' · '+d.s;const small=document.createElement('small');small.textContent=d.sources;text.append(b,small);article.append(link,text);box.append(article);}}
fam.onchange=changeGroup;grp.onchange=render;sens.onchange=render;q.oninput=render;changeGroup();</script></body></html>'''
    (out/'GALERI_5_SKEMA.html').write_text(doc.replace('__DATA__',objects).replace('__NAMES__',names).replace('__TOTAL__',str(csv_count)),encoding='utf-8')


def run(source:Path=SRC,out:Path=OUT,workers:int=3,smoke:bool=False):
    if out.exists():
        raise FileExistsError('Tidak menimpa grafik sebelumnya: '+str(out))
    records=scan_valid_source(source)
    all_records=records
    if smoke:
        chosen={'L-CAT_B62.csv','M-CAT_B62.csv','L-CAT_B63.csv'}
        records=[r for r in records if r['filename'] in chosen]
    if not records:
        raise ValueError('No validated records')
    roasts,batches=group_records(records)
    tasks=[]

    def add(family:str,group:str,items:list[dict],file_basename:str,origin:str,
            batch:str='',level:str=''):
        for sensor in ADC_COLS:
            dst=out/FOLDERS[family]/f'{file_basename}__{sensor}.png'
            tasks.append({'family':family,'group':group,'records':items,
                          'sensor':sensor,'output':str(dst.resolve()),
                          'origin':origin,'batch':batch,'level':level})

    for rec in records:
        add('per_batch',rec['filename'],[rec],Path(rec['filename']).stem,
            rec['origin_code'],rec['batch'],rec['level'])
    for (origin,batch),items in roasts.items():
        add('roast_same_origin_batch',f'{origin}_{batch}',items,
            f'{origin}_{batch}',origin,batch)
        add('roast_same_origin_batch_t0',f'{origin}_{batch}',items,
            f'{origin}_{batch}_t0norm',origin,batch)
    for (origin,level),items in batches.items():
        add('origin_roast_cross_batch',f'{origin}_{ROAST_NAMES[level]}',items,
            f'{origin}_{ROAST_NAMES[level]}',origin,level=level)
        add('origin_roast_cross_batch_t0',f'{origin}_{ROAST_NAMES[level]}',items,
            f'{origin}_{ROAST_NAMES[level]}_t0norm',origin,level=level)
    for folder in FOLDERS.values():
        (out/folder).mkdir(parents=True,exist_ok=True)
    print('PLOT_PLAN',json.dumps({'csv_valid':len(records),
            'roast_groups':len(roasts),'cross_batch_groups':len(batches),
            'tasks_total':len(tasks),'counts':dict(Counter(t['family'] for t in tasks)),
            'workers':workers,'smoke':smoke},ensure_ascii=False),flush=True)
    plot_index=[]
    def on_result(task,output):
        if Path(output)!=Path(task['output']) or not Path(output).is_file():
            raise RuntimeError('Missing expected output: '+task['output'])
        plot_index.append({'family':task['family'],'group':task['group'],
                           'sensor':task['sensor'],'plot_path':output,
                           'inputs':' | '.join(r['filename'] for r in task['records']),
                           'series':len(task['records']),
                           't0_normalized':task['family'].endswith('_t0')})

    if workers<=1:
        for i,task in enumerate(tasks,1):
            on_result(task,plot_task(task))
            if i%100==0 or i==len(tasks):
                print(f'PLOTS_DONE {i}/{len(tasks)}',flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as pool:
            for i,(task,output) in enumerate(zip(tasks,pool.map(plot_task,tasks,chunksize=8)),1):
                on_result(task,output)
                if i%100==0 or i==len(tasks):
                    print(f'PLOTS_DONE {i}/{len(tasks)}',flush=True)
    actual=Counter(p['family'] for p in plot_index)
    expected={'per_batch':len(records)*10,
              'roast_same_origin_batch':len(roasts)*10,
              'origin_roast_cross_batch':len(batches)*10,
              'roast_same_origin_batch_t0':len(roasts)*10,
              'origin_roast_cross_batch_t0':len(batches)*10}
    if any(actual[k]!=v for k,v in expected.items()):
        raise RuntimeError(f'Plot count mismatch {actual} vs {expected}')
    img_files=list(out.rglob('*.png'))
    if len(img_files)!=len(tasks) or any(p.stat().st_size<4000 for p in img_files):
        raise RuntimeError('Missing or blank graphic detected')
    if any(checksum(Path(r['source_path']))!=r['sha256'] for r in all_records):
        raise RuntimeError('Input CSV changed during plotting')
    save_csv(out/'plot_index.csv',plot_index,
             ['family','group','sensor','plot_path','inputs','series','t0_normalized'])
    save_csv(out/'input_provenance.csv',all_records,
             ['filename','sha256','signal_sha256','sample','batch','level',
              'origin_code','rows','cycles','duration_s','source_path'])
    group_index=[]
    for group,items in roasts.items():
        group_index.append({'type':'roast_same_origin_batch','group':'_'.join(group),
                            'count':len(items),'files':' | '.join(r['filename'] for r in items)})
    for (origin,level),items in batches.items():
        group_index.append({'type':'origin_roast_cross_batch','group':f'{origin}_{ROAST_NAMES[level]}',
                            'count':len(items),'files':' | '.join(r['filename'] for r in items)})
    save_csv(out/'comparison_groups.csv',group_index,['type','group','count','files'])
    summary={'source_valid':str(source.resolve()),'input_csv':len(records),
             'all_source_files_checked':len(all_records),'sensor_count':len(ADC_COLS),
             'roast_groups':len(roasts),'cross_batch_groups':len(batches),
             'plot_counts':expected,'plots_total':len(plot_index),
             'new_csv':'M-MING_B65.csv',
             't0':'sample 25 of first purging phase (cycle 1), just BEFORE collecting begins at sample t26; each CSV has its own ADC(t0) baseline',
             't0_formula':'Delta_ADC(t)=ADC(t)-ADC(t0)',
             'original_samples_per_file':900,
             'sampling':'timestamps from raw CSV; no interpolation, resampling, smoothing',
             'overwritten_inputs':False,'smoke':smoke}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    readme=['# Grafik sensor 30 siklus — gabungan 112 CSV valid', '',
            f'Sumber: `{source.resolve()}`; seluruh CSV diperiksa ulang sebelum plotting.',
            f'Input: **{len(records)}** rekaman valid dan **{len(plot_index)}** PNG.',
            '', '## Lima skema', '']
    for key,folder in FOLDERS.items():
        readme.append(f'- `{folder}`: {expected[key]} grafik PNG · {NAMES[key]}')
    readme += ['',
        '## Normalisasi t0', '',
        '- t0 diambil dari pembacaan terakhir purging siklus pertama `sample_idx=25`, sebelum collecting pertama `t26`.',
        '- ΔADC(t) = ADC(t) − ADC(t0), untuk **setiap** rekaman secara terpisah.',
        '- Sumbu waktu berdasarkan timestamp asli, relatif ke awal rekaman atau t0; data purging awal tetap tampil pada waktu negatif.',
        '- No smoothing, interpolasi, resampling, atau pemalsuan titik hilang.',
        '- Area jingga samar menunjukkan rentang collecting nominal 5 detik, bukan hasil pengukuran aktuator terpisah.',
        '- Warna roasting: Light biru, Medium oranye, Dark merah; lintas batch memakai warna berbeda untuk setiap berkas.',
        '- File dengan batch sama tetapi pengambilan berbeda tetap diberi label **filename lengkap** sehingga tidak dianggap salinan identik.',
        '- Kelompok tanpa perbandingan sah (misalnya hanya satu roast untuk origin+batch) tidak dipaksakan.',
        '- Normalisasi t0 tidak sama dengan baseline udara bersih dari file kalibrasi eksternal.',
        '', '## Navigasi dan audit', '',
        '- `GALERI_5_SKEMA.html`: filter skema, grup, sensor, pencarian, klik PNG untuk resolusi penuh.',
        '- `plot_index.csv`: semua grafik dan sumber tiap grafik.',
        '- `input_provenance.csv`: SHA256 dan metadata dari seluruh CSV valid.',
        '- `comparison_groups.csv`: keanggotaan grup roast dan cross-batch.',
        '- `summary.json`: jumlah grafik dan metode.',
        '', '## Batas interpretasi', '',
        'Perbandingan lintas batch/alat adalah eksploratif; tidak membuktikan independensi spesimen, kesetaraan alat atau signifikansi. Semua ADC berasal dari CSV yang lolos audit 30 siklus.',
        '', '## Kelompok roast dalam origin+batch sama', '']
    for (origin,batch),items in roasts.items():
        readme.append('- '+origin+' '+batch+': '+', '.join(r['filename'] for r in items))
    readme+=['','## Kelompok origin+roast sama lintas batch','']
    for (origin,level),items in batches.items():
        readme.append('- '+origin+' '+ROAST_NAMES[level]+': '+', '.join(r['filename'] for r in items))
    (out/'README.md').write_text('\n'.join(readme)+'\n',encoding='utf-8')
    gallery(out,plot_index,len(records))
    print('FINISHED',json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=SRC)
    ap.add_argument('--out',type=Path,default=OUT)
    ap.add_argument('--workers',type=int,default=min(4,os.cpu_count() or 2))
    ap.add_argument('--smoke',action='store_true')
    a=ap.parse_args()
    if a.workers<1 or a.workers>8:
        ap.error('workers must be 1..8')
    run(a.source.resolve(),a.out.resolve(),a.workers,a.smoke)


if __name__=='__main__':
    main()
