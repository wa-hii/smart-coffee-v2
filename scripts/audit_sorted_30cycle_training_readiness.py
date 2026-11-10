"""Read-only QA and AI-readiness screening of data/dataset sorting.

The human labels kept/maybe/excluded are provenance, not ground truth data
quality. No source CSV is rewritten, interpolated, normalized, or dropped.
One file = one recording = one unit for learning/evaluation.
"""
from __future__ import annotations

from collections import Counter, defaultdict
import json
from pathlib import Path
import re

import numpy as np
import pandas as pd

from audit_dataset_30_siklus import audit_one,categorize
from merge_new_30_siklus_audit import checksum,signal_fingerprint

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/'data/dataset sorting'
OLD=ROOT/'results/combined_30cycle_B70_B75_20261031/01_VALID_GABUNGAN'
OLD_PROV=ROOT/'results/combined_30cycle_B70_B75_20261031/accepted_provenance.csv'
OUT=ROOT/'results/dataset_sorting_readiness_20261110'
ADC=['adc_tgs822','adc_mq135','adc_mq3','adc_tgs2611','adc_tgs2620',
     'adc_tgs2600','adc_tgs2602','adc_mq8','adc_tgs813','adc_tgs816']


def scan():
    if OUT.exists():raise FileExistsError('Refuse overwrite previous report: '+str(OUT))
    files=sorted(SOURCE.rglob('*.csv'))
    assert len(files)==366,len(files)
    previous=pd.read_csv(OLD_PROV).fillna('')
    previous_sha={x.sha256:(x.filename,x.source_type) for x in previous.itertuples()}
    old_quality={}
    old_signal={}
    for p in OLD.glob('*.csv'):
        old_signal[signal_fingerprint(p)]=p.name
    all_rows=[];sensor_rows=[];seensha={};seensignal={}
    for index,path in enumerate(files):
        parts=path.relative_to(SOURCE).parts
        if len(parts)!=3 or parts[0] not in ('a','b','c') or parts[1] not in ('kept','maybe','excluded'):
            raise ValueError('Unsupported cohort/status layout '+str(path))
        cohort,bucket,_=parts
        sha=checksum(path)
        audited,_=audit_one(path,sha)
        category=categorize(audited)
        sig=signal_fingerprint(path)
        dupsha=seensha.get(sha,'')
        dupsig=seensignal.get(sig,'')
        seensha.setdefault(sha,str(path.relative_to(SOURCE)))
        seensignal.setdefault(sig,str(path.relative_to(SOURCE)))
        source_match=previous_sha.get(sha)
        old_signal_match=old_signal.get(sig,'')
        quality={}
        if cohort=='b':
            source_meta=ROOT/'data/raw'/audited['batch_ids']/f'{path.stem}.quality.json'
            if source_meta.exists():
                quality=json.loads(source_meta.read_text(encoding='utf-8'))
        audit_reasons=list(audited['anomalies'])
        if quality:
            if quality.get('quality_status')!='validated_complete' or not quality.get('trainable_as_complete_30_cycle_dataset'):
                audit_reasons.append('QUALITY_JSON_INCOMPLETE')
            if quality.get('sample_id')!=audited['sample_ids'] or quality.get('batch_id')!=audited['batch_ids']:
                audit_reasons.append('QUALITY_JSON_METADATA_MISMATCH')
        elif cohort=='b':
            audit_reasons.append('QUALITY_JSON_NOT_FOUND_FOR_B')
        if '_INCOMPLETE' in path.name.upper():
            audit_reasons.append('FILENAME_MARKED_INCOMPLETE')
        valid=(category=='VALID' and not audit_reasons)
        label=audited['sample_ids']
        origin=label.split('-',1)[1] if '-' in label else ''
        roast=audited['roast_levels'].lower()
        row={
          'cohort':cohort,'sort_status':bucket,'filename':path.name,
          'relative_path':str(path.relative_to(SOURCE)),'origin':origin,'roast':roast,
          'sample_id':label,'batch':audited['batch_ids'],
          'n_rows':audited['rows'],'n_cycles':audited['cycles_detected'],
          'audit_category':category,'structurally_valid':valid,
          'audit_reasons':' | '.join(sorted(set(audit_reasons))),
          'sha256':sha,'signal_sha256':sig,
          'duplicate_sha_with_sorted':dupsha,'duplicate_signal_with_sorted':dupsig,
          'same_bytes_in_prior_valid':bool(source_match),
          'prior_source_type':source_match[1] if source_match else '',
          'same_signal_in_prior_valid':bool(old_signal_match),
          'prior_signal_file':old_signal_match,
          'receiver_quality_status':quality.get('quality_status','UNKNOWN'),
          'device_id':quality.get('device_id','UNKNOWN'),
          'source_path':str(path.resolve()),
        }
        if valid:
            data=pd.read_csv(path)
            row['temperature_mean']=float(data.temperature.mean())
            row['humidity_mean']=float(data.humidity.mean())
            row['temperature_span']=float(data.temperature.max()-data.temperature.min())
            row['humidity_span']=float(data.humidity.max()-data.humidity.min())
            for sensor in ADC:
                v=data[sensor].to_numpy(dtype=float).reshape(30,30)
                baseline=np.median(v[:,20:25],axis=1)
                response=v[:,25:30].mean(axis=1)-baseline
                amplitude=float(np.median(np.abs(response)))
                drift=float(np.median(baseline[-5:])-np.median(baseline[:5]))
                sensor_rows.append({'cohort':cohort,'sort_status':bucket,
                    'filename':path.name,'origin':origin,'roast':roast,'sensor':sensor,
                    'median_phase_response':float(np.median(response)),
                    'median_absolute_phase_response':amplitude,
                    'mean_phase_response':float(np.mean(response)),
                    'response_early_late':float(np.median(response[-5:])-np.median(response[:5])),
                    'baseline_first5':float(np.median(baseline[:5])),
                    'baseline_last5':float(np.median(baseline[-5:])),
                    'baseline_drift':drift,
                    'drift_response_ratio':abs(drift)/(amplitude+1),
                    'adc_fraction_near_rail':float(((v<=1)|(v>=32766)).mean()),
                    'collecting_weak_response':amplitude<=2,
                })
        all_rows.append(row)
        if (index+1)%60==0:print('SORT_AUDIT_PROGRESS',index+1,'/',len(files),flush=True)
    summary_df=pd.DataFrame(all_rows)
    sensors=pd.DataFrame(sensor_rows)
    summary_df['duplicate_origin_roast_batch']=summary_df.duplicated(['origin','roast','batch'],keep=False)
    # Independent counts explicitly exclude non-validated and duplicate batch IDs.
    eligible=summary_df[(summary_df.sort_status=='kept')&summary_df.structurally_valid].copy()
    eligible['primary_per_label_batch']=~eligible.duplicated(['origin','roast','batch'])
    eligible['no_duplicate_signal']=~eligible.duplicated('signal_sha256')
    primary=eligible[eligible.primary_per_label_batch&eligible.no_duplicate_signal].copy()
    matrix=summary_df.groupby(['cohort','sort_status','origin','roast']).agg(
        n_csv=('filename','size'),n_valid=('structurally_valid','sum'),
        n_unique_batch=('batch','nunique')).reset_index()
    train_matrix=(primary.groupby(['cohort','origin','roast']).size()
                  .rename('n_independent_label_batches').reset_index())
    env=summary_df[summary_df.structurally_valid].groupby(
        ['cohort','sort_status','roast'],as_index=False).agg(
        n=('filename','size'),temp_mean=('temperature_mean','mean'),
        temp_sd=('temperature_mean','std'),rh_mean=('humidity_mean','mean'),
        rh_sd=('humidity_mean','std'))
    drift=sensors.groupby(['cohort','sort_status','sensor'],as_index=False).agg(
        n=('filename','size'),median_abs_response=('median_absolute_phase_response','median'),
        median_drift_ratio=('drift_response_ratio','median'),
        pct_weak_resp=('collecting_weak_response','mean'),
        pct_adc_rail=('adc_fraction_near_rail',lambda x:float((x>0.01).mean())))
    quality_by_status=pd.crosstab(summary_df.sort_status,summary_df.audit_category)
    summary={
        'total_csv':len(files),
        'counts_by_cohort_status':{f'{a}/{b}':int(n) for (a,b),n in summary_df.groupby(['cohort','sort_status']).size().items()},
        'audit_categories':{k:int(v) for k,v in summary_df.audit_category.value_counts().items()},
        'sort_status_audit':quality_by_status.to_dict(),
        'kept_files':int((summary_df.sort_status=='kept').sum()),
        'kept_valid':len(eligible),'kept_unique_label_batch':len(primary),
        'maybe_valid':int(((summary_df.sort_status=='maybe')&summary_df.structurally_valid).sum()),
        'excluded_valid':int(((summary_df.sort_status=='excluded')&summary_df.structurally_valid).sum()),
        'distinct_sha':summary_df.sha256.nunique(),
        'distinct_signal_hash':summary_df.signal_sha256.nunique(),
        'duplicate_origin_roast_batch_count':int(summary_df.duplicate_origin_roast_batch.sum()),
        'matching_previous_valid_sha':int(summary_df.same_bytes_in_prior_valid.sum()),
        'matching_previous_valid_signal':int(summary_df.same_signal_in_prior_valid.sum()),
        'trainable_class_origin_coverage':train_matrix.to_dict('records'),
        'unknown_device_kept':int(((eligible.device_id=='UNKNOWN')).sum()),
        'source_untouched':True,
    }
    OUT.mkdir(parents=True)
    for name,d in [('all_csv_audit.csv',summary_df),('sensor_signal_metrics.csv',sensors),
                   ('class_distribution_all_status.csv',matrix),
                   ('kept_cohort_class_distribution.csv',train_matrix),
                   ('environment_by_cohort_status_roast.csv',env),
                   ('sensor_drift_by_cohort_status.csv',drift)]:
        d.to_csv(OUT/name,index=False,encoding='utf-8-sig')
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf8')
    print('SORT_AUDIT_RESULT',json.dumps({k:v for k,v in summary.items() if k not in ['sort_status_audit','trainable_class_origin_coverage']},ensure_ascii=True),flush=True)
    print('QUALITY_CROSSTAB',quality_by_status.to_string(),flush=True)
    print('TRAIN_MATRIX',train_matrix.to_string(index=False),flush=True)
    print('VALID_BUT_EXCLUDED',summary_df[(summary_df.sort_status=='excluded')&summary_df.structurally_valid][['cohort','filename']].head(10).to_dict('records'),flush=True)
    print('INVALID_BUT_KEPT',summary_df[(summary_df.sort_status=='kept')&~summary_df.structurally_valid][['cohort','filename','audit_reasons']].to_dict('records'),flush=True)
    return summary


if __name__=='__main__':scan()
