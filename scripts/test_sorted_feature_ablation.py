"""QA and reproducible paired diagnostic for sorted 30-cycle feature ablation."""
from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pandas as pd
from PIL import Image

from compare_sorted_30cycle_feature_ablation import OUT, SOURCE, CORE, BASE, EXTRA, extra_features
from benchmark_sorted_30cycle_readiness import ORIGINS
from merge_new_30_siklus_audit import checksum

ROOT = Path(__file__).resolve().parents[1]
SORT_QA = ROOT / "results/dataset_sorting_readiness_20261110"
LABELS = ["light", "medium", "dark"]


def qa():
    meta = json.loads((OUT / "summary.json").read_text(encoding="utf8"))
    t = pd.read_csv(OUT / "recording_features_extracted.csv")
    labels = pd.read_csv(SORT_QA / "all_csv_audit.csv")
    score = pd.read_csv(OUT / "ablation_model_scores.csv")
    pred = pd.read_csv(OUT / "holdout_c_predictions.csv")
    cv = pd.read_csv(OUT / "train_origin_cv_predictions.csv")
    redundancy = pd.read_csv(OUT / "feature_redundancy_training_only.csv")
    previous = pd.read_csv(SORT_QA / "cohort_c_holdout_model_diagnostic.csv")
    definitions = json.loads((OUT / "feature_sets.json").read_text(encoding="utf8"))
    assert (meta["train_count"],meta["holdout_c_count"]) == (133,66)
    assert len(t)==199 and t.filename.is_unique
    assert len(score)==26 and score.configuration.nunique()==13
    assert len(pred)==26*66 and len(cv)==26*133
    assert len(redundancy)==30
    assert len(definitions)==13
    assert score[["configuration","model"]].duplicated().sum()==0
    assert set(score.model)=={"LogReg_L2","SVM_RBF"}
    assert not set(meta["excluded_incomplete_kept"]).intersection(set(t.filename))
    assert not set(meta["removed_duplicate_batch"]).intersection(set(t.filename))
    assert not set(t[t.cohort=="c"].batch).intersection(set(t[t.cohort.isin(["a","b"])].batch))
    assert len(t[t.cohort=="c"])==66 and len(t[t.cohort.isin(["a","b"])])==133
    assert set(t.origin)==set(ORIGINS)
    assert t[["origin","roast","batch"]].duplicated().sum()==0
    assert t.isna().sum().sum()==0
    assert all(int(r.feature_count)==len(definitions[r.configuration]) for r in score.itertuples())
    # Baseline numbers must be IDENTICAL to the published prior benchmark,
    # ensuring any difference comes from new features rather than dataset changes.
    name_map={"CORE3_F9_BASE":"TGS822_TGS2602_TGS816",
              "ALL10_F30_BASE":"ALL10_LOCAL_CONTRAST"}
    for new,old in name_map.items():
        for name in ["SVM_RBF","LogReg_L2"]:
            a=score[(score.configuration==new)&(score.model==name)].iloc[0]
            b=previous[(previous.feature_set==old)&(previous.model==name)].iloc[0]
            assert np.isclose(a.train_logo_balanced_accuracy,b.train_origin_cv_balanced_accuracy,atol=1e-10)
            assert np.isclose(a.holdout_c_balanced_accuracy,b.holdout_c_balanced_accuracy,atol=1e-10)
    # Independent spot-check of new features on original, checksum-matched CSV.
    lookups=labels.set_index("filename")
    for row in t.iloc[[0,37,88,132,170,198]].itertuples():
        original=lookups.loc[row.filename]
        path=SOURCE / original.relative_path
        assert checksum(path)==original.sha256
        df=pd.read_csv(path)
        for sensor in CORE:
            computed=extra_features(df[sensor].to_numpy(dtype=float).reshape(30,30))
            for feat,x in computed.items():
                assert np.isclose(x,getattr(row,f"{feat}__{sensor}"),atol=1e-7)
    # Paired diagnostic interval, stratified within the manually selected
    # 66 test files; this is not a deployment-level uncertainty estimate.
    subset=pred[(pred.model=="SVM_RBF") &
                pred.configuration.isin(["CORE3_F9_BASE","CORE3_F12_BASELINE_IQR","CORE3_F18_ALL"])]
    reference=subset[subset.configuration=="CORE3_F9_BASE"].sort_values("filename")
    truth=reference.truth.to_numpy()
    cohort={name:subset[subset.configuration==name].set_index("filename")
            .loc[reference.filename].holdout_c_pred.to_numpy()
            for name in ["CORE3_F9_BASE","CORE3_F12_BASELINE_IQR","CORE3_F18_ALL"]}
    rng=np.random.default_rng(42)
    idx_groups=[np.flatnonzero(truth==c) for c in LABELS]
    interval=[]
    for name in ["CORE3_F12_BASELINE_IQR","CORE3_F18_ALL"]:
        arr=[]
        for _ in range(5000):
            ix=np.concatenate([rng.choice(g,len(g),replace=True) for g in idx_groups])
            delta=np.mean([np.mean(cohort[name][ix][truth[ix]==c]==c)-
                           np.mean(cohort["CORE3_F9_BASE"][ix][truth[ix]==c]==c)
                           for c in LABELS])
            arr.append(delta)
        pts=np.quantile(arr,[.025,.5,.975])
        interval.append({"model":"SVM_RBF","candidate":name,"reference":"CORE3_F9_BASE",
                        "observed_change_balanced_accuracy":float(
                            score[(score.configuration==name)&(score.model=="SVM_RBF")]
                                .holdout_c_balanced_accuracy.iloc[0]-
                            score[(score.configuration=="CORE3_F9_BASE")&(score.model=="SVM_RBF")]
                                .holdout_c_balanced_accuracy.iloc[0]),
                        "bootstrap_ci_low":float(pts[0]),"bootstrap_ci_high":float(pts[2]),
                        "candidate_new_correct":int(((cohort[name]==truth)&(cohort["CORE3_F9_BASE"]!=truth)).sum()),
                        "candidate_new_wrong":int(((cohort[name]!=truth)&(cohort["CORE3_F9_BASE"]==truth)).sum()),
                        "bootstrap_replicates":5000,
                        "interpretation":"descriptive stratified file-level resampling only; not robust to shared physical specimen/device and manual sorting"})
    pd.DataFrame(interval).to_csv(OUT/"paired_holdout_uncertainty.csv",index=False,encoding="utf-8-sig")
    # Plot integrity
    img=OUT/"feature_ablation_train_cv.png"
    assert img.is_file() and img.stat().st_size>1000
    with Image.open(img) as im:
        im.verify()
    print("SORTED_FEATURE_ABLATION_QA_PASS",json.dumps({
        "file_count":199,"train":133,"test":66,"excluded_incomplete":4,
        "retained_features_tested":13,"fit_per_model":26,
        "reproduces_previous_9feature_benchmark":True,
        "spotchecked_raw_CSV":6,"paired_intervals":interval,
        "raw_not_modified":True
    },ensure_ascii=True),flush=True)
    return interval


if __name__=="__main__":
    qa()
