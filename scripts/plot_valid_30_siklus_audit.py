"""Reproducible four-family E-Nose sensor plots from audited VALID CSV only.

Input: 01_VALID_30_SIKLUS copies from audited 69-file manifest; check SHA256
against manifest before plotting. Neither original CSV nor classified copies
are ever edited. Output is a separate results folder, with provenance and
plot indices; refuses to overwrite an existing results folder.

1) Every sensor × input recording (30 cycles, 25s purging, 5s collecting).
2) Same origin+batch, compare roast levels, where 2+ levels exist.
3) Same origin+roast, compare cross-batch (replicates separately labeled).
4) Same origin+batch, roast comparison after t0 subtraction, where t0 is
   the final sensor reading of the FIRST purging phase (sample_idx=25).
"""
from __future__ import annotations

import argparse
from collections import defaultdict, Counter
import csv
import hashlib
import html
import json
from pathlib import Path
import re

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
from matplotlib.ticker import MultipleLocator
import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS


ROOT = Path(__file__).resolve().parents[1]
AUDIT = ROOT/'data/raw/data 30 siklus/HASIL_AUDIT_30_SIKLUS_20261019'
OUT = ROOT/'results/plots_30_siklus_valid_audit_20261019'
DIRS = {
    'per_batch': '01_sensor_per_batch',
    'same_origin_batch_roast': '02_roast_same_origin_same_batch',
    'same_origin_roast_cross_batch': '03_same_origin_roast_cross_batch',
    'roast_t0': '04_roast_same_origin_batch_t0',
}
ROAST_NAMES = {'L':'Light', 'M':'Medium', 'D':'Dark'}
ROAST_COLOR = {'L':'#3478C0', 'M':'#E38B37', 'D':'#A84458'}
SENSOR_LABELS = {
    'adc_tgs822':'TGS822', 'adc_mq135':'MQ135', 'adc_mq3':'MQ3',
    'adc_tgs2611':'TGS2611', 'adc_tgs2620':'TGS2620',
    'adc_tgs2600':'TGS2600', 'adc_tgs2602':'TGS2602',
    'adc_mq8':'MQ8', 'adc_tgs813':'TGS813', 'adc_tgs816':'TGS816',
}
COLOR_CYCLE = ['#3E75BC','#D68435','#459E84','#B65068','#855CA8',
               '#7C7B40','#31889D','#AF7F41','#817E9F','#586E90']


def digest(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_verified(audit_root:Path=AUDIT) -> list[dict]:
    manifest = json.loads((audit_root/'audit_manifest.json').read_text(encoding='utf-8'))
    result=[]
    for row in manifest['files']:
        if row['category'] != 'VALID':
            continue
        if row.get('strict_30_cycle_timing_pass') is not True:
            raise ValueError(f"Audit timing flag not PASS: {row['filename']}")
        path=audit_root/'01_VALID_30_SIKLUS'/row['filename']
        if not path.is_file() or digest(path)!=row['sha256']:
            raise ValueError(f'File missing or SHA256 changed since audit: {path}')
        data=pd.read_csv(path,low_memory=False)
        if len(data)!=900:
            raise ValueError(f'CSV row count changed: {path}')
        sample=str(data['sample_id'].iloc[0]); batch=str(data['batch_id'].iloc[0]);
        level,origin=sample.split('-',1)
        if (level not in ROAST_NAMES or row['sample_ids']!=sample or
                row['batch_ids']!=batch or not data['timestamp'].is_monotonic_increasing):
            raise ValueError(f'Identity / ordering failed: {path.name}')
        p1=data.loc[(data.run_id==1)&(data.phase=='purging')]
        c1=data.loc[(data.run_id==1)&(data.phase=='collecting')]
        if (p1.sample_idx.tolist()!=list(range(1,26)) or
                c1.sample_idx.tolist()!=list(range(1,6)) or
                not p1.index[-1]<c1.index[0]):
            raise ValueError(f'No complete 25+5 initial anchor in: {path.name}')
        for sensor in ADC_COLS:
            if pd.to_numeric(data[sensor],errors='coerce').isna().any():
                raise ValueError(f'NaN ADC {sensor} in {path.name}')
        result.append({
            'path':path,'data':data,'filename':row['filename'],
            'sha256':row['sha256'],'sample':sample,'batch':batch,
            'level':level,'origin_code':origin,'origin':str(data['origin'].iloc[0]),
            't0_index':int(p1.index[-1]),
            't0_timestamp_ms':int(p1.timestamp.iloc[-1]),
            't0_definition':'first cycle / purging / sample_idx 25 (immediately before first collecting)',
        })
    return result


def roast_groups(records:list[dict])->dict[tuple,list[dict]]:
    groups=defaultdict(list)
    for rec in records:
        groups[(rec['origin_code'],rec['batch'])].append(rec)
    return {key:sorted(entries,key=lambda z:(list(ROAST_NAMES).index(z['level']),z['filename']))
            for key,entries in sorted(groups.items())
            if len({r['level'] for r in entries})>=2}


def batch_groups(records:list[dict])->dict[tuple,list[dict]]:
    groups=defaultdict(list)
    for rec in records:
        groups[(rec['origin_code'],rec['level'])].append(rec)
    return {key:sorted(entries,key=lambda z:(int(z['batch'][1:]),z['filename']))
            for key,entries in sorted(groups.items())
            if len({r['batch'] for r in entries})>=2}


def x_seconds(rec:dict, relative_t0:bool=False)->np.ndarray:
    ts=rec['data'].timestamp.to_numpy(dtype=float)
    pivot=rec['t0_timestamp_ms'] if relative_t0 else ts[0]
    return (ts-pivot)/1000.0


def y_sensor(rec:dict,sensor:str,relative_t0:bool=False)->np.ndarray:
    value=rec['data'][sensor].to_numpy(dtype=float)
    return value-value[rec['t0_index']] if relative_t0 else value


def figure_style(ax, title:str, xlabel:str, ylabel:str, relative_t0:bool=False):
    ax.set_title(title,fontsize=10.5,pad=12,fontweight='medium')
    ax.set_xlabel(xlabel,fontsize=9)
    ax.set_ylabel(ylabel,fontsize=9)
    ax.tick_params(labelsize=8)
    ax.grid(alpha=.22,linewidth=.55)
    ax.spines[['top','right']].set_visible(False)
    ax.xaxis.set_major_locator(MultipleLocator(60))
    if relative_t0:
        ax.axvline(0,linewidth=1,color='#4C4C4C',linestyle='--',alpha=.75)
        ax.axhline(0,linewidth=.8,color='#777',linestyle=':',alpha=.65)


def shade_collecting(ax,relative_t0:bool=False):
    # first purging t0=sample at nominal t=24s. Collecting starts at 25s.
    offset=-24 if relative_t0 else 0
    for run in range(30):
        ax.axvspan(run*30+25+offset,run*30+30+offset,
                   alpha=.055,color='#CF882B',linewidth=0,zorder=0)


def save_fig(fig,path:Path):
    fig.savefig(path,dpi=140,bbox_inches='tight',facecolor='white')
    plt.close(fig)


def plot_one(rec,sensor,output):
    fig,ax=plt.subplots(figsize=(11.5,4.1),dpi=105)
    shade_collecting(ax)
    ax.plot(x_seconds(rec),y_sensor(rec,sensor),color=ROAST_COLOR[rec['level']],
            linewidth=.88,alpha=.95)
    figure_style(ax,
        f'{rec["sample"]} · {rec["batch"]} · {rec["origin"]} | {SENSOR_LABELS[sensor]}',
        'Waktu sejak sampel pertama (detik) | 30 siklus · 25s purging / 5s collecting',
        'ADC (raw)')
    ax.set_xlim(-3,901)
    fig.tight_layout()
    save_fig(fig,output)


def plot_compare(entries,sensor,output,title,kind):
    relative=(kind=='roast_t0')
    fig,ax=plt.subplots(figsize=(11.5,4.6),dpi=105)
    shade_collecting(ax,relative_t0=relative)
    for i,rec in enumerate(entries):
        # Batch comparisons can legitimately include two independently named
        # recordings with the same batch_id. Label by file to preserve them.
        label=(f'{ROAST_NAMES[rec["level"]]} · {rec["filename"]}'
               if kind in ('roast_t0','same_origin_batch_roast')
               else rec['filename'])
        color=(ROAST_COLOR[rec['level']]
               if kind in ('roast_t0','same_origin_batch_roast')
               else COLOR_CYCLE[i%len(COLOR_CYCLE)])
        linestyle=['-','--',':','-.'][i%4] if kind=='same_origin_batch_roast' else '-'
        ax.plot(x_seconds(rec,relative),y_sensor(rec,sensor,relative),
                color=color,linestyle=linestyle,linewidth=1.05,alpha=.86,label=label)
    figure_style(ax,title,
        ('Waktu relatif terhadap akhir purging awal (detik), t0 = 0'
         if relative else 'Waktu relatif sejak awal setiap CSV (detik)'),
        ('ΔADC = ADC(t) − ADC(t0)' if relative else 'ADC (raw)'),
        relative_t0=relative)
    ax.set_xlim((-27 if relative else -3), (877 if relative else 901))
    ax.legend(loc='upper center',bbox_to_anchor=(.5,-.22),ncol=min(len(entries),4),
              fontsize=7,frameon=False)
    fig.subplots_adjust(bottom=.26)
    save_fig(fig,output)


def write_rows(path:Path,rows:list[dict],fields:list[str]):
    with path.open('w',newline='',encoding='utf-8-sig') as stream:
        writer=csv.DictWriter(stream,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


def build_gallery(out:Path,plots:list[dict]) -> Path:
    """Offline, dependency-free visual index with family/group/sensor filters."""
    listing=[{'family':p['family'], 'group':p['group'],
              'sensor':SENSOR_LABELS[p['sensor']],
              'file':Path(p['plot_path']).relative_to(out).as_posix(),
              'inputs':p['input_filenames']}
             for p in plots]
    js_data=json.dumps(listing,ensure_ascii=False).replace('<','\\u003c')
    template='''<!doctype html>
<html lang="id"><head><meta charset="utf-8"/>
<meta name="viewport" content="width=device-width, initial-scale=1"/>
<title>Galeri E-Nose • 30 Siklus Valid</title>
<style>
:root {font-family:system-ui,Segoe UI,Arial,sans-serif;color-scheme:light dark}
body {max-width:1550px;margin:0 auto;padding:23px;background:#f6f7fa;color:#242936}
h1 {font-size:clamp(1.25rem,3vw,1.8rem);margin:0 0 8px}
.muted {color:#596478;font-size:.9rem;line-height:1.5}
.toolbar {background:white;border:1px solid #e1e4e9;border-radius:13px;
  display:flex;flex-wrap:wrap;align-items:end;gap:13px;padding:15px;margin:18px 0}
label {display:flex;flex-direction:column;font-size:.81rem;font-weight:600;gap:5px;flex:1;min-width:180px}
select,input {padding:9px;border:1px solid #bec8d3;background:white;color:#222;
  border-radius:7px;font:inherit;min-height:38px}
.cards {display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,490px),1fr));gap:15px}
.card {background:white;border:1px solid #e0e3e9;border-radius:12px;overflow:hidden}
.card a {display:block;text-decoration:none;color:inherit}
.card img {width:100%;height:auto;display:block;background:#f6f6f7}
.meta {padding:12px 15px;border-top:1px solid #eceff4;font-size:.85rem}
.meta b {display:block;font-size:.93rem;margin-bottom:5px;word-break:break-word}
.meta p {color:#626d7a;line-height:1.4;margin:0;overflow-wrap:anywhere}
#count {font-weight:700;margin:10px 0 20px}
.foot {color:#596478;font-size:.84rem;line-height:1.6;margin:25px 0}
@media (prefers-color-scheme:dark) {body{background:#121620;color:#f5f7fb}
.toolbar,.card{background:#202633;border-color:#394354}.meta{border-color:#394354}
.muted,.meta p,.foot{color:#acb9ca}select,input{background:#161b26;color:#f1f5fa;border-color:#4c586a}}
</style></head><body>
<h1>Smart Coffee E-Nose · Galeri 30 Siklus Valid</h1>
<p class="muted">38 CSV dari audit ketat · 10 sensor ADC · 610 grafik. Setiap
grafik mempertahankan 900 sampel tanpa smoothing/interpolasi. Klik grafik
untuk membuka PNG ukuran penuh. t0 = sampel purging ke-25 siklus pertama,
tepat sebelum sampel collecting t26.</p>
<div class="toolbar">
<label>Jenis grafik <select id="family"></select></label>
<label>Origin / batch / roast <select id="group"></select></label>
<label>Sensor <select id="sensor"></select></label>
<label>Cari nama file / grup <input id="search" placeholder="contoh: GAW, B60, TOR"/></label>
</div>
<div id="count" role="status"></div>
<div id="cards" class="cards"></div>
<p class="foot">Sumber: folder <code>01_VALID_30_SIKLUS</code> dari hasil audit.
Lihat <a href="README.md">README.md</a>, <a href="plot_index.csv">plot_index.csv</a>,
<a href="input_provenance.csv">input_provenance.csv</a> dan
<a href="comparison_groups.csv">comparison_groups.csv</a>.
Grafik lintas rekaman bersifat eksploratif: instrumen/spesimen bisa berbeda.</p>
<script>
"use strict";
const items=__PLOT_JSON__;
const names={per_batch:'01 · Sensor per batch',
same_origin_batch_roast:'02 · Roast sama origin + batch',
same_origin_roast_cross_batch:'03 · Origin + roast sama, lintas batch',
roast_t0:'04 · Roast sama origin + batch, normalisasi t0'};
const family=document.getElementById('family'), group=document.getElementById('group'),
  sensor=document.getElementById('sensor'),search=document.getElementById('search'),
  cards=document.getElementById('cards'),count=document.getElementById('count');
function options(select, list, allText, current) {
  select.replaceChildren();
  const any=new Option(allText, ''); select.add(any);
  for(const v of list) select.add(new Option(v,v));
  if(list.includes(current))select.value=current;
}
options(family,Object.keys(names).map(key=>key), 'Semua kategori','same_origin_batch_roast');
for(let i=1;i<family.options.length;i++)family.options[i].textContent=names[family.options[i].value];
family.value='same_origin_batch_roast';
function refreshOptions() {
  let subset=items.filter(x=>!family.value||x.family===family.value);
  options(group,[...new Set(subset.map(x=>x.group))].sort(),'Semua grup',group.value);
  options(sensor,[...new Set(subset.map(x=>x.sensor))].sort(),'Semua sensor',sensor.value);
}
function update(){
 const q=search.value.trim().toLowerCase();
 const shown=items.filter(x=>(!family.value||x.family===family.value)
   &&(!group.value||x.group===group.value)
   &&(!sensor.value||x.sensor===sensor.value)
   &&(!q||(x.group+' '+x.file+' '+x.inputs).toLowerCase().includes(q)));
 cards.replaceChildren();
 count.textContent=`Menampilkan ${shown.length} dari ${items.length} grafik`;
 for(const item of shown){
   const article=document.createElement('article');article.className='card';
   const link=document.createElement('a');link.href=item.file;link.target='_blank';
   const img=document.createElement('img');img.src=item.file;img.loading='lazy';
   img.alt=`${item.group} · ${item.sensor}`;link.append(img);
   const meta=document.createElement('div');meta.className='meta';
   const title=document.createElement('b');title.textContent=`${item.group} · ${item.sensor}`;
   const p=document.createElement('p');p.textContent=item.inputs;
   meta.append(title,p);article.append(link,meta);cards.append(article);
 }
}
family.onchange=()=>{refreshOptions();update()};group.onchange=update;
sensor.onchange=update;search.oninput=update;
refreshOptions();update();
</script></body></html>'''
    path=out/'GALERI_GRAFIK.html'
    path.write_text(template.replace('__PLOT_JSON__',js_data),encoding='utf-8')
    return path


def run(audit_dir:Path=AUDIT,out:Path=OUT,only_records:list[str]|None=None)->dict:
    if out.exists():
        raise FileExistsError(f'Refusing to overwrite previous plots: {out}')
    records=load_verified(audit_dir)
    if only_records is not None:
        records=[r for r in records if r['filename'] in only_records]
    if not records:
        raise ValueError('No validated CSV input files')
    by_roast=roast_groups(records)
    by_batch=batch_groups(records)
    for relative in DIRS.values():
        (out/relative).mkdir(parents=True,exist_ok=True)
    plots=[]
    series=[]
    provenance=[]
    for rec in records:
        provenance.append({
            'filename':rec['filename'], 'sample':rec['sample'],
            'batch':rec['batch'],'origin':rec['origin'],
            'sha256':rec['sha256'], 'csv_path':str(rec['path'].resolve()),
            'rows':len(rec['data']), 'cycles':rec['data'].run_id.nunique(),
            'initial_purging_samples':25,'initial_collecting_samples':5,
            't0_timestamp_ms':rec['t0_timestamp_ms'],
            't0_index_zero_based':rec['t0_index'],
        })

    def emit(kind,sensor,filename,group,entries):
        path=out/DIRS[kind]/filename
        if kind=='per_batch':
            plot_one(entries[0],sensor,path)
        else:
            first=entries[0]
            title={
                'same_origin_batch_roast':f'Roast comparison · {first["origin"]} · {first["batch"]}',
                'same_origin_roast_cross_batch':f'Cross-batch · {first["origin"]} · {ROAST_NAMES[first["level"]]}',
                'roast_t0':f'Roast comparison ΔADC @t0 · {first["origin"]} · {first["batch"]}',
            }[kind]+f' | {SENSOR_LABELS[sensor]}'
            plot_compare(entries,sensor,path,title,kind)
        names=[r['filename'] for r in entries]
        plots.append({'family':kind,'group':group,'sensor':sensor,
                      'plot_path':str(path.resolve()),
                      'input_count':len(entries),'input_filenames':' | '.join(names),
                      'normalized_t0':kind=='roast_t0'})
        for rec in entries:
            series.append({'family':kind,'group':group,'sensor':sensor,
                           'filename':rec['filename'],'sha256':rec['sha256'],
                           't0_adc':float(rec['data'][sensor].iloc[rec['t0_index']]),
                           'min_adc':float(rec['data'][sensor].min()),
                           'max_adc':float(rec['data'][sensor].max()),
                           'mean_adc':float(rec['data'][sensor].mean())})

    for rec in records:
        for sensor in ADC_COLS:
            # Two recordings of same sample/batch remain distinguishable.
            emit('per_batch',sensor,
                 f'{Path(rec["filename"]).stem}__{sensor}.png',
                 rec['filename'],[rec])
    for (origin,batch),entries in by_roast.items():
        for sensor in ADC_COLS:
            emit('same_origin_batch_roast',sensor,f'{origin}_{batch}__{sensor}.png',
                 f'{origin}_{batch}',entries)
            emit('roast_t0',sensor,f'{origin}_{batch}__{sensor}_t0.png',
                 f'{origin}_{batch}',entries)
    for (origin,level),entries in by_batch.items():
        for sensor in ADC_COLS:
            emit('same_origin_roast_cross_batch',sensor,
                 f'{origin}_{ROAST_NAMES[level]}__{sensor}.png',
                 f'{origin}_{ROAST_NAMES[level]}',entries)

    expected={
        'per_batch':len(records)*len(ADC_COLS),
        'same_origin_batch_roast':len(by_roast)*len(ADC_COLS),
        'same_origin_roast_cross_batch':len(by_batch)*len(ADC_COLS),
        'roast_t0':len(by_roast)*len(ADC_COLS),
    }
    counts=Counter(p['family'] for p in plots)
    assert all(counts[kind]==n for kind,n in expected.items()),(counts,expected)
    write_rows(out/'plot_index.csv',plots,
               ['family','group','sensor','plot_path','input_count','input_filenames','normalized_t0'])
    write_rows(out/'series_index.csv',series,
               ['family','group','sensor','filename','sha256','t0_adc','min_adc','max_adc','mean_adc'])
    write_rows(out/'input_provenance.csv',provenance,
               ['filename','sample','batch','origin','sha256','csv_path','rows','cycles',
                'initial_purging_samples','initial_collecting_samples','t0_timestamp_ms',
                't0_index_zero_based'])
    grouping_rows=[{'family':'roast_same_origin_batch','group':f'{o}_{b}',
                    'files':' | '.join(r['filename'] for r in items),
                    'records':len(items)} for (o,b),items in by_roast.items()]
    grouping_rows += [{'family':'same_origin_roast_cross_batch',
                       'group':f'{o}_{ROAST_NAMES[l]}',
                       'files':' | '.join(r['filename'] for r in items),
                       'records':len(items)} for (o,l),items in by_batch.items()]
    write_rows(out/'comparison_groups.csv',grouping_rows,
               ['family','group','files','records'])
    summary={
        'audit_manifest':str((audit_dir/'audit_manifest.json').resolve()),
        'audited_valid_input_csv':len(records),
        'sensor_count':len(ADC_COLS),'sensors':list(ADC_COLS),
        'plots_by_family':expected,'total_plots':sum(expected.values()),
        'roast_comparison_groups':len(by_roast),'cross_batch_groups':len(by_batch),
        'files_excluded_from_69_audit':69-len(records) if only_records is None else None,
        'normalization':'ADC(t)-ADC(t0); t0=last sensor sample of cycle 1 purging (sample_idx 25), just BEFORE t26 first collecting sample. Per-CSV anchor, no smoothing/interpolation/resampling.',
        'time_axis':'based on original firmware timestamp milliseconds; per-CSV alignment',
        'source_data_edited':False,
        'cross_recording_caution':'Different E-Nose instruments / specimens cannot be assumed identical; colors are roast/batch group labels, not statistical significance.',
    }
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    explanations=['# Plot 30 siklus — hanya dataset VALID hasil audit','',
                  f'Input: `{audit_dir}` (salinan 01_VALID_30_SIKLUS, SHA256 diperiksa)',
                  f'Dataset: **{len(records)}** / 69 diaudit; grafik: **{sum(expected.values())}**.',
                  '', '## Empat jenis grafik','']
    for kind,folder in DIRS.items():
        explanations.append(f'- `{folder}/`: **{expected[kind]}** PNG ({len(ADC_COLS)} ADC per grup)')
    explanations += ['',
        '## Metode dan interpretasi',
        '- Setiap dataset valid: 900 baris, 30 siklus, 25 purging dan 5 collecting per siklus, diperiksa melalui laporan audit dan SHA256.',
        '- Sumbu X: detik dihitung dari `timestamp` firmware masing-masing CSV, **bukan tanggal absolut**.',
        '- Area jingga samar: interval collecting nominal 5 detik tiap 30 detik. Tanpa smoothing/interpolasi/resampling.',
        '- Warna Light=biru, Medium=oranye, Dark=merah pada grafik perbandingan roasting.',
        '- Normalisasi: nilai sensor dikurangi ADC di akhir purging siklus pertama (indeks sampel 25). Sampel collecting pertama adalah **t26** setelah 25 detik purging. Titik acuan ditandai t0=0.',
        '- Semua 900 sampel dipertahankan dalam grafik normalisasi; 24 sampel purging awal tampak pada waktu negatif.',
        '- Jika dua roast tidak tersedia dalam origin dan batch sama, **tidak dibuat grafik roast kosong** dan tidak dipaksakan mencampur batch.',
        '- Jika satu roast pada satu origin hanya memiliki satu batch, tidak dipaksakan membuat cross-batch.',
        '- Rekaman ulang `M-TEM_B62.csv` dan `M-TEM_B62_20261019_175906.csv` adalah dua CSV berbeda dan keduanya dilabel jelas pada cross-batch; belum terbukti spesimen/alat sama.',
        '- Hasil adalah grafik eksploratif. Identitas alat fisik / kesetaraan spesimen belum diverifikasi lintas CSV.',
        '', '## Indeks dan provenance','',
        '- `plot_index.csv`: semua plot dan input CSV masing-masing.',
        '- `input_provenance.csv`: SHA256, metadata, waktu t0 dari 38 file.',
        '- `series_index.csv`: ringkasan ADC dan titik t0 per kurva.',
        '- `comparison_groups.csv`: grup perbandingan yang benar-benar tersedia.',
        '', '## Grup roast dalam origin dan batch sama', '']
    for (o,b),items in by_roast.items():
        explanations.append('- '+o+' '+b+': '+', '.join(r['filename'] for r in items))
    explanations += ['', '## Grup cross-batch dengan origin dan roast sama', '']
    for (o,l),items in by_batch.items():
        explanations.append('- '+o+' '+ROAST_NAMES[l]+': '+', '.join(r['filename'] for r in items))
    (out/'README.md').write_text('\n'.join(explanations)+'\n',encoding='utf-8')
    build_gallery(out,plots)
    return summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--audit-dir',type=Path,default=AUDIT,
                        help='Folder hasil audit yang berisi audit_manifest.json dan 01_VALID_30_SIKLUS')
    parser.add_argument('--out',type=Path,default=OUT,
                        help='New output folder; must NOT already exist')
    args=parser.parse_args()
    summary=run(args.audit_dir.resolve(),args.out.resolve())
    print(json.dumps(summary,indent=2,ensure_ascii=False))


if __name__=='__main__':
    main()
