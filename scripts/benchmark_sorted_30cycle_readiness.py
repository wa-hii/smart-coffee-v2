"""Exploratory roast-model sanity checks for human-sorted 30-cycle CSV.

No hyperparameter tuning or test-guided selection. One CSV = one observation.
Train cohort A+B kept+valid (exclude duplicate batch); test cohort C kept+valid.
Scaler fits training folds only. Dataset is confounded by sensor devices and
manual selection; scores are *not* deployment performance estimates.
"""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import balanced_accuracy_score,f1_score,recall_score,confusion_matrix,accuracy_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/dataset_sorting_readiness_20261110'
ORIGINS=['CAT','GAW','GRB','MING','TEM','TOR']
SENSORS=['adc_tgs822','adc_mq135','adc_mq3','adc_tgs2611','adc_tgs2620',
         'adc_tgs2600','adc_tgs2602','adc_mq8','adc_tgs813','adc_tgs816']
LABELS=['light','medium','dark']


def prepare():
    a=pd.read_csv(OUT/'all_csv_audit.csv')
    a=a[a.structurally_valid & (a.sort_status=='kept') & a.origin.isin(ORIGINS)].copy()
    a['canonical']=a.apply(lambda r:r.filename==f'{r.sample_id}_{r.batch}.csv',axis=1)
    a=a.sort_values(['origin','roast','batch','canonical'],ascending=[True,True,True,False])
    dup=a[a.duplicated(['origin','roast','batch'])].copy()
    a=a.drop_duplicates(['origin','roast','batch'],keep='first')
    s=pd.read_csv(OUT/'sensor_signal_metrics.csv')
    s=s[s.filename.isin(set(a.filename))]
    feats=['median_phase_response','mean_phase_response','response_early_late']
    data=s.pivot(index='filename',columns='sensor',values=feats)
    data=data[[(f,sen) for sen in SENSORS for f in feats]]
    data.columns=[f'{f}__{sen}' for f,sen in data.columns]
    data=data.reset_index()
    t=a[['filename','origin','roast','batch','cohort','device_id','temperature_mean','humidity_mean']].merge(
        data,on='filename',validate='one_to_one')
    assert len(t)==len(a)
    return t,dup


def scores(y,p):
    return {'balanced_accuracy':float(balanced_accuracy_score(y,p)),
        'macro_f1':float(f1_score(y,p,average='macro',labels=LABELS,zero_division=0)),
        'accuracy':float(accuracy_score(y,p)),
        'recall_light':float(recall_score(y,p,labels=LABELS,average=None,zero_division=0)[0]),
        'recall_medium':float(recall_score(y,p,labels=LABELS,average=None,zero_division=0)[1]),
        'recall_dark':float(recall_score(y,p,labels=LABELS,average=None,zero_division=0)[2])}


def ml(name):
    algorithm={
      'LogReg_L2':LogisticRegression(C=1,max_iter=4000,class_weight='balanced'),
      'SVM_RBF':SVC(C=1,gamma='scale',class_weight='balanced'),
      'Dummy':DummyClassifier(strategy='prior'),
    }[name]
    return Pipeline([('global_train_zscore',StandardScaler()),('classifier',algorithm)])


def run():
    t,dup=prepare()
    train=t[t.cohort.isin(['a','b'])].copy()
    test=t[t.cohort=='c'].copy()
    assert len(train)>90 and len(test)>50
    assert set(train.filename).isdisjoint(test.filename)
    assert not set(train.batch).intersection(set(test.batch))
    feature_sets={
      'TGS822_TGS2602_TGS816':[f'{feat}__{sensor}' for sensor in ['adc_tgs822','adc_tgs2602','adc_tgs816']
                               for feat in ['median_phase_response','mean_phase_response','response_early_late']],
      'ALL10_LOCAL_CONTRAST':[f'{feat}__{sensor}' for sensor in SENSORS
                              for feat in ['median_phase_response','mean_phase_response','response_early_late']],
      'ENV_ONLY_NEGATIVE_CONTROL':['temperature_mean','humidity_mean'],
    }
    results=[];per_origin=[]
    for fset,cols in feature_sets.items():
        X=train[cols].to_numpy(dtype=float)
        y=train.roast.to_numpy();groups=train.origin.to_numpy()
        xx=test[cols].to_numpy(dtype=float);yy=test.roast.to_numpy()
        for name in ['LogReg_L2','SVM_RBF','Dummy']:
            out=np.empty(len(train),dtype=object)
            for tr,va in LeaveOneGroupOut().split(X,y,groups):
                model=ml(name)
                model.fit(X[tr],y[tr])
                out[va]=model.predict(X[va])
            cv=scores(y,out)
            model=ml(name).fit(X,y)
            p=model.predict(xx)
            ts=scores(yy,p)
            row={'feature_set':fset,'model':name,'n_train':len(train),
                 'n_test_c':len(test),'n_features':len(cols),
                 'train_origin_cv_balanced_accuracy':cv['balanced_accuracy'],
                 'train_origin_cv_macro_f1':cv['macro_f1'],
                 'holdout_c_confusion':json.dumps(confusion_matrix(yy,p,labels=LABELS).tolist()),
                 **{'holdout_c_'+k:v for k,v in ts.items()}}
            results.append(row)
            for origin,sub in test.groupby('origin'):
                ix=test.index.get_indexer(sub.index)
                per_origin.append({'feature_set':fset,'model':name,'origin':origin,
                 'n_test':len(sub),'classes_present':';'.join(sorted(set(sub.roast))),
                 **scores(sub.roast.to_numpy(),p[ix])})
            print('SORTED_MODEL',fset,name,'cv',round(cv['balanced_accuracy'],3),
                  'c',round(ts['balanced_accuracy'],3),'recall',
                  [round(ts[k],2) for k in ['recall_light','recall_medium','recall_dark']],flush=True)
    r=pd.DataFrame(results)
    r.to_csv(OUT/'cohort_c_holdout_model_diagnostic.csv',index=False,encoding='utf-8-sig')
    pd.DataFrame(per_origin).to_csv(OUT/'cohort_c_holdout_per_origin.csv',index=False,encoding='utf-8-sig')
    (OUT/'model_diagnostic_summary.json').write_text(json.dumps({
      'training_counts_by_origin_roast':{'|'.join(k):int(v) for k,v in train.groupby(['origin','roast']).size().items()},
      'testing_counts_by_origin_roast':{'|'.join(k):int(v) for k,v in test.groupby(['origin','roast']).size().items()},
      'train_n':len(train),'test_n':len(test),'duplicate_kept_discarded':[x.filename for x in dup.itertuples()],
      'training_cohorts':['a','b'],'testing_cohort':'c',
      'label_sources':'manual sorted/kept; only structural QA-validated; not random prospective samples',
      'grouping_for_cv':'origin (5 train, 1 validate); test cohort c B80-B90 is never used to fit scalers',
      'inherent_limitations':['class-origin coverage incomplete in test C',
        'origin/roast/device confounded especially in B70-B75',
        'missing device identifiers for A and C',
        'manual sorting may bias distribution / select response amplitudes',
        'physical specimen/preparation independence unverified',
        'exploratory configuration comparison on test is not a final unbiased estimate']
      },indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return r


if __name__=='__main__':run()
