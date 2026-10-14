"""Read-only deep QC of imported B36/B37. Never train or select ML models."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
from acquisition_schema import ADC_COLS, CSV_COLUMNS
from validate_acquisition import validate_file, classify_rows

INPUT = ROOT / 'data/raw/irul_B36_B37'
MANIFEST = ROOT / 'data/analysis/irul_B36_B37_import_manifest.csv'
OLDER = ROOT / 'data/analysis/stage2_v2/file_manifest.csv'

def run():
    manifest = pd.read_csv(MANIFEST, dtype=str).fillna('')
    old = pd.read_csv(OLDER, dtype=str).fillna('')
    assert len(manifest) == 32 and not manifest['sha256'].duplicated().any()
    rows, cycles = [], []
    for rec in manifest.itertuples(index=False):
        p = INPUT / Path(rec.source_path).name
        assert p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest() == rec.sha256
        df = pd.read_csv(p)
        errors = validate_file(p)
        assert list(df.columns) == CSV_COLUMNS
        sensor, events, partial = classify_rows(df)
        s = df.loc[sensor].copy()
        base = rec.source_path.endswith('BASELINE_B36.csv') or rec.source_path.endswith('BASELINE_B37.csv')
        phasecounts = s.groupby(['run_id','phase']).size().to_dict()
        label = str(s['roast_level'].dropna().iloc[0]) if len(s) else ''
        origin = str(s['origin'].dropna().iloc[0]) if len(s) else ''
        sample = str(s['sample_id'].dropna().iloc[0]) if len(s) else ''
        allsensor = s[ADC_COLS].apply(pd.to_numeric,errors='coerce')
        t = pd.to_numeric(s['timestamp'],errors='coerce')
        diff = t.diff().dropna()
        duplicates = int(allsensor.duplicated().sum())
        rows.append({
            'file':p.name,'batch':'B36' if '_B36' in p.name else 'B37',
            'source_sha256':rec.sha256,'source_bytes':int(rec.byte_count),
            'control_baseline':base,'sample_id_ui':sample,'roast_ui':label,'origin_ui':origin,
            'canonical_valid':not errors,'validator_error_count':len(errors),'validator_errors':' | '.join(errors),
            'sensor_rows':len(s),'metadata_rows':int(events.sum()),'partial_rows':int(partial.sum()),
            'cycles':int(s['run_id'].nunique()),
            'purging_rows':int(s['phase'].eq('purging').sum()),
            'collecting_rows':int(s['phase'].eq('collecting').sum()),
            'adc_nan_cells':int(allsensor.isna().sum().sum()),
            'adc_zero_cells':int((allsensor==0).sum().sum()),
            'adc_saturation_cells':int((allsensor>=32767).sum().sum()),
            'adc_identical_full_sensor_rows':duplicates,
            'temp_valid_rows':int(pd.to_numeric(s['temperature'],errors='coerce').notna().sum()),
            'humidity_valid_rows':int(pd.to_numeric(s['humidity'],errors='coerce').notna().sum()),
            'timestamp_step_median_ms':float(diff.median()) if len(diff) else None,
            'timestamp_step_min_ms':float(diff.min()) if len(diff) else None,
            'timestamp_step_max_ms':float(diff.max()) if len(diff) else None,
            'historical_sha_collision':rec.sha256 in set(old.source_sha256),
            'physical_specimen_and_lot_verified':False,
            'eligible_for_independent_blind':False,
        })
        for cycle in range(1,6):
            a=s.loc[s.run_id==cycle]
            purge=a.loc[a.phase=='purging']; collect=a.loc[a.phase=='collecting']
            for channel in ADC_COLS:
                x=pd.to_numeric(purge[channel],errors='coerce')
                y=pd.to_numeric(collect[channel],errors='coerce')
                baseline=float(x.tail(5).median()) if len(x)>=5 else np.nan
                mean=float(y.mean()) if len(y) else np.nan
                cycles.append({'file':p.name,'batch':'B36' if '_B36' in p.name else 'B37',
                    'cycle':cycle,'channel':channel,'purge_n':len(purge),'collect_n':len(collect),
                    'purge_tail_baseline':baseline,'collect_mean':mean,
                    'delta_adc':mean-baseline,
                    'relative_delta':(mean-baseline)/max(abs(baseline),1)})
    files=pd.DataFrame(rows)
    cyc=pd.DataFrame(cycles)
    # Same batch baseline is control only, not an inferred negative class.
    for batch in ('B36','B37'):
        controls=cyc.loc[(cyc.batch==batch)&cyc.file.eq('BASELINE_'+batch+'.csv')]
        if len(controls)==50:
            reference=controls.groupby('channel')['purge_tail_baseline'].median()
            for channel,value in reference.items():
                mask=(cyc.batch==batch)&cyc.channel.eq(channel)
                cyc.loc[mask,'delta_baseline_from_batch_control']=cyc.loc[mask,'purge_tail_baseline']-value
    summary={
        'status':'B36_B37_DEEP_QC_DONE_BLIND_NOT_APPROVED',
        'source_branch':'origin/irul','source_commit':manifest.source_commit.iloc[0],
        'files':len(files),'B36':int(files.batch.eq('B36').sum()),'B37':int(files.batch.eq('B37').sum()),
        'baseline_controls':int(files.control_baseline.sum()),
        'coffee_ui_files':int((~files.control_baseline).sum()),
        'canonical_pass':int(files.canonical_valid.sum()),
        'canonical_hold':int((~files.canonical_valid).sum()),
        'held_filenames':files.loc[~files.canonical_valid,'file'].tolist(),
        'sensor_rows':int(files.sensor_rows.sum()),
        'phase_rows_purging':int(files.purging_rows.sum()),
        'phase_rows_collecting':int(files.collecting_rows.sum()),
        'files_missing_all_temp':int(files.temp_valid_rows.eq(0).sum()),
        'files_missing_all_humidity':int(files.humidity_valid_rows.eq(0).sum()),
        'historical_sha_collisions':int(files.historical_sha_collision.sum()),
        'source_file_sha_verified':True,
        'labels_verified':False,'physical_lot_independent':False,
        'blind_score_allowed':False,'model_promotion_allowed':False,
    }
    return files,cyc,summary

def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir',required=True,type=Path)
    dst=parser.parse_args().output_dir.resolve()
    if dst.exists() or dst==INPUT.resolve() or INPUT.resolve() in dst.parents:
        raise ValueError('Never overwrite data or earlier audit')
    files,cycles,summary=run()
    dst.mkdir(parents=True)
    files.to_csv(dst/'file_quality.csv',index=False)
    cycles.to_csv(dst/'cycle_channel_diagnostics.csv',index=False)
    (dst/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':
    main()
