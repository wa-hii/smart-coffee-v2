"""Overlay all audited 30-cycle L/M/D trials per coffee origin (any batch ID).

Acceptance: every batch ID is a recording identifier, strict 900-row QA, five *unique*
batch IDs for each of the three roast levels. Repetitions in one batch are
reported but never silently counted as different independent replicates.
All 900 readings from each selected CSV are shown, raw and per-file t0=purge25
normalized, with the same roast colors and distinct dashes within roast.

Does not modify source CSV. Refuses to overwrite an existing output directory.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor
import csv
import hashlib
import json
import os
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from audit_dataset_30_siklus import audit_one, categorize
from merge_new_30_siklus_audit import checksum, signal_fingerprint
from plot_merged_30_siklus_five_schemes import SRC, SENSOR_LABELS, ROAST_NAMES


ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/plots_origin_LMD_merge_all_valid_20261021'
ROASTS=['L','M','D']
# Visual-only palette for origin-level L/M/D overlays. Do not change the
# shared palette used by older figure families or modify sensor readings.
# Gold-yellow is sufficiently dark to remain legible on a white chart.
ROAST_COLOR={'L':'#168A43', 'M':'#D4A400', 'D':'#C62828'}
LINE_STYLES=['solid','dashed','dashdot','dotted',(0,(4,1,1,1)),(0,(2,2,1,2)),(0,(7,2))]
CSV_FIELDS_PROVENANCE=['filename','origin','roast_level','batch_id','sha256','signal_sha256',
                       'rows','cycles','duration_seconds','source_path','status','selection_reason']


def write_csv(path,rows,fields):
    with path.open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


def read_and_audit(source:Path):
    files=sorted(source.glob('*.csv'))
    if not files:
        raise RuntimeError('No source data: '+str(source))
    candidates=[]; provenance=[]; issues=[]
    hashes={}; signals={}
    for file in files:
        sha=checksum(file)
        audit,_=audit_one(file,sha)
        category=categorize(audit)
        sample=audit['sample_ids'];batch=audit['batch_ids'];roast=audit['roast_levels'].lower()
        level=sample[0] if len(sample)>2 else ''
        origin=sample.split('-',1)[1] if '-' in sample else ''
        status='NOT_ELIGIBLE'
        reasons=[]
        if category!='VALID' or '_INCOMPLETE' in file.stem.upper():
            reasons.append('AUDIT_'+category)
        try:
            batch_number=int(batch[1:]) if batch.startswith('B') else -1
        except ValueError:
            batch_number=-1
        if batch_number<0:
            reasons.append('BATCH_ID_NOT_NUMERIC')
        if not origin or level not in ROASTS or roast!=ROAST_NAMES.get(level,'').lower():
            reasons.append('INVALID_SAMPLE_ROAST')
        fp=signal_fingerprint(file)
        if sha in hashes or fp in signals:
            reasons.append('DUPLICATE_SHA_OR_SIGNAL')
        else:
            hashes[sha]=file.name
            signals[fp]=file.name
        if not reasons:
            status='CANDIDATE'
            candidates.append({'filename':file.name,'origin':origin,'level':level,
                               'roast_level':ROAST_NAMES[level],'batch_id':batch,
                               'batch_number':batch_number,'sha256':sha,
                               'signal_sha256':fp,'rows':audit['rows'],
                               'cycles':audit['cycles_detected'],
                               'duration_seconds':audit['span_estimate_seconds'],
                               'source_path':str(file.resolve())})
        row={'filename':file.name,'origin':origin,'roast_level':ROAST_NAMES.get(level,roast),
             'batch_id':batch,'sha256':sha,'signal_sha256':fp,
             'rows':audit['rows'],'cycles':audit['cycles_detected'],
             'duration_seconds':audit['span_estimate_seconds'],
             'source_path':str(file.resolve()),'status':status,
             'selection_reason':';'.join(reasons)}
        provenance.append(row)
        if category!='VALID':
            issues.append({'filename':file.name,'issues':';'.join(audit['anomalies']),
                           'category':category})
    return candidates,provenance,issues


def choose_groups(candidates,provenance):
    grouped=defaultdict(list)
    for record in candidates:
        grouped[record['origin'],record['level'],record['batch_id']].append(record)
    chosen={}; conflicts=[]
    # Prefer plain canonical filenames over timestamped/renamed additional
    # copies for the same batch. They remain visible in input_provenance.csv.
    for key,items in sorted(grouped.items()):
        origin,level,batch=key
        sorted_items=sorted(items,key=lambda x:
                            (x['filename']!=f'{level}-{origin}_{batch}.csv',
                             x['filename']))
        selected=sorted_items[0]
        chosen[key]=selected
        for additional in sorted_items[1:]:
            conflicts.append({'origin':origin,'roast':ROAST_NAMES[level],
                              'batch':batch,'selected_file':selected['filename'],
                              'other_valid_file':additional['filename'],
                              'reason':'MULTIPLE_VALID_RECORDINGS_SAME_BATCH_UNVERIFIED_INDEPENDENCE'})

    matrix=[]; eligible=[]; origin_inputs={}
    # Discover origins from actual verified CSVs, not a hardcoded name list.
    for origin in sorted({r['origin'] for r in candidates}):
        per_level={level:sorted([r for (o,l,b),r in chosen.items() if o==origin and l==level],
                                key=lambda x:x['batch_number']) for level in ROASTS}
        batches={level:[r['batch_id'] for r in per_level[level]] for level in ROASTS}
        valid=all(len(batches[level])>=5 for level in ROASTS)
        reason='LULUS_SEMUA_ROAST_MIN_5_UNIQUE_BATCH' if valid else 'TIDAK_LENGKAP_'+','.join(
            f'{ROAST_NAMES[l]}:{len(batches[l])}/5' for l in ROASTS if len(batches[l])<5)
        matrix.append({'origin':origin,'light_valid_batch':len(batches['L']),
                       'medium_valid_batch':len(batches['M']),
                       'dark_valid_batch':len(batches['D']),
                       'light_batches':';'.join(batches['L']),
                       'medium_batches':';'.join(batches['M']),
                       'dark_batches':';'.join(batches['D']),
                       'eligible':valid,'reason':reason})
        if valid:
            eligible.append(origin)
            origin_inputs[origin]=[r for level in ROASTS for r in per_level[level]]
    selected_paths={r['source_path'] for rows in origin_inputs.values() for r in rows}
    conflict_paths={c['other_valid_file'] for c in conflicts}
    for row in provenance:
        if row['source_path'] in selected_paths:
            row['status']='SELECTED_FOR_PLOT'
            row['selection_reason']='VALID_IN_ALL_BATCHES_UNIQUE_BATCH_AND_ORIGIN_ELIGIBLE'
        elif row['status']=='CANDIDATE':
            if row['filename'] in conflict_paths:
                row['status']='EXCLUDED_EXTRA_SAME_BATCH'
                row['selection_reason']='ADDITIONAL_VALID_CSV_SAME_ORIGIN_ROAST_BATCH'
            else:
                row['status']='EXCLUDED_INELIGIBLE_ORIGIN'
                row['selection_reason']='ORIGIN_HAS_ROAST_WITH_FEWER_THAN_5_UNIQUE_BATCHES'
    return matrix,eligible,origin_inputs,conflicts


def build_measurements(origin_inputs):
    anchor_rows=[]; metrics=[]
    for origin,records in origin_inputs.items():
        for rec in records:
            data=pd.read_csv(rec['source_path'],low_memory=False)
            if len(data)!=900 or data.loc[24,'run_id']!=1 or data.loc[24,'phase']!='purging' or int(data.loc[24,'sample_idx'])!=25:
                raise RuntimeError('Invalid t0 anchor: '+rec['filename'])
            for sensor in ADC_COLS:
                v=data[sensor].to_numpy(dtype=float)
                base=float(v[24])
                anchor_rows.append({'origin':origin,'roast_level':rec['roast_level'],
                                    'batch_id':rec['batch_id'],'filename':rec['filename'],
                                    'sensor':sensor,'t0_index_zero_based':24,
                                    't0_timestamp_ms':int(data.timestamp.iloc[24]),
                                    't0_adc':base,'delta_adc_at_t0':float(v[24]-base)})
                # Every cycle has a collecting response, calculated against
                # its immediately preceding purge tail. This is descriptive
                # and avoids treating 150 points as independent replicates.
                phase_responses=[]
                for cycle in range(1,31):
                    block=data.loc[data.run_id==cycle]
                    purge=block.loc[block.phase=='purging',sensor].to_numpy(dtype=float)
                    collect=block.loc[block.phase=='collecting',sensor].to_numpy(dtype=float)
                    phase_responses.append(float(collect.mean()-np.median(purge[-5:])))
                metrics.append({'origin':origin,'roast_level':rec['roast_level'],
                                'batch_id':rec['batch_id'],'filename':rec['filename'],
                                'sensor':sensor,'baseline_t0_adc':base,
                                'response_collect_vs_last5purge_mean_30cycles':float(np.mean(phase_responses)),
                                'response_collect_vs_last5purge_sd_30cycles':float(np.std(phase_responses,ddof=1)),
                                'raw_start_adc':float(v[0]),
                                'raw_end_adc':float(v[-1]),
                                'delta_end_t0':float(v[-1]-base),
                                'baseline_drift_adc':float(v[-1]-v[0]),
                                't0norm_collecting_mean_delta':float((data.loc[data.phase=='collecting',sensor]-base).mean()),
                                'purge_tail_median_adc':float(np.median(v[20:25]))})
    return anchor_rows,metrics


def compute_comparison(metrics):
    groups=defaultdict(lambda:defaultdict(list))
    for row in metrics:
        groups[row['origin'],row['sensor']][row['roast_level']].append(row)
    comparison=[]
    for (origin,sensor),roasts in sorted(groups.items()):
        o={'origin':origin,'sensor':sensor,'n_total':sum(len(a) for a in roasts.values()),
           'light_n':len(roasts['Light']),'medium_n':len(roasts['Medium']),'dark_n':len(roasts['Dark'])}
        for field,short in [('response_collect_vs_last5purge_mean_30cycles','response'),
                            ('baseline_t0_adc','baseline'),('baseline_drift_adc','drift'),
                            ('t0norm_collecting_mean_delta','normalized_collect')]:
            groups_data=[np.array([r[field] for r in roasts[level]],dtype=float)
                         for level in ('Light','Medium','Dark')]
            means=[float(np.mean(a)) for a in groups_data]
            stds=[float(np.std(a,ddof=1)) if len(a)>1 else 0 for a in groups_data]
            grand=np.concatenate(groups_data)
            within=sum(((a-a.mean())**2).sum() for a in groups_data)
            between=sum(len(a)*(a.mean()-grand.mean())**2 for a in groups_data)
            score=float(between/(within+1e-12))
            o[short+'_class_between_within_ratio']=score
            for level,mean,sd in zip(('light','medium','dark'),means,stds):
                o[level+'_'+short+'_mean']=mean
                o[level+'_'+short+'_sd']=sd
            o[short+'_mean_max_minus_min']=max(means)-min(means)
            o[short+'_mean_rank_low_high']=' < '.join(x[0] for x in sorted(
                zip(('Light','Medium','Dark'),means),key=lambda x:x[1]))
            ranges=[(a.min(),a.max()) for a in groups_data]
            o[short+'_all_three_ranges_overlap']=bool(max(lo for lo,hi in ranges) <= min(hi for lo,hi in ranges))
        comparison.append(o)
    return comparison


def plot_one(task):
    origin,sensor,mode,records,out=task
    normalized=mode=='T0NORM'
    fig,ax=plt.subplots(figsize=(13.2,6.6),dpi=120)
    for level in ROASTS:
        group=[r for r in records if r['level']==level]
        for i,rec in enumerate(group):
            data=pd.read_csv(rec['source_path'],low_memory=False,
                             usecols=['timestamp',sensor,'run_id','phase','sample_idx'])
            if len(data)!=900:
                raise RuntimeError('Unexpected source size: '+rec['filename'])
            ts=data['timestamp'].to_numpy(dtype=float)
            y=data[sensor].to_numpy(dtype=float)
            if normalized:
                x=(ts-ts[24])/1000.0
                y=y-y[24]
                if not (x[24]==0 and y[24]==0):
                    raise RuntimeError('t0 calibration mismatch '+rec['filename'])
            else:
                x=(ts-ts[0])/1000.0
            ax.plot(x,y,color=ROAST_COLOR[level],
                    linestyle=LINE_STYLES[i%len(LINE_STYLES)],
                    linewidth=1.25,alpha=.92,
                    label=f'{ROAST_NAMES[level]} | {rec["filename"]}')
    lo,hi=ax.get_ylim()
    # Single artist: nominal collecting intervals, 25s purge + 5s collect.
    # The sample25 t0 timestamp is normally t=24s from first sample.
    # Nominal collecting windows only; true per-file timestamps may vary by ms.
    offs=-24 if normalized else 0
    ax.broken_barh([(cycle*30+25+offs,5) for cycle in range(30)],
                   (lo,hi-lo),facecolors='#A5ABB3',alpha=.045,zorder=0,linewidths=0)
    ax.set_ylim(lo,hi)
    if normalized:
        ax.axvline(0,linewidth=.9,color='#5C6671',ls='--')
        ax.axhline(0,linewidth=.6,color='#777777',ls=':')
        ax.set_xlim(-26,877)
        ax.set_ylabel('ΔADC = ADC(t) − ADC(t0)')
        ax.set_xlabel('Waktu terhadap t0 akhir purging pertama (detik)')
    else:
        ax.set_xlim(-2,902)
        ax.set_ylabel('ADC (raw)')
        ax.set_xlabel('Waktu dari awal pengambilan setiap CSV (detik)')
    ax.xaxis.set_major_locator(MultipleLocator(60))
    ax.grid(alpha=.22,linewidth=.55)
    ax.spines[['top','right']].set_visible(False)
    ax.set_title(f'{origin} · Light / Medium / Dark · All valid batches · {SENSOR_LABELS[sensor]} · {mode}',
                 fontsize=13,pad=14)
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.18),ncol=3,
              fontsize=7.4,frameon=False,handlelength=3)
    fig.subplots_adjust(left=.08,right=.985,top=.91,bottom=.38)
    path=Path(out)
    path.parent.mkdir(parents=True,exist_ok=True)
    fig.savefig(path,dpi=160,facecolor='white')
    plt.close(fig)
    return str(path)


def write_gallery(out,plot_index):
    data=[{'origin':r['origin'],'sensor':SENSOR_LABELS[r['sensor']],
           'mode':r['mode'],'image':Path(r['plot_path']).relative_to(out).as_posix(),
           'sources':r['inputs']} for r in plot_index]
    obj=json.dumps(data,ensure_ascii=False).replace('<','\\u003c')
    html='''<!doctype html><html lang="id"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Smart Coffee E-Nose: LMD Merge All Valid Batches</title><style>
body{font-family:system-ui,Segoe UI,sans-serif;background:#f6f7fa;color:#263142;max-width:1350px;padding:24px;margin:auto}
h1{font-size:1.7rem}.muted{color:#5c6679}.control{display:flex;gap:12px;flex-wrap:wrap;background:#fff;border:1px solid #ddd;padding:16px;border-radius:12px}
label{display:grid;gap:6px;flex:1;min-width:160px;font-size:.84rem;font-weight:600}select{border:1px solid #bfc6d4;padding:8px;border-radius:7px;background:#fff;color:#222}
.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,550px),1fr));gap:16px;margin:16px 0}.plot{background:white;border:1px solid #dfe4ea;border-radius:12px;overflow:hidden}
.plot img{width:100%;height:auto;display:block}.meta{padding:13px;font-size:.87rem}.meta small{display:block;color:#5b6679;margin-top:5px;line-height:1.45;overflow-wrap:anywhere}
@media(prefers-color-scheme:dark){body{background:#131a24;color:#f2f4f8}.plot,.control{background:#202b3b;border-color:#3e4b60}.muted,.meta small{color:#b8c2d1}select{background:#1b2532;color:#fff;border-color:#637086}}
</style></head><body><h1>Perbandingan Light–Medium–Dark dalam satu origin</h1>
<p class="muted">Seluruh batch valid (nomor batch adalah identitas, bukan batas seleksi) · minimal lima batch berbeda per roast · 10 sensor · dua mode (RAW ADC dan normalisasi t0). Semua kurva asli ditampilkan.</p>
<p><strong style="color:#168A43">● Light = hijau</strong> &nbsp; <strong style="color:#D4A400">● Medium = kuning</strong> &nbsp; <strong style="color:#C62828">● Dark = merah</strong></p>
<div class="control"><label>Origin<select id="origin"></select></label><label>Sensor<select id="sensor"></select></label><label>Grafik<select id="mode"></select></label></div>
<p id="count" class="muted"></p><div class="gallery" id="gallery"></div><p class="muted">t0 ialah purging siklus 1 indeks sampel 25, tepat sebelum collecting t26. Detail provenance pada README.md, plot_index.csv dan input_provenance.csv.</p>
<script>const data=__DATA__,origin=document.getElementById('origin'),sensor=document.getElementById('sensor'),mode=document.getElementById('mode');
const unique=(arr)=>[...new Set(arr)].sort();function fill(e,arr){e.replaceChildren(new Option('Semua',''));arr.forEach(x=>e.append(new Option(x,x)));}
fill(origin,unique(data.map(x=>x.origin)));fill(sensor,unique(data.map(x=>x.sensor)));fill(mode,['RAW','T0NORM']);
function render(){const shown=data.filter(x=>(!origin.value||x.origin===origin.value)&&(!sensor.value||x.sensor===sensor.value)&&(!mode.value||x.mode===mode.value));
document.getElementById('count').textContent=`Menampilkan ${shown.length}/${data.length} grafik`;
const grid=document.getElementById('gallery');grid.replaceChildren();for(const r of shown){const div=document.createElement('div');div.className='plot';const link=document.createElement('a');link.href=r.image;link.target='_blank';const img=document.createElement('img');img.loading='lazy';img.src=r.image;img.alt=r.origin+' '+r.sensor+' '+r.mode;link.append(img);const desc=document.createElement('div');desc.className='meta';const title=document.createElement('strong');title.textContent=r.origin+' · '+r.sensor+' · '+r.mode;const small=document.createElement('small');small.textContent=r.sources;desc.append(title,small);div.append(link,desc);grid.append(div);}}
origin.onchange=render;sensor.onchange=render;mode.onchange=render;render();</script></body></html>'''
    (out/'GALERI_LMD_MERGE.html').write_text(html.replace('__DATA__',obj),encoding='utf-8')


def run(source=SRC,out=OUT,workers=3):
    if out.exists():
        raise FileExistsError(f'Output already exists, refusing overwrite: {out}')
    candidates,provenance,audit_issues=read_and_audit(source)
    matrix,eligible,by_origin,conflicts=choose_groups(candidates,provenance)
    if not eligible:
        raise RuntimeError('No origin with >=5 unique batches for each roast')
    print('AUDIT',json.dumps({'source_files':len(provenance),'eligible':eligible,
          'groups':matrix,'same_batch_collisions':conflicts},ensure_ascii=False),flush=True)
    out.mkdir(parents=True)
    all_files=[r for v in by_origin.values() for r in v]
    anchor_rows,metrics=build_measurements(by_origin)
    comparisons=compute_comparison(metrics)
    tasks=[];idx=[]
    for origin,records in by_origin.items():
        for sensor in ADC_COLS:
            for mode,folder in [('RAW','01_RAW_LMD_MERGED'),('T0NORM','02_T0_NORMALIZED_LMD_MERGED')]:
                name=f'{origin}_LMD_MERGED'+('_T0NORM' if mode=='T0NORM' else '')+f'_{sensor}.png'
                path=out/folder/origin/name
                path.parent.mkdir(parents=True,exist_ok=True)
                tasks.append((origin,sensor,mode,records,str(path.resolve())))
                idx.append({'origin':origin,'sensor':sensor,'mode':mode,
                            'light_count':len([r for r in records if r['level']=='L']),
                            'medium_count':len([r for r in records if r['level']=='M']),
                            'dark_count':len([r for r in records if r['level']=='D']),
                            'plot_path':str(path.resolve()),
                            'inputs':' | '.join(r['filename'] for r in records)})
    print('PLOT_PLAN',len(tasks),'SOURCE_RECORDINGS',len(all_files),flush=True)
    if workers<=1:
        for i,task in enumerate(tasks,1):
            returned=plot_one(task)
            if returned!=task[-1]:
                raise RuntimeError('Wrong plot output')
            if i%20==0:
                print(f'PLOTS_DONE {i}/{len(tasks)}',flush=True)
    else:
        with ProcessPoolExecutor(max_workers=workers) as executor:
            for i,(task,returned) in enumerate(zip(tasks,executor.map(plot_one,tasks,chunksize=2)),1):
                if returned!=task[-1]:
                    raise RuntimeError('Wrong plot output')
                if i%20==0:
                    print(f'PLOTS_DONE {i}/{len(tasks)}',flush=True)

    image_paths=list(out.rglob('*.png'))
    if len(image_paths)!=len(tasks) or any(p.stat().st_size<10000 for p in image_paths):
        raise RuntimeError('PNG count/size validation failed')
    if any(checksum(Path(r['source_path']))!=r['sha256'] for r in provenance):
        raise RuntimeError('Source data changed during plotting')
    if not all(r['delta_adc_at_t0']==0 for r in anchor_rows):
        raise RuntimeError('Baseline error')
    write_csv(out/'eligible_origins.csv',matrix,
              ['origin','light_valid_batch','medium_valid_batch','dark_valid_batch',
               'light_batches','medium_batches','dark_batches','eligible','reason'])
    write_csv(out/'input_provenance.csv',provenance,CSV_FIELDS_PROVENANCE)
    write_csv(out/'baseline_t0_per_sensor.csv',anchor_rows,
              ['origin','roast_level','batch_id','filename','sensor',
               't0_index_zero_based','t0_timestamp_ms','t0_adc','delta_adc_at_t0'])
    write_csv(out/'plot_index.csv',idx,
              ['origin','sensor','mode','light_count','medium_count','dark_count','plot_path','inputs'])
    write_csv(out/'duplicate_same_batch_qa.csv',conflicts,
              ['origin','roast','batch','selected_file','other_valid_file','reason'])
    fields=list(comparisons[0])
    write_csv(out/'sensor_separation_diagnostics.csv',comparisons,fields)
    summary={'source':str(source.resolve()),'source_files_audited':len(provenance),
             'batch_policy':'All valid numeric batch IDs; no maximum or minimum cutoff; names alone cannot exclude a valid CSV',
             'input_candidates_valid_all_batches':len(candidates),
             'selected_files':len(all_files),'excluded_same_batch_records':len(conflicts),
             'eligible_origins':eligible,
             'origin_counts':{origin:dict(Counter(r['roast_level'] for r in rows)) for origin,rows in by_origin.items()},
             'total_plots':len(tasks),'raw_plots':len(eligible)*len(ADC_COLS),
             't0_plots':len(eligible)*len(ADC_COLS),'sensors':list(ADC_COLS),
             't0_definition':'purging cycle 1 sample_idx=25 (zero-based row 24), before collecting at t26',
             't0_math':'ADC(t) - ADC(t0) for each CSV separately',
             'roast_colors':{'Light':ROAST_COLOR['L'],
                             'Medium':ROAST_COLOR['M'],
                             'Dark':ROAST_COLOR['D']},
             'input_unchanged':True,'no_smoothing_interpolation_resampling':True,
             'independence_warning':'Each run is a curve; 30 cycles are not independent replicates; physical device and specimen independence not established.'}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    notes=['# Overlay Light–Medium–Dark berdasarkan origin, seluruh batch valid','',
           'Sumber: `'+str(source.resolve())+'`.',
           f'CSV diperiksa: **{len(provenance)}**; rekaman digunakan: **{len(all_files)}**; origin eligible: **{len(eligible)}**.',
           f'PNG: **{len(tasks)}** (RAW {len(tasks)//2}, T0 normalized {len(tasks)//2}).','',
           '## Kelayakan per origin','',
           '| Origin | Light (batch unik) | Medium | Dark | Eligible |','|---|---:|---:|---:|---|']
    for row in matrix:
        notes.append(f'| {row["origin"]} | {row["light_valid_batch"]} | {row["medium_valid_batch"]} | {row["dark_valid_batch"]} | {"Ya" if row["eligible"] else "Tidak: "+row["reason"]} |')
    notes+=['','## Methodology','',
            '- Overlay **all selected genuine CSV curves** per sensor/roast on one axis (not averaged curves).',
            '- Tidak ada filter nomor batch: batch hanya label identitas rekaman; semua CSV valid dinilai menggunakan aturan yang sama. Setiap CSV 900 sampel dan 30 × (25s purging + 5s collecting).',
            '- Minimum five **unique batch IDs** each roast. Canonical sample code filename is preferred if repeated valid recordings share a batch; see `duplicate_same_batch_qa.csv`.',
            '- RAW ADC unchanged. ΔADC(t) = ADC(t) − ADC(t0) where t0=last purging measurement in cycle1 (sample_idx=25, at nominal t=24s). t26 is first collecting measurement.',
            '- All 900 samples plotted; t0-normalized negative time interval retains first 24 purge samples.',
            '- Light hijau (`#168A43`), Medium kuning keemasan (`#D4A400`), Dark merah (`#C62828`). Different batch runs within a roast have different dash patterns.',
            '- Shaded collecting phases show 5s *nominal* windows, not independently logged actual valve movement.',
            '- No smoothing, interpolation, resampling, filling missing points, or synthetic readings.',
            '', '## Files','',
            '- `01_RAW_LMD_MERGED/ORIGIN/*.png`: 10 sensors × origin, raw.',
            '- `02_T0_NORMALIZED_LMD_MERGED/ORIGIN/*.png`: 10 sensors × origin, normalized.',
            '- `GALERI_LMD_MERGE.html`: filter origin, sensor, raw/t0.',
            '- `plot_index.csv`: one row per graph and source list.',
            '- `input_provenance.csv`: SHA256 and selection reason for **all audited** source CSV.',
            '- `eligible_origins.csv`: seluruh origin yang ditemukan pada dataset dan pemeriksaan kelayakannya.',
            '- `baseline_t0_per_sensor.csv`: anchor ADC for every selected record and sensor.',
            '- `sensor_separation_diagnostics.csv`: per-origin/sensor descriptive ratios, ranks, baseline spread, drift and collection contrast.',
            '- `duplicate_same_batch_qa.csv`: records excluded from the graph for sharing same roast+origin+batch without independent provenance.',
            '', '## Interpretation limitations','',
            'Metrics are descriptive (ratios of between-roast to within-roast variation in *recording-level* features). They are **not classification accuracy, p-values, or evidence of independence**. Baseline at t0 is a within-run purge reference, not an external clean-air calibration. Physical instrument, temperature/humidity, chamber memory, specimen identity and temporal drift remain potential confounders.',
            '']
    (out/'README.md').write_text('\n'.join(notes),encoding='utf-8')
    write_gallery(out,idx)
    print('PLOTS_AND_PROVENANCE_PASS',json.dumps(summary,ensure_ascii=False),flush=True)
    return summary


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--source',type=Path,default=SRC)
    p.add_argument('--out',type=Path,default=OUT)
    p.add_argument('--workers',type=int,default=min(4,os.cpu_count() or 2))
    args=p.parse_args()
    if not 1<=args.workers<=8:
        p.error('Workers must be 1..8')
    run(args.source.resolve(),args.out.resolve(),args.workers)


if __name__=='__main__':
    main()
