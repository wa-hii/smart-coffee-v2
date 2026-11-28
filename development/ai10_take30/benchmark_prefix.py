"""Offline duration benchmark, no serial access; preserve original CSV and FIX.

One recording = one sample. Fixed previously audited six-origin cohorts;
selection on A+B only; C is a previously examined diagnostic, not prospective.
"""
import csv, hashlib, json, platform, sys, warnings
from pathlib import Path
import numpy as np
import pandas as pd
import sklearn
from sklearn.ensemble import RandomForestClassifier, ExtraTreesClassifier
from sklearn.svm import SVC
from sklearn.linear_model import LogisticRegression
from sklearn.preprocessing import StandardScaler
from sklearn.pipeline import make_pipeline
from sklearn.model_selection import LeaveOneGroupOut, StratifiedGroupKFold
from sklearn.metrics import balanced_accuracy_score, f1_score, recall_score, confusion_matrix, accuracy_score

ROOT=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(ROOT/'scripts'))
from roast_rf30_pi_inference import validate_extract, ADC_COLUMNS
OUT=Path(__file__).resolve().parent/'benchmark_results'
DURATIONS=(5,10,15,20,30); LABELS=['light','medium','dark']; SEED=42
ORIGINS=['CAT','GAW','GRB','MING','TEM','TOR']
CORE=[0,6,9]

def digest(p):return hashlib.sha256(p.read_bytes()).hexdigest()
def extract(v,n):
    assert v.shape==(30,30,10) and np.isfinite(v).all()
    v=v[:n]; p=v[:,:25,:]; c=v[:,25:,:]; b=np.median(p[:,20:25,:],axis=1)
    d=c-b[:,None,:]; mean=d.mean(axis=1)
    k=max(1,n//6)
    # Independent of future cycles; relative normalization uses only current cycle.
    rel=d/np.maximum(np.abs(b[:,None,:]),1.)
    features={
        'raw3':np.array([c[:,:,0].max(axis=1).mean(),p[:,:,0].mean(),c[:,:,7].max(axis=1).mean()]),
        'core9':np.stack([np.median(mean,axis=0),mean.mean(axis=0),np.median(mean[-k:],axis=0)-np.median(mean[:k],axis=0)],axis=1)[CORE].ravel(),
        'delta50':np.stack([np.median(mean,axis=0),mean.mean(axis=0),np.median(d.max(axis=1),axis=0),np.median(d[:,-1,:]-d[:,0,:],axis=0)/4,np.median(mean[-k:],axis=0)-np.median(mean[:k],axis=0)],axis=1).ravel(),
        'relative30':np.stack([np.median(rel.mean(axis=1),axis=0),np.median(rel.max(axis=1),axis=0),np.median(rel[:,-1,:]-rel[:,0,:],axis=0)/4],axis=1).ravel(),
    }
    return features

def load():
    a=pd.read_csv(ROOT/'results/dataset_sorting_readiness_20261110/all_csv_audit.csv')
    invalid=a[(a.sort_status=='kept')&(~a.structurally_valid)]
    t=a[(a.sort_status=='kept')&a.structurally_valid&a.origin.isin(ORIGINS)].copy()
    t['canonical']=t.apply(lambda r:r.filename==f'{r.sample_id}_{r.batch}.csv',axis=1)
    t=t.sort_values(['origin','roast','batch','canonical','filename'],ascending=[True,True,True,False,True]);dup=t[t.duplicated(['origin','roast','batch'])];t=t.drop_duplicates(['origin','roast','batch'])
    assert len(t)==199 and len(invalid)==4 and len(dup)==1
    rows=[]; rejected=[]; arrays={n:{} for n in DURATIONS}; seen=set()
    for r in t.itertuples():
        p=ROOT/'data/dataset sorting'/r.relative_path
        try:
            assert digest(p)==r.sha256,'source hash changed'
            validate_extract(p)
            f=pd.read_csv(p);assert set(f.roast_level)=={r.roast} and set(f.sample_id)=={r.sample_id} and set(f.batch_id)=={r.batch},'label mismatch'
            v=f[list(ADC_COLUMNS)].to_numpy(dtype=float).reshape(30,30,10)
            signal=hashlib.sha256(v.tobytes()).hexdigest();assert signal not in seen,'duplicate signal';seen.add(signal)
        except Exception as e:
            rejected.append({'filename':r.filename,'reason':str(e)});continue
        rows.append({k:getattr(r,k) for k in ['filename','relative_path','origin','roast','batch','cohort','device_id','sha256']})
        for n in DURATIONS:
            for k,x in extract(v,n).items():arrays[n].setdefault(k,[]).append(x)
    t=pd.DataFrame(rows);assert not set(t[t.cohort!='c'].batch)&set(t[t.cohort=='c'].batch)
    print('DATA_AUDIT',len(t),'train',sum(t.cohort!='c'),'C',sum(t.cohort=='c'),'strict_rejects',rejected,flush=True)
    return t,{n:{k:np.stack(x) for k,x in a.items()} for n,a in arrays.items()},rejected,invalid.filename.tolist(),dup.filename.tolist()

def model(name):
    if name=='RF':return RandomForestClassifier(n_estimators=100,min_samples_leaf=2,class_weight='balanced',random_state=SEED,n_jobs=1)
    if name=='ET':return ExtraTreesClassifier(n_estimators=100,min_samples_leaf=2,class_weight='balanced',random_state=SEED,n_jobs=1)
    if name=='SVM':return make_pipeline(StandardScaler(),SVC(C=1,gamma='scale',class_weight='balanced'))
    return make_pipeline(StandardScaler(),LogisticRegression(C=1,max_iter=2000,class_weight='balanced'))
def metrics(y,p):
    return {'ba':float(balanced_accuracy_score(y,p)),'f1':float(f1_score(y,p,labels=LABELS,average='macro',zero_division=0)),'acc':float(accuracy_score(y,p)),**{f'recall_{l}':float(v) for l,v in zip(LABELS,recall_score(y,p,labels=LABELS,average=None,zero_division=0))}}

def main():
    assert not OUT.exists(),'results exist; protect prior run'
    t,xs,rejected,invalid,dup=load();train=np.flatnonzero(t.cohort!='c');test=np.flatnonzero(t.cohort=='c');y=t.roast.to_numpy();yt=y[train]
    origin=t.origin.to_numpy()[train];batch=t.batch.to_numpy()[train]
    splits={'origin':list(LeaveOneGroupOut().split(train,yt,origin)),'batch':list(StratifiedGroupKFold(n_splits=5,shuffle=True,random_state=SEED).split(train,yt,batch))}
    for name,folds in splits.items():
        g=origin if name=='origin' else batch
        assert all(not set(g[a])&set(g[b]) and set(yt[a])==set(LABELS) for a,b in folds)
    OUT.mkdir();t.to_csv(OUT/'recordings.csv',index=False)
    splitrows=[]
    for name,folds in splits.items():
        for i,(_,val) in enumerate(folds):
            splitrows.extend({'scheme':name,'fold':i,'filename':t.iloc[train[j]].filename} for j in val)
    pd.DataFrame(splitrows).to_csv(OUT/'folds.csv',index=False)
    rows=[];preds=[]
    for n in DURATIONS:
        for fs,X in xs[n].items():
            for alg in ('RF','ET','SVM','LR'):
                r={'cycles':n,'minutes':n/2,'features':fs,'model':alg,'n_features':X.shape[1]}
                for name,folds in splits.items():
                    p=np.empty(len(train),dtype=object)
                    for a,b in folds:
                        m=model(alg).fit(X[train[a]],yt[a]);p[b]=m.predict(X[train[b]])
                    r.update({f'{name}_{k}':v for k,v in metrics(yt,p).items()})
                # Conservative rank across both grouping schemes, C invisible to selection.
                r['selection_score']=min(r['origin_ba'],r['batch_ba']);rows.append(r)
        print('CV_DONE',n,'best',max((r for r in rows if r['cycles']==n),key=lambda r:r['selection_score']),flush=True)
    cv=pd.DataFrame(rows);cv.to_csv(OUT/'cv_scores.csv',index=False)
    winners=[]
    for n in DURATIONS:
        # Predeclared deterministic tie break: min BA, mean F1, fewer features, alphabetical.
        candidates=[r for r in rows if r['cycles']==n];r=sorted(candidates,key=lambda r:(-r['selection_score'],-(r['origin_f1']+r['batch_f1']),r['n_features'],r['features'],r['model']))[0].copy()
        X=xs[n][r['features']];m=model(r['model']).fit(X[train],yt);p=m.predict(X[test]);r.update({f'c_{k}':v for k,v in metrics(y[test],p).items()});r['c_confusion']=confusion_matrix(y[test],p,labels=LABELS).tolist();winners.append(r)
        preds.extend({'cycles':n,'filename':t.iloc[j].filename,'origin':t.iloc[j].origin,'truth':y[j],'predicted':pred} for j,pred in zip(test,p))
    pd.DataFrame(preds).to_csv(OUT/'diagnostic_c_predictions.csv',index=False)
    pd.DataFrame(winners).to_csv(OUT/'duration_comparison.csv',index=False)
    target=next(r for r in winners if r['cycles']==10)
    summary={'train_n':len(train),'diagnostic_c_n':len(test),'counts':{str(k):int(v) for k,v in t.groupby(['cohort','roast']).size().items()},'device_counts':t.device_id.value_counts(dropna=False).to_dict(),'strict_rejected':rejected,'prior_invalid':invalid,'duplicate_identity':dup,'winners':winners,'selected_10cycle':target,'versions':{'python':platform.python_version(),'sklearn':sklearn.__version__,'numpy':np.__version__,'pandas':pd.__version__},'seed':SEED,'selection':'min(origin CV BA,batch CV BA); C not used for selection','release_approved':False,'limitations':['C previously explored; no prospective holdout','manual kept selection; origin and device confounding; specimen identity unknown','no physical cross-device or 10-cycle deployment validation'],'candidate_gate':'require prospective independent two-device validation; no automatic hardware or model deployment'}
    (OUT/'summary.json').write_text(json.dumps(summary,indent=2)+'\n',encoding='utf8');print('BENCHMARK_COMPLETE',json.dumps(winners),flush=True)
if __name__=='__main__':main()
