"""Non-destructive QA checks for 30-cycle sensor variation/drift reports."""
from __future__ import annotations

from collections import Counter
import json

import numpy as np
import pandas as pd

from audit_30cycle_sensor_variability_drift import OUT,SOURCE,ADC_COLS,checksum


def main():
    summary=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    record=pd.read_csv(OUT/'recording_retest_priority.csv')
    sensor=pd.read_csv(OUT/'sensor_per_recording.csv')
    primary=pd.read_csv(OUT/'sensor_primary_batch_with_outlier_flags.csv')
    cycle=pd.read_csv(OUT/'cycle_per_sensor.csv')
    repeat=pd.read_csv(OUT/'repeatability_per_origin_roast_sensor.csv')
    roast=pd.read_csv(OUT/'roast_separation_exploratory.csv')
    ranked=pd.read_csv(OUT/'sensor_exploratory_ranking.csv')
    assert (len(record),len(sensor),len(primary),len(cycle))==(112,1120,1100,33600)
    assert record[['origin','roast','batch']].drop_duplicates().shape[0]==110
    assert int(record.is_primary_batch.sum())==110
    assert set(record.review_level)=={'PRIORITAS_UJI_ULANG','PERLU_REVIEW',
                                      'TIDAK_ADA_FLAG_BESAR','KONFIRMASI_REPLIKASI_BATCH'}
    assert int((record.review_level=='PRIORITAS_UJI_ULANG').sum())==10
    assert int((record.review_level=='KONFIRMASI_REPLIKASI_BATCH').sum())==2
    assert len(repeat)==210 and len(roast)==60 and len(ranked)==10
    assert len(summary['source_hashes'])==112
    assert all(checksum(SOURCE/x['filename'])==x['sha256'] for x in summary['source_hashes'])
    assert summary['input_unchanged'] is True
    assert int(primary.flag_saturated.sum())==0
    assert np.allclose(primary['baseline_last5']-primary['baseline_first5'],
                       primary['baseline_drift'],atol=1e-10)
    keys=['filename','sensor']
    phase_mean=cycle.groupby(keys).phase_contrast.mean().rename('cycle_mean')
    combined=sensor.set_index(keys).join(phase_mean)
    assert np.allclose(combined.response_mean,combined.cycle_mean,atol=1e-9)
    assert all(n==30 for n in cycle.groupby(keys).size().values)
    assert cycle.cycle.min()==1 and cycle.cycle.max()==30
    assert (OUT/'drift_to_response_heatmap.png').is_file()
    print('DRIFT_VARIABILITY_QA_PASS',json.dumps({
        'valid_csv':len(record),'unique_batches':int(record.is_primary_batch.sum()),
        'sensor_recording_rows':len(sensor),'cycle_sensor_rows':len(cycle),
        'high_priority':int((record.review_level=='PRIORITAS_UJI_ULANG').sum()),
        'duplicate_same_batch':int((record.review_level=='KONFIRMASI_REPLIKASI_BATCH').sum()),
        'clip_channels':int(primary.flag_saturated.sum()),
        'source_hash_matches':len(summary['source_hashes'])},ensure_ascii=True))


if __name__=='__main__':main()
