"""Descriptive B36 signal diagnostics; do not train/select classifiers."""
from pathlib import Path
import json
import numpy as np
import pandas as pd
from scipy.stats import kruskal
from acquisition_schema import ADC_COLS

ROOT=Path(__file__).resolve().parents[1]
FILES=ROOT/'results/local_b36_b37_audit_20261016/file_quality.csv'
OUT=ROOT/'results/b36_signal_provenance_20261016'

def main():
    if OUT.exists():raise FileExistsError('No overwrite of existing analysis')
    inventory=pd.read_csv(FILES)
    inventory=inventory[inventory.batch.eq('B36')].copy()
    assert len(inventory)==18 and inventory.canonical_pass.all()
    records=[]
    for f in inventory.itertuples(index=False):
        raw=pd.read_csv(ROOT/'data/raw'/f.file)
        for run in range(1,6):
            group=raw[raw.run_id.eq(run)]
            purge=group[group.phase.eq('purging')]
            collect=group[group.phase.eq('collecting')]
            assert len(purge)>=25 and len(collect)>=5
            for ch in ADC_COLS:
                baseline=float(purge[ch].tail(5).median())
                resp=float(collect[ch].mean())
                records.append(dict(file=f.file,roast_ui=f.roast_ui,origin_ui=f.origin_ui,
                                    cycle=run,channel=ch,purge_baseline=baseline,
                                    collect_mean=resp,delta=resp-baseline,
                                    relative_delta=(resp-baseline)/max(abs(baseline),1),
                                    purging_n=len(purge),collecting_n=len(collect)))
    frame=pd.DataFrame(records)
    per_file=frame.groupby(['file','roast_ui','origin_ui','channel'],as_index=False).agg(
        relative_mean=('relative_delta','mean'),relative_std=('relative_delta','std'),
        abs_response_mean=('delta','mean'),baseline_start=('purge_baseline','first'),
        baseline_end=('purge_baseline','last'))
    per_file['cycle_cv_percent']=100*per_file.relative_std/per_file.relative_mean.abs().replace(0,np.nan)
    per_file['baseline_drift_percent']=100*(per_file.baseline_end-per_file.baseline_start)/per_file.baseline_start.abs().clip(lower=1)
    # Descriptive file-level differences only; no p-values or inference on independent specimens.
    roast=per_file.groupby(['roast_ui','channel'],as_index=False).agg(
        file_count=('file','size'),median_relative_response=('relative_mean','median'),
        median_cycle_cv_percent=('cycle_cv_percent','median'),
        median_baseline_drift_percent=('baseline_drift_percent','median'))
    cross=per_file.groupby('channel',as_index=False).agg(
        median_cycle_cv_percent=('cycle_cv_percent','median'),
        median_abs_baseline_drift_percent=('baseline_drift_percent',lambda x:float(x.abs().median())),
        max_abs_baseline_drift_percent=('baseline_drift_percent',lambda x:float(x.abs().max())))
    # Canonical fields do not contain physically attestable evidence for provenance.
    provenance=inventory[['file','sha256','roast_ui','origin_ui','sample_code']].copy()
    for field in ['physical_specimen_id','coffee_lot_id','roast_batch_physical_id',
                  'operator_session_id','reference_roast_evidence','reference_origin_evidence',
                  'independent_reviewer_signoff']:
        provenance[field]='NOT_VERIFIED'
    provenance['evidence_status']='HOLD_EXTERNAL_PROVENANCE'
    summary={
      'status':'DESCRIPTIVE_SIGNAL_QC_COMPLETE_PROVENANCE_NOT_VERIFIED',
      'coffee_files':len(inventory),'roast_ui_counts':inventory.roast_ui.value_counts().sort_index().to_dict(),
      'sensor_channels':len(ADC_COLS),'cycles_per_file':5,
      'cycle_channel_rows':len(frame),
      'physical_specimens_verified':0,'independent_roast_labels_verified':0,
      'independent_origin_labels_verified':0,
      'notes':['Cycle CV is unstable when signed mean response is near zero; review absolute response too.',
               'Responses are descriptive ADC-based signals, not validated physical analyte measurements.',
               'Repeated cycles from one file are not independent coffee specimens.',
               'Per-roast comparisons are exploratory and confounded by origin, lot, session and drift.',
               'No classifier fitting, test score, model selection or prospective blind-test claim.'],
      'blind_test_approved':False,'model_promotion_allowed':False}
    OUT.mkdir(parents=True)
    frame.to_csv(OUT/'cycle_responses.csv',index=False)
    per_file.to_csv(OUT/'per_file_repeatability_drift.csv',index=False)
    roast.to_csv(OUT/'roast_descriptive_comparison.csv',index=False)
    cross.to_csv(OUT/'channel_quality_summary.csv',index=False)
    provenance.to_csv(OUT/'provenance_review.csv',index=False)
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))
    print('CHANNEL SUMMARY');print(cross.to_string(index=False))
    print('ROAST SUMMARY');print(roast.to_string(index=False))

if __name__=='__main__':main()
