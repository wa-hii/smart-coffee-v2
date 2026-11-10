#!/usr/bin/env python3
"""30-cycle Smart Coffee E-Nose RF inference, offline/host-only by default.

Reads CANONICAL ADC columns from CSV containing exactly 30 complete cycles of
25 purge + 5 collect samples (900 rows). Features MATCH supplied helper:
  tgs822_max_mean, tgs822_purging_mean_mean, mq8_max_mean.
There is NO baseline subtraction, fit, global Z-score, or test-label input.

This utility DOES NOT open serial ports, transmit to ATmega/Nextion, or
operate pumps. Do not apply this 30-cycle model to 5-cycle AI_TEST captures.

The joblib format executes Python during loading. Load ONLY the provenance-
verified SHA256-pinned artifact and within an isolated Python environment.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import sys

FEATURES = ("tgs822_max_mean","tgs822_purging_mean_mean","mq8_max_mean")
CLASSES = ("dark","light","medium")
ADC_COLUMNS = ("adc_tgs822","adc_mq135","adc_mq3","adc_tgs2611",
               "adc_tgs2620","adc_tgs2600","adc_tgs2602","adc_mq8",
               "adc_tgs813","adc_tgs816")
REQUIRED_COLUMNS = ("timestamp","run_id","phase","sample_idx",*ADC_COLUMNS)
EXPECTED_ROWS = 900
EXPECTED_CYCLES = 30
EXPECTED_SHA = "b2b6e8d8ff03e92c695c1b0b55a8c06ea9d4178249c9ce012203e602ff1bcf5d"
EXPECTED_SKLEARN_VERSION = "1.7.2"
ROOT = Path(__file__).resolve().parents[1]


class InvalidCapture(ValueError):
    """A capture was incomplete, corrupted or incompatible with RF training."""


def validate_extract(csv_path: Path) -> tuple[dict[str,float],dict]:
    """Strict validation before feature extraction; never invent missing ADC."""
    if not csv_path.is_file():
        raise InvalidCapture("csv_not_found")
    with csv_path.open(newline="",encoding="utf-8-sig") as fh:
        reader=csv.DictReader(fh)
        if not reader.fieldnames or not set(REQUIRED_COLUMNS).issubset(reader.fieldnames):
            raise InvalidCapture("missing_required_columns")
        # Bound memory and reject incomplete/oversized captures.
        rows=[]
        for row in reader:
            if len(rows)>=EXPECTED_ROWS:
                raise InvalidCapture("too_many_rows")
            if None in row or any(x is None for x in row.values()):
                raise InvalidCapture("malformed_csv_width")
            rows.append(row)
    if len(rows)!=EXPECTED_ROWS:
        raise InvalidCapture(f"wrong_row_count_{len(rows)}")
    purge_means=[]
    collect_822_peaks=[]
    collect_mq8_peaks=[]
    last_ts=-1
    for cycle in range(1,EXPECTED_CYCLES+1):
        subset=rows[(cycle-1)*30:cycle*30]
        purge_822=[]
        collect_822=[]
        collect_mq8=[]
        for index,row in enumerate(subset):
            phase="purging" if index<25 else "collecting"
            idx=index+1 if index<25 else index-24
            try:
                run_id=int(row["run_id"])
                sample_idx=int(row["sample_idx"])
                timestamp=int(row["timestamp"])
                values={s:float(row[s]) for s in ADC_COLUMNS}
            except (ValueError,TypeError,OverflowError) as e:
                raise InvalidCapture("non_numeric_field") from e
            if run_id!=cycle or row["phase"]!=phase or sample_idx!=idx:
                raise InvalidCapture(f"invalid_cycle_phase_idx_at_row_{(cycle-1)*30+index+1}")
            if timestamp<=last_ts:
                raise InvalidCapture("stale_or_duplicate_timestamp")
            last_ts=timestamp
            if any(not math.isfinite(v) or v<0 or v>32767 for v in values.values()):
                raise InvalidCapture("invalid_sensor_adc")
            if phase=="purging":
                purge_822.append(values["adc_tgs822"])
            else:
                collect_822.append(values["adc_tgs822"])
                collect_mq8.append(values["adc_mq8"])
        # These are the exact feature definitions in the uploaded helper.
        purge_means.append(sum(purge_822)/25)
        collect_822_peaks.append(max(collect_822))
        collect_mq8_peaks.append(max(collect_mq8))
    features={
        "tgs822_max_mean":sum(collect_822_peaks)/EXPECTED_CYCLES,
        "tgs822_purging_mean_mean":sum(purge_means)/EXPECTED_CYCLES,
        "mq8_max_mean":sum(collect_mq8_peaks)/EXPECTED_CYCLES,
    }
    sha=hashlib.sha256(csv_path.read_bytes()).hexdigest()
    return features,{"rows":len(rows),"cycles":EXPECTED_CYCLES,"purge_s":25,
                     "collect_s":5,"input_sha256":sha,"recording":csv_path.name}


def verify_artifact(model_path: Path,metadata_path: Path) -> dict:
    try:
        info=json.loads(metadata_path.read_text(encoding="utf-8"))
    except (OSError,ValueError) as e:
        raise ValueError("model_metadata_missing_or_invalid") from e
    if (info.get("features")!=list(FEATURES) or
        set(info.get("classes",[]))!=set(CLASSES) or
        info.get("model")!="RandomForestClassifier" or
        info.get("n_estimators")!=500):
        raise ValueError("model_metadata_schema_mismatch")
    if not model_path.is_file():
        raise FileNotFoundError(f"model_not_found: {model_path}")
    digest=hashlib.sha256(model_path.read_bytes()).hexdigest()
    if digest!=EXPECTED_SHA:
        raise ValueError("unapproved_model_sha256")
    return {"sha256":digest,**info}


def predict_validated(features: dict[str,float],clf) -> dict:
    """In-memory inference; no built-in hard-coded confidence threshold."""
    import numpy as np
    names=list(FEATURES)
    if getattr(clf,"n_features_in_",None)!=len(names):
        raise ValueError("model_feature_count_incompatible")
    actual=[str(x) for x in getattr(clf,"classes_",[])]
    if set(actual)!=set(CLASSES) or len(actual)!=3:
        raise ValueError("model_class_order_incompatible")
    if (hasattr(clf,"feature_names_in_") and
        list(clf.feature_names_in_)!=names):
        raise ValueError("model_feature_names_incompatible")
    matrix=np.array([[features[k] for k in names]],dtype=float)
    labels=clf.predict(matrix)
    proba=clf.predict_proba(matrix)
    if getattr(labels,"shape",None)!=(1,) or getattr(proba,"shape",None)!=(1,3):
        raise ValueError("invalid_model_output_shape")
    guess=str(labels[0]).lower()
    p=[float(x) for x in proba[0]]
    if guess not in CLASSES or not all(math.isfinite(x) and 0<=x<=1 for x in p):
        raise ValueError("invalid_model_output")
    if abs(sum(p)-1)>0.000001:
        raise ValueError("invalid_probability_sum")
    return {"roast_predicted":guess,
            "probabilities_uncalibrated":dict(zip(actual,p)),
            "probability_note":"RF vote fractions, not calibrated confidence"}


def predict_capture(csv_path:Path,model_path:Path,meta_path:Path, *,
                    validate_only:bool=False,model=None)->dict:
    feats,qa=validate_extract(csv_path)
    payload={"status":"VALID_CAPTURE" if validate_only else "OFFLINE_CANDIDATE",
             "input":qa,"features":feats,"feature_order":list(FEATURES),
             "model_kind":"rf500_30cycle","pi_to_mcu_transmitted":False,
             "nextion_updated":False,
             "origin_predicted":None,"deployment_approved":False}
    if validate_only:
        return payload
    verified=verify_artifact(model_path,meta_path)
    if model is None:
        # Joblib/Pickle deserialization is executable: pinned hash and trusted
        # user-provided origin are mandatory prerequisites.
        import joblib
        model=joblib.load(model_path)
    payload.update(predict_validated(feats,model))
    payload["model_sha256"]=verified["sha256"]
    return payload


def run_cli(argv:list[str]|None=None)->int:
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",required=True,type=Path,help="1 CSV or folder of CSVs")
    ap.add_argument("--model",type=Path,help="Explicit location of SHA-pinned final_model.joblib")
    ap.add_argument("--metadata",type=Path,help="Original final_model_info.json")
    ap.add_argument("--validate-only",action="store_true",
                    help="Validate and extract 3 features; NEVER load joblib")
    ap.add_argument("--output",type=Path,help="Optional host-only JSON report (NOT data/raw)")
    args=ap.parse_args(argv)
    if not args.validate_only and (args.model is None or args.metadata is None):
        ap.error("Prediksi memerlukan --model dan --metadata; atau gunakan --validate-only")
    target=args.input
    sources=sorted(target.glob("*.csv")) if target.is_dir() else [target]
    if not sources:
        ap.error("Folder tidak berisi CSV")
    source_roots=[ROOT/"data/raw", ROOT/"data/dataset sorting"]
    if args.output and (args.output.resolve()==target.resolve() or
                       (target.is_dir() and target.resolve() in args.output.resolve().parents) or
                       any(p.resolve()==args.output.resolve() or
                           p.resolve() in args.output.resolve().parents
                           for p in source_roots)):
        ap.error("Output must be outside input directory")
    model=None
    if not args.validate_only:
        # Never import or deserialize an untrusted model before checking its
        # provenance, metadata and exact hash.
        verify_artifact(args.model,args.metadata)
        import sklearn
        if sklearn.__version__!=EXPECTED_SKLEARN_VERSION:
            raise ValueError(f"sklearn_version_mismatch_expected_{EXPECTED_SKLEARN_VERSION}"
                             f"_got_{sklearn.__version__}")
        import joblib
        model=joblib.load(args.model)
    results=[]
    for path in sources:
        try:
            res=predict_capture(path,args.model,args.metadata,
                                validate_only=args.validate_only,model=model)
        except (InvalidCapture,ValueError,OSError,ImportError,RuntimeError) as exc:
            res={"status":"REJECTED","input_file":path.name,"reason":str(exc),
                 "pi_to_mcu_transmitted":False,"nextion_updated":False}
        results.append(res)
        print(json.dumps(res,ensure_ascii=False,allow_nan=False))
    if args.output:
        args.output.parent.mkdir(parents=True,exist_ok=True)
        args.output.write_text(json.dumps(results,indent=2,ensure_ascii=False,allow_nan=False)+"\n",
                               encoding="utf-8")
    return 0 if all(r["status"]!="REJECTED" for r in results) else 2


if __name__=="__main__":
    sys.exit(run_cli())
