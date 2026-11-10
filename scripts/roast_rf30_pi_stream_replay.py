#!/usr/bin/env python3
"""OFFLINE replay of ATmega legacy NDJSON through the RF 30-cycle Pi pipeline.

Feed a pre-recorded firmware JSON-lines log (NOT a live serial port).
Requires one complete 30-cycle session. Reconstructs canonical MQ3 CSV
in an ephemeral temporary directory; ignores all operator ground-truth
labels so they cannot affect inference. Never writes MCU/Nextion.

Firmware today sends 30 cycles only for labeled_data (Take Data);
AI_TEST is FIVE cycles and MUST NOT use this RF 30-cycle model unchanged.
"""
from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory

from roast_rf30_pi_inference import ADC_COLUMNS, predict_capture

FIELDS=("timestamp","run_id","phase","sample_idx",*ADC_COLUMNS)


class StreamError(ValueError):
    pass


def collect_firmware_ndjson(log_path:Path)->list[dict]:
    """Fail closed on missing start/complete, count, phase or invalid bytes."""
    active=False
    complete=False
    events=0
    rows=[]
    last_ts=-1
    with log_path.open("r",encoding="utf8") as fh:
        for line in fh:
            if not line.strip():
                continue
            if len(line.encode("utf8"))>4096:
                raise StreamError("oversized_serial_frame")
            try:
                frame=json.loads(line)
            except ValueError as e:
                raise StreamError("malformed_serial_json") from e
            if not isinstance(frame,dict):
                raise StreamError("invalid_serial_object")
            ev=frame.get("event")
            if ev=="ACQ_START":
                if active or complete or rows:
                    raise StreamError("duplicate_or_interrupted_session")
                if (frame.get("mode") not in ("labeled_data","ai_test") or
                    frame.get("cycles_total")!=30 or
                    frame.get("purge_s")!=25 or frame.get("collect_s")!=5):
                    raise StreamError("start_contract_not_30_cycles")
                active=True
                events+=1
                continue
            if not active:
                # Standalone device boot/status is harmless; no inference.
                if ev in ("FW_HELLO",None) and not complete:
                    continue
                if complete:
                    # Other later status logs do not re-open the session.
                    continue
                continue
            if ev=="ACQ_STOP" or ev=="ACQ_TIMING_FAULT":
                raise StreamError("acquisition_aborted")
            if ev=="ACQ_COMPLETE":
                if frame.get("cycles")!=30 or frame.get("total_samples")!=900 or len(rows)!=900:
                    raise StreamError("incomplete_or_wrong_complete_count")
                active=False
                complete=True
                events+=1
                continue
            if ev is not None:
                # PHASE_CHANGE etc are supplemental; sample order validated below.
                continue
            if "phase" not in frame or "sample_idx" not in frame:
                # An arbitrary JSON status frame is not a sample.
                continue
            if len(rows)>=900:
                raise StreamError("too_many_samples")
            idx=len(rows)
            exp_run=idx//30+1
            exp_phase="purging" if idx%30<25 else "collecting"
            exp_idx=idx%30+1 if idx%30<25 else idx%30-24
            if (frame.get("cycle")!=exp_run or frame.get("phase")!=exp_phase or
                frame.get("sample_idx")!=exp_idx):
                raise StreamError("out_of_order_sensor_index_or_phase")
            if not set(ADC_COLUMNS).issubset(frame):
                raise StreamError("missing_adc_column")
            try:
                now=int(frame["timestamp"])
            except (KeyError,ValueError,TypeError) as e:
                raise StreamError("invalid_sensor_timestamp") from e
            if now<=last_ts:
                raise StreamError("stale_sensor_timestamp")
            last_ts=now
            # Critical: never copy sample_id, roast_level, origin into predictors.
            rows.append({"timestamp":now,"run_id":exp_run,"phase":exp_phase,
                         "sample_idx":exp_idx,
                         **{name:frame[name] for name in ADC_COLUMNS}})
    if active or not complete or events!=2 or len(rows)!=900:
        raise StreamError("session_not_complete")
    return rows


def replay(log_path:Path,model_path:Path|None=None,metadata_path:Path|None=None,
           validate_only:bool=True,model=None)->dict:
    rows=collect_firmware_ndjson(log_path)
    with TemporaryDirectory(prefix="roast_rf30_pi_replay_") as temp:
        f=Path(temp)/"validated_from_firmware_stream.csv"
        with f.open("w",newline="",encoding="utf8") as handle:
            wr=csv.DictWriter(handle,fieldnames=FIELDS)
            wr.writeheader();wr.writerows(rows)
        result=predict_capture(f,model_path,metadata_path,
                               validate_only=validate_only,model=model)
    result["input"]["recording"]=log_path.name
    result["source"]="firmware_ndjson_host_replay"
    result["raw_saved_to_training"]=False
    result["pi_to_mcu_transmitted"]=False
    result["nextion_updated"]=False
    return result


def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-ndjson",required=True,type=Path)
    p.add_argument("--validate-only",action="store_true")
    p.add_argument("--model",type=Path)
    p.add_argument("--metadata",type=Path)
    args=p.parse_args(argv)
    if not args.validate_only and (not args.model or not args.metadata):
        p.error("Model prediction requires --model and --metadata or --validate-only")
    try:
        result=replay(args.input_ndjson,model_path=args.model,
                      metadata_path=args.metadata,validate_only=args.validate_only)
    except (ValueError,OSError) as e:
        result={"status":"REJECTED","reason":str(e),
                "pi_to_mcu_transmitted":False,"nextion_updated":False}
    print(json.dumps(result,ensure_ascii=False))
    return 0 if result["status"]!="REJECTED" else 2


if __name__=="__main__":
    sys.exit(main())
