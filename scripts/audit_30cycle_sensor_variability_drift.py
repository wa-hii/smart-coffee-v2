"""Read-only quantitative E-Nose 30-cycle drift, variation, outlier audit.

All CSVs in audited valid archive are revalidated. Every output measurement is
computed at the recording level, not by treating cycles as independent runs.
Pairwise same-roast/same-origin repeatability uses unique batch IDs only.
Flags are *investigation candidates*, never an automatic declaration that a
physically acquired sample is wrong or that an AI model will classify it.
"""

from __future__ import annotations

import argparse
from collections import Counter, defaultdict
from datetime import datetime
import json
from pathlib import Path

import numpy as np
import pandas as pd

from acquisition_schema import ADC_COLS
from audit_dataset_30_siklus import audit_one,categorize
from merge_new_30_siklus_audit import checksum,signal_fingerprint,OUTPUT

ROOT=Path(__file__).resolve().parents[1]
SOURCE=OUTPUT/'01_VALID_GABUNGAN'
OUT=ROOT/'results/sensor_drift_variability_audit_20261023'
ORIGINS_LMD=['CAT','GAW','GRB','MING','TEM','TOR']
TARGET={(o,lev) for o in ORIGINS_LMD for lev in ('light','medium','dark')}
TARGET |= {('RAT','dark'),('MUK','medium'),('GAY','light')}


def robust_z(s:pd.Series)->pd.Series:
    """MAD-based z. NaN when MAD vanishes (do not amplify quantization)."""
    med=float(s.median())
    mad=float((s-med).abs().median())
    if mad<=1e-9:
        return pd.Series(np.zeros(len(s)),index=s.index,dtype=float)
    return 0.67448975*(s-med)/mad


def between_within(rows:pd.DataFrame,field:str)->dict:
    """Three-class descriptive effect; avoid treating cycles as replicates."""
    arrays=[x[field].to_numpy(dtype=float) for _,x in rows.groupby('roast')]
    if len(arrays)<3 or min(map(len,arrays))<3:
        return {}
    total=np.concatenate(arrays)
    grand=float(total.mean())
    between=float(sum(len(a)*(float(a.mean())-grand)**2 for a in arrays))
    within=float(sum(np.sum((a-a.mean())**2) for a in arrays))
    return {'between_within_ratio':between/(within+1e-9),
            'eta_squared':between/(within+between+1e-9),
            'roast_means':{name:float(g[field].mean()) for name,g in rows.groupby('roast')}}


def analyze(source:Path,out:Path):
    if out.exists():
        raise FileExistsError('Refusing to overwrite existing audit: '+str(out))
    files=sorted(source.glob('*.csv'))
    if not files:
        raise ValueError('No source CSV in '+str(source))
    records=[];sens=[];cycles=[];seen_sha={};seen_signal={};issues=[]
    for file in files:
        sha=checksum(file)
        a,_=audit_one(file,sha)
        if categorize(a)!='VALID':
            issues.append((file.name,a['anomalies']))
            continue
        fingerprint=signal_fingerprint(file)
        if sha in seen_sha or fingerprint in seen_signal:
            issues.append((file.name,'DUPLICATE_WITHIN_VALID_POOL'))
            continue
        seen_sha[sha]=file.name;seen_signal[fingerprint]=file.name
        df=pd.read_csv(file,low_memory=False)
        sample=a['sample_ids'];level=sample[0];origin=sample.split('-',1)[-1]
        roast={'L':'light','M':'medium','D':'dark'}[level]
        batch=a['batch_ids']
        # One CSV=one run. Data already validated as 30x(25 purge+5 collect).
        T=df['temperature'].to_numpy(dtype=float)
        H=df['humidity'].to_numpy(dtype=float)
        base={'filename':file.name,'origin':origin,'roast':roast,'batch':batch,
              'sha256':sha,'signal_sha256':fingerprint,
              'temperature_mean':float(np.nanmean(T)) if np.isfinite(T).any() else np.nan,
              'temperature_change':float(T[-1]-T[0]) if np.isfinite([T[0],T[-1]]).all() else np.nan,
              'humidity_mean':float(np.nanmean(H)) if np.isfinite(H).any() else np.nan,
              'humidity_change':float(H[-1]-H[0]) if np.isfinite([H[0],H[-1]]).all() else np.nan,
              'temp_missing':int(np.count_nonzero(~np.isfinite(T))),
              'humidity_missing':int(np.count_nonzero(~np.isfinite(H)))}
        records.append(base)
        for sensor in ADC_COLS:
            vals=df[sensor].to_numpy(dtype=float).reshape(30,30)
            tail=vals[:,20:25]
            collect=vals[:,25:30]
            purge_tail=np.median(tail,axis=1)
            response=collect.mean(axis=1)-purge_tail
            span_cycle=collect.max(axis=1)-collect.min(axis=1)
            noise=np.std(tail,axis=1,ddof=1)
            first_baseline=float(np.median(purge_tail[:5]))
            end_baseline=float(np.median(purge_tail[-5:]))
            baseline_drift=end_baseline-first_baseline
            t0=float(vals[0,24])
            mean_abs_response=float(np.median(abs(response)))
            sensor_rec={**{k:base[k] for k in ('filename','origin','roast','batch')},
                'sensor':sensor,
                'adc_t0':t0,
                'adc_min':float(vals.min()),'adc_max':float(vals.max()),
                'adc_overall_mean':float(vals.mean()),
                'adc_full_range':float(np.ptp(vals)),
                'baseline_first5':first_baseline,'baseline_last5':end_baseline,
                'baseline_drift':baseline_drift,
                'baseline_drift_abs':abs(baseline_drift),
                'baseline_drift_per_cycle':float(np.polyfit(np.arange(1,31),purge_tail,1)[0]),
                'baseline_cycle_range':float(np.ptp(purge_tail)),
                'baseline_cycle_sd':float(np.std(purge_tail,ddof=1)),
                'response_mean':float(response.mean()),
                'response_median':float(np.median(response)),
                'response_abs_median':mean_abs_response,
                'response_cycle_sd':float(np.std(response,ddof=1)),
                'response_cycle_iqr':float(np.percentile(response,75)-np.percentile(response,25)),
                'response_first5':float(np.median(response[:5])),
                'response_last5':float(np.median(response[-5:])),
                'response_change_firstlast':float(np.median(response[-5:])-np.median(response[:5])),
                'response_early_late_abs':abs(float(np.median(response[-5:])-np.median(response[:5]))),
                'response_positive_fraction':float(np.mean(response>0)),
                'response_signal_to_purge_noise':float(mean_abs_response/(np.median(noise)+1)),
                'drift_to_response_ratio':float(abs(baseline_drift)/(mean_abs_response+1)),
                'drift_to_baseline_pct':float(abs(baseline_drift)/(abs(first_baseline)+1)*100),
                'noise_median_purge_tail':float(np.median(noise)),
                'collecting_intraphase_median_range':float(np.median(span_cycle)),
                'adc_clip_fraction':float(np.mean((vals<=1)|(vals>=32766))),
                't0norm_collect_mean':float(np.mean(collect)-t0),
                't0norm_end_adc':float(vals[-1,-1]-t0),
            }
            sens.append(sensor_rec)
            for cy in range(30):
                cycles.append({'filename':file.name,'origin':origin,'roast':roast,'batch':batch,
                    'sensor':sensor,'cycle':cy+1,'purge_tail_median':float(purge_tail[cy]),
                    'collect_mean':float(collect[cy].mean()),
                    'phase_contrast':float(response[cy]),
                    'noise_purge_tail':float(noise[cy])})
    if issues:
        raise RuntimeError('Audit failed, no outputs generated: '+str(issues[:15]))
    rec=pd.DataFrame(records)
    ss=pd.DataFrame(sens)
    cc=pd.DataFrame(cycles)
    # Only *one* representative recording per origin/roast/batch for
    # repeatability comparisons (time-stamped repeat is still documented).
    rec['is_primary_batch']=~rec.duplicated(['origin','roast','batch'])
    selected=set(rec.loc[rec.is_primary_batch,'filename'])
    ss['is_primary_batch']=ss.filename.isin(selected)
    p=ss[ss.is_primary_batch].copy()
    p['z_response_peer']=np.nan
    p['z_baseline_peer']=np.nan
    p['z_abs_drift_peer']=np.nan
    p['z_temp_peer']=np.nan
    p['z_hum_peer']=np.nan
    for (_,_,sensor),group in p.groupby(['origin','roast','sensor']):
        if len(group)<4:continue
        for field,target in [('response_mean','z_response_peer'),
                             ('baseline_first5','z_baseline_peer'),
                             ('baseline_drift_abs','z_abs_drift_peer')]:
            p.loc[group.index,target]=robust_z(group[field])
    # Threshold >=3 sensors at very high MAD distance, or broad drift
    # dominance, should trigger *inspection*, not absolute exclusion.
    p['flag_response_peer']=p.z_response_peer.abs()>=3.5
    p['flag_baseline_peer']=p.z_baseline_peer.abs()>=3.5
    p['flag_drift_peer']=p.z_abs_drift_peer>=3.5
    p['flag_drift_dominant']=p.drift_to_response_ratio>=3
    p['flag_weak_response']=p.response_signal_to_purge_noise<1.2
    p['flag_saturated']=p.adc_clip_fraction>0.01
    p['flag_early_late_change']=p.response_early_late_abs>np.maximum(p.response_abs_median*2,10)

    status=[]
    for row in rec.to_dict('records'):
        fs=p[p.filename==row['filename']]
        reasons=[]
        if not row['is_primary_batch']:
            status.append({**row,'review_level':'KONFIRMASI_REPLIKASI_BATCH',
                          'reasons':'Batch identik dengan run lain (konten berbeda): cek alat/spesimen/sesi sebelum training',
                          'response_outlier_sensors':0,'baseline_outlier_sensors':0,
                          'drift_outlier_sensors':0,'drift_dominant_sensors':0,
                          'saturated_sensors':0,'weak_response_sensors':0})
            continue
        response_out=int(fs.flag_response_peer.sum())
        baseline_out=int(fs.flag_baseline_peer.sum())
        drift_out=int(fs.flag_drift_peer.sum())
        dominant=int(fs.flag_drift_dominant.sum())
        saturated=int(fs.flag_saturated.sum())
        weak=int(fs.flag_weak_response.sum())
        earlylate=int(fs.flag_early_late_change.sum())
        env_temp=abs(row['temperature_change']) if pd.notna(row['temperature_change']) else np.nan
        env_rh=abs(row['humidity_change']) if pd.notna(row['humidity_change']) else np.nan
        if saturated:
            reasons.append(f'{saturated} sensor ADC dekat batas 0/32767 pada >1% titik')
        if response_out>=3:
            reasons.append(f'{response_out} sensor respons berbeda dari pengambilan sebaya (|robust z|≥3.5)')
        if baseline_out>=3:
            reasons.append(f'{baseline_out} sensor baseline awal outlier (|robust z|≥3.5)')
        if drift_out>=3:
            reasons.append(f'{drift_out} sensor drift abnormal vs pengambilan sebaya (robust z≥3.5)')
        if dominant>=5:
            reasons.append(f'{dominant} sensor drift baseline >3× respons khas collecting')
        if earlylate>=5:
            reasons.append(f'{earlylate} sensor mengalami perubahan respons awal–akhir >2× median |respons| dan >10 ADC')
        if pd.notna(env_temp) and env_temp>=4:
            reasons.append(f'Perubahan suhu {env_temp:.1f}°C selama satu run')
        if pd.notna(env_rh) and env_rh>=12:
            reasons.append(f'Perubahan kelembapan {env_rh:.1f} poin selama satu run')
        if row['temp_missing'] or row['humidity_missing']:
            reasons.append(f'Pembacaan suhu/RH hilang {row["temp_missing"]}/{row["humidity_missing"]} baris')
        severe=bool(saturated or response_out>=5 or drift_out>=5 or
                    (dominant>=7 and (response_out>=2 or baseline_out>=2)))
        review=bool(reasons)
        status.append({**row,
            'review_level':'PRIORITAS_UJI_ULANG' if severe else 'PERLU_REVIEW' if review else 'TIDAK_ADA_FLAG_BESAR',
            'reasons':' | '.join(reasons),
            'response_outlier_sensors':response_out,
            'baseline_outlier_sensors':baseline_out,
            'drift_outlier_sensors':drift_out,
            'drift_dominant_sensors':dominant,
            'early_late_changed_sensors':earlylate,
            'saturated_sensors':saturated,
            'weak_response_sensors':weak})
    flagged=pd.DataFrame(status)

    groups=[]
    for (origin,roast,sensor),g in p.groupby(['origin','roast','sensor']):
        n=len(g)
        mean=float(g.response_mean.mean())
        sd=float(g.response_mean.std(ddof=1)) if n>1 else np.nan
        med=float(g.response_mean.median())
        mad=float((g.response_mean-med).abs().median())
        groups.append({'origin':origin,'roast':roast,'sensor':sensor,'n_batch_unique':n,
            'response_mean_among_batches':mean,
            'response_sd_among_batches':sd,
            'response_cv_pct':100*sd/(abs(mean)+1) if np.isfinite(sd) else np.nan,
            'response_robust_rsd_pct':100*1.4826*mad/(abs(med)+1),
            'response_abs_median':float(g.response_abs_median.median()),
            'mean_abs_drift':float(g.baseline_drift_abs.mean()),
            'median_abs_drift':float(g.baseline_drift_abs.median()),
            'median_drift_to_response':float(g.drift_to_response_ratio.median()),
            'median_phase_response_to_noise':float(g.response_signal_to_purge_noise.median()),
            'median_cycle_response_sd':float(g.response_cycle_sd.median()),
            'median_baseline_cycle_sd':float(g.baseline_cycle_sd.median()),
            'fraction_positive_phase_response':float((g.response_mean>0).mean())})
    group_df=pd.DataFrame(groups)

    candidates=[]
    for origin in ORIGINS_LMD:
        for sensor in ADC_COLS:
            sub=p[(p.origin==origin)&(p.sensor==sensor)]
            effect=between_within(sub,'response_mean')
            if not effect:continue
            normalized=between_within(sub,'t0norm_collect_mean')
            candidates.append({'origin':origin,'sensor':sensor,
                'response_between_within_ratio':effect['between_within_ratio'],
                'response_eta_squared':effect['eta_squared'],
                't0norm_between_within_ratio':normalized.get('between_within_ratio',np.nan),
                't0norm_eta_squared':normalized.get('eta_squared',np.nan),
                'overall_median_drift_response_ratio':float(sub.drift_to_response_ratio.median()),
                'overall_median_response_noise_ratio':float(sub.response_signal_to_purge_noise.median()),
                'median_within_batch_cv_pct':float(group_df[(group_df.origin==origin)&(group_df.sensor==sensor)].response_cv_pct.median()),
                'roast_level_means':json.dumps(effect['roast_means'],ensure_ascii=False),
                'n_recordings':len(sub)})
    score=pd.DataFrame(candidates)
    # Auxiliary *exploratory* across-origin indicators, not a pre-trained
    # feature selector. Avoid optimizing for these metrics on held-out data.
    ranked=(score.groupby('sensor',as_index=False)
            .agg(origins=('origin','nunique'),
                 median_roast_separation_ratio=('response_between_within_ratio','median'),
                 median_t0norm_separation_ratio=('t0norm_between_within_ratio','median'),
                 median_drift_response_ratio=('overall_median_drift_response_ratio','median'),
                 median_response_noise_ratio=('overall_median_response_noise_ratio','median'),
                 median_within_class_cv_pct=('median_within_batch_cv_pct','median')))
    ranked=ranked.sort_values('median_roast_separation_ratio',ascending=False)

    # Single summary plot: drift/response heatmap, consistent sensor scale,
    # non-destructive, one value per source recording aggregated by median.
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    heat=p.groupby(['origin','sensor']).drift_to_response_ratio.median().unstack('sensor').reindex(columns=ADC_COLS)
    fig,ax=plt.subplots(figsize=(12.3,5.6),dpi=135)
    z=np.clip(np.log10(1+heat.to_numpy(dtype=float)),0,np.log10(21))
    im=ax.imshow(z,aspect='auto',cmap='magma',vmin=0,vmax=np.log10(21))
    ax.set_xticks(range(len(ADC_COLS)),[s.replace('adc_','').upper() for s in ADC_COLS],rotation=42,ha='right',fontsize=9)
    ax.set_yticks(range(len(heat.index)),heat.index,fontsize=10)
    ax.set_title('Median |drift baseline awal→akhir| / median |respons collecting| · per origin & sensor',fontsize=10.7)
    for i in range(len(heat.index)):
        for j in range(len(ADC_COLS)):
            ax.text(j,i,f'{heat.iloc[i,j]:.1f}',ha='center',va='center',fontsize=8,
                    color='white' if z[i,j]>.8 else '#171717')
    cb=fig.colorbar(im,ax=ax,shrink=.87)
    cb.set_label('log10(1+rasio), color scale capped 20',fontsize=9)
    fig.subplots_adjust(left=.11,right=.98,top=.91,bottom=.22)

    out.mkdir(parents=True)
    fig.savefig(out/'drift_to_response_heatmap.png',dpi=145,facecolor='white')
    plt.close(fig)
    for name,table in [('sensor_per_recording.csv',ss),('cycle_per_sensor.csv',cc),
            ('sensor_primary_batch_with_outlier_flags.csv',p),
            ('recording_retest_priority.csv',flagged),
            ('repeatability_per_origin_roast_sensor.csv',group_df),
            ('roast_separation_exploratory.csv',score),
            ('sensor_exploratory_ranking.csv',ranked)]:
        table.to_csv(out/name,index=False,encoding='utf-8-sig')
    source_manifest=[{'filename':r['filename'],'sha256':r['sha256'],'sample_id':r['origin']+'/'+r['roast'],
                      'batch':r['batch']} for r in records]
    summary={
        'created_at':datetime.now().isoformat(timespec='seconds'),
        'source':str(source.resolve()),'original_csv_count':len(files),
        'audited_valid_csv':len(records),
        'unique_origin_roast_batch_recordings':int(rec.is_primary_batch.sum()),
        'repeated_same_batch_recordings':int((~rec.is_primary_batch).sum()),
        'sensor_channels':len(ADC_COLS), 'sensor_rows':len(ss),
        'cycle_sensor_rows':len(cc),
        'records_by_review_level':flagged.review_level.value_counts().to_dict(),
        'thresholds_are_screening_not_definitive':'MAD outlier >=3.5; >=3 channels or drift dominance >=5, no automatic invalidation; see README',
        'device_provenance':'No device ID field in CSV. Device/lot/date/external clean-air baseline not independently established.',
        'input_unchanged':True,
        'source_hashes':source_manifest}
    (out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    (out/'README.md').write_text(
        '# Audit variasi, respons collecting, dan drift 30 siklus\n\n'
        'Seluruh 112 CSV valid dibaca ulang tanpa modifikasi. Per rekaman terdapat 30 siklus; '
        '30 siklus **bukan** 30 pengulangan independen.\n\n'
        '## Tabel utama\n\n'
        '- `recording_retest_priority.csv`: urutan flag yang perlu inspeksi / kandidat pengambilan ulang; **flag bukan bukti invalid**.\n'
        '- `sensor_per_recording.csv`: fitur/indikator setiap sensor dari setiap CSV.\n'
        '- `sensor_primary_batch_with_outlier_flags.csv`: flags dan robust z terhadap pengambilan origin+roast sejenis.\n'
        '- `repeatability_per_origin_roast_sensor.csv`: variasi antar-batch unik (CV dan robust RSD dapat tidak stabil jika rerata respons mendekati nol).\n'
        '- `cycle_per_sensor.csv`: 30 nilai respons collecting dan baseline purging masing-masing sensor/rekaman.\n'
        '- `roast_separation_exploratory.csv`: perbedaan rerata fitur antar-roasting / dalam-roasting untuk 6 origin dengan 3 roast.\n'
        '- `sensor_exploratory_ranking.csv`: agregasi antar-origin (bukan fitur/model terbaik teruji).\n'
        '- `drift_to_response_heatmap.png`: nilai median drift/response per origin+sensor (tampilan log10).\n\n'
        '## Definisi\n\n'
        '- Setiap siklus: purging 25 titik lalu collecting 5 titik.\n'
        '- Respons collecting siklus = mean(5 collecting) − median(5 titik purging terakhir).\n'
        '- Baseline tiap siklus = median(5 titik purging terakhir).\n'
        '- Drift run = median(baseline siklus 26–30) − median(baseline siklus 1–5).\n'
        '- Drift/respons = |drift| / (median(|respons collecting 30 siklus|)+1).\n'
        '- CV antar-batch dihitung dari respons mean per *rekaman unik*, bukan dari semua 900 titik.\n'
        '- Robust z = 0.67449 × (x−median grup) / MAD (jika MAD nol, tidak ada flag).\n'
        '- Prioritas uji ulang bersifat konservatif: sensor saturasi, >=5 kanal ekstrem vs peer, >=5 kanal drift ekstrem, '
        'atau drift dominan >=7 sensor disertai anomali antar-peer. Review mencakup >=3 kanal anomali peer, drift dominan >=5, '
        'respons awal–akhir berubah di >=5 sensor, atau suhu/RH berubah >=4 C/12 poin.\n'
        '- Data dengan origin+roast+batch sama tetapi isi berbeda ditandai sebagai perlu konfirmasi independensi; '
        'hanya satu representatif dipakai untuk menghitung repeatability.\n'
        '- Sensor/rekaman tanpa respons kuat **bukan** otomatis alat rusak; sensitivitas terhadap kopi mungkin kecil.\n'
        '- Tidak bisa membedakan drift sensor fisik vs volatilitas kopi/chamber vs alat berbeda vs suhu/RH dari CSV saja.\n'
        '- Saran uji ulang harus dikonfirmasi dengan run udara bersih, satu alat tetap, urutan sampel diacak, kondisi lingkungan, '
        'kontrol residu chamber, dan minimal lima preparasi sampel independen per kelas.\n',encoding='utf-8')
    if any(checksum(source/r['filename'])!=r['sha256'] for r in records):
        raise RuntimeError('Source checksum changed while auditing')
    print('AUDIT_COMPLETE',json.dumps({k:v for k,v in summary.items() if k!='source_hashes'},ensure_ascii=False),flush=True)
    print('RETEST_PRIORITY_TOP',flagged[flagged.review_level!='TIDAK_ADA_FLAG_BESAR'].sort_values(
        ['review_level','response_outlier_sensors','drift_outlier_sensors'],ascending=[True,False,False])
          [['filename','review_level','reasons']].head(25).to_json(orient='records',force_ascii=True),flush=True)
    print('SENSOR_RANKING',ranked.to_json(orient='records',force_ascii=True),flush=True)
    return summary


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('--source',type=Path,default=SOURCE)
    ap.add_argument('--out',type=Path,default=OUT)
    args=ap.parse_args()
    analyze(args.source.resolve(),args.out.resolve())


if __name__=='__main__':main()
