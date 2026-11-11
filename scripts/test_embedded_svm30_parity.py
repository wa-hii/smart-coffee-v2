#!/usr/bin/env python3
"""B1/B2/B3 golden-model vs native streaming C++ / libsvm parity.

Uses the pinned *user-supplied* SVM and original feature helper.
Strictly rejects incomplete/invalid CSV before invoking the permissive
training-time helper. No Pi, serial, flashing, HMI, or actuator access.
The private golden vectors/results are saved below private/ (gitignored).
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import math
import subprocess
import sys
import warnings
from pathlib import Path

import joblib
import numpy as np
import sklearn
from sklearn.exceptions import InconsistentVersionWarning

ROOT=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(ROOT/"scripts"))
from svm30_roast_model import ADC_COLUMNS, InvalidCapture, extract_features
from svm30_embedded_features import FEATURE_ORDER
from export_svm30_for_avr import EXPECTED_SHA, EXPECTED_CLASSES


def sha(path:Path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def reference_module(path:Path):
    spec=importlib.util.spec_from_file_location("user_final_svm_helper",path)
    assert spec and spec.loader
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def strict_source(path:Path):
    # Previously vetted 30 x (25 purge + 5 collect), 10 ADC channels.
    extract_features(path)
    with path.open(newline="",encoding="utf-8-sig") as file:
        rows=list(csv.DictReader(file))
    if len(rows)!=900:
        raise InvalidCapture("not_900_samples")
    for row in rows:
        for col in ADC_COLUMNS:
            v=float(row[col])
            if not math.isfinite(v) or int(v)!=v or not 0<=v<=32767:
                raise InvalidCapture("non_integer_or_invalid_adc")
    return rows


def svm_gold(module,bundle,path:Path):
    c,p=module.load_cycles(path)
    names=tuple(str(n) for n in bundle["feature_names"])
    assert names==FEATURE_ORDER
    x=module.extract_features_for_names(c,p,names)
    if x.shape!=(30,) or not np.isfinite(x).all():
        raise ValueError("invalid_30_features")
    scaled=bundle["scaler"].transform(x.reshape(1,-1))
    return x,scaled[0],str(bundle["model"].predict(scaled)[0])


def libsvm_pair_scores(svm,scaled):
    """Independent float64 libsvm one-vs-one score reference.

    Not sklearn's public one-vs-rest decision_function; match internal
    dual coefficient layout and class-order tie handling.
    """
    sv=svm.support_vectors_
    kernel=np.exp(-float(svm._gamma)*np.sum((sv-scaled)**2,axis=1))
    counts=[int(v) for v in svm.n_support_]
    starts=[0,counts[0],counts[0]+counts[1]]
    scores=[]
    for i in range(3):
        for j in range(i+1,3):
            si,sj=starts[i],starts[j]
            value=(float(np.dot(svm.dual_coef_[j-1,si:si+counts[i]],
                                kernel[si:si+counts[i]]))+
                   float(np.dot(svm.dual_coef_[i,sj:sj+counts[j]],
                                kernel[sj:sj+counts[j]]))+
                   float(svm.intercept_[len(scores)]))
            scores.append(value)
    return scores


def native_input(rows):
    # Only cycle, phase, sample index and ADC values enter C++, not roast label.
    chunks=[]
    for row in rows:
        fields=[
            row["run_id"],
            "0" if row["phase"]=="purging" else "1",
            row["sample_idx"],
            *(str(int(float(row[col]))) for col in ADC_COLUMNS),
        ]
        chunks.append(" ".join(fields))
    return "\n".join(chunks)+"\n"


def native_prediction(binary:Path,serial_input:str):
    proc=subprocess.run([str(binary)],input=serial_input,text=True,
                        capture_output=True,timeout=40)
    if proc.returncode:
        raise RuntimeError(f"native_exit_{proc.returncode}:{proc.stderr[:180]}")
    result=json.loads(proc.stdout)
    if result["roast"] not in EXPECTED_CLASSES or len(result["features"])!=30:
        raise RuntimeError("invalid_native_response")
    return result


def safe_cases(root:Path,max_cases:int):
    from benchmark_sorted_30cycle_readiness import prepare
    valid,_=prepare()
    audit=__import__("pandas").read_csv(
        root/"results/dataset_sorting_readiness_20261110/all_csv_audit.csv")
    hashes={row.filename:(row.relative_path,row.sha256)
            for row in audit.itertuples()}
    # Prioritize all 66 holdout c before a+b, preserving breadth by roast.
    val=valid.copy()
    val["priority"]=val.cohort.map({"c":0,"a":1,"b":2})
    val=val.sort_values(["priority","roast","origin","filename"])
    # Round-robin by class across sorted cohort priority so L/M/D occur
    # even if --limit is small. This is an engineering parity corpus, NOT CV.
    groups={k:list(g.itertuples()) for k,g in val.groupby("roast")}
    cases=[]
    while any(groups.values()) and len(cases)<max_cases:
        for label in ("dark","light","medium"):
            if groups[label] and len(cases)<max_cases:
                case=groups[label].pop(0)
                relative,expected=hashes[case.filename]
                path=root/"data/dataset sorting"/relative
                if sha(path)!=expected:
                    raise RuntimeError("source_hash_drift:"+case.filename)
                cases.append((path,expected,label,case.cohort))
    return cases


def run(bundle:Path,helper:Path,binary:Path,output:Path,limit:int):
    if not bundle.is_file() or sha(bundle)!=EXPECTED_SHA:
        raise RuntimeError("refuse_unpinned_model")
    if output.exists():
        raise FileExistsError("protect_existing_golden_reference")
    if not binary.is_file():
        raise FileNotFoundError(binary)
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always",InconsistentVersionWarning)
        model=joblib.load(bundle)
    assert set(model)=={"model","scaler","feature_names","feature_indices","classes"}
    assert tuple(model["model"].classes_)==EXPECTED_CLASSES
    assert tuple(model["feature_names"])==FEATURE_ORDER
    ref=reference_module(helper)
    cases=safe_cases(ROOT,limit)
    summary=[]
    errors=[]
    failures=0
    max_score_abs=0.0
    min_score_to_boundary=float("inf")
    for i,(path,expected_sha,source_label,cohort) in enumerate(cases,1):
        data=strict_source(path)
        x,scaled,pred=svm_gold(ref,model,path)
        result=native_prediction(binary.resolve(),native_input(data))
        pair_gold=libsvm_pair_scores(model["model"],scaled)
        if len(result.get("pair_scores",[]))!=3:
            raise ValueError("native_missing_pairwise_scores")
        pair_errors=[abs(a-b) for a,b in zip(pair_gold,result["pair_scores"])]
        max_score_abs=max(max_score_abs,max(pair_errors))
        min_score_to_boundary=min(min_score_to_boundary,
                                  min(abs(v) for v in pair_gold))
        diff=np.abs(x-np.array(result["features"],dtype=float))
        max_abs=float(diff.max())
        max_rel=float((diff/np.maximum(1.0,np.abs(x))).max())
        if pred!=result["roast"]:
            failures+=1
        errors.append((max_abs,max_rel))
        summary.append({
            "filename":path.name,
            "sha256":expected_sha,
            "cohort":cohort,
            "source_roast_label_not_used_as_input":source_label,
            "python_model_prediction":pred,
            "avr_float32_simulation_prediction":result["roast"],
            "native_vote_margin":result["vote_margin"],
            "feature_max_absolute_error":max_abs,
            "feature_max_relative_error":max_rel,
            "features_python":x.tolist(),
            "features_avr_float32_simulation":result["features"],
            "features_scaled_python":scaled.tolist(),
            "libsvm_pair_scores_python":pair_gold,
            "libsvm_pair_scores_avr_float32_sim":result["pair_scores"],
            "max_pair_score_abs_error":max(pair_errors),
        })
        if i%10==0:
            print("B1_B2_B3_PARITY_PROGRESS",i,len(cases),flush=True)
    report={
        "status":"B1_B2_B3_NATIVE_GOLDEN_PARITY",
        "model_sha256":EXPECTED_SHA,
        "helper_sha256":sha(helper),
        "sklearn_reference_version":sklearn.__version__,
        "sklearn_pickle_version":"1.7.2",
        "version_warning_present":any(issubclass(w.category,InconsistentVersionWarning)
                                      for w in caught),
        "input_cases":len(summary),
        "classes_checked":sorted({item["source_roast_label_not_used_as_input"]
                                  for item in summary}),
        "prediction_mismatches":failures,
        "max_feature_absolute_error":max(a for a,b in errors),
        "max_feature_relative_error":max(b for a,b in errors),
        "max_pair_score_absolute_error":max_score_abs,
        "smallest_reference_pairwise_margin":min_score_to_boundary,
        "pair_score_parity_gate":"max absolute error <= 0.01",
        "value_gate":"relative_error <=0.003 or abs_error <=0.05 on every feature",
        "no_pi_usb_hardware":True,
        "cases":summary,
    }
    # Save only in a private, gitignored location.
    output.parent.mkdir(parents=True,exist_ok=True)
    output.write_text(json.dumps(report,indent=2,ensure_ascii=False)+"\n",
                      encoding="utf8")
    within=all(
        abs(x-y)<=0.05 or abs(x-y)/max(1.0,abs(x))<=0.003
        for case in summary
        for x,y in zip(case["features_python"],
                       case["features_avr_float32_simulation"])
    )
    concise={k:v for k,v in report.items() if k!="cases"}
    print("B1_B2_B3_PARITY_SUMMARY",json.dumps(concise),flush=True)
    if failures or not within or max_score_abs>0.01:
        raise AssertionError("native_svm_or_feature_parity_FAILED")


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--bundle",type=Path,required=True)
    ap.add_argument("--helper",type=Path,required=True)
    ap.add_argument("--binary",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--limit",type=int,default=36)
    args=ap.parse_args()
    assert 3<=args.limit<=199
    run(args.bundle,args.helper,args.binary,args.output,args.limit)


if __name__=="__main__":
    main()
