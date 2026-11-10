#!/usr/bin/env python3
"""Fit the LOCKED 9-feature SVM using only sorted cohort a+b (133 records).

Training must run in the target Pi's isolated scikit-learn environment.
Existing holdout c is used once for descriptive diagnostics ONLY.
Never use holdout scores to change configuration/hyperparameters.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

import joblib
import numpy as np
import sklearn
from sklearn.metrics import balanced_accuracy_score, confusion_matrix, f1_score, recall_score
from sklearn.model_selection import LeaveOneGroupOut
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler
from sklearn.svm import SVC

from svm30_roast_model import CLASSES, FEATURE_ORDER, digest, verify_model

LABELS=("light","medium","dark")


def load(path:Path):
    with path.open(newline="",encoding="utf8") as fh:
        rows=list(csv.DictReader(fh))
    if not rows or not set(FEATURE_ORDER).issubset(rows[0]):
        raise ValueError("bad_training_feature_table")
    if len({r["filename"] for r in rows})!=len(rows):
        raise ValueError("duplicate_training_filename")
    if len({(r["origin"],r["roast"],r["batch"]) for r in rows})!=len(rows):
        raise ValueError("duplicate_roast_origin_batch")
    X=np.array([[float(r[f]) for f in FEATURE_ORDER] for r in rows],dtype=float)
    if not np.isfinite(X).all():
        raise ValueError("nonfinite_feature")
    y=np.array([r["roast"] for r in rows])
    g=np.array([r["origin"] for r in rows])
    if not set(y).issubset(CLASSES):
        raise ValueError("unexpected_roast")
    return rows,X,y,g


def pipeline():
    return Pipeline([
        ("global_train_zscore",StandardScaler()),
        ("classifier",SVC(kernel="rbf",C=1,gamma="scale",
                          class_weight="balanced",probability=False)),
    ])


def metrics(y,p):
    return {
        "balanced_accuracy":float(balanced_accuracy_score(y,p)),
        "macro_f1":float(f1_score(y,p,labels=LABELS,average="macro",zero_division=0)),
        "accuracy":float(np.mean(y==p)),
        "recall_by_roast":dict(zip(LABELS,[
            float(x) for x in recall_score(y,p,labels=LABELS,
                                           average=None,zero_division=0)])),
        "confusion_order":list(LABELS),
        "confusion":confusion_matrix(y,p,labels=LABELS).tolist(),
    }


def run(source:Path, output:Path):
    if output.exists():
        raise FileExistsError("refusing_to_overwrite_existing_svm_candidate")
    info=json.loads((source/"source_manifest.json").read_text(encoding="utf8"))
    for fname,expected_sha in info["files"].items():
        if digest(source/fname)!=expected_sha:
            raise ValueError("feature_table_sha256_mismatch:"+fname)
    train,xt,yt,groups=load(source/"train_a_b_133.csv")
    test,xu,yu,_=load(source/"holdout_c_66.csv")
    if (len(train)!=133 or len(test)!=66 or set(groups)!={"CAT","GAW","GRB","MING","TEM","TOR"}
        or {r["cohort"] for r in train}!={"a","b"} or {r["cohort"] for r in test}!={"c"}
        or set(r["batch"] for r in train)&set(r["batch"] for r in test)):
        raise ValueError("training_test_contract_changed")
    assert info["feature_order"]==list(FEATURE_ORDER)
    out_cv=np.empty(133,dtype=object)
    cv_fold=[]
    logo=LeaveOneGroupOut()
    for tr,va in logo.split(xt,yt,groups):
        assert set(groups[tr]).isdisjoint(set(groups[va]))
        model=pipeline().fit(xt[tr],yt[tr])
        out_cv[va]=model.predict(xt[va])
        cv_fold.append({"holdout_origin":str(groups[va][0]),"n":int(len(va)),
                        **metrics(yt[va],out_cv[va])})
    cv=metrics(yt,out_cv)
    candidate=pipeline().fit(xt,yt)
    predicted=candidate.predict(xu)
    holdout=metrics(yu,predicted)
    # Locked against previous benchmark numbers. Any deviation >2pp should
    # block promotion, not trigger tuning against the held-out cohort.
    if abs(cv["balanced_accuracy"]-0.547)>0.022 or abs(holdout["balanced_accuracy"]-0.653)>0.022:
        raise AssertionError("SVM_scores_differ_from_previous_locked_benchmark")
    output.mkdir(parents=True)
    artifact=output/"svm30_9feat_candidate.joblib"
    joblib.dump(candidate,artifact,compress=3)
    metadata={
        "model_type":"SVC_RBF",
        "feature_order":list(FEATURE_ORDER),
        "sensors":["adc_tgs822","adc_tgs2602","adc_tgs816"],
        "classes":sorted(CLASSES),
        "C":1,"gamma":"scale","kernel":"rbf","class_weight":"balanced",
        "n_cycles":30,"purging_s":25,"collecting_s":5,
        "train_n":133,"holdout_n":66,
        "training_preprocessing":"StandardScaler fitted on cohort a+b only",
        "baseline_correction":"median last 5 purge ADC per cycle, subtracted from 5 collecting ADC mean",
        "training_cohorts":["a","b"],
        "heldout_cohort":"c",
        "crossvalidation":"LeaveOneGroupOut(origin) inside cohort a+b",
        "cv_metrics":cv,"cv_fold_metrics":cv_fold,
        "holdout_diagnostic_only":holdout,
        "source_features_sha256":info["files"],
        "model_selection":"locked 9-feature SVM C=1 RBF gamma=scale before holdout; no tuning",
        "sklearn_version":sklearn.__version__,
        "numpy_version":np.__version__,
        "joblib_version":joblib.__version__,
        "artifact_sha256":digest(artifact),
        "deployed_to_production":False,
        "class_probability_calibrated":False,
        "limitations":["manual kept sorting","no confirmed independent physical specimens",
                       "device origin roast confounding","prospective unknown detection missing",
                       "model outputs class only (no calibrated probability)"],
    }
    (output/"svm30_9feat_metadata.json").write_text(
        json.dumps(metadata,ensure_ascii=False,indent=2)+"\n",encoding="utf8")
    with (output/"holdout_predictions.csv").open("w",newline="",encoding="utf8") as fh:
        writer=csv.writer(fh)
        writer.writerow(("filename","origin","true_roast","predicted_roast"))
        for row,y,p in zip(test,yu,predicted):
            writer.writerow((row["filename"],row["origin"],y,p))
    verify_model(artifact,output/"svm30_9feat_metadata.json")
    print("SVM30_TRAINING_QA_PASS",json.dumps({
        "train_n":133,"holdout_n":66,"cv_balanced_accuracy":cv["balanced_accuracy"],
        "holdout_balanced_accuracy":holdout["balanced_accuracy"],
        "holdout_macro_f1":holdout["macro_f1"],
        "holdout_recall":holdout["recall_by_roast"],
        "sha256":metadata["artifact_sha256"],"source_sha256":info["files"],
        "deployment_approved":False
    },ensure_ascii=True),flush=True)


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--features-dir",type=Path,required=True)
    ap.add_argument("--output-dir",type=Path,required=True)
    args=ap.parse_args(argv)
    run(args.features_dir,args.output_dir)
    return 0


if __name__=="__main__":
    sys.exit(main())
