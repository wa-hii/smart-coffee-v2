#!/usr/bin/env python3
"""SVM9 (30-cycle) -> ATmega -> Nextion bridge, disabled for live by default.

Reuses the approved *shape* of the RF30 wire protocol #rf30:TOKEN:roast;
this is a transport name, NOT a RandomForest requirement. Firmware
receives the same 3-class string regardless of model algorithm.

Offline testing is safe: no serial open or MCU command. Live bench requires
an explicit operator-supervised safety gate and uses exactly one response.
SVM probability=False; confidence/origin remain N/A in Nextion.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
import time

from rf30_pi_result_bridge import (
    BoundedLineFramer, BUILD_ID, HostSession, ReturnProtocolError, USB_BY_ID,
    wire_command,
)
from svm30_roast_model import ADC_COLUMNS, extract_features, predict, verify_model

LIVE_GATE="I_APPROVE_ONSITE_G2_G3_SERIAL_AND_REPLY"
MODEL_GATE="I_ACCEPT_EXPLORATORY_SVM30_BENCH_ONLY"
EXPECTED_MODEL="SVC_RBF"
TEST_TOKEN="B1F503A9"  # mock / offline only


def load_candidate(model_file:Path,metadata_file:Path):
    metadata=verify_model(model_file,metadata_file)
    import sklearn
    if sklearn.__version__!=metadata["sklearn_version"]:
        raise ReturnProtocolError("svm_model_sklearn_version_mismatch")
    import joblib
    pipeline=joblib.load(model_file)  # SHA-pinned, trusted candidate only
    def callback(csv_file:Path):
        return predict(csv_file,model_file,metadata_file,model=pipeline)
    return metadata,callback


def csv_to_test_stream(csv_file:Path,token:str=TEST_TOKEN):
    # No use of filename, roast_level, sample_id, origin or batch as predictors.
    extract_features(csv_file)
    messages=[
        {"event":"ACQ_START","mode":"ai_test","fw_build_id":BUILD_ID,
         "phase":"purging","cycle":1,"cycles_total":30,
         "purge_s":25,"collect_s":5,"ai_session_token":token}
    ]
    with csv_file.open(newline="",encoding="utf-8-sig") as fh:
        rows=list(csv.DictReader(fh))
    for r in rows:
        s={"cycle":int(r["run_id"]),"phase":r["phase"],
           "sample_idx":int(r["sample_idx"]),"timestamp":int(r["timestamp"])}
        for a in ADC_COLUMNS:
            # Real MCU ADC is integral. An offline file with interpolated
            # fractional ADC must NOT be silently truncated in a wire replay.
            v=float(r[a])
            if not v.is_integer() or not 0<=v<=32767:
                raise ReturnProtocolError("fractional_or_invalid_adc_in_replay")
            s[a]=int(v)
        messages.append(s)
    messages.extend([
        {"event":"ACQ_COMPLETE","cycles":30,"total_samples":900},
        {"event":"AI_AWAITING_RESULT","token":token,"samples":900,
         "window_ms":30000}
    ])
    return [json.dumps(v,separators=(",",":")) for v in messages]


def replay_csv(csv_file:Path,model_path:Path,metadata_path:Path, *,
               emulate_ack:bool=True):
    metadata,predictor=load_candidate(model_path,metadata_path)
    session=HostSession()
    command=None
    status=None
    for line in csv_to_test_stream(csv_file):
        got,status=session.feed(line,allow_predict=True,predictor=predictor)
        if got:
            if command is not None:
                raise ReturnProtocolError("multiple_model_results")
            command=got
    if command is None or status["status"]!="RESULT_READY_FOR_SUPERVISED_TX":
        raise ReturnProtocolError("svm_model_result_not_ready")
    if emulate_ack:
        _,ack=session.feed(json.dumps({"event":"AI_RESULT_ACK",
                   "token":TEST_TOKEN,"roast":status["roast"]}))
        if ack["status"]!="MCU_ACK_CONFIRMED":
            raise ReturnProtocolError("mock_ack_failed")
    return {
        "status":"SVM30_OFFLINE_900_SAMPLE_PREDICTION_PASS",
        "roast_predicted":status["roast"],
        "simulated_mcu_command":command.decode("ascii"),
        "mcu_ack":"SIMULATED_ONLY" if emulate_ack else "NOT_RUN",
        "model_sha256":metadata["artifact_sha256"],
        "feature_count":9,"cycles":30,"sensor_samples":900,
        "calibrated_confidence":None,"origin_predicted":None,
        "hardware_serial_opened":False,"mcu_serial_written":False,
        "nextion_physical_updated":False,"prospective_blind_test":False,
        "deployment_approved":False
    }


def live_bench(port:Path,expected_serial:str,model:Path,metadata:Path,
               *,serial_gate:str,model_gate:str,onsite:bool,idle:bool,
               max_seconds:int=1260):
    """Unsafe-by-default guarded supervised one-shot bench, NEVER autostart."""
    if (serial_gate!=LIVE_GATE or model_gate!=MODEL_GATE or
        not onsite or not idle):
        raise ReturnProtocolError("onsite_idle_sop_and_double_approval_required")
    if (not USB_BY_ID.fullmatch(str(port)) or
        expected_serial not in port.name or not port.is_symlink() or
        not port.exists() or port.resolve().name!="ttyUSB0"):
        raise ReturnProtocolError("unexpected_usb_serial_device")
    if not 920<=max_seconds<=1260:
        raise ReturnProtocolError("invalid_session_duration_limit")
    _,predictor=load_candidate(model,metadata)
    # Only after all gates and artifact verification, access the tty.
    import serial
    dev=serial.Serial(port=None,baudrate=115200,timeout=1,
                      rtscts=False,dsrdtr=False,exclusive=True)
    dev.dtr=False
    dev.rts=False
    engine=HostSession()
    sent=False
    start=time.monotonic()
    last_rx=start
    try:
        dev.port=str(port)
        dev.open()  # may reset a custom ATmega: onsite approval needed
        print("SVM30_BENCH_LISTENER_READY",flush=True)
        framing=BoundedLineFramer()
        while time.monotonic()-start<max_seconds:
            fragment=dev.read(512)
            if fragment:
                last_rx=time.monotonic()
            if engine.token is not None and time.monotonic()-last_rx>10:
                raise ReturnProtocolError("serial_stalled_mid_acquisition")
            for frame in framing.feed(fragment):
                result,state=engine.feed(frame,allow_predict=True,predictor=predictor)
                if result:
                    if sent:
                        raise ReturnProtocolError("already_sent_one_result")
                    dev.write(result)
                    dev.flush()
                    sent=True
                if state["status"]=="MCU_ACK_CONFIRMED":
                    return {"status":"MCU_ACK_CONFIRMED","roast":state["roast"],
                            "sensor_samples":900,
                            "uart_tx":sent,"lcd_visual_verified":False}
        raise ReturnProtocolError("supervised_window_timeout")
    finally:
        dev.close()


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    group=p.add_mutually_exclusive_group(required=True)
    group.add_argument("--offline-csv",type=Path)
    group.add_argument("--serial-live",type=Path)
    p.add_argument("--model",type=Path,required=True)
    p.add_argument("--metadata",type=Path,required=True)
    p.add_argument("--expected-ftdi-serial",default="")
    p.add_argument("--ack-serial",default="")
    p.add_argument("--ack-model",default="")
    p.add_argument("--onsite-operator",action="store_true")
    p.add_argument("--device-idle",action="store_true")
    args=p.parse_args(argv)
    if args.offline_csv:
        out=replay_csv(args.offline_csv,args.model,args.metadata)
    else:
        out=live_bench(args.serial_live,args.expected_ftdi_serial,
                       args.model,args.metadata,serial_gate=args.ack_serial,
                       model_gate=args.ack_model,onsite=args.onsite_operator,
                       idle=args.device_idle)
    print(json.dumps(out,ensure_ascii=False))
    return 0


if __name__=="__main__":
    sys.exit(main())
