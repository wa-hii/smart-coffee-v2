"""Reproduce preselected 10-cycle candidate in Pi-compatible sklearn; never deploy.

Known physical capture labels are external operator labels, not old predictions.
Read-only SSH, bounded timeout, no UART, and no raw data changes.
"""
import hashlib, json, subprocess, sys, warnings
from pathlib import Path
import joblib
import numpy as np
import pandas as pd
from sklearn.model_selection import LeaveOneGroupOut, StratifiedGroupKFold
from sklearn.metrics import confusion_matrix
from benchmark_prefix import ROOT, OUT, LABELS, ADC_COLUMNS, load, model, metrics, SEED, digest, extract
import sklearn

PRIVATE=ROOT/'private/ai10_take30_diagnostic'
FEATURES=['tgs822_max_mean','tgs822_purging_mean_mean','mq8_max_mean']
ARCHIVES={'light':'20261127T114703_115182Z_2F8B1BDB','medium':'20261127T121326_371285Z_8DFA7D31','dark':'20261127T131321_711300Z_6BCB1F9C'}

def check_rows(rows,n):
    if len(rows)!=30*n:raise ValueError('wrong row count')
    last=-1;out=[]
    for i,r in enumerate(rows):
        cycle=i//30+1;k=i%30;phase='purging' if k<25 else 'collecting';idx=k+1 if k<25 else k-24
        if (int(r.get('cycle',r.get('run_id',0))),r['phase'],int(r['sample_idx']))!=(cycle,phase,idx):raise ValueError('wrong cycle/phase/index')
        ts=int(r['timestamp']);v=np.array([float(r[s]) for s in ADC_COLUMNS])
        if ts<=last or not np.isfinite(v).all() or np.any(v<0) or np.any(v>32767):raise ValueError('bad timestamp/ADC')
        last=ts;out.append(v)
    return np.stack(out).reshape(n,30,10)

def features300(rows):
    v=check_rows(rows,10)
    return np.array([v[:,25:,0].max(axis=1).mean(),v[:,:25,0].mean(),v[:,25:,7].max(axis=1).mean()])

def ssh(host,remote,pi2=False):
    args=['ssh','-o','BatchMode=yes','-o','ConnectTimeout=5','-o','ServerAliveInterval=3','-o','ServerAliveCountMax=2']
    if pi2:args+=['-o','IdentitiesOnly=yes','-i',str(Path.home()/'.ssh/id_ed25519_enose_pi2')]
    return subprocess.check_output(args+[host,remote],timeout=18,stderr=subprocess.PIPE)

def diagnose_archives(clf):
    base='smart-coffee-stage7/rf30_staging/com4_integration_20261117/always_on/recordings/'
    result=[]
    for label,stem in ARCHIVES.items():
        try:
            meta=json.loads(ssh('enose-v3@enose-pi5','cat '+base+stem+'.json'))
            raw=ssh('enose-v3@enose-pi5','cat '+base+stem+'.ndjson')
            assert hashlib.sha256(raw).hexdigest()==meta['capture_sha256'] and meta['samples']==900 and meta['status']=='MCU_ACK_CONFIRMED'
            (PRIVATE/(stem+'.ndjson')).write_bytes(raw)
            (PRIVATE/(stem+'.json')).write_text(json.dumps(meta,indent=2),encoding='utf8')
            frames=[json.loads(line) for line in raw.splitlines()];rows=[x for x in frames if all(s in x for s in ADC_COLUMNS) and 'sample_idx' in x]
            v=check_rows(rows,30);f=features300(rows[:300]);assert np.allclose(f,extract(v,10)['raw3'])
            p=clf.predict(f.reshape(1,-1))[0];prob=clf.predict_proba(f.reshape(1,-1))[0]
            result.append({'capture':stem,'operator_label':label,'origin':'unverified','old_30cycle_prediction':meta['roast_predicted'],'candidate_10cycle_prediction':str(p),'features':dict(zip(FEATURES,f.tolist())),'uncalibrated_probabilities':dict(zip(clf.classes_.tolist(),prob.tolist())),'capture_sha256':meta['capture_sha256']})
        except Exception as e:result.append({'capture':stem,'operator_label':label,'error':type(e).__name__+': '+str(e)[:180]})
    return result

def main():
    assert sklearn.__version__=='1.7.2',sklearn.__version__
    chosen=json.loads((OUT/'summary.json').read_text())['selected_10cycle'];assert (chosen['model'],chosen['features'])==('RF','raw3')
    t,xs,rejected,invalid,dup=load();assert len(t)==199 and not rejected
    tr=np.flatnonzero(t.cohort!='c');te=np.flatnonzero(t.cohort=='c');X=xs[10]['raw3'];y=t.roast.to_numpy();yt=y[tr]
    folds=pd.read_csv(OUT/'folds.csv');cv={}
    for name in ('origin','batch'):
        p=np.empty(len(tr),dtype=object)
        for fold,g in folds[folds.scheme==name].groupby('fold'):
            b=np.flatnonzero(t.iloc[tr].filename.isin(g.filename));a=np.setdiff1d(np.arange(len(tr)),b)
            p[b]=model('RF').fit(X[tr[a]],yt[a]).predict(X[tr[b]])
        cv[name]=metrics(yt,p)
    clf=model('RF').fit(X[tr],yt);pred=clf.predict(X[te]);diag=metrics(y[te],pred)
    PRIVATE.mkdir(parents=True,exist_ok=False);artifact=PRIVATE/'rf100_10cycle_research_only.joblib';joblib.dump(clf,artifact)
    report={'model':'RandomForestClassifier','n_estimators':100,'sklearn':sklearn.__version__,'features':FEATURES,'classes':clf.classes_.tolist(),'cycles':10,'samples':300,'training_n':len(tr),'diagnostic_c_n':len(te),'cv':cv,'diagnostic_c':diag,'confusion_c':confusion_matrix(y[te],pred,labels=LABELS).tolist(),'artifact_sha256':digest(artifact),'deployment_approved':False,'artifact_path':'private/ai10_take30_diagnostic/rf100_10cycle_research_only.joblib','physical_archive_diagnostic':[]}
    print('COMPATIBLE_CANDIDATE',json.dumps({k:v for k,v in report.items() if k!='physical_archive_diagnostic'}),flush=True)
    report['physical_archive_diagnostic']=diagnose_archives(clf)
    (OUT/'rf10_compatible_diagnostic.json').write_text(json.dumps(report,indent=2)+'\n',encoding='utf8')
    print('PHYSICAL_ARCHIVE_DIAGNOSTIC',json.dumps(report['physical_archive_diagnostic']),flush=True)
if __name__=='__main__':main()
