"""Recompute SVM 9-feature training inputs from QC-valid original CSVs.

Never accepts the manual kept label on its own. Enforces previous audit SHA,
strict 900-row acquisition, deduplicated origin/roast/batch, and exact
feature parity with the previous benchmark before writing staging CSV.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np
import pandas as pd

from benchmark_sorted_30cycle_readiness import prepare
from svm30_roast_model import FEATURE_ORDER, extract_features

ROOT=Path(__file__).resolve().parents[1]
SOURCE=ROOT/"data/dataset sorting"
AUDIT=ROOT/"results/dataset_sorting_readiness_20261110/all_csv_audit.csv"
OUT=ROOT/"results/svm30_candidate_20261111"


def run(out:Path=OUT):
    if any((out/name).exists() for name in
           ("train_a_b_133.csv","holdout_c_66.csv")):
        raise FileExistsError("protect_existing_candidate_feature_tables")
    previous,duplicates=prepare()
    audit=pd.read_csv(AUDIT)
    lookups=audit.set_index("filename")
    assert lookups.index.is_unique
    assert len(previous)==199 and len(duplicates)==1
    blocked=set(audit.loc[(audit.sort_status=="kept") &
                          (~audit.structurally_valid),"filename"])
    assert len(blocked)==4 and set(previous.filename).isdisjoint(blocked)
    assert not previous[["origin","roast","batch"]].duplicated().any()
    rows=[]
    for i,row in enumerate(previous.itertuples(),1):
        source=lookups.loc[row.filename]
        assert source.sort_status=="kept" and bool(source.structurally_valid)
        path=SOURCE/Path(str(source.relative_path))
        if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest()!=source.sha256:
            raise RuntimeError("source_missing_or_modified:"+row.filename)
        f=extract_features(path)
        for name in FEATURE_ORDER:
            expected=float(getattr(row,name))
            if not np.isclose(f[name],expected,rtol=0,atol=1e-7):
                raise AssertionError(f"feature_mismatch:{row.filename}:{name}:{f[name]}:{expected}")
        rows.append({"filename":row.filename,"cohort":row.cohort,
                     "origin":row.origin,"roast":row.roast,"batch":row.batch,
                     "source_sha256":str(source.sha256),**f})
        if i%50==0:
            print("SVM_EXTRACTED",i,199,flush=True)
    table=pd.DataFrame(rows)
    train=table[table.cohort.isin(["a","b"])].copy()
    test=table[table.cohort=="c"].copy()
    assert len(train)==133 and len(test)==66
    assert set(train.batch).isdisjoint(test.batch)
    assert set(train.origin)=={"CAT","GAW","GRB","MING","TEM","TOR"}
    assert set(train.roast)=={"light","medium","dark"}
    assert not table[list(FEATURE_ORDER)].isna().any().any()
    out.mkdir(parents=True,exist_ok=True)
    train.to_csv(out/"train_a_b_133.csv",index=False,encoding="utf-8")
    test.to_csv(out/"holdout_c_66.csv",index=False,encoding="utf-8")
    summary={
        "feature_order":list(FEATURE_ORDER),
        "training_files":len(train),"test_files":len(test),
        "train_groups":sorted(train.origin.unique().tolist()),
        "excluded_invalid_kept":sorted(blocked),
        "excluded_duplicate_filenames":duplicates.filename.tolist(),
        "source":"structurally_valid + manual_kept + dedup origin,roast,batch",
        "feature_parity":"recomputed independently from 199 original SHA-pinned CSV and matched existing 9 benchmark features (absolute tolerance 1e-7)",
        "test_policy":"Never use cohort c for scaler fit, feature tuning or training",
        "files":{
           name:hashlib.sha256((out/name).read_bytes()).hexdigest()
           for name in ("train_a_b_133.csv","holdout_c_66.csv")
        },
    }
    (out/"source_manifest.json").write_text(
        json.dumps(summary,indent=2,ensure_ascii=False)+"\n",encoding="utf8")
    print("SVM_FEATURE_EXPORT_PASS",json.dumps(summary,ensure_ascii=False),flush=True)


if __name__=="__main__":
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir",type=Path,default=OUT)
    run(parser.parse_args().output_dir)
