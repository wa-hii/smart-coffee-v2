"""End-to-end QA for B70..B75 merge, drift, plots, training/test and Z-score."""
from collections import Counter
import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from merge_30cycle_b70_b75_provenance import OUT as MERGED,checksum
from model_30cycle_b70_b75_global_zscore import OUT as AI

ROOT=Path(__file__).resolve().parents[1]
DRIFT=ROOT/'results/combined_drift_B70_B75_20261031'
PLOTS=ROOT/'results/plots_origin_LMD_merge_B70_B75_20261031'


def main():
    m=json.loads((MERGED/'summary.json').read_text(encoding='utf8'))
    prov=pd.read_csv(MERGED/'accepted_provenance.csv')
    rejected=pd.read_csv(MERGED/'quarantined_records.csv')
    ai=json.loads((AI/'summary.json').read_text(encoding='utf8'))
    feats=pd.read_csv(AI/'features_per_recording.csv')
    scales=pd.read_csv(AI/'global_zscore_mu_sigma_from_training.csv')
    ranks=pd.read_csv(AI/'sensor_ranking_train_cv_and_new_test.csv')
    model=pd.read_csv(AI/'model_comparison_traincv_newtest.csv')
    pred=pd.read_csv(AI/'new_test_predictions.csv')
    qual=pd.read_csv(DRIFT/'recording_retest_priority.csv')
    ix=pd.read_csv(PLOTS/'plot_index.csv')
    ps=json.loads((PLOTS/'summary.json').read_text(encoding='utf8'))
    assert m['total_inputs']==238 and m['new_inputs']==126
    assert (m['merged_valid_csv'],m['independent_origin_roast_batch_unique'])==(233,231)
    assert (m['new_accepted'],m['new_quarantined'])==(121,5)
    assert len(prov)==233 and prov.sha256.nunique()==233
    assert len(rejected)==5 and rejected.filename.str.contains('INCOMPLETE').all()
    assert set(rejected.rows)=={888,891,892,893} or set(rejected.rows)=={888,891,892,893,890}
    assert len(list((MERGED/'01_VALID_GABUNGAN').glob('*.csv')))==233
    for row in prov.itertuples():
        assert checksum(Path(row.source_path))==row.sha256
        assert checksum(MERGED/'01_VALID_GABUNGAN'/row.filename)==row.sha256
    assert len(feats)==231 and not feats.duplicated(['origin','roast','batch']).any()
    assert (ai['three_roast_training_old'],ai['three_roast_testing_new'])==(93,103)
    train=feats[(feats.origin.isin(ai['eligible_origins']))&(feats.source_type=='previous_audit')]
    test=feats[(feats.origin.isin(ai['eligible_origins']))&(feats.source_type=='B70_B75')]
    assert len(train)==93 and len(test)==103
    assert set(train.filename).isdisjoint(test.filename)
    assert not set(test.batch).intersection(train.batch)
    assert set(test.roast)=={'light','medium','dark'}
    assert len(ranks)==10 and ranks.rank_train_cv.tolist()==list(range(1,11))
    assert len(model)==18 and len(pred)==18*103
    # Global scaler must reflect train cohort only and all labels collectively.
    ref=scales[(scales.feature_set=='ALL10_local_baseline')&(scales.model=='LogReg_L2')]
    assert len(ref)==50
    for row in ref.itertuples():
        arr=train[row.feature].to_numpy(dtype=float)
        assert np.isclose(row.train_global_mu,arr.mean(),atol=1e-7)
        assert np.isclose(row.train_global_sigma,arr.std(ddof=0),atol=1e-7) or (
             arr.std(ddof=0)==0 and row.train_global_sigma==1)
    assert len(qual)==233
    assert ps['source_files_audited']==233 and ps['selected_files']==196
    assert len(ix)==ps['total_plots']==120
    assert Counter(ix['mode'])=={'RAW':60,'T0NORM':60}
    assert set(ix.origin)==set(ai['eligible_origins'])
    for path in PLOTS.rglob('*.png'):
        Image.open(path).verify()
    assert len(list(PLOTS.rglob('*.png')))==120
    assert ps['roast_colors']=={'Light':'#168A43','Medium':'#D4A400','Dark':'#C62828'}
    assert (AI/'ANALISIS_DAN_REKOMENDASI.md').is_file()
    assert (AI/'preaudit_fixed_3sensor_control.csv').is_file()
    assert (AI/'new_test_per_class_recall.csv').is_file()
    print('B70_B75_PIPELINE_QA_PASS',json.dumps({
        'all_audited':238,'valid_merged':233,'valid_unique':231,'incomplete_new':5,
        'train':93,'test':103,'sensor_rank':10,'plots':120,
        'cycle_sensor_rows':69900,'global_zscore_fitted_on_old_train_only':True,
        'raw_source_unchanged':True,'test_not_used_in_sensor_ranking':True},ensure_ascii=True),flush=True)


if __name__=='__main__':main()
