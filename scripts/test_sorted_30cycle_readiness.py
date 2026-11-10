"""Reproducible, non-destructive QA for sorted E-Nose audit and benchmark."""

import json
from pathlib import Path

import numpy as np
import pandas as pd

from audit_sorted_30cycle_training_readiness import SOURCE,OUT,checksum


def main():
    audit=json.loads((OUT/'summary.json').read_text(encoding='utf-8'))
    model=json.loads((OUT/'model_diagnostic_summary.json').read_text(encoding='utf-8'))
    a=pd.read_csv(OUT/'all_csv_audit.csv')
    sig=pd.read_csv(OUT/'sensor_signal_metrics.csv')
    features=pd.read_csv(OUT/'cohort_c_holdout_model_diagnostic.csv')
    blocked=pd.read_csv(OUT/'excluded_invalid_from_kept.csv')
    assert audit['total_csv']==len(a)==366
    assert len(list(SOURCE.rglob('*.csv')))==366
    assert a.audit_category.value_counts().to_dict()=={'VALID':361,'INCOMPLETE':5}
    assert a.sha256.nunique()==a.signal_sha256.nunique()==366
    assert a.sort_status.value_counts().to_dict()=={'kept':232,'excluded':86,'maybe':48}
    assert audit['kept_valid']==228 and audit['kept_unique_label_batch']==227
    assert audit['maybe_valid']==47 and audit['excluded_valid']==86
    assert int(((a.sort_status=='kept')&~a.structurally_valid).sum())==4
    assert len(blocked)==4 and blocked.filename.str.contains('INCOMPLETE').all()
    assert set(blocked.filename)==set(a[(a.sort_status=='kept')&~a.structurally_valid].filename)
    assert a[(a.sort_status=='kept')&~a.structurally_valid].filename.str.contains('INCOMPLETE').all()
    assert int(a.same_signal_in_prior_valid.sum())==232
    assert int(a.same_bytes_in_prior_valid.sum())==121
    assert len(sig)==361*10
    assert not sig[['filename','sensor']].duplicated().any()
    assert (a[a.structurally_valid].n_rows==900).all()
    assert (a[a.structurally_valid].n_cycles==30).all()
    assert len(features)==9 and model['train_n']==133 and model['test_n']==66
    assert model['excluded_invalid_kept_count']==4
    assert set(model['excluded_invalid_kept_files'])==set(blocked.filename)
    assert len(set(model['duplicate_kept_discarded']))==1
    assert set(features.feature_set)=={'TGS822_TGS2602_TGS816','ALL10_LOCAL_CONTRAST','ENV_ONLY_NEGATIVE_CONTROL'}
    assert all(0<=v<=1 for v in features.holdout_c_balanced_accuracy)
    assert np.isclose(features.query('feature_set=="TGS822_TGS2602_TGS816" and model=="SVM_RBF"').holdout_c_balanced_accuracy.iloc[0],0.65258,atol=.002)
    for row in a.itertuples():
        src=SOURCE/row.relative_path
        assert src.is_file() and checksum(src)==row.sha256
    assert (OUT/'ANALISIS_KELAYAKAN_TRAINING.md').is_file()
    print('SORTED_30CYCLE_QA_PASS',json.dumps({
        'source_hashes_verified':366,'valid':361,'incomplete':5,
        'kept_valid':228,'kept_unique_batch_ids':227,'excluded_structurally_valid':86,
        'train_cohort_a_b':133,'test_cohort_c':66,'source_unchanged':True,
    },ensure_ascii=True))


if __name__=='__main__':main()
