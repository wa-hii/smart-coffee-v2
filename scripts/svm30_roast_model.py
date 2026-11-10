#!/usr/bin/env python3
"""Smart Coffee 30-cycle SVM, exact nine-feature baseline-corrected contract.

NO USB or Nextion access. The model is exploratory, not approved production AI.
One CSV = one sample: 30 x (25 purge + 5 collect) = exactly 900 ADC records.
For each of TGS822, TGS2602, TGS816:
  purge baseline for cycle = median(purge samples 21..25)
  cycle response = mean(collecting samples 1..5) - purge baseline
  three features = median(cycle response), mean(cycle response),
                   median(last five cycle responses) -
                   median(first five cycle responses)
Training-only z-score is INSIDE the serialized SVM pipeline.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
from pathlib import Path
import statistics
import sys

SENSORS=("adc_tgs822","adc_tgs2602","adc_tgs816")
FEATURE_NAMES=("median_phase_response","mean_phase_response",
               "response_early_late")
FEATURE_ORDER=tuple(f"{f}__{s}" for s in SENSORS for f in FEATURE_NAMES)
CLASSES={"light","medium","dark"}
ADC_COLUMNS=("adc_tgs822","adc_mq135","adc_mq3","adc_tgs2611",
             "adc_tgs2620","adc_tgs2600","adc_tgs2602","adc_mq8",
             "adc_tgs813","adc_tgs816")
REQUIRED=("timestamp","run_id","phase","sample_idx",*ADC_COLUMNS)
EXPECTED_SAMPLES=900
EXPECTED_CYCLES=30


class InvalidCapture(ValueError):
    """Fail closed on malformed or incomplete sensor acquisitions."""


def digest(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def extract_features(csv_path:Path)->dict[str,float]:
    with csv_path.open(newline="",encoding="utf-8-sig") as fh:
        reader=csv.DictReader(fh)
        if not reader.fieldnames or not set(REQUIRED).issubset(reader.fieldnames):
            raise InvalidCapture("missing_required_columns")
        readings={s:[] for s in SENSORS}
        count=0
        previous_ts=None
        for row in reader:
            if count>=EXPECTED_SAMPLES or None in row or any(x is None for x in row.values()):
                raise InvalidCapture("too_many_or_malformed_rows")
            cycle=count//30+1
            pos=count%30
            phase="purging" if pos<25 else "collecting"
            idx=pos+1 if pos<25 else pos-24
            try:
                expected=(int(row["run_id"])==cycle and
                          int(row["sample_idx"])==idx and
                          row["phase"]==phase)
                ts=int(row["timestamp"])
                value={s:float(row[s]) for s in ADC_COLUMNS}
            except (TypeError,ValueError,OverflowError,KeyError) as e:
                raise InvalidCapture("invalid_record_field") from e
            if not expected:
                raise InvalidCapture(f"cycle_phase_index_invalid_at_{count+1}")
            if previous_ts is not None and ts<=previous_ts:
                raise InvalidCapture("timestamp_out_of_order")
            previous_ts=ts
            if any(not math.isfinite(v) or v<0 or v>32767 for v in value.values()):
                raise InvalidCapture("sensor_adc_out_of_range")
            for s in SENSORS:
                readings[s].append(value[s])
            count+=1
    if count!=EXPECTED_SAMPLES:
        raise InvalidCapture(f"incomplete_{count}_of_900")
    output={}
    for s in SENSORS:
        adc=readings[s]
        response=[]
        for cycle in range(EXPECTED_CYCLES):
            v=adc[cycle*30:(cycle+1)*30]
            baseline=statistics.median(v[20:25])
            response.append(statistics.mean(v[25:30])-baseline)
        output[f"median_phase_response__{s}"]=float(statistics.median(response))
        output[f"mean_phase_response__{s}"]=float(statistics.mean(response))
        output[f"response_early_late__{s}"]=float(
            statistics.median(response[-5:])-statistics.median(response[:5]))
    if list(output)!=list(FEATURE_ORDER):
        raise AssertionError("feature_contract_order_drift")
    return output


def verify_model(model_path:Path,metadata_path:Path)->dict:
    info=json.loads(metadata_path.read_text(encoding="utf8"))
    if (info.get("model_type")!="SVC_RBF" or
        info.get("feature_order")!=list(FEATURE_ORDER) or
        info.get("train_n")!=133 or
        info.get("training_preprocessing")!="StandardScaler fitted on cohort a+b only" or
        not isinstance(info.get("artifact_sha256"),str) or
        info.get("deployed_to_production") is not False):
        raise ValueError("svm30_model_manifest_incompatible")
    if digest(model_path)!=info["artifact_sha256"]:
        raise ValueError("svm30_model_sha256_mismatch")
    return info


def predict(csv_path:Path,model_path:Path,metadata_path:Path,*,model=None)->dict:
    features=extract_features(csv_path)
    info=verify_model(model_path,metadata_path)
    if model is None:
        import sklearn
        if sklearn.__version__!=info.get("sklearn_version"):
            raise ValueError("svm30_sklearn_version_mismatch")
        import joblib
        model=joblib.load(model_path)  # only SHA-pinned trusted local artifact
    if not hasattr(model,"named_steps") or set(model.named_steps)!={"global_train_zscore","classifier"}:
        raise ValueError("svm30_pipeline_schema_mismatch")
    svm=model.named_steps["classifier"]
    if (svm.kernel!="rbf" or svm.C!=1 or svm.gamma!="scale" or
        svm.class_weight!="balanced" or
        set(svm.classes_)!=CLASSES):
        raise ValueError("svm30_classifier_incompatible")
    import numpy as np
    values=np.array([[features[key] for key in FEATURE_ORDER]],dtype=float)
    label=str(model.predict(values)[0])
    if label not in CLASSES:
        raise ValueError("svm30_invalid_prediction_class")
    return {"status":"OFFLINE_CANDIDATE","roast_predicted":label,
            "feature_order":list(FEATURE_ORDER),"features":features,
            "model_type":"SVM_RBF","n_sensor_samples":EXPECTED_SAMPLES,
            "class_confidence":None,"probability_calibrated":False,
            "model_sha256":info["artifact_sha256"],
            "serial_opened":False,"nextion_updated":False,
            "deployed_to_production":False}


def main(argv=None):
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--input",type=Path,required=True)
    ap.add_argument("--model",type=Path)
    ap.add_argument("--metadata",type=Path)
    ap.add_argument("--validate-only",action="store_true")
    args=ap.parse_args(argv)
    if args.validate_only:
        result={"status":"VALID_CAPTURE","features":extract_features(args.input),
                "feature_order":list(FEATURE_ORDER),"serial_opened":False}
    else:
        if not args.model or not args.metadata:
            ap.error("prediction requires --model and --metadata")
        result=predict(args.input,args.model,args.metadata)
    print(json.dumps(result,ensure_ascii=False))
    return 0


if __name__=="__main__":
    sys.exit(main())
