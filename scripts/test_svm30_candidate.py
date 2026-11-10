"""Offline SVM9 feature-extraction / model-return QA. No serial/model load."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from svm30_roast_model import FEATURE_ORDER,InvalidCapture,extract_features
from svm30_pi_return_bridge import (
    TEST_TOKEN,LIVE_GATE,MODEL_GATE,csv_to_test_stream,live_bench,
)
from rf30_pi_result_bridge import HostSession,ReturnProtocolError,wire_command

ROOT=Path(__file__).resolve().parents[1]
FILE=ROOT/"data/dataset sorting/b/kept/D-CAT_B70.csv"


def expect_exception(fun,kind,fragment):
    try:
        fun()
    except kind as err:
        assert fragment in str(err),(fragment,str(err))
    else:
        raise AssertionError("Expected rejection: "+fragment)


def run():
    result=extract_features(FILE)
    assert list(result)==list(FEATURE_ORDER)
    assert len(result)==9
    expected={
        "median_phase_response__adc_tgs822":405.5,
        "mean_phase_response__adc_tgs822":455.5666666666666,
        "response_early_late__adc_tgs822":-501.6000000000022,
        "median_phase_response__adc_tgs2602":163.0,
        "mean_phase_response__adc_tgs2602":212.2,
        "response_early_late__adc_tgs2602":-219.39999999999964,
        "median_phase_response__adc_tgs816":338.3000000000002,
        "mean_phase_response__adc_tgs816":427.6266666666668,
        "response_early_late__adc_tgs816":-478.0,
    }
    for f,expected_value in expected.items():
        assert abs(result[f]-expected_value)<1e-7,(f,result[f])
    with FILE.open(newline="",encoding="utf-8-sig") as fh:
        reader=csv.DictReader(fh)
        cols=reader.fieldnames
        rows=list(reader)
    assert len(rows)==900
    with TemporaryDirectory(prefix="svm30_test_") as tmp:
        p=Path(tmp)/"capture.csv"
        def write(data):
            with p.open("w",newline="",encoding="utf8") as file:
                writer=csv.DictWriter(file,fieldnames=cols)
                writer.writeheader();writer.writerows(data)
        write(rows[:-1])
        expect_exception(lambda:extract_features(p),InvalidCapture,"incomplete")
        write(rows[:150])
        expect_exception(lambda:extract_features(p),InvalidCapture,"incomplete")
        bad=[dict(r) for r in rows]
        bad[26]["phase"]="purging"
        write(bad)
        expect_exception(lambda:extract_features(p),InvalidCapture,"cycle_phase_index")
        bad=[dict(r) for r in rows]
        bad[26]["sample_idx"]="33"
        write(bad)
        expect_exception(lambda:extract_features(p),InvalidCapture,"cycle_phase_index")
        bad=[dict(r) for r in rows]
        bad[100]["adc_tgs822"]="nan"
        write(bad)
        expect_exception(lambda:extract_features(p),InvalidCapture,"sensor_adc_out_of_range")
        bad=[dict(r) for r in rows]
        bad[100]["timestamp"]=bad[99]["timestamp"]
        write(bad)
        expect_exception(lambda:extract_features(p),InvalidCapture,"timestamp_out_of_order")
        write(rows)
        messages=csv_to_test_stream(p)
        assert len(messages)==903
        start=json.loads(messages[0])
        assert start["mode"]=="ai_test" and "roast_level" not in start
        assert "origin_code" not in start and "sample_id" not in start
        assert start["ai_session_token"]==TEST_TOKEN
        assert json.loads(messages[-1])["samples"]==900
        obj=HostSession()
        for message in messages:
            _,status=obj.feed(message,allow_predict=False)
        assert status["status"]=="VALIDATED_ONLY_NO_MODEL_TX"
        assert obj.samples==900 and obj.complete
        assert wire_command(TEST_TOKEN,"dark")==b"#rf30:B1F503A9:dark;"
        bad=[dict(r) for r in rows]
        bad[5]["adc_tgs822"]="17200.5"
        write(bad)
        expect_exception(lambda:csv_to_test_stream(p),ReturnProtocolError,"fractional")
    # Refuse to touch Pi/MCU unless onsite, idle and double opt-in all present.
    expect_exception(lambda:live_bench(Path("/dev/ttyUSB0"),"A10KNJBL",
                     Path("untrusted.joblib"),Path("untrusted.json"),
                     serial_gate="",model_gate="",onsite=False,idle=False),
                     ReturnProtocolError,"double_approval_required")
    assert LIVE_GATE and MODEL_GATE
    print("SVM30_CANDIDATE_OFFLINE_QA_PASS",json.dumps({
        "features":9,"tested_csv_samples":900,"rejected_incomplete":True,
        "rejected_fractional_adc_wire_replay":True,
        "ai_test_ground_truth_not_injected":True,
        "usb_opened":False,"model_deserialized":False,
        "firmware_flashing":False,
    }))


if __name__=="__main__":
    run()
