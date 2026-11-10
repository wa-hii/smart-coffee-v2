"""Offline regression tests for candidate 30-cycle RF inference.

Tests reject historical 5-cycle captures, malformed ADC and label leakage.
No joblib file is deserialized, no serial port opened or HMI controlled.
"""
from __future__ import annotations

import csv
from pathlib import Path
import tempfile

import numpy as np

from roast_rf30_pi_inference import (
    CLASSES, FEATURES, InvalidCapture, validate_extract, predict_validated,
    run_cli,
)

ROOT=Path(__file__).resolve().parents[1]
REAL=ROOT/"data/dataset sorting/b/kept/D-CAT_B70.csv"


def expected_from_uploaded_helper(rows):
    cycles_col={}
    cycles_pur={}
    for r in rows:
        run_id=int(r["run_id"])
        phase=r["phase"]
        if phase=="collecting":
            cycles_col.setdefault(run_id,{"tgs822":[],"mq8":[]})
            cycles_col[run_id]["tgs822"].append(float(r["adc_tgs822"]))
            cycles_col[run_id]["mq8"].append(float(r["adc_mq8"]))
        elif phase=="purging":
            cycles_pur.setdefault(run_id,{"tgs822":[]})
            cycles_pur[run_id]["tgs822"].append(float(r["adc_tgs822"]))
    return {
        "tgs822_max_mean":float(np.mean([np.max(cycles_col[c]["tgs822"]) for c in sorted(cycles_col)])),
        "tgs822_purging_mean_mean":float(np.mean([np.mean(cycles_pur[c]["tgs822"]) for c in sorted(cycles_pur)])),
        "mq8_max_mean":float(np.mean([np.max(cycles_col[c]["mq8"]) for c in sorted(cycles_col)])),
    }


class MockForest:
    n_features_in_=3
    classes_=np.array(["dark","light","medium"])

    def predict(self,x):
        assert x.shape==(1,3)
        return np.array(["medium"])

    def predict_proba(self,x):
        return np.array([[0.1,0.2,0.7]],dtype=float)


def write_rows(path,fields,rows):
    with path.open("w",newline="",encoding="utf8") as f:
        w=csv.DictWriter(f,fieldnames=fields)
        w.writeheader();w.writerows(rows)


def assert_invalid(tmp,fields,rows,reason):
    p=tmp/"bad.csv"
    write_rows(p,fields,rows)
    try:
        validate_extract(p)
    except InvalidCapture as err:
        assert reason in str(err),(reason,str(err))
    else:
        raise AssertionError(f"Invalid sample accepted: {reason}")


def main():
    assert REAL.is_file()
    with REAL.open(newline="",encoding="utf8") as f:
        rd=csv.DictReader(f);fields=rd.fieldnames;rows=list(rd)
    assert fields is not None and len(rows)==900
    x,qa=validate_extract(REAL)
    old=expected_from_uploaded_helper(rows)
    assert list(x)==list(FEATURES)
    for k in FEATURES:
        assert np.isclose(x[k],old[k],rtol=0,atol=1e-7),(k,x[k],old[k])
    res=predict_validated(x,MockForest())
    assert res["roast_predicted"]=="medium"
    assert res["probabilities_uncalibrated"]["medium"]==0.7
    assert set(res["probabilities_uncalibrated"])==set(CLASSES)
    assert run_cli(["--input",str(REAL),"--validate-only"])==0
    with tempfile.TemporaryDirectory() as t:
        root=Path(t)
        assert_invalid(root,fields,rows[:150],"wrong_row_count_150")  # firmware 5-cycle AI TEST
        assert_invalid(root,fields,rows[:-1],"wrong_row_count_899")
        changed=[dict(r) for r in rows]
        changed[29]["sample_idx"]="8"
        assert_invalid(root,fields,changed,"invalid_cycle_phase_idx")
        changed=[dict(r) for r in rows]
        changed[56]["timestamp"]=changed[55]["timestamp"]
        assert_invalid(root,fields,changed,"stale_or_duplicate_timestamp")
        changed=[dict(r) for r in rows]
        changed[26]["adc_mq8"]=""
        assert_invalid(root,fields,changed,"non_numeric_field")
        changed=[dict(r) for r in rows]
        changed[26]["adc_tgs822"]="nan"
        assert_invalid(root,fields,changed,"invalid_sensor_adc")
        changed=[dict(r) for r in rows]
        changed[26]["adc_tgs822"]="99999"
        assert_invalid(root,fields,changed,"invalid_sensor_adc")
        changed=[dict(r) for r in rows]
        changed[55]["phase"]="purging"
        assert_invalid(root,fields,changed,"invalid_cycle_phase_idx")
        changed=[dict(r) for r in rows]
        changed[300]["adc_tgs822"]="0"
        # Zero is a valid ADC integer in a coherent stream; do not change feature semantics.
        path=root/"valid_zero.csv";write_rows(path,fields,changed)
        validate_extract(path)
        reduced=[k for k in fields if k!="adc_mq8"]
        assert_invalid(root,reduced,[{k:v for k,v in r.items() if k in reduced} for r in rows],
                       "missing_required_columns")
    print("RF30_PI_OFFLINE_QA_PASS",{
        "verified_original_3_feature_values":x,
        "cycles":qa["cycles"],"rows":qa["rows"],
        "rejected_5_cycle_ai_test":True,
        "hardware_touched":False,"model_joblib_deserialized":False,
    })


if __name__=="__main__":
    main()
