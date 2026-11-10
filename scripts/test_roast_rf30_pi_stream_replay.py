"""Offline firmware-shaped stream replay; never touches real serial hardware."""
from __future__ import annotations

import csv
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import numpy as np

from roast_rf30_pi_inference import ADC_COLUMNS,validate_extract
from roast_rf30_pi_stream_replay import replay,StreamError

ROOT=Path(__file__).resolve().parents[1]
INPUT=ROOT/"data/dataset sorting/b/kept/D-CAT_B70.csv"


def emit(path,rows,*,cycles=30,mode="labeled_data",
         leak_label=False,remove_index=None,wrong_phase_at=None):
    start={"event":"ACQ_START","mode":mode,"cycle":1,
           "phase":"purging","cycles_total":cycles,"purge_s":25,"collect_s":5}
    if mode=="labeled_data" or leak_label:
        start.update(roast_level="light",origin_code="FAKE")
    with path.open("w",encoding="utf8") as f:
        f.write(json.dumps(start)+"\n")
        for idx,row in enumerate(rows):
            if idx==remove_index:
                continue
            frame={"timestamp":int(row["timestamp"]),"cycle":int(row["run_id"]),
                   "phase":"collecting" if idx==wrong_phase_at else row["phase"],
                   "sample_idx":int(row["sample_idx"])}
            frame.update({s:int(row[s]) for s in ADC_COLUMNS})
            f.write(json.dumps(frame)+"\n")
        f.write(json.dumps({"event":"ACQ_COMPLETE","cycles":cycles,
                            "total_samples":900 if cycles==30 else 150})+"\n")


def must_fail(path,reason):
    try:
        replay(path,validate_only=True)
    except StreamError as e:
        assert reason in str(e),(reason,str(e))
    else:
        raise AssertionError("Bad stream accepted: "+reason)


def main():
    with INPUT.open(newline="",encoding="utf8") as f:
        rows=list(csv.DictReader(f))
    expected,_=validate_extract(INPUT)
    with TemporaryDirectory(prefix="rf30_streamqa_") as t:
        p=Path(t)/"frames.ndjson"
        emit(p,rows)
        result=replay(p,validate_only=True)
        assert result["status"]=="VALID_CAPTURE"
        assert result["raw_saved_to_training"] is False
        assert result["nextion_updated"] is False
        for name,value in expected.items():
            assert np.isclose(result["features"][name],value,atol=1e-7),name
        # Active AI_TEST now also sends 30 cycles, but NO operator label.
        emit(p,rows,mode="ai_test")
        ai=replay(p,validate_only=True)
        assert ai["status"]=="VALID_CAPTURE" and ai["input"]["cycles"]==30
        for name,value in expected.items():
            assert np.isclose(ai["features"][name],value,atol=1e-7),name
        emit(p,rows,mode="ai_test",leak_label=True)
        must_fail(p,"ai_test_label_leakage")
        emit(p,rows[:150],cycles=5)
        must_fail(p,"start_contract_not_30_cycles")
        emit(p,rows,remove_index=35)
        must_fail(p,"out_of_order_sensor_index_or_phase")
        emit(p,rows,wrong_phase_at=52)
        must_fail(p,"out_of_order_sensor_index_or_phase")
    print("RF30_STREAM_REPLAY_QA_PASS",{
        "complete_30_cycle_replay":True,"ai_test_30_cycles_supported":True,
        "five_cycle_ai_mode_rejected":True,"ai_label_leak_rejected":True,
        "missing_sample_rejected":True,"wrong_phase_rejected":True,
        "labels_not_used":True,"serial_ports_opened":0,
        "nextion_updates":0
    })


if __name__=="__main__":
    main()
