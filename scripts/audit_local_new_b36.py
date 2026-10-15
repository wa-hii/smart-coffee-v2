"""Read-only inventory/QC of root-level untracked B36/B37 acquisitions.

Run only on explicit frozen filenames supplied from current git status.
No training, model selection, hardware, or edits to raw data.
"""
from pathlib import Path
import hashlib, json, argparse
import numpy as np
import pandas as pd
from acquisition_schema import ADC_COLS, CSV_COLUMNS
from validate_acquisition import validate_file, classify_rows

ROOT=Path(__file__).resolve().parents[1]
RAW=ROOT/'data/raw'
IRUL=RAW/'irul_B36_B37'

def audit(names):
    old=pd.read_csv(ROOT/'data/analysis/stage2_v2/file_manifest.csv',dtype=str).fillna('')
    frozen=set(old.source_sha256)
    rows=[]; cycles=[]
    for name in sorted(names):
        path=RAW/name
        if path.name!=name or not path.is_file() or not name.endswith('.csv'):
            raise ValueError('Unsafe or missing source '+name)
        data=path.read_bytes(); digest=hashlib.sha256(data).hexdigest()
        df=pd.read_csv(path)
        errs=validate_file(path)
        sensors,meta,partial=classify_rows(df) if list(df.columns)==CSV_COLUMNS else ([],[],[])
        s=df.loc[sensors] if len(sensors) else pd.DataFrame()
        ad=s[ADC_COLS].apply(pd.to_numeric,errors='coerce') if len(s) else pd.DataFrame()
        peer=IRUL/name
        peer_hash=hashlib.sha256(peer.read_bytes()).hexdigest() if peer.is_file() else ''
        phase=s.groupby(['run_id','phase']).size().to_dict() if len(s) else {}
        rows.append(dict(file=name,sha256=digest,bytes=len(data),batch=str(s.batch_id.iloc[0]) if len(s) else '',
          sample_code=str(s.sample_id.iloc[0]) if len(s) else '',roast_ui=str(s.roast_level.iloc[0]) if len(s) else '',
          origin_ui=str(s.origin.iloc[0]) if len(s) else '',canonical_pass=not bool(errs),
          error_count=len(errs),errors=' | '.join(errs),sensor_rows=len(s),
          purging_rows=int(s.phase.eq('purging').sum()) if len(s) else 0,
          collecting_rows=int(s.phase.eq('collecting').sum()) if len(s) else 0,
          cycles=int(s.run_id.nunique()) if len(s) else 0,
          adc_missing=int(ad.isna().sum().sum()) if len(ad) else 0,
          adc_zero=int(ad.eq(0).sum().sum()) if len(ad) else 0,
          adc_saturated=int(ad.ge(32767).sum().sum()) if len(ad) else 0,
          temp_valid=int(pd.to_numeric(s.temperature,errors='coerce').notna().sum()) if len(s) else 0,
          humidity_valid=int(pd.to_numeric(s.humidity,errors='coerce').notna().sum()) if len(s) else 0,
          sha_matches_historical=digest in frozen,irul_same_name_exists=peer.is_file(),
          irul_same_name_same_bytes=bool(peer_hash==digest),irul_peer_sha256=peer_hash,
          physical_specimen_provenance_verified=False,blind_test_eligible=False))
        for c in range(1,6):
          p=s[(s.run_id==c)&(s.phase=='purging')] if len(s) else pd.DataFrame()
          t=s[(s.run_id==c)&(s.phase=='collecting')] if len(s) else pd.DataFrame()
          for sensor in ADC_COLS:
            b=float(pd.to_numeric(p[sensor],errors='coerce').tail(5).median()) if len(p) else np.nan
            z=float(pd.to_numeric(t[sensor],errors='coerce').mean()) if len(t) else np.nan
            cycles.append(dict(file=name,cycle=c,channel=sensor,purging_rows=len(p),collecting_rows=len(t),
              purge_baseline=b,collect_mean=z,delta_adc=z-b,relative_response=(z-b)/max(abs(b),1)))
    summary=dict(status='B36_B37_LOCAL_QA_ONLY_NOT_BLIND',files=len(rows),
      B36=sum('_B36.csv' in r['file'] for r in rows),B37=sum('_B37.csv' in r['file'] for r in rows),
      canonical_pass=sum(r['canonical_pass'] for r in rows),
      canonical_hold=[r['file'] for r in rows if not r['canonical_pass']],
      total_sensor_rows=sum(r['sensor_rows'] for r in rows),
      missing_all_temperature=sum(r['temp_valid']==0 for r in rows),
      missing_all_humidity=sum(r['humidity_valid']==0 for r in rows),
      same_name_on_irul=sum(r['irul_same_name_exists'] for r in rows),
      same_bytes_as_irul=sum(r['irul_same_name_same_bytes'] for r in rows),
      duplicate_historical_sha=sum(r['sha_matches_historical'] for r in rows),
      independent_specimen_ids_verified=0,blind_test_approved=False,model_promotion_allowed=False)
    return pd.DataFrame(rows),pd.DataFrame(cycles),summary

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--files',nargs='+',required=True)
    parser.add_argument('--output-dir',type=Path,required=True)
    args=parser.parse_args(); out=args.output_dir.resolve()
    if out.exists() or RAW.resolve()==out or RAW.resolve() in out.parents:
        raise ValueError('Refuse overwrite and raw destinations')
    files,cycles,summary=audit(args.files);out.mkdir(parents=True)
    files.to_csv(out/'file_quality.csv',index=False)
    cycles.to_csv(out/'cycle_diagnostics.csv',index=False)
    (out/'summary.json').write_text(json.dumps(summary,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    print(json.dumps(summary,indent=2,ensure_ascii=False))

if __name__=='__main__':main()
