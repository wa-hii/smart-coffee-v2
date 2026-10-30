"""Baseline-first, train-fitted global Z-score and held-out B70..B75 roast test.

Input: provenance verified merged 30-cycle archive. One CSV=one observation,
never 30 independent samples. Training old archive; test new B70..B75.
Training-only leave-one-origin-out CV ranks sensors. Test data is never used
to fit StandardScaler, select core sensors or tune models.
"""
from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.impute import SimpleImputer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import accuracy_score,balanced_accuracy_score,confusion_matrix,f1_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from acquisition_schema import ADC_COLS
from merge_30cycle_b70_b75_provenance import OUT as MERGED, checksum

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'results/ai_30cycle_B70_B75_global_zscore_20261031'
COMPLETE=['CAT','GAW','GRB','MING','TEM','TOR']
CLASSES=['light','medium','dark']
ROAST_COLORS={'light':'#168A43','medium':'#D4A400','dark':'#C62828'}
LOCAL=['response_median','response_iqr','response_trend',
       'peak_response_median','collecting_slope_median']
RAW=['collecting_adc_median','baseline_adc_median','collecting_adc_iqr']
T0=['t0collect_median','t0collect_iqr','t0collect_trend']


def percentile_iqr(v):
    return float(np.percentile(v,75)-np.percentile(v,25))


def features_from_csv(path:Path,origin:str,roast:str,batch:str,source_type:str,device_id:str):
    df=pd.read_csv(path,low_memory=False)
    if len(df)!=900 or not np.array_equal(df['run_id'].to_numpy(dtype=int),np.repeat(np.arange(1,31),30)):
        raise RuntimeError('Invalid cycle count: '+path.name)
    if not np.all(df['phase'].to_numpy().reshape(30,30)[:,25:]=='collecting'):
        raise RuntimeError('Invalid collecting phase: '+path.name)
    rec={'filename':path.name,'origin':origin,'roast':roast,'batch':batch,
         'source_type':source_type,'device_id':device_id,
         'temperature_mean':float(df.temperature.mean()),'humidity_mean':float(df.humidity.mean())}
    sensor_rows=[]
    for sensor in ADC_COLS:
        adc=df[sensor].to_numpy(dtype=float).reshape(30,30)
        baseline=np.median(adc[:,20:25],axis=1)  # only current cycle's purge
        corr=adc[:,25:30]-baseline[:,None]     # collecting minus own baseline
        resp=corr.mean(axis=1)
        peaks=corr.max(axis=1)
        slopes=np.polyfit(np.arange(5),corr.T,1)[0]  # 30 independent slopes, per cycle
        first_anchor=adc[0,24]
        t0coll=adc[:,25:30].mean(axis=1)-first_anchor
        feats={
            'response_median':float(np.median(resp)),
            'response_iqr':percentile_iqr(resp),
            'response_trend':float(np.polyfit(np.arange(1,31),resp,1)[0]),
            'peak_response_median':float(np.median(peaks)),
            'collecting_slope_median':float(np.median(slopes)),
            'collecting_adc_median':float(np.median(adc[:,25:30].mean(axis=1))),
            'baseline_adc_median':float(np.median(baseline)),
            'collecting_adc_iqr':percentile_iqr(adc[:,25:30].mean(axis=1)),
            't0collect_median':float(np.median(t0coll)),
            't0collect_iqr':percentile_iqr(t0coll),
            't0collect_trend':float(np.polyfit(np.arange(1,31),t0coll,1)[0]),
            'drift_adc_firstlast':float(np.median(baseline[-5:])-np.median(baseline[:5])),
            'median_abs_cycle_response':float(np.median(abs(resp))),
            'drift_response_ratio':float(abs(np.median(baseline[-5:])-np.median(baseline[:5]))/(np.median(abs(resp))+1)),
            'pct_collecting_positive':float((resp>0).mean()),
            'adc_min':float(adc.min()),'adc_max':float(adc.max()),
        }
        rec.update({f'{f}__{sensor}':v for f,v in feats.items() if f in LOCAL+RAW+T0})
        sensor_rows.append({'filename':path.name,'origin':origin,'roast':roast,'batch':batch,
                'source_type':source_type,'device_id':device_id,'sensor':sensor,**feats})
    return rec,sensor_rows


def estimator(name):
    if name=='LogReg_L2':
        ml=LogisticRegression(max_iter=5000,class_weight='balanced',C=1.0)
    elif name=='SVM_RBF':
        ml=SVC(kernel='rbf',C=1.0,class_weight='balanced',gamma='scale')
    elif name=='RandomForest':
        ml=RandomForestClassifier(n_estimators=160,max_depth=5,min_samples_leaf=3,
                                   class_weight='balanced',random_state=42,n_jobs=1)
    elif name=='Dummy':
        ml=DummyClassifier(strategy='prior')
    else:raise ValueError(name)
    return Pipeline([('imputer',SimpleImputer(strategy='median')),
                     ('global_train_zscore',StandardScaler()),('classifier',ml)])


def metric(y,pred):
    return {'accuracy':float(accuracy_score(y,pred)),
            'balanced_accuracy':float(balanced_accuracy_score(y,pred)),
            'macro_f1':float(f1_score(y,pred,labels=CLASSES,average='macro',zero_division=0))}


def train_cv(table,cols,model_name):
    X=table[cols].to_numpy(dtype=float);y=table.roast.to_numpy();groups=table.origin.to_numpy()
    outs=np.empty(len(y),dtype=object)
    for tr,va in LeaveOneGroupOut().split(X,y,groups):
        assert set(groups[tr]).isdisjoint(groups[va])
        model=estimator(model_name)
        model.fit(X[tr],y[tr]);outs[va]=model.predict(X[va])
    return metric(y,outs)


def main():
    if OUT.exists():raise FileExistsError(f'Output exists: {OUT}')
    prov=pd.read_csv(MERGED/'accepted_provenance.csv').fillna('')
    assert len(prov)==233
    p=prov[prov.primary_independent_batch].copy()
    assert len(p)==231
    rows=[];sensor_rows=[]
    for rec in p.to_dict('records'):
        f=MERGED/'01_VALID_GABUNGAN'/rec['filename']
        if checksum(f)!=rec['sha256']:
            raise RuntimeError('Invalid SHA '+f.name)
        row,ss=features_from_csv(f,rec['origin'],rec['roast_level'],rec['batch_id'],
                                  rec['source_type'],rec['device_id'])
        rows.append(row);sensor_rows.extend(ss)
    all_df=pd.DataFrame(rows)
    metrics_df=pd.DataFrame(sensor_rows)
    eligible=all_df[all_df.origin.isin(COMPLETE)].copy()
    tr=eligible[eligible.source_type=='previous_audit'].copy()
    te=eligible[eligible.source_type=='B70_B75'].copy()
    assert (len(tr),len(te))==(93,103),(len(tr),len(te))
    assert set(tr.filename).isdisjoint(set(te.filename))
    assert all(tr.groupby('origin').roast.nunique()==3)
    assert all(te.groupby('origin').roast.nunique()==3)
    print('FEATURE_ROWS',len(all_df),'TRAIN',len(tr),'TEST_NEW',len(te),flush=True)

    # Select sensors using OLD training origin held-out CV only.
    one_sensor=[]
    for s in ADC_COLS:
        cols=[f'{f}__{s}' for f in LOCAL]
        cv=train_cv(tr,cols,'LogReg_L2')
        model=estimator('LogReg_L2').fit(tr[cols],tr.roast)
        pred=model.predict(te[cols])
        one_sensor.append({'sensor':s,'n_features':len(cols),
             'train_cv_balanced_accuracy':cv['balanced_accuracy'],
             'train_cv_macro_f1':cv['macro_f1'],
             'new_batch_test_balanced_accuracy':metric(te.roast,pred)['balanced_accuracy'],
             'new_batch_test_macro_f1':metric(te.roast,pred)['macro_f1'],
             'new_batch_test_accuracy':metric(te.roast,pred)['accuracy']})
    rank=pd.DataFrame(one_sensor).sort_values(['train_cv_balanced_accuracy','train_cv_macro_f1'],ascending=False).reset_index(drop=True)
    rank.insert(0,'rank_train_cv',np.arange(1,len(rank)+1))
    top3=rank.sensor.iloc[:3].tolist();top5=rank.sensor.iloc[:5].tolist()
    print('SENSOR_RANK_CV',rank[['rank_train_cv','sensor','train_cv_balanced_accuracy','new_batch_test_balanced_accuracy']].round(3).to_json(orient='records'),flush=True)

    def cols_for(sensor_list,feature_list):
        return [f'{feat}__{sensor}' for sensor in sensor_list for feat in feature_list]
    feature_sets={
        'TOP3_local_baseline':cols_for(top3,LOCAL),
        'TOP5_local_baseline':cols_for(top5,LOCAL),
        'ALL10_local_baseline':cols_for(ADC_COLS,LOCAL),
        'ALL10_t0_only':cols_for(ADC_COLS,T0),
        'ALL10_raw_ADC':cols_for(ADC_COLS,RAW),
        'ENV_ONLY_negative_control':['temperature_mean','humidity_mean'],
    }
    results=[];pred_rows=[];per_origin_device=[];scalers=[]
    for fname,cols in feature_sets.items():
        for model_name in ['LogReg_L2','SVM_RBF','RandomForest']:
            cv=train_cv(tr,cols,model_name)
            model=estimator(model_name)
            model.fit(tr[cols],tr.roast)
            pred=model.predict(te[cols]);m=metric(te.roast,pred)
            results.append({'feature_set':fname,'model':model_name,'n_features':len(cols),
                'n_train':len(tr),'n_test':len(te),
                **{'train_origin_cv_'+k:v for k,v in cv.items()},
                **{'new_batch_test_'+k:v for k,v in m.items()},
                'test_confusion_matrix':json.dumps(confusion_matrix(te.roast,pred,labels=CLASSES).tolist())})
            scaler=model.named_steps['global_train_zscore']
            for col,mean,scale in zip(cols,scaler.mean_,scaler.scale_):
                scalers.append({'feature_set':fname,'model':model_name,'feature':col,
                                'train_global_mu':float(mean),'train_global_sigma':float(scale)})
            for j,(_,r) in enumerate(te.iterrows()):
                pred_rows.append({'feature_set':fname,'model':model_name,'filename':r.filename,
                    'origin':r.origin,'roast_actual':r.roast,'roast_predicted':pred[j],
                    'device_id':r.device_id,'batch':r.batch})
            for kind in ['origin','device_id']:
                for label,group in te.groupby(kind):
                    ix=te.index.get_indexer(group.index)
                    per_origin_device.append({'feature_set':fname,'model':model_name,'group_type':kind,
                                               'group':label,'n_test':len(group),
                                               **metric(group.roast,pred[ix])})
            print('EVAL',fname,model_name,'trainCV',round(cv['balanced_accuracy'],3),
                  'newTest',round(m['balanced_accuracy'],3),flush=True)
    # Data-quality summaries; not use new test to select sensors.
    sensor_quality=metrics_df.groupby(['source_type','sensor'],as_index=False).agg(
        recordings=('filename','nunique'),
        median_absolute_collecting_response=('median_abs_cycle_response','median'),
        median_abs_drift_adc=('drift_adc_firstlast',lambda s:float(np.median(np.abs(s)))),
        median_drift_over_response=('drift_response_ratio','median'),
        fraction_near_adc_rail=('adc_max',lambda s:float((s>=32766).mean())))

    OUT.mkdir(parents=True)
    def csv(name,df):df.to_csv(OUT/name,index=False,encoding='utf-8-sig')
    csv('features_per_recording.csv',all_df)
    csv('metrics_per_sensor_recording.csv',metrics_df)
    csv('sensor_ranking_train_cv_and_new_test.csv',rank)
    csv('model_comparison_traincv_newtest.csv',pd.DataFrame(results))
    csv('new_test_predictions.csv',pd.DataFrame(pred_rows))
    csv('new_test_per_origin_device.csv',pd.DataFrame(per_origin_device))
    csv('global_zscore_mu_sigma_from_training.csv',pd.DataFrame(scalers))
    csv('sensor_drift_quality_old_vs_new.csv',sensor_quality)
    summary={'total_merged_valid_csv':len(prov),'unique_recordings_all':len(all_df),
         'three_roast_training_old':len(tr),'three_roast_testing_new':len(te),
         'eligible_origins':COMPLETE,'training_groups':tr.groupby(['origin','roast']).size().to_dict(),
         'testing_groups':te.groupby(['origin','roast']).size().to_dict(),
         'sensor_rank_based_on':'OLD-TRAIN leave-one-origin-out CV (no new test selection)',
         'top3_from_train_cv':top3,'top5_from_train_cv':top5,
         'global_zscore_fitted_only_on':'OLD-TRAIN all roasting classes together, per feature; never fit on new test',
         'baseline_formula':'median purge samples 21..25 each cycle, subtract from 5 collecting ADC samples, then extract run-level features',
         'holdout':'B70..B75 all valid complete CSV for six three-roast origins',
         'no_label_dependent_baselines':True,
         'no_interpolation_incomplete':True,
         'main_limitations':['Train device metadata UNKNOWN, no direct old-vs-new instrument harmonization',
             'New device assignment is not balanced across origin/roast',
             'Batch is not proof of separate physical coffee preparation',
             'Held-out new test score is single temporal split not prospectively independent specimens',
             'Sensor rankings based on small six-origin training cross-validation are exploratory']}
    summary['training_groups']={'|'.join(k):int(v) for k,v in summary['training_groups'].items()}
    summary['testing_groups']={'|'.join(k):int(v) for k,v in summary['testing_groups'].items()}
    (OUT/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n',encoding='utf8')

    # Labelled, nonmisleading figure: ranking uses only old-train origin CV.
    fig,ax=plt.subplots(figsize=(9.4,5.4),dpi=155)
    order=rank.iloc[::-1]
    ax.barh(order.sensor.str.replace('adc_','',regex=False).str.upper(),
            100*order.train_cv_balanced_accuracy,color='#277A77')
    ax.axvline(100/3,c='#B8692F',ls='--',lw=1.2,label='Peluang 3 kelas: 33,3%')
    ax.set(xlabel='Balanced accuracy CV origin dari data training lama (%)',
           title='Ranking sensor tunggal — baseline per siklus + global Z-score training')
    ax.legend(loc='lower right');ax.grid(axis='x',alpha=.2)
    fig.tight_layout();fig.savefig(OUT/'sensor_ranking_train_origin_cv.png');plt.close(fig)
    print('RUN_COMPLETE',json.dumps({
       'valid':len(prov),'all_unique':len(all_df),'train':len(tr),'test':len(te),
       'top3':top3,'best_old_train_cv':pd.DataFrame(results).sort_values('train_origin_cv_balanced_accuracy',ascending=False).iloc[0][['feature_set','model','train_origin_cv_balanced_accuracy','new_batch_test_balanced_accuracy']].to_dict()},ensure_ascii=True),flush=True)
    return summary


if __name__=='__main__':main()
